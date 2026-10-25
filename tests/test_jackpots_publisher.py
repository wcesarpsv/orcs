import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, Mock
import threading
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jackpots_publisher import make_snapshot, failure_snapshot, atomic_publish, Publisher

NOW = datetime(2026,10,24,16,0,tzinfo=timezone.utc)
def html(maximum=25, gold=28, count=0, date='Tue, Oct 27, 2026, 10:30 pm'):
    def panel(name, value, draw, label):
        return f'''<div class="resultsdrawing"><section><h2>{name}</h2>
        <time>Historical draw</time><a>20 MaxMillions/MaxPlus Draws</a></section>
        <section><div class="resultsNextDrawInfo"><strong>Next Drawing:</strong>
        <span class="resultsnextdate">{draw}</span></div>
        <div class="resultsJackpotAmount"><strong>{label}</strong>
        <span>CA${value} Million<br><span>US$999 Million</span></span></div>
        <div class="resultsJackpotChange">CA$100 Million</div></section></div>'''
    return (panel('Canada Lotto 6/49', gold, 'Sat, Oct 24, 2026, 10:30 pm', 'Next Gold Ball Jackpot:')
            + panel('Lotto Max', maximum, date, 'Next Jackpot:'))

class PublisherTests(unittest.TestCase):
    def test_valid_snapshot_and_lifetime(self):
        d=make_snapshot(html(),NOW)
        self.assertTrue(d['transmit_allowed'])
        self.assertEqual(d['values'],dict(lotto_max=25,gold_ball=28,maxmillions=0))
        self.assertEqual(d['expires_at_unix']-d['generated_at_unix'],300)
        self.assertEqual(d['schema_version'],1)
    def test_conflicting_same_draw_blocks_invalid(self):
        d=make_snapshot(html()+html(maximum=30),NOW)
        self.assertFalse(d['transmit_allowed'])
        self.assertTrue(all(v is None for v in d['values'].values()))
    def test_stale_date(self):
        self.assertFalse(make_snapshot(html(date='Tue, Oct 20, 2026, 10:30 pm'),NOW)['transmit_allowed'])
    def test_impossible_date(self):
        self.assertFalse(make_snapshot(html(date='Tue, Feb 31, 2026, 10:30 pm'),NOW)['transmit_allowed'])
    def test_missing_or_changed_page(self):
        self.assertFalse(make_snapshot('<html>New layout</html>',NOW)['transmit_allowed'])
    def test_out_of_range(self):
        self.assertFalse(make_snapshot(html(maximum=999),NOW)['transmit_allowed'])
    def test_duplicates_are_not_conflicts(self):
        self.assertTrue(make_snapshot(html()+html(),NOW)['transmit_allowed'])
    def test_failure_never_reuses_numbers(self):
        d=failure_snapshot('timeout',NOW)
        self.assertFalse(d['transmit_allowed']); self.assertEqual(d['expires_at_unix'],d['generated_at_unix'])
        self.assertTrue(all(x is None for x in d['values'].values()))
    def test_atomic_publish_and_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'static'/'jackpots_current.json'
            atomic_publish(p,make_snapshot(html(),NOW))
            self.assertEqual(json.loads(p.read_text())['status'],'ok')
            atomic_publish(p,failure_snapshot('failed',NOW))
            self.assertEqual(json.loads(p.read_text())['status'],'unavailable')
            self.assertFalse(p.with_suffix('.tmp').exists())
    def test_toronto_date_near_utc_midnight(self):
        now=datetime(2026,10,25,0,30,tzinfo=timezone.utc)
        self.assertTrue(make_snapshot(html(),now)['transmit_allowed'])

    def test_missing_maxmillions_is_explicit_zero(self):
        d=make_snapshot(html(), NOW)
        self.assertEqual(d['values']['maxmillions'], 0)
        self.assertEqual(d['maxmillions_mode'], 'fixed_zero')
    def test_us_currency_is_not_used(self):
        self.assertEqual(make_snapshot(html(), NOW)['values']['lotto_max'], 25)
        self.assertFalse(make_snapshot(html().replace('CA$', 'US$'), NOW)['transmit_allowed'])
    def test_missing_game_never_defaults_jackpots(self):
        self.assertFalse(make_snapshot(html().replace('Lotto Max', 'Other Game'), NOW)['transmit_allowed'])
    def test_fractional_amount_is_not_truncated(self):
        self.assertFalse(make_snapshot(html(maximum='25.5'), NOW)['transmit_allowed'])
    def test_future_date_outside_window(self):
        self.assertFalse(make_snapshot(html(date='Tue, Nov 10, 2026, 10:30 pm'), NOW)['transmit_allowed'])

    def test_http_error_code_survives_snapshot_read(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = Publisher.__new__(Publisher)
            worker.path = Path(directory) / 'jackpots_current.json'
            worker.lock = threading.Lock()
            response = Mock(status_code=403)
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
            with patch('jackpots_publisher.requests.get', return_value=response):
                worker.refresh()
            result = worker.snapshot()
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['errors'], ['Lottery Post fetch failed: HTTP 403'])
            self.assertFalse(result['transmit_allowed'])
    def test_valid_expired_snapshot_is_still_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = Publisher.__new__(Publisher)
            worker.path = Path(directory) / 'jackpots_current.json'
            worker.lock = threading.Lock()
            atomic_publish(worker.path, make_snapshot(html(), NOW))
            with patch('jackpots_publisher.time.time', return_value=NOW.timestamp()+301):
                result = worker.snapshot()
            self.assertEqual(result['status'], 'expired')
            self.assertFalse(result['transmit_allowed'])

if __name__=='__main__': unittest.main()
