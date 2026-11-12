"""Tests for india_vmm/safety.py. Run: python -m unittest discover -s india_vmm/tests"""
import datetime as dt
import os
import sys
import unittest

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rules  # noqa: E402
import safety  # noqa: E402
from test_rules import make_panel  # noqa: E402


class TestCleanPanel(unittest.TestCase):
    def test_thin_extra_row_no_longer_breaks_200d(self):
        """10 Nov 2026 bug: one extra session row (e.g. a special session a few stocks traded)
        put a NaN inside every 200-day window -> all 200d lines NaN, market filter OFF."""
        closes, volumes = make_panel()
        extra = pd.Timestamp("2026-10-25")  # a Sunday, only one stock has a price
        closes.loc[extra] = np.nan
        closes.loc[extra, "UP0.NS"] = closes["UP0.NS"].iloc[-1]
        volumes.loc[extra] = np.nan
        closes, volumes = closes.sort_index(), volumes.sort_index()
        broken = rules.signals(closes, volumes)
        self.assertFalse(np.isfinite(broken["sma200"]["UP5.NS"]))  # the bug reproduced
        c2, v2 = safety.clean_panel(closes, volumes)
        fixed = rules.signals(c2, v2)
        self.assertTrue(np.isfinite(fixed["sma200"]["UP5.NS"]))
        self.assertTrue(fixed["market_ok"])

    def test_duplicate_dates_from_mixed_time_zones_merge(self):
        closes, volumes = make_panel(n=260)
        a = closes.iloc[:, :5].copy()
        b = closes.iloc[:, 5:].copy()
        b.index = b.index + pd.Timedelta(hours=9, minutes=15)  # same sessions, different timestamp
        mixed = pd.concat([a, b], axis=1)
        vmix = pd.concat([volumes.iloc[:, :5], volumes.iloc[:, 5:].set_axis(b.index)], axis=1)
        c2, _ = safety.clean_panel(mixed, vmix)
        self.assertEqual(len(c2), 260)
        self.assertEqual(int(c2.isna().sum().sum()), int(closes.isna().sum().sum()))


class TestHealthAndStale(unittest.TestCase):
    def test_health_flags_missing_market_and_holdings(self):
        closes, volumes = make_panel()
        sig = rules.signals(closes, volumes)
        self.assertEqual(safety.data_health(sig, ["UP1.NS", "DN1.NS"]), [])
        bad = dict(sig, market_sma=np.nan, sma200=sig["sma200"] * np.nan)
        probs = safety.data_health(bad, ["UP1.NS", "DN1.NS"])
        self.assertEqual(len(probs), 2)

    def test_health_ignores_holdings_too_young_for_a_200d_line(self):
        closes, volumes = make_panel()
        sig = rules.signals(closes, volumes)
        young = dict(sig, sma200=sig["sma200"] * np.nan, hist=sig["hist"] * 0 + 50)
        self.assertEqual(safety.data_health(young, ["UP1.NS", "DN1.NS"]), [])
        self.assertEqual(safety.data_health(young, ["NOT_IN_DATA.NS"]), [])

    def test_stale(self):
        today = dt.date(2026, 11, 10)  # Tuesday
        self.assertFalse(safety.stale(pd.Timestamp("2026-11-09"), today, 3))
        self.assertFalse(safety.stale(pd.Timestamp("2026-11-06"), today, 3))  # Friday, weekend between
        self.assertTrue(safety.stale(pd.Timestamp("2026-10-30"), today, 3))


class TestLossHaltAndPriceCheck(unittest.TestCase):
    def test_loss_halt(self):
        d = dt.date(2026, 11, 10)
        self.assertTrue(safety.loss_halt({"2026-11-09": 25000}, 20000, d, 15)[0])
        self.assertFalse(safety.loss_halt({"2026-11-09": 25000}, 23000, d, 15)[0])
        self.assertFalse(safety.loss_halt({"2026-10-01": 50000}, 20000, d, 15)[0])  # old high ignored
        self.assertFalse(safety.loss_halt({}, float("nan"), d, 15)[0])

    def test_price_check(self):
        buy = {"action": "BUY", "ticker": "A.NS", "symbol": "A", "limit": 101.0}
        sell = {"action": "SELL", "ticker": "B.NS", "symbol": "B", "limit": 97.0}
        keep, w = safety.price_check([buy, sell], {"A.NS": 93.0, "B.NS": 92.0}, 0.15)  # normal -7%/-8% days
        self.assertEqual(len(keep), 2)
        self.assertEqual(w, [])
        keep, w = safety.price_check([buy, sell], {"A.NS": 50.0, "B.NS": 50.0}, 0.15)  # bad data
        self.assertEqual([o["action"] for o in keep], ["SELL"])
        self.assertEqual(len(w), 2)
        keep, _ = safety.price_check([buy, sell], {}, 0.15)  # no live prices: sells still go
        self.assertEqual([o["action"] for o in keep], ["SELL"])


if __name__ == "__main__":
    unittest.main()
