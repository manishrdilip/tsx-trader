"""Produce cash and passive comparators on the same local dates and execution model."""
import argparse
import json
from pathlib import Path

import numpy as np

from eodhd import atomic_json
from profit_campaign import load
from profit_engine import METRICS, simulate


def compare(root, config):
    comparisons = []
    for job in config["jobs"]:
        if not job.get("action_snapshot_sha256"):
            raise ValueError("Passive comparison requires a pinned action snapshot")
        _, prices, _, splits, actions = load(root, job, config["dates"])
        signals = np.ones((1, 1, len(prices)), dtype=np.bool_)
        selector = np.array([0], dtype=np.int64)
        friction = (job["half_spread_bps"] + job["slippage_bps"]) / 10000
        for i, split in enumerate(("train", "validation")):
            start, end = splits[i:i+2]
            metrics = simulate(prices, signals, selector, selector, start, end, end-start-2,
                               5000., friction, job["fee_per_order"], *actions)
            comparisons.append({"symbol": job["symbol"], "currency": job["currency"], "split": split,
                                "start": config["dates"][i], "end_exclusive": config["dates"][i+1],
                                "cash_net_profit": 0, "passive": dict(zip(METRICS, metrics)),
                                "vmm": None, "vmm_profit_multiple": None})
    return {"mode": "engineering", "passive_model": "first next-open entry, last open exit",
            "comparators": comparisons}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = compare(args.root, json.loads(args.config.read_bytes()))
    atomic_json(args.output, result)
    print("Verified", len(result["comparators"]), "split-level cash/passive comparisons")
