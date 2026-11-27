"""Audit frozen candidate ranges and build a shared-cohort follow-up."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import duckdb

from eodhd import atomic_json
from profit_features import ADDITIONAL, FAMILIES, space


def read(path):
    return json.loads(path.read_bytes())


def normalize(ranges):
    result = []
    for start, stop in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(stop, result[-1][1])
        else:
            result.append([start, stop])
    return result


def intersect(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        if max(a,c) < min(b,d):
            result.append([max(a,c),min(b,d)])
        if b < d:
            i += 1
        else:
            j += 1
    return result


def size(ranges):
    return sum(b-a for a,b in ranges)


def audit(folder):
    groups = defaultdict(lambda: defaultdict(list))
    evidence = []
    totals = dict(committed=0, planned=0, failed_attempts=0)
    for manifest_path in sorted(folder.glob("batch-*/manifest.json")):
        batch = manifest_path.parent
        progress = read(batch/"progress.json")
        manifest = read(manifest_path)
        if manifest["mode"] != "engineering":
            raise ValueError("Provisional audit expected")
        jobs = {job["id"]:job for job in manifest["jobs"]}
        if progress["status"] == "complete":
            with duckdb.connect(str(batch/"global.duckdb"),read_only=True) as db:
                aggregate = dict(db.execute(
                    "select job,sum(size) from ranges where state='complete' group by job").fetchall())
                distribution = dict(db.execute(
                    "select job,sum(rows) from batch_distribution group by job").fetchall())
                if aggregate != distribution or aggregate != progress["completed_by_job"]:
                    raise ValueError(f"Completed ledger mismatch: {batch.name}")
        for identifier, job in jobs.items():
            count = progress["completed_by_job"].get(identifier,0)
            offset = job.get("sample_offset",0)
            if not 0 <= count <= job["quota"] or offset+job["quota"] > job["capacity"]:
                raise ValueError("Invalid candidate interval")
            # A version and common seed identify the same canonical permutation.
            domain = json.dumps([job["currency"],manifest["dates"],job["depth"],job["seed"],job["capacity"],
                                  job["half_spread_bps"],job["slippage_bps"],job["fee_per_order"],
                                  job.get("prior_turnover_fraction"),manifest["code"]["profit_features.py"],
                                  manifest["code"]["profit_engine.py"]],sort_keys=True)
            key = (job["symbol"],job["data_sha256"])
            if count:
                groups[domain][key].append([offset,offset+count])
            evidence.append(dict(batch=batch.name,state=progress["status"],symbol=job["symbol"],
                 data_sha256=job["data_sha256"],domain=domain,planned=job["quota"],
                 committed=count,range_start=offset,range_stop=offset+count))
            totals["planned"]+=job["quota"]
            totals["committed"]+=count
        totals["failed_attempts"]+=progress["failed_attempts"]
    summary=[]
    for domain, members in sorted(groups.items()):
        union=normalize([r for ranges in members.values() for r in ranges])
        common=union
        cells=[]
        for (symbol,revision),ranges in sorted(members.items()):
            merged=normalize(ranges)
            common=intersect(common,merged)
            cells.append(dict(symbol=symbol,data_sha256=revision,committed=size(ranges),unique=size(merged),
                 duplicated=size(ranges)-size(merged),missing_from_observed_union=size(union)-size(merged),
                 committed_ranges=merged))
        config=json.loads(domain)
        summary.append(dict(domain=domain,currency=config[0],depth=config[2],timeframe="1d",
            registry_families=list(FAMILIES)+list(ADDITIONAL),
            unique_in_union=size(union),shared_by_all_in_domain=size(common),instruments=cells))
    return dict(provisional=True,official=0,totals=totals,domains=summary,ranges=evidence,
        notes=["Half-open permutation index ranges encode actual configuration cells.",
               "Family follows deterministic strategy ID decoding under the pinned registry.",
               "Completed ledgers checked against their distribution tables. Active batch uses last atomic progress snapshot.",
               "Overlap counts apply within one permutation domain. Cross-seed and mathematical equivalence are outside that count."])


def follow_up(folder):
    source=read(folder/"scope.json")
    jobs={}
    for path in sorted(folder.glob("scope*.json")):
        for job in read(path)["jobs"]:
            jobs[job["symbol"]]=job
    # New depths distinguish these cells from the depth-six continuous runs.
    # The fixed seed, offset and quota are identical for every eligible instrument.
    configurations=[]
    for depth,quota in ((1,space(1)[1]),(2,1000),(3,1000)):
        keys=sorted(jobs)
        for i in range(0,len(keys),3):
            group=[dict(jobs[k],depth=depth,quota=quota,seed=732019,sample_offset=0) for k in keys[i:i+3]]
            configurations.append(dict(source, jobs=group, target=quota*len(group),batch=1000,threads=1,
                                       mode="engineering",grid=f"shared-cohort-v1-depth-{depth}"))
    return dict(cohort="shared-cohort-v1",timeframe="1d",planned=sum(s["target"] for s in configurations),
                coverage="Exhaustive depth one. Deterministic sampled depth two and three. Other families and timeframes remain pending.",
                jobs=sorted(jobs),batches=configurations)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("root",type=Path)
    args=p.parse_args()
    r=args.root
    folder=r/"results/continuous-development-v1"
    report=audit(folder)
    atomic_json(r/"reports/portfolio-coverage-matrix.json",report)
    plan=follow_up(folder)
    atomic_json(r/"config/shared-cohort-v1.json",plan)
    print(report["totals"])
    for d in report["domains"]:
        print(d["currency"],len(d["instruments"]),"union",d["unique_in_union"],"all",d["shared_by_all_in_domain"],
              "overlap",sum(x["duplicated"] for x in d["instruments"]))
    print("Follow-up",plan["planned"],len(plan["jobs"]),"instruments")
