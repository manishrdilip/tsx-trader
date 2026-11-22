"""Deterministic execution-timing regression tests; no market download or live orders."""
import unittest
from unittest.mock import patch
import pandas as pd
from research import pro_intraday_test as bt

class ExecutionAccountingTests(unittest.TestCase):
    def test_no_same_bar_cash_or_slot_recycling(self):
        ts=pd.date_range("2026-11-20 09:30",periods=4,freq="5min",tz="America/Toronto")
        # A buys on second candle, hits stop on third; B signals on second
        # candle, attempts entry on third. A's exit cannot finance B.
        def bars(opens,lows,highs):
            return pd.DataFrame({"Open":opens,"High":highs,"Low":lows,
                "Close":opens,"Volume":[100]*4},index=ts)
        a=bars([100,100,100,100],[100,100,90,100],[100,100,100,100])
        b=bars([100,100,100,100],[100]*4,[100]*4)
        def fake_signals(d,method):
            s=[False,False,False,False]
            s[0 if d is a else 1]=True
            return pd.DataFrame({"signal":s,"stop":[95]*4,
                "rvol":[2]*4},index=d.index)
        with patch.object(bt,"signals",side_effect=fake_signals),patch.object(bt,"SLOTS",1):
            _,trades,_=bt.simulate({"A":a,"B":b},"bull_flag")
        self.assertFalse(any(t["ticker"]=="B" for t in trades))
        self.assertTrue(any(t["ticker"]=="A" for t in trades))

    def test_entry_bar_stop_is_charged(self):
        ts=pd.date_range("2026-11-20 09:30",periods=3,freq="5min",tz="America/Toronto")
        d=pd.DataFrame({"Open":[100]*3,"High":[100]*3,
          "Low":[100,90,100],"Close":[100]*3,"Volume":[100]*3},index=ts)
        def fake_signals(d,method):
            return pd.DataFrame({"signal":[True,False,False],
               "stop":[95]*3,"rvol":[2]*3},index=d.index)
        with patch.object(bt,"signals",side_effect=fake_signals):
            _,trades,_=bt.simulate({"A":d},"bull_flag")
        self.assertEqual(len(trades),1)
        self.assertEqual(trades[0]["reason"],"entry_bar_stop")
        self.assertLess(trades[0]["pnl"],0)

if __name__=="__main__":unittest.main()
