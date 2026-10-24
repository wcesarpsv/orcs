import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jackpots_publisher import make_snapshot, failure_snapshot, atomic_publish

NOW = datetime(2026,10,24,16,0,tzinfo=timezone.utc)
def html(maximum=25, gold=28, count=20, date='2026年10月27日'):
    return f'''<html><script>fake $99999999</script><div>下期头奖将于2026年10月24日
    <h2>$5,000,000</h2><h2>${gold},000,000</h2>或1百万元大奖</div>
    <div>下期头奖将于{date}<h2>${maximum},000,000 估计彩金</h2>
    另加{count}项1百万元的MAXMILLIONS</div></html>'''

class PublisherTests(unittest.TestCase):
    def test_valid_snapshot_and_lifetime(self):
        d=make_snapshot(html(),NOW)
        self.assertTrue(d['transmit_allowed'])
        self.assertEqual(d['values'],dict(lotto_max=25,gold_ball=28,maxmillions=20))
        self.assertEqual(d['expires_at_unix']-d['generated_at_unix'],300)
        self.assertEqual(d['schema_version'],1)
    def test_conflicting_same_draw_blocks_invalid(self):
        d=make_snapshot(html()+html(maximum=30),NOW)
        self.assertFalse(d['transmit_allowed'])
        self.assertTrue(all(v is None for v in d['values'].values()))
    def test_stale_date(self):
        self.assertFalse(make_snapshot(html(date='2026年10月20日'),NOW)['transmit_allowed'])
    def test_impossible_date(self):
        self.assertFalse(make_snapshot(html(date='2026年02月31日'),NOW)['transmit_allowed'])
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

if __name__=='__main__': unittest.main()
