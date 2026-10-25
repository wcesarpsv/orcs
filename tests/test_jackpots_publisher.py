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
def html(maximum=25, gold=28, count=0, date='2026-10-27'):
    def when(d):
        parts=d.split('-')
        return f'<span class="title">下期头奖将于<time datetime="{d}">{int(parts[0])}年{int(parts[1])}月{int(parts[2])}日</time></span>'
    return f'''<div class="block"><img src="images/max-logo.png"><div class="text">
    {when(date)}<strong class="price">${maximum},000,000<span>估计彩金</span></strong>
    <span>另加25项10万元的奖金</span></div></div>
    <div class="slide banner649"><div class="text">{when('2026-10-24')}
    <div><img class="classic"><h2>$5,000,000</h2></div>
    <div><img class="goldBall" src="images/goldball-sc.png"><h2>${gold},000,000</h2></div>
    </div></div>'''

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
        self.assertFalse(make_snapshot(html(date='2026-10-20'),NOW)['transmit_allowed'])
    def test_impossible_date(self):
        self.assertFalse(make_snapshot(html(date='2026-02-31'),NOW)['transmit_allowed'])
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
    def test_missing_amount_is_not_zero(self):
        self.assertEqual(make_snapshot(html(), NOW)['values']['lotto_max'], 25)
        self.assertFalse(make_snapshot(html().replace('$25,000,000', 'Calculating'), NOW)['transmit_allowed'])
    def test_missing_game_never_defaults_jackpots(self):
        self.assertFalse(make_snapshot(html().replace('max-logo.png', 'other.png'), NOW)['transmit_allowed'])
    def test_fractional_amount_is_not_truncated(self):
        self.assertFalse(make_snapshot(html().replace('$25,000,000', '2.55千万元'), NOW)['transmit_allowed'])
    def test_future_date_outside_window(self):
        self.assertFalse(make_snapshot(html(date='2026-11-10'), NOW)['transmit_allowed'])

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
            self.assertEqual(result['errors'], ['OLG fetch failed: HTTP 403'])
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

    def test_chinese_units_and_spaces(self):
        for amount in ('2.5千万元', '2.5 千万元', '$ 25,000,000', '25百万元'):
            with self.subTest(amount=amount):
                self.assertEqual(make_snapshot(html().replace('$25,000,000', amount), NOW)['values']['lotto_max'],25)
    def test_other_game_cannot_supply_max(self):
        wrong=html().replace('max-logo.png','lightning.png')
        self.assertFalse(make_snapshot(wrong, NOW)['transmit_allowed'])
    def test_zero_main_jackpot_is_blocked(self):
        self.assertFalse(make_snapshot(html(maximum=0), NOW)['transmit_allowed'])
    def test_visible_date_disagrees(self):
        self.assertFalse(make_snapshot(html().replace('2026年10月27日','2026年10月28日'), NOW)['transmit_allowed'])

if __name__=='__main__': unittest.main()
