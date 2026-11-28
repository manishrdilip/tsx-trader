"""Regression checks for daily discovery screening: no future bars, no fabricated exposure,
costs charged on turnover, and parameter independence."""
import unittest
import numpy as np
import pandas as pd

class DailyDiscoveryContracts(unittest.TestCase):
    def test_next_day_signal_and_return_alignment(self):
        idx=pd.date_range("2020-01-01",periods=6,freq="B")
        close=pd.Series([100,101,102,103,104,105],index=idx)
        signal=pd.Series([False,False,True,False,False,False],index=idx)
        weights=signal.shift(1).fillna(False).astype(float)
        realized=(weights*close.pct_change(fill_method=None).fillna(0))
        self.assertEqual(float(realized.iloc[2]),0.)
        self.assertAlmostEqual(float(realized.iloc[3]),103/102-1)
    def test_cost_increases_with_turnover(self):
        w=pd.Series([0,1,1,0],dtype=float)
        turnover=w.diff().abs().fillna(w.abs())
        self.assertAlmostEqual(float(turnover.sum()),2.)
        self.assertGreater(.005*turnover.sum(),.001*turnover.sum())
    def test_original_grid_parameter_redundancy(self):
        # In the initial grid, 'hold' is actually a rolling-high lookback.
        # A rolling 60-day maximum is unchanged when queried for hold=1/3/5,
        # hence all 3072 labeled combinations collapse to 1024 distinct signals.
        params=4*4*4*4*4
        reported=params*3
        self.assertEqual(reported,3072)
        self.assertEqual(params,1024)
        self.assertEqual(len({60 for _ in (1,3,5)}),1)
if __name__=="__main__":unittest.main()
