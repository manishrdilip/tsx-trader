"""Research-only temporal stability diagnostic; NOT independent out-of-sample validation.
Splits the available Yahoo 5m history into three contiguous chronological blocks.
Each block restarts with CAD 5000; no stitching or annualization of 60d returns.
"""
import json, os
from pathlib import Path
import pandas as pd
import pro_intraday_test as core

OUT=Path("research/temporal_stability_results")
METHODS=("orb","vwap","bull_flag","resistance","mean_reversion")
COSTS=(0.001,0.0025,0.005)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    downloaded={}
    failures={}
    for ticker in core.TICKERS:
        try:
            d=core.get_data(ticker)
            if d is not None:downloaded[ticker]=d
            else:failures[ticker]="insufficient bars"
        except Exception as e:
            failures[ticker]=str(e)[:150]
    if len(downloaded)<5:raise RuntimeError("Insufficient real 5-minute data")
    sessions=sorted({str(ts.date()) for d in downloaded.values() for ts in d.index})
    if len(sessions)<30:raise RuntimeError("Insufficient trading sessions for three chronological blocks")
    n=len(sessions)
    boundaries=[0,n//3,2*n//3,n]
    rows=[]
    for block in range(3):
        days=set(sessions[boundaries[block]:boundaries[block+1]])
        subset={t:d.loc[[str(ts.date()) in days for ts in d.index]].copy()
                for t,d in downloaded.items()}
        subset={t:d for t,d in subset.items() if len(d)>150}
        if len(subset)<5:raise RuntimeError("Insufficient tickers in block "+str(block))
        for cost in COSTS:
            core.COST=cost
            for method in METHODS:
                z,trades,daily=core.simulate(dict(subset),method)
                z.update(block=block+1,first_session=min(days),last_session=max(days),
                         cost_per_side=cost,return_pct=round(100*z["net"]/core.START_CASH,3))
                rows.append(z)
    pd.DataFrame(rows).to_csv(OUT/"block_comparison.csv",index=False)
    (OUT/"audit.json").write_text(json.dumps({
        "sessions":n,"usable_tickers":list(downloaded),"failures":failures,
        "limitations":["All blocks from previously explored 60d Yahoo five-minute data",
                       "NOT untouched out-of-sample","NOT forward paper trading",
                       "Currently listed universe: survivorship bias",
                       "No observed spreads, liquidity, queue priority or market impact",
                       "Fixed per-side cost proxy and stop-first OHLC approximation",
                       "Each block independently resets capital to CAD 5000",
                       "Not comparable to VMM until identical periods and accounting verified"]
    },indent=2))
    print(pd.DataFrame(rows).to_string(index=False))
if __name__=="__main__":main()
