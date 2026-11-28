"""Research-only accounting invariants on synthetic OHLC; no brokerage access."""
import unittest
from unittest.mock import patch
import pandas as pd
from research import pro_intraday_test as bt

class CashInvariantTests(unittest.TestCase):
    def bars(self, opens, highs=None, lows=None):
        ts=pd.date_range("2026-11-20 09:30", periods=len(opens), freq="5min", tz="America/Toronto")
        return pd.DataFrame({"Open":opens,"High":highs or opens,"Low":lows or opens,
                             "Close":opens,"Volume":[100]*len(opens)},index=ts)

    def test_flat_market_round_trip_loses_both_sides_of_cost(self):
        d=self.bars([100,100,100])
        def sig(d,method):
            return pd.DataFrame({"signal":[True,False,False],"stop":[95]*3,
                                 "rvol":[2]*3},index=d.index)
        with patch.object(bt,"signals",side_effect=sig),patch.object(bt,"COST",0.005):
            summary,trades,daily=bt.simulate({"A":d},"orb")
        self.assertEqual(len(trades),1)
        self.assertLess(summary["final"],5000)
        self.assertAlmostEqual(summary["net"],sum(t["pnl"] for t in trades),delta=0.02)
        self.assertEqual(summary["final"],daily[-1]["equity"])

    def test_no_overnight_signal_carry(self):
        ts=pd.DatetimeIndex(["2026-11-19 15:55","2026-11-20 09:30","2026-11-20 09:35"]).tz_localize("America/Toronto")
        d=pd.DataFrame({"Open":[100]*3,"High":[100]*3,"Low":[100]*3,
                        "Close":[100]*3,"Volume":[100]*3},index=ts)
        def sig(d,method):
            return pd.DataFrame({"signal":[True,False,False],"stop":[95]*3,
                                 "rvol":[2]*3},index=d.index)
        with patch.object(bt,"signals",side_effect=sig):
            summary,trades,_=bt.simulate({"A":d},"orb")
        self.assertEqual(trades,[])
        self.assertEqual(summary["final"],5000)

    def test_quantity_never_exceeds_preopen_cash(self):
        d=self.bars([100,100,100,100],highs=[100,100,100,100],lows=[100,100,100,100])
        def sig(d,method):
            return pd.DataFrame({"signal":[True,False,False,False],"stop":[99]*4,
                                 "rvol":[2]*4},index=d.index)
        with patch.object(bt,"signals",side_effect=sig),patch.object(bt,"COST",0.005):
            summary,trades,_=bt.simulate({"A":d},"orb")
        self.assertEqual(len(trades),1)
        self.assertLessEqual(summary["final"],5000)
        self.assertGreaterEqual(summary["final"],0)

if __name__=="__main__": unittest.main()
