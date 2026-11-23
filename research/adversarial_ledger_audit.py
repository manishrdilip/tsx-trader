"""Research-only deterministic adversarial audit of daily_cash_ledger_audit. No market performance claims."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.daily_cash_ledger_audit import ledger

def synthetic():
    idx=pd.bdate_range("2020-01-01",periods=270)
    close=pd.DataFrame(index=idx)
    op=pd.DataFrame(index=idx)
    for j,t in enumerate(("AAA.TO","BBB.TO","CCC.TO")):
        c=10.0*(1.003+0.0001*j)**np.arange(len(idx))
        o=c.copy()
        # An adverse overnight discontinuity after a long positive trend.
        o[230]=c[229]*0.40
        c[230]=o[230]
        c[231:]=c[230]*(1.003+0.0001*j)**np.arange(1,len(idx)-230)
        o[231:]=c[230]*(1.003+0.0001*j)**np.arange(1,len(idx)-230)
        close[t]=c
        op[t]=o
    return op,close

def main():
    op,cl=synthetic()
    checks=[]
    for slots in (1,3,5):
        for cost in (0.0,0.001,0.005,0.02):
            by_stop={}
            for stop in (0.05,0.10,0.20):
                trades,curve=ledger(op,cl,cost,slots,20,stop)
                assert len(curve)>20 and np.isfinite(curve.to_numpy()).all()
                assert (curve>=0).all(), "negative equity"
                assert len(trades)>0, "synthetic test never traded"
                # No external cash flows: final realized equity must reconcile to P&L.
                assert abs(float(curve.iloc[-1])-(5000+float(trades.pnl.sum())))<1e-6
                assert (trades.entry_date<trades.exit_date).all()
                by_stop[stop]=(trades,curve)
            reference=by_stop[0.05][1]
            for stop in (0.10,0.20):
                assert np.array_equal(reference.to_numpy(),by_stop[stop][1].to_numpy()), "diagnostic stop unexpectedly changed fills"
            checks.append(dict(slots=slots,cost=cost,ending_equity=float(reference.iloc[-1]),
                               realized_trades=len(by_stop[0.05][0]),
                               gap_flags={str(s):int(by_stop[s][0].gap_beyond_stop.sum()) for s in by_stop}))
    # This is an execution-identifiability audit, not a profitability screen.
    out=Path("research/adversarial_ledger_results")
    out.mkdir(parents=True,exist_ok=True)
    (out/"report.json").write_text(json.dumps({
      "status":"passed","cases":len(checks)*3,"checks":checks,
      "interpretation":"stop_pct is diagnostic only: it never changes execution or equity",
      "limitations":["synthetic prices only","not a matched VMM baseline",
       "not actual broker fills or observed bid/ask","no untouched out-of-sample or forward paper trading",
       "Yahoo 5-minute history is typically limited to roughly 60 days",
       "surviving-stock Yahoo daily data has survivorship bias"]},indent=2))
    print("PASS: adversarial ledger accounting; stop thresholds are not executable stops",len(checks)*3)

if __name__=="__main__":
    main()
