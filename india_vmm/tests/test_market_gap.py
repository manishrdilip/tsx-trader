import os, sys, unittest
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from india_vmm import rules


class MarketGapTest(unittest.TestCase):
    def test_one_missing_market_bar_keeps_200d_average(self):
        idx = pd.bdate_range("2025-01-01", periods=300)
        closes = pd.DataFrame({rules.MARKET: np.linspace(100, 130, 300),
                               "AAA.NS": np.linspace(50, 90, 300)}, index=idx)
        closes.iloc[-10, 0] = np.nan          # Yahoo gap for the market line
        volumes = pd.DataFrame(1e6, index=idx, columns=closes.columns)
        sig = rules.signals(closes, volumes)
        self.assertTrue(np.isfinite(sig["market_sma"]))


if __name__ == "__main__":
    unittest.main()
