"""Stress frozen development candidates without querying the final holdout."""
import argparse
import json
from pathlib import Path

import numpy as np

from campaign_evidence import rules_for
from eodhd import atomic_json
from profit_campaign import load
from profit_engine import METRICS, simulate
from profit_features import space


def stress(root, manifest, rankings):
    if manifest["mode"] != "engineering" or rankings["mode"] != "engineering":
        raise ValueError("Expected development engineering artifacts")
    wanted = {}
    for scope in rankings["scopes"]:
        for band in scope["risk_bands"].values():
            for candidate in band["overall"][:1]:
                wanted[candidate["job_id"], candidate["strategy_id"]] = candidate
    result = []
    for job in manifest["jobs"]:
        ids = [candidate for (job_id, candidate) in wanted if job_id == job["id"]]
        if not ids:
            continue
        hashes, prices, signals, splits, actions = load(root, job, manifest["dates"])
        if hashes != job["development_hashes"]:
            raise ValueError("Development data drift")
        groups, _ = space(job["depth"])
        friction = (job["half_spread_bps"] + job["slippage_bps"]) / 10000
        fee = job["fee_per_order"]
        start, end = splits[1:]
        intervals = np.linspace(start, end, 4, dtype=np.int64)
        for identifier in sorted(ids):
            hold, families, variants = rules_for(identifier, groups)
            variants = np.array(variants, dtype=np.int64)

            def replay(first, last, cost_multiple):
                outcome = simulate(prices, signals, families, variants, first, last, hold, 5000.,
                                   cost_multiple * friction, cost_multiple * fee, *actions)
                return dict(zip(METRICS, outcome))

            base = replay(start, end, 1.)
            np.testing.assert_allclose(base["net_profit"],
                                       wanted[job["id"], identifier]["net_profit"], atol=1.e-10)
            result.append({"job_id": job["id"], "strategy_id": identifier, "base": base,
                           "1.5x_cost": replay(start, end, 1.5), "2x_cost": replay(start, end, 2.),
                           "chronological_validation_slices": [
                               replay(a, b, 1.) for a, b in zip(intervals[:-1], intervals[1:])
                           ]})
    return {"mode": "engineering", "validation_end_exclusive": manifest["dates"][2],
            "selection": "fixed first ranked candidate per development risk band",
            "evaluation": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("rankings", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_bytes())
    rankings = json.loads(args.rankings.read_bytes())
    report = stress(args.root, manifest, rankings)
    atomic_json(args.output, report)
    print("Replayed and cost-stressed", len(report["evaluation"]), "fixed development candidates")
