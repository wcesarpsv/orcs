"""Publish OLG snapshots from this Streamlit process on the same host.

No Streamlit APIs are called by the worker. The main app must call start_publisher
on startup/rerun; the worker then refreshes while the process is alive.
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from lotoquebec_parser import parse_jackpots, SOURCE

REFRESH_SECONDS = 120
VALID_SECONDS = 300
_workers = {}
_workers_lock = threading.Lock()


def make_snapshot(html, now=None):
    now = now or datetime.now(timezone.utc)
    parsed = parse_jackpots(html)
    values = parsed['values']
    draw_dates = parsed['draw_dates']
    today = now.astimezone(ZoneInfo('America/Toronto')).date()
    errors = []
    for key in ('lotto_max', 'gold_ball', 'maxmillions'):
        v = values.get(key)
        if type(v) is not int or not (0 if key == 'maxmillions' else 1) <= v <= 200:
            errors.append(f'{key}: missing/conflicting/out of range')
    for key in ('lotto_max', 'gold_ball'):
        try:
            draw = date.fromisoformat(draw_dates.get(key) or '')
            if not today <= draw <= today + timedelta(days=8):
                errors.append(f'{key}: stale/unexpected draw date')
        except ValueError:
            errors.append(f'{key}: invalid draw date')
    allowed = not errors
    return {
        'schema_version': 1,
        'status': 'ok' if allowed else 'unverified',
        'transmit_allowed': allowed,
        'values': values if allowed else dict.fromkeys(('lotto_max', 'gold_ball', 'maxmillions')),
        'draw_dates': draw_dates,
        'checked_at': now.isoformat(timespec='seconds'),
        'generated_at_unix': int(now.timestamp()),
        'expires_at_unix': int(now.timestamp()) + VALID_SECONDS,
        'maxmillions_mode': 'extracted',
        'source': SOURCE,
        'served_by': 'orcomputer.streamlit.app',
        'errors': errors,
    }


def failure_snapshot(message, now=None):
    now = now or datetime.now(timezone.utc)
    return {
        'schema_version': 1, 'status': 'unavailable', 'transmit_allowed': False,
        'values': dict.fromkeys(('lotto_max', 'gold_ball', 'maxmillions')),
        'draw_dates': {}, 'checked_at': now.isoformat(timespec='seconds'),
        'generated_at_unix': int(now.timestamp()), 'expires_at_unix': int(now.timestamp()),
        'maxmillions_mode': 'extracted',
        'source': SOURCE, 'served_by': 'orcomputer.streamlit.app',
        'errors': [message],
    }


def atomic_publish(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Publisher:
    def __init__(self, static_dir):
        self.path = Path(static_dir) / 'jackpots_current.json'
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.last_success_at = None
        self.last_success_method = None
        self.thread = threading.Thread(target=self.run, name='olg-jackpots-publisher', daemon=True)
        # Every process start invalidates a leftover snapshot before fetching.
        atomic_publish(self.path, failure_snapshot('Starting publisher'))
        self.thread.start()

    def refresh(self):
        try:
            r = requests.get(SOURCE, headers={
                'User-Agent': 'Mozilla/5.0 (ORComputer Jackpot Publisher/7.0)',
                'Accept-Language': 'en-CA,en;q=0.9',
            }, timeout=(8, 20))
            r.raise_for_status()
            if len(r.content) > 2_000_000:
                raise ValueError('Loto-Québec response too large')
            r.encoding = 'utf-8'
            result = make_snapshot(r.text)
            result['fetch_method'] = 'requests'
            if not result['transmit_allowed']:
                from bs4 import BeautifulSoup
                import re
                soup = BeautifulSoup(r.text, 'html.parser')
                body = soup.get_text(' ', strip=True)
                scripts = soup.find_all('script')
                # Check whether the values are embedded in HTML/JSON before
                # starting a resource-intensive headless browser.
                result['errors'].append(
                    f'HTML diagnostic: HTTP {r.status_code}, {len(r.content)} bytes, '
                    f'visible_text={len(body)}, scripts={len(scripts)}, '
                    f'gold_ball_in_html={bool(re.search("gold.ball", r.text, re.I))}, '
                    f'maxmillions_in_html={"maxmillions" in r.text.lower()}'
                )
                # A Chromium fallback is optional: Streamlit Cloud may not
                # have the browser binary installed even with playwright pip.
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
                        try:
                            page = browser.new_page(locale='en-CA', viewport={'width': 1280, 'height': 900})
                            page.goto(SOURCE, wait_until='domcontentloaded', timeout=25000)
                            page.wait_for_timeout(5000)
                            rendered = page.content()
                            browser_result = make_snapshot(rendered)
                            browser_result['fetch_method'] = 'chromium'
                            if browser_result['transmit_allowed']:
                                result = browser_result
                            else:
                                result['errors'].append(
                                    f'Chromium diagnostic: HTML {len(rendered)} bytes, '
                                    f'visible_text={len(page.locator("body").inner_text())} chars, '
                                    f'lotto_max={"Lotto Max" in rendered}, '
                                    f'gold_ball={bool(re.search("gold.ball", rendered, re.I))}'
                                )
                        finally:
                            browser.close()
                except Exception as exc:
                    result['errors'].append(f'Chromium unavailable: {type(exc).__name__}: {str(exc)[:180]}')
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else 'unknown'
            result = failure_snapshot(f'Loto-Québec fetch failed: HTTP {code}')
        except Exception as exc:
            result = failure_snapshot(f'Loto-Québec fetch failed: {type(exc).__name__}')
        with self.lock:
            if result.get('transmit_allowed'):
                self.last_success_at = result['checked_at']
                self.last_success_method = result.get('fetch_method', 'unknown')
            result['last_success_at'] = self.last_success_at
            result['last_success_method'] = self.last_success_method
            atomic_publish(self.path, result)

    def run(self):
        while not self.stop_event.is_set():
            self.wake.clear()
            self.refresh()
            self.wake.wait(REFRESH_SECONDS)

    def request_refresh(self):
        self.wake.set()

    def snapshot(self):
        with self.lock:
            try:
                result = json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                return failure_snapshot('Snapshot not available')
        if result.get('status') == 'ok' and time.time() >= result.get('expires_at_unix', 0):
            result['status'] = 'expired'
            result['transmit_allowed'] = False
            result['values'] = dict.fromkeys(('lotto_max', 'gold_ball', 'maxmillions'))
        return result


def start_publisher(static_dir=None):
    # In Community Cloud the working directory is normally the repository root.
    # For an entry script in a subfolder, pass its parent / 'static' explicitly.
    directory = Path(static_dir or os.getenv('JACKPOTS_STATIC_DIR', 'static')).resolve()
    with _workers_lock:
        worker = _workers.get(str(directory))
        if worker is None or not worker.thread.is_alive():
            worker = Publisher(directory)
            _workers[str(directory)] = worker
        return worker

