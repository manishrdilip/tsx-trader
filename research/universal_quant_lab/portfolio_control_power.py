"""Repeat a preregistered planted-edge ladder under the original hard checks."""
import argparse
import hashlib
from pathlib import Path

import duckdb
import numpy as np

from eodhd import atomic_json
from portfolio_positive_controls import plant
from portfolio_robustness import account_inputs, fold_starts, read, search, synthetic


def run(root, scope_file, plan_file, output):
    cfg=read(plan_file)
    parent=plan_file.with_name(cfg["parent_plan"])
    plan=read(parent)
    scope=read(scope_file)
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True,
                        config={"threads":1,"memory_limit":"192MB"}) as db:
        calendar,bars,close,_,_,excluded=account_inputs(root,db,scope,cfg["currency"],plan)
    folds=fold_starts(calendar,plan)
    fingerprint={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        plan_file,parent,scope_file,Path(__file__),Path(__file__).with_name("portfolio_positive_controls.py"),
        Path(__file__).with_name("portfolio_robustness.py"),Path(__file__).with_name("portfolio_discovery.py"))}
    report=read(output) if output.exists() else dict(state="running",hashes=fingerprint,
                symbols=list(close.columns),excluded=excluded,scenarios=[],holdout_accessed=False,official=0)
    if report["hashes"]!=fingerprint:
        raise ValueError("Preregistered inputs changed")
    completed={(x["seed"],x["edge"]) for x in report["scenarios"]}
    for seed in cfg["seeds"]:
        rng=np.random.default_rng(seed)
        sample,path,dates=synthetic(bars,close,rng)
        marker,active=plant(path,rng,True)
        controls=[(("synthetic event marker",0,0,hold),marker) for hold in cfg["marker_holds"]]
        for edge in cfg["injected_returns"]:
            if (seed,edge) in completed:
                continue
            factors=np.exp(np.cumsum(active*np.log1p(edge)/10,axis=0))
            prices=sample.copy()
            prices[:,:,:3]*=factors[:,:,None]
            rows,_=search(root,prices,path*factors,dates,1,folds,plan,True,controls)
            order=sorted(rows,key=lambda row:(-row["score"],row["id"]))
            primary=next(row for row in rows if row["rule"][0]=="synthetic event marker"
                         and row["rule"][3]==cfg["primary_hold"])
            report["scenarios"].append(dict(seed=seed,edge=edge,primary=primary,
                rank=order.index(primary)+1,candidates=len(rows)))
            atomic_json(output,report)
        print("Seed",seed,"finished",flush=True)
    report["state"]="complete"
    atomic_json(output,report)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("scope",type=Path)
    p.add_argument("plan",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    run(a.root,a.scope,a.plan,a.output)
