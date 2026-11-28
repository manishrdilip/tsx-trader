"""Research-only deterministic causality and ordering audit for daily cash ledger."""
import unittest
import numpy as np
import pandas as pd
from research.daily_cash_ledger_audit import ledger

class CausalityAndOrdering(unittest.TestCase):
    def fixtures(self):
        ix=pd.bdate_range("2022-01-03",periods=270)
        t=np.arange(len(ix),dtype=float)
        op=pd.DataFrame({"AAA.TO":100+.3*t,"BBB.TO":75+.225*t,"CCC.TO":55+.11*t},index=ix)
        cl=op*1.001
        return op,cl

    def test_column_permutation_does_not_change_equity_or_trades(self):
        op,cl=self.fixtures()
        a,eq_a=ledger(op,cl,.0025,2,20,.1)
        cols=list(reversed(op.columns))
        b,eq_b=ledger(op[cols],cl[cols],.0025,2,20,.1)
        pd.testing.assert_series_equal(eq_a,eq_b)
        pd.testing.assert_frame_equal(a.reset_index(drop=True),b.reset_index(drop=True))

    def test_future_open_mutation_cannot_change_past_equity(self):
        op,cl=self.fixtures()
        _,baseline=ledger(op,cl,.0025,2,20,.1)
        altered=op.copy()
        altered.iloc[245:]*=3
        _,revised=ledger(altered,cl,.0025,2,20,.1)
        pd.testing.assert_series_equal(baseline.loc[:op.index[244]],revised.loc[:op.index[244]])

    def test_no_transaction_cost_on_flat_prices_without_signal(self):
        ix=pd.bdate_range("2022-01-03",periods=260)
        op=pd.DataFrame({"AAA.TO":np.full(len(ix),100.)},index=ix)
        trades,curve=ledger(op,op,.005,1,20,.1)
        self.assertEqual(len(trades),0)
        self.assertTrue(np.allclose(curve.to_numpy(),5000.))

    def test_raising_cost_does_not_improve_flat_to_rising_fixture(self):
        op,cl=self.fixtures()
        outcomes=[]
        for cost in (0.,.001,.005):
            trades,curve=ledger(op,cl,cost,2,20,.1)
            self.assertGreater(len(trades),0)
            self.assertAlmostEqual(float(curve.iloc[-1]),5000+float(trades.pnl.sum()),places=6)
            outcomes.append(float(curve.iloc[-1]))
        self.assertGreaterEqual(outcomes[0],outcomes[1])
        self.assertGreaterEqual(outcomes[1],outcomes[2])

if __name__=="__main__":
    unittest.main()
