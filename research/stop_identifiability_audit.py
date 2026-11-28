"""Research-only independent invariance and parameter-identifiability audit.
Tests whether advertised stop thresholds actually change executable outcomes.
No downloads, trades, or live-code changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.daily_cash_ledger_audit import ledger

OUT=Path("research/stop_identifiability_results")
def synthetic():
    dates=pd.bdate_range("2020-01-01",periods=245)
    # Deterministic, non-random synthetic series with occasional overnight gaps.
    x=np.arange(len(dates))
    op=pd.DataFrame({"AAA.TO":100+0.08*x+2*np.sin(x/9),
                     "BBB.TO":75+0.07*x+np.cos(x/7)},index=dates)
    op.iloc[220,0]*=.86
    close=op*(1+.002*np.sin(x/4)[:,None])
    return op,close
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    op,close=synthetic()
    signatures=[]
    for stop in (.02,.05,.10,.20,.35):
        trades,curve=ledger(op,close,.0025,2,20,stop)
        signatures.append((stop,round(float(curve.iloc[-1]),8),
            tuple(np.round(trades.pnl.to_numpy(),8)),int(trades.gap_beyond_stop.sum())))
    # This is a deliberate RED audit: thresholds change diagnostics, not execution.
    unique_execution=len(set((a,b) for _,a,b,_ in signatures))
    result={"tested_stop_thresholds":[x[0] for x in signatures],
            "unique_executable_outcomes":unique_execution,
            "threshold_diagnostics":[{"stop":s,"final_cash":v,"gap_count":g}
                                     for s,v,_,g in signatures],
            "conclusion":"STOP THRESHOLD IS NOT AN EXECUTABLE STOP. Do not count stop settings as independent strategies.",
            "limitations":["Synthetic data for deterministic regression only",
                           "Not a strategy profitability backtest",
                           "No intraday OHLC stop execution in audited ledger"]}
    (OUT/"stop_identifiability.json").write_text(json.dumps(result,indent=2))
    assert unique_execution==1,"Unexpected executable stop variation; inspect implementation"
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
