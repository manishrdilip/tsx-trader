"""Research-only causal feature audit. No orders or live code changes.

For each method, compare the signal and stop at every eligible bar with
the same values computed on a history truncated at that bar. A discrepancy
means future candles affected a historical decision.
"""
import unittest
import numpy as np
import pandas as pd
from research import pro_intraday_test as core

METHODS = ("orb", "vwap", "bull_flag", "resistance", "mean_reversion")

def fixture():
    dates = pd.bdate_range("2026-09-14", periods=4)
    idx = pd.DatetimeIndex(
        [d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=5*i)
         for d in dates for i in range(78)]
    ).tz_localize(core.TZ)
    n = np.arange(len(idx))
    close = 100 + 0.02*n + 0.8*np.sin(n/7)
    return pd.DataFrame({
        "Open": close-0.03, "High": close+0.2,
        "Low": close-0.2, "Close": close,
        "Volume": 1000 + (n*37)%800,
    }, index=idx)

class CausalSignalTests(unittest.TestCase):
    def test_all_methods_are_prefix_invariant(self):
        d = fixture()
        # Test around session boundaries and signal eligibility transitions.
        checkpoints = [6, 12, 29, 41, 54, 76, 77, 78, 84, 90, 119,
                       155, 156, 168, 200, 233, 234, 245, 300, 311]
        for method in METHODS:
            full = core.signals(d, method)
            for i in checkpoints:
                with self.subTest(method=method, bar=i):
                    partial = core.signals(d.iloc[:i+1], method)
                    self.assertEqual(bool(full.signal.iloc[i]), bool(partial.signal.iloc[-1]))
                    if bool(full.signal.iloc[i]):
                        self.assertAlmostEqual(float(full.stop.iloc[i]),
                                               float(partial.stop.iloc[-1]), places=8)
                        self.assertAlmostEqual(float(full.rvol.iloc[i]),
                                               float(partial.rvol.iloc[-1]), places=8)

if __name__ == "__main__":
    unittest.main()
