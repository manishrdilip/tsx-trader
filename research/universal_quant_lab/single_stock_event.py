"""Small pre-registered single-instrument event screen."""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
from pathlib import Path

import duckdb
import numpy as np

from eodhd import atomic_json
from portfolio_discovery import CAPITAL
from portfolio_robustness import (account_inputs, backtest, check,
    compound, extract_trades, fold_starts, read)


def signals(bars, close, threshold, direction):
    opening, last = bars[:,0,0], bars[:,0,2]
    # Infer an event-day closing recovery without using an intraday path.
    scaled=close.iloc[:,0].to_numpy()
    prev=np.r_[np.nan,scaled[:-1]]
    gap=np.divide(opening*scaled,last*prev)
    # The parent loader stores open, low and close but omits the high.
    # Define follow-through with observable open-to-close direction.
    return (direction*(gap-1)>=threshold) & (last>opening)


def candidate_masks(cfg, bars, close, benchmark):
    family=cfg.get("family","gap")
    price=close.iloc[:,0]
    prior_valid=price.rolling(20).count().shift().eq(20).to_numpy()
    if family=="gap":
        for direction,threshold,hold in itertools.product((1,-1),cfg["gap_abs_thresholds"],cfg["holding_sessions"]):
            key="up_gap_followthrough" if direction==1 else "down_gap_reversal"
            yield key,threshold,hold,(signals(bars,close,threshold,direction)&prior_valid)[:,None]
        return
    current_return=price.pct_change(fill_method=None)
    for threshold,hold in itertools.product(cfg["thresholds"],cfg["holding_sessions"]):
        if family=="relative_strength":
            # Both changes come from the same completed session.
            market_return=benchmark.pct_change(fill_method=None)
            condition=(market_return<0)&(current_return-market_return>=threshold)
        elif family=="failed_breakdown":
            # Convert the current bar low to the same split-consistent scale as prior closes.
            low=price * (bars[:,0,1]/bars[:,0,2])
            support=price.shift().rolling(20).min()
            condition=(low<=support*(1-threshold))&(price>support)&(current_return>0)
        elif family=="market_rebound":
            market_return=benchmark.pct_change(fill_method=None)
            condition=(market_return.shift()<=-threshold)&(market_return>0)&(current_return>0)
        elif family=="trend_pullback":
            trend=price.shift().rolling(200).mean()
            recent_return=price.pct_change(5,fill_method=None)
            condition=(price>trend)&(recent_return<=-threshold)&(current_return>0)
        elif family=="contraction_breakout":
            prior_vol=current_return.shift().rolling(10).std()
            baseline_vol=current_return.shift().rolling(60).std()
            condition=(prior_vol<baseline_vol*threshold)&(price>price.shift().rolling(20).max())
        else:
            raise ValueError("Unknown event family")
        yield family,threshold,hold,(condition.to_numpy(dtype=bool)&prior_valid)[:,None]


def run(root, scope_file, plan_file, output):
    cfg=read(plan_file)
    plan=read(plan_file.with_name(cfg["parent_plan"]))
    scope=read(scope_file)
    if cfg["cutoff_exclusive"]!=plan["evaluation_cutoff_exclusive"]:
        raise ValueError("Research cutoff changed")
    check(root)
    report=dict(state="running",plan_sha256=hashlib.sha256(plan_file.read_bytes()).hexdigest(),
                source_scope_sha256=hashlib.sha256(scope_file.read_bytes()).hexdigest(),
                code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                cutoff_exclusive=cfg["cutoff_exclusive"],official=0,holdout_accessed=False,
                instruments={},excluded=scope.get("excluded",{}),evaluations=0,hard_gate_passes=0)
    report["dependencies"]={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
         for name in ("portfolio_discovery.py","portfolio_robustness.py")}
    report["dependencies"]["parent_plan"]=hashlib.sha256(plan_file.with_name(cfg["parent_plan"]).read_bytes()).hexdigest()
    if output.exists() and cfg.get("resume",False):
        saved=read(output)
        for key in ("plan_sha256","source_scope_sha256","code_sha256","dependencies"):
            if saved[key]!=report[key]:
                raise ValueError(f"Checkpoint fingerprint changed: {key}")
        if saved["state"]=="complete":
            return
        report=saved
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True,
                        config={"threads":1,"memory_limit":"192MB"}) as db:
        inputs={currency:account_inputs(root,db,scope,currency,plan)
                for currency in sorted({job["currency"] for job in scope["jobs"]})}
    for currency,(calendar,all_bars,all_close,all_mapping,slots,excluded) in inputs.items():
        report["excluded"].update(excluded)
        folds=fold_starts(calendar,plan)
        priority=np.zeros((len(calendar),1),dtype=np.int64)
        false=np.zeros(priority.shape,dtype=bool)
        for i,symbol in enumerate(all_close.columns):
            if ("targets" in cfg and symbol not in cfg["targets"]) or symbol in report["instruments"]:
                continue
            check(root)
            bars=np.ascontiguousarray(all_bars[:,i:i+1])
            mapping=np.ascontiguousarray(all_mapping[:,i:i+1])
            close=all_close.iloc[:,i:i+1]
            sma=close.rolling(200).mean()
            above=(close>sma).to_numpy()
            below=(close<sma).to_numpy()
            passive=close.notna().to_numpy()
            benchmark=all_close["XIU.TO" if currency=="CAD" else "SPY.US"]
            benchmarks={}
            for year,_,new,end in folds:
                if close.iloc[new:end,0].notna().sum()<100 or not passive[new-1,0]:
                    continue
                bh,*_=backtest(bars,mapping,slots,passive,false,10000,new,end,priority,position_count=1)
                trend,*_=backtest(bars,mapping,slots,above,below,10000,new,end,priority,position_count=1)
                benchmarks[year]=(bh,trend)
            rows=[]
            if not benchmarks:
                report["excluded"][symbol]="No comparable fold with 100 sessions and an eligible opening position"
                continue
            for pattern,threshold,hold,mask in candidate_masks(cfg,bars,close,benchmark):
                outcomes=[]; history=[]
                for year,_,new,end in folds:
                    if year not in benchmarks:
                        continue
                    ret,risk,trades,fills=backtest(bars,mapping,slots,mask,false,hold,new,end,priority,True,
                                                   position_count=1)
                    pnl,_=extract_trades(bars,fills,new)
                    if len(pnl)!=trades or not np.isclose(sum(pnl),ret*CAPITAL,atol=1e-6):
                        raise ValueError("Trade trace does not reconcile")
                    outcomes.extend(pnl)
                    bh,trend=benchmarks[year]
                    history.append(dict(year=year,net_return=ret,drawdown=risk,closed_trades=int(trades),
                         passive_return=bh,sma200_return=trend,positive_trades=int(sum(x>0 for x in pnl))))
                ret=compound([x["net_return"] for x in history])
                cut=int(np.ceil(len(outcomes)*plan["gates"]["remove_top_fraction"]))
                trim=float(sum(sorted(outcomes)[:len(outcomes)-cut]))
                failures=[]
                if len(outcomes)<plan["gates"]["min_closed_test_trades"]: failures.append("trade_count")
                if trim<=0: failures.append("trimmed_profit")
                if ret<=max(compound([x["passive_return"] for x in history]),
                            compound([x["sma200_return"] for x in history])): failures.append("benchmarks")
                if max(x["drawdown"] for x in history)>plan["gates"]["max_fold_drawdown"]: failures.append("drawdown")
                if np.mean([x["net_return"]>0 for x in history])<=plan["gates"]["min_positive_fold_fraction_exclusive"]:
                    failures.append("fold_consistency")
                rows.append(dict(direction=pattern,
                     threshold=threshold,hold=hold,return_after_cost=ret,closed_trades=len(outcomes),
                     wins=int(sum(x>0 for x in outcomes)),trimmed_profit=trim,hard_gate_failures=failures,folds=history))
            report["instruments"][symbol]=dict(currency=currency,results=rows)
            report["evaluations"]+=len(rows)
            report["hard_gate_passes"]+=sum(not rule["hard_gate_failures"] for rule in rows)
            atomic_json(output,report)
    report.update(state="complete",completed_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(output,report)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("root","scope","plan","output"):
        p.add_argument(arg,type=Path)
    a=p.parse_args()
    run(a.root,a.scope,a.plan,a.output)
