"""Request-driven feed for Vercel. No worker threads or filesystem snapshots."""
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import requests
from jackpot_parser import SOURCE, parse_jackpots
VALID_SECONDS=300
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
        'served_by': 'orcs-reports.vercel.app',
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
        'source': SOURCE, 'served_by': 'orcs-reports.vercel.app',
        'errors': [message],
    }

def fetch_html():
    with requests.get(SOURCE,headers={'User-Agent':'Mozilla/5.0 (ORCS Jackpot Monitor)','Accept-Language':'en-CA,en;q=0.9','Cache-Control':'no-cache'},timeout=(8,20),stream=True) as response:
        response.raise_for_status()
        chunks=[];size=0
        for chunk in response.iter_content(65536):
            size+=len(chunk)
            if size>2_000_000:raise ValueError('Source response too large')
            chunks.append(chunk)
        return b''.join(chunks).decode('utf-8')


def current_snapshot():
    try:
        snapshot=make_snapshot(fetch_html())
        snapshot['fetch_method']='requests'
        return snapshot
    except requests.HTTPError as exc:
        code=exc.response.status_code if exc.response is not None else 'unknown'
        return failure_snapshot(f'Loto-Quebec fetch failed: HTTP {code}')
    except Exception as exc:
        return failure_snapshot(f'Loto-Quebec fetch failed: {type(exc).__name__}')


def diagnostics():
    import re
    from bs4 import BeautifulSoup
    raw=fetch_html();parsed=parse_jackpots(raw);soup=BeautifulSoup(raw,'html.parser')
    for n in soup(['script','style','nav','footer','header']):n.decompose()
    visible=' '.join(soup.stripped_strings)
    snippets={}
    for term in ('Lotto Max','Maxmillions','The Gold Ball','Lotto 6/49'):
        hits=list(re.finditer(re.escape(term),visible,re.I))
        snippets[term]={'count':len(hits),'snippets':[visible[max(0,m.start()-120):m.end()+260] for m in hits[:4]]}
    return {'source':SOURCE,'bytes':len(raw.encode('utf-8')),'visible_characters':len(visible),'parsed':parsed,'visible_text':visible[:6000],'matches':snippets,'note':'Read-only inspection; does not publish or change device values.'}
