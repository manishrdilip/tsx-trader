"""Synthetic metamorphic tests of daily long-only cash accounting; no downloads."""
import unittest
import numpy as np
import pandas as pd
from research.daily_cash_ledger_audit import ledger

class DailyLedgerMetamorphicTests(unittest.TestCase):
    @staticmethod
    def data():
        ix=pd.bdate_range("2024-01-02",periods=260)
        t=np.arange(len(ix),dtype=float)
        op=pd.DataFrame({"A":100+0.3*t,"B":65+0.12*t},index=ix)
        close=op*1.001
        return op,close

    def test_reconcile_realized_pnl_and_cash_costs(self):
        op,cl=self.data()
        for cost in (0,.001,.005):
            for slots in (1,2,5):
                trades,curve=ledger(op,cl,cost,slots,20,.1)
                self.assertGreater(len(trades),0)
                self.assertTrue(np.isfinite(curve.to_numpy()).all())
                self.assertTrue((curve>=0).all())
                self.assertAlmostEqual(float(curve.iloc[-1]),5000+float(trades.pnl.sum()),places=6)
                self.assertTrue((pd.to_datetime(trades.exit_date)>pd.to_datetime(trades.entry_date)).all())

    def test_future_close_mutation_cannot_change_past_equity(self):
        op,cl=self.data()
        _,baseline=ledger(op,cl,.0025,2,20,.1)
        altered=cl.copy()
        altered.iloc[240:]*=1000
        _,revised=ledger(op,altered,.0025,2,20,.1)
        pd.testing.assert_series_equal(baseline.loc[:op.index[239]],revised.loc[:op.index[239]])

    def test_diagnostic_stop_does_not_masquerade_as_executable_stop(self):
        op,cl=self.data()
        a,curve_a=ledger(op,cl,.0025,2,20,.05)
        b,curve_b=ledger(op,cl,.0025,2,20,.30)
        pd.testing.assert_series_equal(curve_a,curve_b)
        pd.testing.assert_series_equal(a.pnl,b.pnl)

if __name__=="__main__":
    unittest.main()
