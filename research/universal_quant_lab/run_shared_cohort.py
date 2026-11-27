"""Execute a frozen matched cohort using the standalone provisional runner."""
import argparse
import json
from pathlib import Path

import duckdb

from continuous_development import run_worker
from eodhd import atomic_json
from profit_ledger import Ledger


def read(p):
    return json.loads(p.read_bytes())


def main(root):
    plan=read(root/"config/shared-cohort-v1.json")
    folder=root/"results"/plan["cohort"]
    folder.mkdir(exist_ok=True)
    digest_path=folder/"plan.json"
    if digest_path.exists() and read(digest_path)!=plan:
        raise ValueError("Frozen cohort plan changed")
    if not digest_path.exists():
        atomic_json(digest_path,plan)
    report=dict(cohort=plan["cohort"],planned=plan["planned"],official=0,
                completed=0,instruments={},state="running")
    for i,config in enumerate(plan["batches"]):
        out=folder/f"batch-{i:02d}"
        out.mkdir(exist_ok=True)
        cfg=out/"config.json"
        if cfg.exists() and read(cfg)!=config:
            raise ValueError("Frozen cohort batch changed")
        if not cfg.exists():
            atomic_json(cfg,config)
        progress=out/"progress.json"
        if not progress.exists() or read(progress)["status"]!="complete":
            run_worker(root,cfg)
        s=read(progress)
        if s["status"]!="complete":
            report["state"]=s["status"]
            report["completed"]+=s["engineering_completed"]
            atomic_json(folder/"progress.json",report)
            return
        manifest=read(out/"manifest.json")
        ledger=Ledger(out,manifest)
        try:
            ledger.reconcile()
        finally:
            ledger.close()
        for job in manifest["jobs"]:
            paths=[p.as_posix() for p in (out/"parquet"/job["id"]).glob("*.parquet")]
            with duckdb.connect(config={"threads":1,"memory_limit":"192MB"}) as db:
                rows=db.execute("""select strategy_id,validation_net_profit,validation_mtm_drawdown,validation_trades
                    from read_parquet(?) order by validation_net_profit desc, validation_mtm_drawdown, strategy_id limit 100""",
                    [paths]).fetchall()
            series=report["instruments"].setdefault(job["symbol"],{})
            series[str(job["depth"])]=dict(completed=s["completed_by_job"][job["id"]],job=job["id"],
                 code=manifest["code"]["profit_features.py"],batch=i,top=[dict(strategy_id=x,net_profit=p,
                     drawdown_pct=100*d,trades=int(n)) for x,p,d,n in rows])
        report["completed"]+=s["engineering_completed"]
        atomic_json(folder/"progress.json",report)
    if report["completed"]!=report["planned"]:
        raise ValueError("Cohort completion count mismatch")
    report["state"]="complete"
    atomic_json(folder/"progress.json",report)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    main(parser.parse_args().root)
