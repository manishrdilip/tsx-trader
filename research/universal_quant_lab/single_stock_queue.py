"""Run the fixed research queue and preserve per-instrument checkpoints."""
import argparse
import hashlib
from pathlib import Path
import time

from daily_campaign import exclusive
from eodhd import atomic_json
from portfolio_robustness import read
from single_stock_event import run


def execute(root, plan_file, scope, name):
    plan=read(plan_file)
    folder=root/"results"/name
    if folder.parent!=(root/"results") or not name.startswith("single-stock-"):
        raise ValueError("Expected a dedicated single-stock results folder")
    folder.mkdir(exist_ok=True)
    status=folder/"progress.json"
    with exclusive(folder/"runner.lock"):
        frozen=folder/"queue.json"
        if frozen.exists() and read(frozen)!=plan:
            raise ValueError("Frozen queue changed")
        if not frozen.exists():
            atomic_json(frozen,plan)
        for idea in plan["queue"]:
            name=idea["family"]
            config=folder/f"{name}-plan.json"
            # The inherited validation plan resolves relative to each phase plan.
            parent=plan_file.with_name(plan["parent_plan"])
            local_parent=folder/parent.name
            if local_parent.exists() and local_parent.read_bytes()!=parent.read_bytes():
                raise ValueError("Inherited plan changed")
            if not local_parent.exists():
                local_parent.write_bytes(parent.read_bytes())
            spec={**{k:v for k,v in plan.items() if k!="queue"},**idea}
            if config.exists() and read(config)!=spec:
                raise ValueError("Frozen phase changed")
            if not config.exists():
                atomic_json(config,spec)
            target=folder/f"{name}.json"
            while True:
                if (folder/"PAUSE").exists():
                    atomic_json(status,dict(state="operator_paused",phase=name,official=0))
                    return
                atomic_json(status,dict(state="running",phase=name,official=0))
                try:
                    run(root,scope,config,target)
                    break
                except RuntimeError as error:
                    if not str(error).startswith("Laptop resource guard paused research"):
                        raise
                    atomic_json(status,dict(state="resource_paused",phase=name,official=0,reason=str(error)))
                    time.sleep(30)
            print(name,read(target)["evaluations"],flush=True)
        results=[read(folder/f'{x["family"]}.json') for x in plan["queue"]]
        atomic_json(status,dict(state="complete",evaluations=sum(x["evaluations"] for x in results),
            hard_gate_passes=sum(x["hard_gate_passes"] for x in results),official=0,holdout_accessed=False,
            queue_sha256=hashlib.sha256(plan_file.read_bytes()).hexdigest()))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    p.add_argument("plan",type=Path)
    p.add_argument("--scope",type=Path)
    p.add_argument("--name",default="single-stock-followup-v1")
    args=p.parse_args()
    execute(args.root,args.plan,args.scope or args.root/"config/portfolio-discovery-v2.json",args.name)
