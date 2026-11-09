"""Unit tests for india_vmm/rules.py. Run: python -m unittest discover -s india_vmm/tests"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rules  # noqa: E402


def make_panel(n=300, seed=0):
    """Synthetic NSE-like panel. Ends 2026-11-06 (completed sessions only)."""
    idx = pd.bdate_range(end="2026-11-06", periods=n)
    cols = {}
    vols = {}
    # 10 strong uptrends of different strength -> eligible, above 200d, ranked
    for i in range(10):
        drift = 0.002 + 0.0005 * i
        cols[f"UP{i}.NS"] = 100 * (1 + drift) ** np.arange(n)
        vols[f"UP{i}.NS"] = np.full(n, 200_000.0)
    # 10 downtrends -> below 200d, so never bought and sold if held
    for i in range(10):
        cols[f"DN{i}.NS"] = 300 * (1 - 0.002 - 0.0003 * i) ** np.arange(n)
        vols[f"DN{i}.NS"] = np.full(n, 200_000.0)
    cols["CHEAP.NS"] = np.full(n, 30.0)  # below Rs 60
    vols["CHEAP.NS"] = np.full(n, 10_000_000.0)
    cols["ILLIQ.NS"] = 100 * (1.004) ** np.arange(n)  # traded value far below Rs 50 lakh
    vols["ILLIQ.NS"] = np.full(n, 10.0)
    short = 100 * (1.004) ** np.arange(n)
    short[: n - 100] = np.nan  # under 253 sessions of history
    cols["NEW.NS"] = short
    vols["NEW.NS"] = np.full(n, 200_000.0)
    cols["NIFTYBEES.NS"] = 250 * (1.0005) ** np.arange(n)  # ETF: market reference, not a candidate
    vols["NIFTYBEES.NS"] = np.full(n, 1_000_000.0)
    closes = pd.DataFrame(cols, index=idx)
    volumes = pd.DataFrame(vols, index=idx)
    return closes, volumes


class TestRules(unittest.TestCase):
    def setUp(self):
        self.closes, self.volumes = make_panel()
        self.sig = rules.signals(self.closes, self.volumes)

    def test_candidate_filter(self):
        self.assertTrue(rules.is_candidate("RELIANCE.NS"))
        self.assertTrue(rules.is_candidate("BAJAJ-AUTO.NS"))
        self.assertFalse(rules.is_candidate("^NSEI"))
        self.assertFalse(rules.is_candidate("NIFTYBEES.NS"))
        self.assertFalse(rules.is_candidate("GOLDBEES.NS"))
        self.assertFalse(rules.is_candidate("SGBDEC30.NS"))
        self.assertFalse(rules.is_candidate("RELIANCE.TO"))

    def test_universe_excludes_bad_names(self):
        el = self.sig["eligible"]
        self.assertFalse(el["CHEAP.NS"])  # price band
        self.assertFalse(el["ILLIQ.NS"])  # liquidity
        self.assertFalse(el["NEW.NS"])  # history
        self.assertFalse(el["NIFTYBEES.NS"])  # ETF
        self.assertTrue(el["UP0.NS"])

    def test_ranking_only_uptrends_above_200d(self):
        ranked = self.sig["ranked"]
        self.assertTrue(ranked, "expected at least one ranked candidate")
        for s in ranked:
            self.assertTrue(s.startswith("UP"), s)
        r = self.sig["r12"]
        self.assertEqual(ranked, sorted(ranked, key=lambda s: -r[s]))  # strongest first

    def test_market_filter_on(self):
        self.assertTrue(self.sig["market_ok"])
        self.assertEqual(self.sig["market"], "NIFTYBEES.NS")

    def test_market_filter_off_blocks_buys_but_not_sells(self):
        sig = dict(self.sig, market_ok=False)
        orders, notes = rules.plan(sig, {"DN0.NS": 10}, equity=20_000, cash=20_000)
        self.assertTrue(all(o["action"] == "SELL" for o in orders))
        self.assertTrue(any("market filter OFF" in n for n in notes))
        orders, _ = rules.plan(sig, {}, equity=20_000, cash=20_000)
        self.assertEqual(orders, [])

    def test_sell_rule_below_200d(self):
        orders, _ = rules.plan(self.sig, {"DN0.NS": 10}, equity=20_000, cash=0)
        self.assertEqual(len(orders), 1)
        o = orders[0]
        self.assertEqual((o["action"], o["symbol"], o["qty"]), ("SELL", "DN0", 10))
        self.assertLess(o["limit"], float(self.sig["close"]["DN0.NS"]))
        self.assertIn("200d", o["reason"])

    def test_no_sell_for_healthy_holding(self):
        orders, _ = rules.plan(self.sig, {"UP9.NS": 5}, equity=20_000, cash=0)
        self.assertFalse([o for o in orders if o["action"] == "SELL"])

    def test_buy_limit_is_close_plus_1pct_on_tick(self):
        orders, _ = rules.plan(self.sig, {}, equity=20_000, cash=20_000)
        buys = [o for o in orders if o["action"] == "BUY"]
        self.assertTrue(buys)
        for o in buys:
            px = float(self.sig["close"][o["ticker"]])
            self.assertGreaterEqual(o["limit"], round(px * 1.01, 2) - 0.05)
            self.assertLessEqual(o["limit"], round(px * 1.01, 2) + 0.05)
            self.assertAlmostEqual(round(o["limit"] / 0.05) * 0.05, o["limit"], places=6)

    def test_15pct_cap_per_order(self):
        for equity in (2_000, 6_000, 25_000, 500_000):
            orders, _ = rules.plan(self.sig, {}, equity=equity, cash=equity)
            for o in orders:
                self.assertLessEqual(o["value"], 0.15 * equity + 1e-9, (equity, o))

    def test_slots_and_order_count(self):
        orders, notes = rules.plan(self.sig, {}, equity=2_000, cash=2_000)
        self.assertLessEqual(len([o for o in orders if o["action"] == "BUY"]), rules.MAX_SLOTS)
        self.assertLessEqual(len(orders), rules.MAX_ORDERS_PER_RUN)
        self.assertTrue(any(n.startswith("slots") for n in notes))

    def test_no_duplicate_when_order_open(self):
        orders, notes = rules.plan(self.sig, {}, equity=20_000, cash=20_000, open_syms={"UP9.NS"})
        self.assertFalse([o for o in orders if o["ticker"] == "UP9.NS"])
        self.assertTrue(any("already open" in n for n in notes))

    def test_protected_never_sold_or_bought(self):
        prot = frozenset({"DN0.NS", "UP9.NS"})
        orders, notes = rules.plan(self.sig, {"DN0.NS": 10}, equity=20_000, cash=20_000, protected=prot)
        self.assertFalse([o for o in orders if o["ticker"] in prot])
        self.assertTrue(any("protected" in n for n in notes))
        self.assertTrue(all(o["ticker"] not in prot for o in orders))

    def test_no_add_on_to_existing_holding(self):
        orders, _ = rules.plan(self.sig, {"UP9.NS": 5}, equity=20_000, cash=20_000)
        self.assertFalse([o for o in orders if o["action"] == "BUY" and o["ticker"] == "UP9.NS"])

    def test_tick_rounding(self):
        self.assertEqual(rules.tick_up(100.01), 100.05)
        self.assertEqual(rules.tick_up(100.00), 100.00)
        self.assertEqual(rules.tick_down(100.07), 100.05)
        self.assertEqual(rules.tick_down(100.00), 100.00)


if __name__ == "__main__":
    unittest.main()


class RiskAdjRankTest(unittest.TestCase):
    def test_smoother_stock_ranks_first(self):
        n = 300
        idx = pd.bdate_range(end="2026-11-06", periods=n)
        rng = np.random.default_rng(1)
        cols, vols = {}, {}
        for i in range(30):
            cols[f"F{i}.NS"] = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
            vols[f"F{i}.NS"] = np.full(n, 200_000.0)
        # higher return but very noisy vs slightly lower return, smooth
        cols["NOISY.NS"] = 100 * np.exp(np.linspace(0, 1.2, n) + rng.normal(0, 0.05, n))
        cols["SMOOTH.NS"] = 100 * np.exp(np.linspace(0, 1.0, n) + rng.normal(0, 0.002, n))
        vols["NOISY.NS"] = vols["SMOOTH.NS"] = np.full(n, 200_000.0)
        cols["NIFTYBEES.NS"] = 100 * (1.0005) ** np.arange(n)
        vols["NIFTYBEES.NS"] = np.full(n, 1e6)
        C, V = pd.DataFrame(cols, index=idx), pd.DataFrame(vols, index=idx)
        sig = rules.signals(C, V)
        self.assertIn("SMOOTH.NS", sig["ranked"])
        self.assertIn("NOISY.NS", sig["ranked"])
        self.assertLess(sig["ranked"].index("SMOOTH.NS"), sig["ranked"].index("NOISY.NS"))
        self.assertGreater(sig["r12"]["NOISY.NS"], sig["r12"]["SMOOTH.NS"])
