"""Freeze a development universe using revision-specific local audit evidence."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

from profit_campaign import load


def freeze(root):
    read = lambda name: json.loads((root / name).read_bytes())
    config = read("config/profit-actions-pilot.json")
    calendars = read("reports/eodhd-daily-audit-profit-first.json")["datasets"]
    actions = read("reports/profit-corporate-actions-v2.json")
    baseline = read("reports/profit-actions-baselines.json")
    eligible = []
    for job in config["jobs"]:
        match = next(x for x in calendars if x["sha256"] == job["data_sha256"] and x["symbol"] == job["symbol"])
        snapshot = next(x for x in actions if x["action_snapshot_sha256"] == job["action_snapshot_sha256"])
        start, _, end = config["dates"]
        if not match["calendar"] or match["window_start"] > start or match["window_end"] < end:
            raise ValueError("Calendar audit lacks coverage")
        issues = match["missing_sessions"] + match["extra_sessions"]
        if any(start <= day < end for day in issues) or snapshot["unexplained_factor_moves"]:
            raise ValueError("Unreconciled development sessions or corporate actions")
        hashes, _, _, splits, events = load(root, job, config["dates"])
        assert all(int(n) > 0 for n in (splits[1]-splits[0], splits[2]-splits[1]))
        comparators = [x for x in baseline["comparators"] if x["symbol"] == job["symbol"] and x["currency"] == job["currency"]]
        assert {x["split"] for x in comparators} == {"train", "validation"}
        eligible.append({key:job[key] for key in ("symbol","market","currency","data_sha256","action_snapshot_sha256")})
    return {"dates":config["dates"], "development_universe":eligible,
            "benchmark":"Same-instrument cash and passive next-open entry, last-open exit, same capital and costs",
            "benchmark_artifact_sha256":hashlib.sha256((root/"reports/profit-actions-baselines.json").read_bytes()).hexdigest(),
            "holdout_protocol":"Use only observations after the later of this preregistration and the final timestamped shortlist freeze. Exclude all previously acquired observations. Collect and seal before one-time independent validation.",
            "holdout_dataset_status":"prospective; observations pending",
            "execution_cost_status":"engineering sensitivity only; historical executable spreads and slippage unverified"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = freeze(args.root)
    payload = json.dumps(result, indent=2) + "\n"
    if args.output.exists() and json.loads(args.output.read_bytes()) != result:
        raise SystemExit("Existing freeze differs")
    if not args.output.exists():
        with args.output.open("x",encoding="utf-8") as f:
            f.write(payload)
    print([j["symbol"] for j in result["development_universe"]])
