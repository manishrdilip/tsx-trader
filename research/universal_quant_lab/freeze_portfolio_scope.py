"""Freeze the longest usable contiguous audited history per stock."""
import argparse
import json
from pathlib import Path

import duckdb
import exchange_calendars as xc
import pandas as pd

from eodhd import atomic_json
from portfolio_discovery import load_equity


def freeze(root, plan, audits):
    start, end = plan["start"], plan["end_exclusive"]
    sessions = {currency: pd.Index(xc.get_calendar(venue,start=start,end=end).sessions.strftime("%Y-%m-%d"))
                for currency,venue in (("CAD","XTSE"),("USD","XNYS"))}
    revisions = {a["symbol"]:a for a in audits}
    eligible = []
    rejected = dict(plan["excluded"])
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True) as db:
        for j in plan["jobs"]:
            symbol = j["symbol"]
            audit = revisions[symbol]
            if any(value["status"]!=200 for value in audit["actions"].values()):
                rejected[symbol] = "Corporate-action service incomplete"
                continue
            job=dict(j,action_snapshot_sha256=audit["action_snapshot_sha256"])
            glob=db.execute("select parquet_glob from datasets where sha256=?",[job["data_sha256"]]).fetchone()[0]
            observed=pd.Index([x[0] for x in db.execute(
                "select session from read_parquet(?) where session>=? and session<? order by session",
                [glob,start,end]).fetchall()])
            if observed.empty:
                rejected[symbol]="No bars in window"
                continue
            calendar=sessions[job["currency"]]
            calendar=calendar[calendar<end]
            expected=calendar[calendar>=observed[0]]
            breaks=sorted(set(expected.symmetric_difference(observed))|set(audit["unexplained_factor_moves"]))
            earliest=max(start,observed[0])
            if breaks:
                remaining=calendar[calendar>breaks[-1]]
                if len(remaining)==0:
                    rejected[symbol]="Unresolved calendar or action discrepancy at end of window"
                    continue
                earliest=max(earliest,remaining[0])
            reason="Unusable corporate-action execution history"
            for cutoff in [earliest]+[f"{year}-01-01" for year in range(int(earliest[:4])+1,int(end[:4]))]:
                try:
                    load_equity(root,db,job,cutoff,end,calendar)
                except ValueError as error:
                    reason=str(error)
                    continue
                eligible.append(dict(job,eligible_from=cutoff))
                break
            else:
                rejected[symbol]=reason
    return dict(plan,jobs=eligible,excluded=rejected,
                selection_note="Latest contiguous usable segment after calendar/action gaps. Later listings enter after signal warm-up. Survivorship and coverage bias remain.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    r=args.root
    result=freeze(r,json.loads((r/"config/portfolio-deep-audit.json").read_bytes()),
                  json.loads((r/"reports/portfolio-deep-actions.json").read_bytes()))
    atomic_json(args.output,result)
    print(len(result["jobs"]),"admitted",len(result["excluded"]),"excluded")
    print([(job["symbol"],job["eligible_from"]) for job in result["jobs"]])
