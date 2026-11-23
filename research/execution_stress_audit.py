"""Research-only deterministic execution stress suite; no network or brokerage.
Demonstrates that fractional-weight return screens can disagree with cash-ledger fills.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.daily_cash_ledger_audit import ledger

OUT=Path("research/execution_stress_results")
def scenario(name, gap, cost):
    dates=pd.bdate_range("2020-01-01",periods=255)
    i=np.arange(len(dates))
    # 200-day warmup, then positive momentum and an overnight shock.
    base=100+0.18*i
    op=pd.DataFrame({"AAA.TO":base.copy(),"BBB.TO":base*.81},index=dates,dtype=float)
    cl=op.copy()
    # An unanticipated gap at an exit open. No stop can guarantee a stop-price fill.
    op.iloc[235,0]*=(1+gap)
    cl.iloc[235,0]=op.iloc[235,0]
    trades,curve=ledger(op,cl,cost,2,20,.05)
    if (curve<0).any():raise AssertionError("Negative equity")
    if not np.isfinite(curve).all():raise AssertionError("Nonfinite equity")
    if len(trades)==0:raise AssertionError("Expected trades")
    # Identity: final equity equals initial cash plus realized P&L.
    pnl=float(trades.pnl.sum())
    if not np.isclose(float(curve.iloc[-1]),5000+pnl,atol=1e-5):
        raise AssertionError("Cash ledger reconciliation failure")
    return {"scenario":name,"gap":gap,"cost_per_side":cost,
            "final_cash":float(curve.iloc[-1]),"net_profit":pnl,
            "max_drawdown":float((curve/curve.cummax()-1).min()),
            "trade_count":len(trades),"gap_beyond_stop":int(trades.gap_beyond_stop.sum())}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cases=[]
    for gap in (0.,-.10,-.30,-.60):
        for cost in (.001,.0025,.005):
            cases.append(scenario(f"gap_{gap}_cost_{cost}",gap,cost))
    # The shock must have a measurable adverse effect on the account, not merely a label.
    normal=next(x for x in cases if x["gap"]==0 and x["cost_per_side"]==.0025)
    severe=next(x for x in cases if x["gap"]==-.60 and x["cost_per_side"]==.0025)
    if severe["final_cash"]>=normal["final_cash"]:
        raise AssertionError("Adverse gap did not reduce account equity")
    if severe["max_drawdown"]>=normal["max_drawdown"]:
        raise AssertionError("Adverse gap did not increase drawdown")
    report={"cases":cases,"reconciled":True,
        "severe_gap_reduces_equity":True,
        "severe_gap_increases_drawdown":True,
        "limits":["Synthetic regression tests only; not empirical strategy performance",
                  "Current overnight ledger has NO intraday stop orders",
                  "Stop threshold only labels next-open gap events",
                  "Surviving-stock Yahoo sample and 60-day five-minute history cannot validate 3x",
                  "No independently corrected VMM baseline or forward paper evidence"]}
    (OUT/"execution_stress.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({"scenarios":len(cases),"normal":normal,"severe":severe},indent=2))
if __name__=="__main__":main()
