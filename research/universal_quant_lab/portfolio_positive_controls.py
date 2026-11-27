"""Compare the research-only VMM signal reconstruction and known synthetic signals."""
import argparse
import hashlib
from pathlib import Path

import duckdb
import numpy as np

from eodhd import atomic_json
from portfolio_discovery import CAPITAL, simulate
from portfolio_robustness import (account_inputs, benchmark_folds, evaluate_rule,
    fold_starts, read, search, synthetic)


def vmm_proxy(bars,close,mapping,slots,folds,plan):
    if "XIU.TO" not in close:
        raise ValueError("XIU is required for the VMM market filter")
    sma=close.rolling(200).mean()
    roc=close.pct_change(252,fill_method=None)
    # Existing whole-share model stores prior 20-session minimum dollar turnover.
    eligible=roc.notna() & (bars[:,:,2]>=1) & (bars[:,:,2]<=100) & (bars[:,:,5]>=300000)
    eligible["XIU.TO"]=False
    selected=roc.where(eligible)
    momentum=(selected.ge(selected.quantile(.9,axis=1),axis=0) & (close>sma))
    entry=momentum.mul(close["XIU.TO"]>sma["XIU.TO"],axis=0)
    exit_=(close<sma) | roc.lt(selected.quantile(.6,axis=1),axis=0)
    priority=np.argsort(-selected.fillna(-np.inf).to_numpy(),axis=1,kind="stable")
    cmp=benchmark_folds(bars,close,mapping,slots,folds,plan,np.tile(np.arange(close.shape[1]),(len(close),1)))
    outcome,_=evaluate_rule(bars,mapping,slots,folds,plan,("VMM signal reconstruction",0,0,10000),
                         entry.to_numpy(),exit_.to_numpy(),priority,cmp)
    matched=[]
    for fold,(_,_,start,end) in zip(outcome["folds"],folds):
        _,_,_,_,curve,_=simulate(bars,mapping,slots,entry.to_numpy(),exit_.to_numpy(),10000,
                                 start,end,5,priority)
        change=curve/np.r_[CAPITAL,curve[:-1]]-1
        if not np.isclose(np.prod(1+change)-1,fold["net_return"]):
            raise ValueError("Daily benchmark returns and fold result disagree")
        matched.extend(dict(date=date,net_return=float(ret),equity=float(equity)) for date,ret,equity in
                       zip(close.index[start:end],change,curve))
    return outcome,matched


def plant(close,rng,sparse):
    flag=np.zeros(close.shape,dtype=bool)
    if sparse:
        available=close.notna().to_numpy()
        ready=np.zeros(close.shape[1],dtype=int)
        for day in range(25,len(close)-12,4):
            pool=np.flatnonzero(available[day] & (ready<=day))
            if len(pool):
                ticker=int(rng.choice(pool))
                flag[day,ticker]=True
                ready[ticker]=day+24
    else:
        for t in range(close.shape[1]):
            start=np.flatnonzero(close.iloc[:,t].notna().to_numpy())[0]
            # An observable synthetic event, chosen before applying any future returns.
            flag[start+25+int(rng.integers(24)):-12:24,t]=True
    # Spread each event's shock over the ten closes reached after next-open entry.
    active=np.zeros(flag.shape)
    for lag in range(2,12):
        active[lag:]+=flag[:-lag]
    return flag,active


def controls(root,scope_path,plan_path,output,sparse=False):
    plan=read(plan_path)
    scope=read(scope_path)
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True,
                        config={"threads":1,"memory_limit":"192MB"}) as db:
        calendar,bars,close,mapping,slots,excluded=account_inputs(root,db,scope,"CAD",plan)
    folds=fold_starts(calendar,plan)
    vmm,matched=vmm_proxy(bars,close,mapping,slots,folds,plan)
    report=dict(state="running",vmm=vmm,currency="CAD",symbols=list(close.columns),excluded=excluded,
                plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                scope_sha256=hashlib.sha256(scope_path.read_bytes()).hexdigest(),
                vmm_limitations="VMM top-decile, 200-day and XIU entry filters with top-40% and SMA exits. Shared five-slot research fills with conservative volume proxy. Live-specific trailing/rebuy, allocations, guard, routing and actual account returns are unavailable in this reconstruction.",
                injection_layout='one cross-sectional event per four sessions' if sparse else 'frequent per-symbol events',
                injections=[])
    benchmark=output.with_name(output.stem+"-vmm-daily.json")
    atomic_json(benchmark,dict(source="VMM signal reconstruction",currency="CAD",fold_capital=CAPITAL,
                 scope_sha256=report["scope_sha256"],plan_sha256=report["plan_sha256"],returns=matched))
    report["vmm_daily_sha256"]=hashlib.sha256(benchmark.read_bytes()).hexdigest()
    atomic_json(output,report)
    print("VMM reconstruction:",vmm["score"],vmm["trades"],vmm["hard_gate_failures"],flush=True)
    rng=np.random.default_rng(17653)
    sample,path,dates=synthetic(bars,close,rng)
    marker,active=plant(path,rng,sparse)
    controls=[(("synthetic event marker",0,0,hold),marker) for hold in (8,10,12)]
    for rate in (0.,.005,.04):
        factor=np.exp(np.cumsum(active*np.log1p(rate)/10,axis=0))
        raised=sample.copy()
        raised[:,:,:3]*=factor[:,:,None]
        rows,_=search(root,raised,path*factor,dates,1,folds,plan,True,controls)
        ordered=sorted(rows,key=lambda row:(-row["score"],row["id"]))
        markers=[dict(row,unfiltered_rank=ordered.index(row)+1) for row in ordered if row["rule"][0]=="synthetic event marker"]
        entry=dict(planted_return=rate,search_size=len(rows),markers=markers,
                   screen_passes=sum(not row["hard_gate_failures"] for row in rows))
        report["injections"].append(entry)
        atomic_json(output,report)
        print(rate,[(x["rule"][3],x["unfiltered_rank"],round(x["score"],4),x["hard_gate_failures"]) for x in markers],flush=True)
    report["state"]="complete"
    atomic_json(output,report)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("scope",type=Path)
    p.add_argument("plan",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--sparse",action="store_true")
    args=p.parse_args()
    controls(args.root,args.scope,args.plan,args.output,args.sparse)
