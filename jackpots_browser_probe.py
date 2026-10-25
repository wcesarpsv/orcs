"""One-shot Chromium diagnostic. Never publishes or authorizes C6 values."""
import json
import os
import importlib.util
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
URL = 'https://www.lotterypost.com/results/zz'


def probe():
    if not _LOCK.acquire(blocking=False):
        return {'ok': False, 'error': 'Um teste já está em andamento.'}
    try:
        if importlib.util.find_spec('playwright') is None:
            return {'ok': False, 'stage': 'streamlit_dependencies',
                    'error': 'Playwright não está instalado no ambiente do próprio Streamlit.',
                    'probe_version': 2}
        # Cloud launchers may add their managed environment to sys.path without
        # changing sys.executable. Carry these paths into the isolated process.
        environment = os.environ.copy()
        environment['PYTHONPATH'] = os.pathsep.join(
            str(Path(p or os.getcwd()).resolve()) for p in sys.path)
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--child'],
            capture_output=True, text=True, timeout=70, check=False,
            env=environment)
        if completed.returncode:
            return {'ok': False, 'error': 'Falha ao executar o teste do navegador.'}
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'O teste excedeu 70 segundos.'}
    except (OSError, ValueError) as exc:
        return {'ok': False, 'error': f'Falha no teste: {type(exc).__name__}'}
    finally:
        _LOCK.release()


def child_probe():
    result = {'ok': False, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'source': URL, 'publishes_to_c6': False, 'probe_version': 2}
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
        from jackpots_publisher import make_snapshot
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable:
            raise RuntimeError('Chromium não instalado. Aguarde a reconstrução do app ou faça Reboot app.')
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable, headless=True,
                args=['--disable-dev-shm-usage'], timeout=15000)
            try:
                page = browser.new_page(locale='en-CA')
                response = page.goto(URL, wait_until='domcontentloaded', timeout=30000)
                result['http_status'] = response.status if response else None
                result['final_url'] = page.url
                result['title'] = page.title()
                if response and response.ok:
                    try:
                        page.locator('.resultsdrawing .resultsJackpotAmount').first.wait_for(timeout=10000)
                    except BrowserTimeout:
                        pass
                    snapshot = make_snapshot(page.content())
                    result['ok'] = snapshot['transmit_allowed']
                    result['values'] = snapshot['values']
                    result['draw_dates'] = snapshot['draw_dates']
                    result['errors'] = snapshot['errors']
                    if not result['ok']:
                        result['error'] = 'Página abriu, mas os jackpots não passaram na validação.'
                else:
                    result['error'] = f'Lottery Post recusou o navegador: HTTP {result["http_status"]}'
            finally:
                browser.close()
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {str(exc)[:1200]}'
    return result


if __name__ == '__main__' and sys.argv[1:] == ['--child']:
    print(json.dumps(child_probe(), ensure_ascii=False))
