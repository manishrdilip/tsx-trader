"""Walk-forward portfolio screening and search-wide synthetic null pilot."""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path

import duckdb
import exchange_calendars as xc
import numpy as np
import pandas as pd

from campaign_watchdog import guard, health
from eodhd import atomic_json
from portfolio_discovery import CAPITAL, FEE, FRICTION, load_equity, simulate
from profit_admission import cpu_guard


def read(path):
    return json.loads(path.read_bytes())


def candidates(close, grid):
    change = close.diff()
    for family, options in grid.items():
        if family == "holding_sessions":
            continue
        windows = options.get("lookback", options.get("rsi_window"))
        for length, level in product(windows, options["threshold"]):
            if family == "momentum":
                signal = close.pct_change(length, fill_method=None) > level
            elif family == "mean_reversion":
                gains = change.clip(lower=0).ewm(alpha=1/length, adjust=False, min_periods=length).mean()
                losses = -change.clip(upper=0).ewm(alpha=1/length, adjust=False, min_periods=length).mean()
                signal = 100*gains/(gains+losses) <= level
            elif family == "breakout":
                signal = close > close.shift().rolling(length).max()
            else:
                risk = close.pct_change(fill_method=None).rolling(length).std()
                signal = (risk >= level) & (close > close.rolling(length).mean())
            for hold in grid["holding_sessions"]:
                yield (family,length,level,hold),signal.to_numpy(dtype=bool)


def check(root):
    reason = guard(health(root)) or cpu_guard(root,85) == "cpu_temperature"
    if reason:
        raise RuntimeError(f"Laptop resource guard paused research: {reason}")


def account_inputs(root, db, scope, currency, plan):
    first = f'{plan["folds"]["first_train_year"]}-01-01'
    end = plan["evaluation_cutoff_exclusive"]
    venue = "XTSE" if currency == "CAD" else "XNYS"
    calendar = pd.Index(xc.get_calendar(venue,start=first,end=end).sessions.strftime("%Y-%m-%d"))
    calendar = calendar[calendar<end]
    symbols=[]; packed=[]; close=[]; mapping=[]; slots=1; excluded={}
    for job in sorted(scope["jobs"],key=lambda x:x["symbol"]):
        if job["currency"]!=currency:
            continue
        try:
            bars, prices, cash_map, count = load_equity(root,db,job,max(first,job.get("eligible_from",first)),end,calendar)
        except ValueError as error:
            excluded[job["symbol"]]=str(error)
            continue
        packed.append(bars)
        close.append(prices)
        mapping.append(cash_map)
        symbols.append(job["symbol"])
        slots=max(slots,count)
    if not symbols or calendar.max()>=end:
        raise ValueError("Invalid development scope")
    prices=pd.concat(close,axis=1)
    prices.columns=symbols
    return calendar,np.ascontiguousarray(np.stack(packed,axis=1)),prices,np.stack(mapping,axis=1),slots,excluded


def fold_starts(calendar, plan):
    first=plan["folds"]["first_train_year"]
    last=plan["folds"]["last_complete_test_year"]
    width=plan["folds"]["train_years"]
    index=lambda year: int(calendar.searchsorted(f"{year}-01-01"))
    return [(year,max(1,index(year-width)),index(year),index(year+1))
            for year in range(first+width,last+1)]


def extract_trades(bars, fills, start):
    active={}
    outcomes=[]
    signatures=set()
    for (day,ticker,side) in np.argwhere(fills):
        offset=day+start
        units=int(fills[day,ticker,side])
        opening=bars[offset,ticker,0]
        if side==1:
            active[ticker]=(offset,units,units*opening*(1+FRICTION)+FEE)
            signatures.add((offset,int(ticker)))
        else:
            entered,qty,paid=active.pop(ticker)
            distributions=0.
            for factor,div in bars[entered+1:offset+1,ticker,3:5]:
                qty=int(qty*factor)
                distributions+=qty*div
            if qty!=units:
                raise ValueError("Trade and action replay disagree on shares")
            outcomes.append(units*opening*(1-FRICTION)-FEE+distributions-paid)
    if active:
        raise ValueError("Fold contains an unclosed position")
    return outcomes,signatures


def backtest(bars,mapping,slots,signal,exit_,hold,a,b,priority,trace=False,position_count=5):
    profit,risk,trades,_,_,fills=simulate(bars,mapping,slots,signal,exit_,hold,a,b,position_count,priority,trace)
    return profit/CAPITAL,risk,trades,fills


def compound(returns):
    return float(np.prod(1+np.asarray(returns))-1)


def search(root,bars,close,mapping,slots,folds,plan,detail):
    priority=np.tile(np.arange(close.shape[1]),(len(close),1))
    false=np.zeros(close.shape,dtype=bool)
    sma=close.rolling(200).mean()
    passive=close.notna().to_numpy()
    above=(close>sma).to_numpy()
    below=(close<sma).to_numpy()
    comparators={}
    if detail:
        for year,_,start,end in folds:
            held,*_=backtest(bars,mapping,slots,passive,false,10000,start,end,priority,
                              position_count=close.shape[1])
            trend,*_=backtest(bars,mapping,slots,above,below,10000,start,end,priority)
            limits=plan["regimes"]
            regime="bull" if held>limits["benchmark_bull_above"] else (
                   "bear" if held<limits["benchmark_bear_below"] else "choppy")
            comparators[year]=dict(passive=held,sma200=trend,regime=regime)
    rows=[]
    signatures={}
    for index,(rule,signal) in enumerate(candidates(close,plan["grid"])):
        if index%30==0:
            check(root)
        outcomes=[]
        sig=set()
        fold_rows=[]
        for year,train,start,end in folds:
            result,risk,trades,fills=backtest(bars,mapping,slots,signal,false,rule[3],start,end,priority,detail)
            row=dict(year=year,net_return=result)
            if detail:
                train_return,*_=backtest(bars,mapping,slots,signal,false,rule[3],train,start,priority)
                pnl,signature=extract_trades(bars,fills,start)
                if len(pnl)!=trades or not np.isclose(sum(pnl),result*CAPITAL,atol=1e-6):
                    raise ValueError("Trade P&L does not reconcile to account equity")
                sig.update(signature)
                outcomes.extend(pnl)
                row.update(train_return=train_return,drawdown=risk,trades=int(trades),**comparators[year])
            fold_rows.append(row)
        score=compound([row["net_return"] for row in fold_rows])
        record=dict(id=index,rule=rule,score=score)
        if detail:
            gates=plan["gates"]
            cut=int(np.ceil(len(outcomes)*gates["remove_top_fraction"]))
            trimmed=float(sum(sorted(outcomes)[:len(outcomes)-cut]))
            reasons=[]
            if len(outcomes)<gates["min_closed_test_trades"]:
                reasons.append("fewer_than_200_closed_trades")
            if trimmed<=0:
                reasons.append("nonpositive_after_top_5pct_removed")
            if score<=max(compound([f["passive"] for f in fold_rows]),compound([f["sma200"] for f in fold_rows])):
                reasons.append("did_not_beat_both_benchmarks")
            if np.mean([f["net_return"]>0 for f in fold_rows])<=gates["min_positive_fold_fraction_exclusive"]:
                reasons.append("positive_in_at_most_half_of_folds")
            if max(f["drawdown"] for f in fold_rows)>gates["max_fold_drawdown"]:
                reasons.append("fold_drawdown_limit")
            record.update(folds=fold_rows,trades=len(outcomes),trimmed_profit=trimmed,hard_gate_failures=reasons)
            signatures[index]=sig
        rows.append(record)
    return rows,signatures


def synthetic(bars,close,rng):
    # Shared signs preserve same-day cross-asset dependence and retain vol clustering.
    returns=np.log(close).diff()
    signs=np.repeat(rng.choice((-1.,1.),size=(len(close)+19)//20),20)[:len(close)]
    shocks=returns.subtract(returns.mean()).mul(signs,axis=0)
    prices=pd.DataFrame(index=close.index,columns=close.columns,dtype=float)
    sample=bars.copy()
    for index,name in enumerate(close.columns):
        live=np.flatnonzero(close[name].notna().to_numpy())
        first=live[0]
        path=bars[first,index,2]*np.exp(shocks[name].iloc[first:].fillna(0).cumsum().to_numpy())
        prices.iloc[first:,index]=path
        factor=path/bars[first:,index,2]
        sample[first:,index,:3]*=factor[:,None]
    sample[:,:,3]=1.
    sample[:,:,4]=0.
    return sample,prices,np.full(bars.shape[:2]+(2,),-1,dtype=np.int64)


def analyze(root,scope,plan,output,reps):
    plan_hash=hashlib.sha256(plan.read_bytes()).hexdigest()
    spec=read(plan)
    report=dict(plan_sha256=plan_hash,scope=str(scope.name),official=0,accounts={},
                cutoff_exclusive=spec["evaluation_cutoff_exclusive"],
                published_utc=datetime.now(timezone.utc).isoformat(),
                state="running",promotion_candidates=[])
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True,config={"threads":1,"memory_limit":"192MB"}) as db:
        for currency in ("CAD","USD"):
            check(root)
            calendar,bars,close,mapping,slots,excluded=account_inputs(root,db,read(scope),currency,spec)
            folds=fold_starts(calendar,spec)
            rows,fills=search(root,bars,close,mapping,slots,folds,spec,True)
            # Reset each year to the same starting capital. Rank the stitched
            # returns as sequential folds, while preserving per-fold cash ledgers.
            rng=np.random.default_rng(spec["null"]["seed"])
            maxima=[]
            for _ in range(reps):
                prices,signals,dates=synthetic(bars,close,rng)
                trial,_=search(root,prices,signals,dates,1,folds,spec,False)
                maxima.append(max(x["score"] for x in trial))
            for row in rows:
                row["search_adjusted_empirical_p"]=(1+sum(x>=row["score"] for x in maxima))/(1+len(maxima))
            hard_pass=sorted((x for x in rows if not x["hard_gate_failures"]),
                             key=lambda x:(-x["score"],max(f["drawdown"] for f in x["folds"]),x["id"]))
            distinct=[]
            for row in hard_pass:
                current=fills[row["id"]]
                duplicate_of=next((x["id"] for x in distinct if len(current&fills[x["id"]])/
                                  max(1,len(current|fills[x["id"]]))>=spec["duplicate_trade_overlap_jaccard"]),None)
                row["duplicate_of"]=duplicate_of
                if duplicate_of is None:
                    distinct.append(row)
            # Pick each fold's parameters from the trailing 3 years only.
            adaptive={}
            for family in {r["rule"][0] for r in rows}:
                choices=[r for r in rows if r["rule"][0]==family]
                picked=[max(choices,key=lambda r:(r["folds"][i]["train_return"],-r["id"])) for i in range(len(folds))]
                adaptive[family]=[dict(rule=r["rule"],**r["folds"][i]) for i,r in enumerate(picked)]
            report["accounts"][currency]=dict(symbols=list(close.columns),excluded=excluded,
                actual_rules=len(rows),null_draws=len(maxima),null_maxima=maxima,
                hard_gate_passes=len(hard_pass),distinct_after_overlap=len(distinct),
                adaptive_walk_forward=adaptive,candidates=rows)
            print(currency,len(rows),len(hard_pass),len(distinct),"max null",max(maxima),flush=True)
            atomic_json(output,report)
    report["state"]="complete"
    atomic_json(output,report)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("scope",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    analyze(args.root,args.scope,args.plan,args.output,read(args.plan)["null"]["pilot_replicates"])
