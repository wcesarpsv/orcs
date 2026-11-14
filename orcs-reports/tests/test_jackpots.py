import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from app import app
from jackpots import make_snapshot, failure_snapshot, current_snapshot
from jackpot_parser import parse_jackpots
NOW=datetime(2026,11,14,15,0,tzinfo=timezone.utc)
def fixture(maximum=20,gold=10,count=0,date='November 17, 2026'):
    return f'<nav>Lotto Max Lotto 6/49</nav><section><img alt="Lotto Max"><p>This Tuesday, {date}</p><p>${maximum} million</p><p>{str(count)+" Maxmillions" if count else "20 x $100,000"}</p></section><section><img alt="Lotto 6/49"><p>Tonight, November 14, 2026</p><p>The Gold Ball ${gold} million</p><p>The Classic $5 million</p></section>'
class JackpotTests(unittest.TestCase):
    def test_snapshot_and_feed_contract(self):
        s=make_snapshot(fixture(),NOW)
        self.assertTrue(s['transmit_allowed']);self.assertEqual(s['values'],dict(lotto_max=20,gold_ball=10,maxmillions=0));self.assertEqual(s['expires_at_unix']-s['generated_at_unix'],300)
        self.assertEqual(s['served_by'],'orcs-reports.vercel.app')
    def test_count(self):self.assertEqual(make_snapshot(fixture(count=15),NOW)['values']['maxmillions'],15)
    def test_fail_closed(self):
        for html in [fixture(maximum=0),fixture(maximum=201),fixture(maximum='20.5'),fixture(date='November 1, 2026'),fixture(date='December 1, 2026'),fixture(date='February 31, 2026'),fixture().replace('alt="Lotto Max"','alt="Other game"'),fixture().replace('The Gold Ball $10 million','The Gold Ball unreadable'),fixture()+fixture(maximum=30),'<p>New layout</p>']:
            with self.subTest(html=html):
                s=make_snapshot(html,NOW);self.assertFalse(s['transmit_allowed']);self.assertTrue(all(x is None for x in s['values'].values()))
    def test_identical_duplicates(self):self.assertTrue(make_snapshot(fixture()+fixture(),NOW)['transmit_allowed'])
    def test_gold_ball_never_classic(self):self.assertEqual(make_snapshot(fixture(gold=15),NOW)['values']['gold_ball'],15)
    def test_foreign_game_cannot_replace_missing_max(self):
        raw=fixture().replace('alt="Lotto Max"','alt="Other"')+'<section><p>This Tuesday, November 17, 2026</p><p>$50 million</p></section>'
        self.assertIsNone(parse_jackpots(raw)['values']['lotto_max'])
    def test_toronto_midnight(self):
        now=datetime(2026,11,15,0,30,tzinfo=timezone.utc)
        self.assertTrue(make_snapshot(fixture(),now)['transmit_allowed'])
    def test_failure_does_not_reuse_values(self):
        with patch('jackpots.fetch_html',side_effect=TimeoutError()):s=current_snapshot()
        self.assertFalse(s['transmit_allowed']);self.assertEqual(s['expires_at_unix'],s['generated_at_unix']);self.assertTrue(all(v is None for v in s['values'].values()))
    def test_routes_request_driven(self):
        client=app.test_client()
        with patch('jackpots.current_snapshot',return_value=make_snapshot(fixture(),NOW)) as fetch:
            for path in ['/api/jackpots','/api/jackpots/current.json','/static/jackpots_current.json']:
                r=client.get(path);self.assertEqual(r.status_code,200);self.assertEqual(r.json['schema_version'],1);self.assertIn('no-store',r.headers['Cache-Control'])
            self.assertEqual(fetch.call_count,3)
        for path in ['/','/jackpots','/JackpotsOLG']:
            r=client.get(path);self.assertEqual(r.status_code,200);self.assertIn(b'Jackpots OLG',r.data);self.assertIn(b'Expense Report</option>',r.data)
        self.assertIn(b'data-initial-tab="jackpots"',client.get('/jackpots').data)
    def test_diagnostics_does_not_publish(self):
        with patch('jackpots.fetch_html',return_value=fixture()),patch('jackpots.current_snapshot') as fetch:
            r=app.test_client().get('/api/jackpots/diagnostics');self.assertEqual(r.status_code,200);self.assertIn('visible_text',r.json);fetch.assert_not_called()
if __name__=='__main__':unittest.main()
