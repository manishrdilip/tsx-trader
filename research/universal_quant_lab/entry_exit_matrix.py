"""Separate entry and exit effects in a bounded, matched daily development study."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from itertools import product

import exchange_calendars as xc
from numba import njit
import numpy as np
import pandas as pd

from available_intraday_screen import CAPITAL, FEE, FRICTION, check, digest
from eodhd import atomic_json
from run_universe import read


DATES = ("2016-01-01", "2022-01-01", "2024-11-27")
ENTRIES = ("monthly_calendar", "monthly_trend_gate", "weekly_pullback_in_uptrend")
EXITS = ("20_session_time_exit", "8pct_trailing_exit", "100_day_trend_exit")
GRID = tuple(product(ENTRIES, EXITS))


def features(bars):
    close = bars.close
    dates = pd.DatetimeIndex(bars.session)
    month = dates.to_period("M")
    week = dates.to_period("W-FRI")
    monthly = pd.Series(np.r_[month[:-1] != month[1:], False],index=bars.index)
    weekly = pd.Series(np.r_[week[:-1] != week[1:], False],index=bars.index)
    trend = close.gt(close.rolling(200).mean())
    positive_quarter = close.gt(close.shift(63))
    bounce = close.gt(close.shift())
    dip = close.lt(.95*close.shift().rolling(20).max())
    entries = np.column_stack((monthly, monthly & trend & positive_quarter, weekly & trend & dip & bounce))
    return entries, close.lt(close.rolling(100).mean()).to_numpy()


@njit
def replay(opens, closes, entry, trend_exit, exit_index, first, last):
    cash, units, basis, highest, peak, max_dd = CAPITAL, 0., CAPITAL, 0., CAPITAL, 0.
    opened, trades, wins, held, bars_exposed = 0, 0, 0, 0, 0
    for i in range(first, last):
        liquidated = False
        if units > 0:
            exit_signal = ((exit_index == 0 and i-opened >= 20) or
                           (exit_index == 1 and closes[i-1] <= highest*.92) or
                           (exit_index == 2 and trend_exit[i-1]))
            if exit_signal or i == last-1:
                cash += units*opens[i]*(1-FRICTION)-FEE
                wins += int(cash>basis)
                trades += 1
                held += i-opened
                units = 0.
                liquidated = True
        if units == 0 and not liquidated and i < last-1 and i > first and entry[i-1] and cash > FEE:
            basis = cash
            units = (cash-FEE)/(opens[i]*(1+FRICTION))
            cash, opened, highest = 0., i, opens[i]
        if units > 0:
            highest = max(highest,closes[i])
            bars_exposed += 1
        equity = cash + (units*closes[i]*(1-FRICTION)-FEE if units > 0 else 0.)
        peak = max(peak,equity)
        max_dd = max(max_dd,1-equity/peak)
    passive = (((CAPITAL-FEE)/(opens[first]*(1+FRICTION)))*opens[last-1]*(1-FRICTION)-FEE)/CAPITAL-1
    return cash/CAPITAL-1, max_dd, trades, wins, held, bars_exposed, passive


def run(root,out):
    expected = xc.get_calendar("XNYS",start="2013-01-01",end="2024-11-26").sessions.strftime("%Y-%m-%d")
    source = root/"results/available-swing-140-v1/plan.json"
    inputs = read(source)["source"]
    out.mkdir(parents=True,exist_ok=True)
    plan = out/"plan.json"
    if not plan.exists():
        atomic_json(plan,{"strategy_scope":"provisional development","start":DATES[0],"split":DATES[1],"end":DATES[2],
                          "input_plan_sha256":digest(source),"code_sha256":digest(Path(__file__)),
                          "entries":ENTRIES,"exits":EXITS,"side_friction":FRICTION,"fee_per_fill":FEE,
                          "admission":"Require continuous sessions between first and last observed date in the evaluation span",
                          "ranking":"Select on training compounded net returns, compare all rules on validation"})
    control=read(plan)
    if control["input_plan_sha256"]!=digest(source) or control["code_sha256"]!=digest(Path(__file__)):
        raise RuntimeError("Study source or rules changed")
    progress_file=out/"progress.json"
    progress=read(progress_file) if progress_file.exists() else {"admitted":{},"excluded":{}}
    for symbol, raw in inputs.items():
        if symbol in progress["admitted"] or symbol in progress["excluded"]:
            continue
        check(root)
        reason = "No daily data" if not raw else None
        if raw:
            paths=[]
            for name, fingerprint in raw["files"]:
                path=root/name
                if digest(path)!=fingerprint:
                    raise RuntimeError("Daily source fingerprint changed")
                paths.append(path)
            bars=pd.read_parquet(paths,columns=["session","open","close","adjusted_close"])
            bars=bars[bars.session.isin(expected)].sort_values("session").reset_index(drop=True)
            first,split,last=[int(bars.session.searchsorted(d)) for d in DATES]
            if (split-first<250 or last-split<180 or bars.session.duplicated().any()):
                reason="Insufficient or duplicate daily bars"
            else:
                coverage=pd.Index(bars.session.iloc[first:last])
                sessions=expected[(expected>=coverage[0])&(expected<=coverage[-1])]
                if coverage.tolist()!=sessions.tolist():
                    reason="Missing exchange sessions inside evaluation"
                elif coverage[-1] != expected[-1]:
                    # Avoid assuming an exit fill at the end of a delisted or truncated series.
                    reason="Cannot verify exit through the common development cutoff"
        if reason:
            progress["excluded"][symbol]=reason
        else:
            opens=(bars.open*bars.adjusted_close/bars.close).to_numpy()
            closes=bars.adjusted_close.to_numpy()
            entry, trend=features(bars.assign(close=closes))
            if (not np.isfinite(opens).all() or not np.isfinite(closes).all()
                    or (opens<=0).any() or (closes<=0).any()):
                progress["excluded"][symbol]="Invalid executable prices"
            else:
                values=[list(replay(opens,closes,entry[:,ENTS],trend,XL,a,b))
                        for ENTS,XL in product(range(len(ENTRIES)),range(len(EXITS)))
                        for a,b in ((first,split),(split,last))]
                progress["admitted"][symbol]=values
        atomic_json(progress_file,progress)
    if not progress["admitted"]:
        raise RuntimeError("No eligible instrument")
    data=np.asarray(list(progress["admitted"].values())).reshape(-1,len(GRID),2,7)
    rows=[]
    for idx,(entry,exit_) in enumerate(GRID):
        row={"entry":entry,"exit":exit_}
        for period,name in enumerate(("train","validation")):
            values=data[:,idx,period,:]
            n=values[:,2].sum()
            row[name]={"net_return":float(values[:,0].mean()),"median_drawdown":float(np.median(values[:,1])),
                       "trades":int(n),"win_rate":float(values[:,3].sum()/n) if n else None,
                       "mean_hold_sessions":float(values[:,4].sum()/n) if n else None,
                       "buy_and_hold":float(values[:,6].mean())}
        rows.append(row)
    rows.sort(key=lambda x:-x["train"]["net_return"])
    results={"scope":"provisional development","official_v2_evaluations":0,"checked":len(inputs),
             "admitted":list(progress["admitted"]),"excluded":progress["excluded"],
             "candidate_count":len(GRID),"symbol_candidate_replays":len(progress["admitted"])*len(GRID),
             "plan_sha256":digest(plan),"train_ranked":rows,
             "limitations":["Point-in-time eligibility, total-return adjustments and exit liquidity remain approximate.",
                            "Previously observed development periods. Continuous coverage filter creates survivorship bias.",
                            "Separate equal-capital sleeves. No matched VMM return series."]}
    atomic_json(out/"report.json",results)
    print(rows[0], flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("out",type=Path)
    args=parser.parse_args()
    run(args.root,args.out)
