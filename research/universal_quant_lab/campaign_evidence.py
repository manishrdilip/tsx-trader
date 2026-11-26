"""Replay deterministic audit strategies and retain their trade evidence locally."""
import argparse
from pathlib import Path
import json

import duckdb
import numba
import numpy as np

from campaign_progress import summarize
from daily_campaign import digest, inputs, sampled_ids
from daily_engine import FAMILIES, HOLDS, RULES_PER_FAMILY, WINDOWS, evaluate, space
from eodhd import atomic_json


def rules_for(candidate, groups):
    hold = HOLDS[candidate % len(HOLDS)]
    encoded = candidate // len(HOLDS)
    depth = groups.shape[1]
    family = groups[encoded // RULES_PER_FAMILY**depth]
    variants = []
    for _ in range(depth):
        variants.append(encoded % RULES_PER_FAMILY)
        encoded //= RULES_PER_FAMILY
    return hold, family, variants


def trades_for(opens, rules, start, end, holding, family, variants, cash, cost):
    trades = []
    peak = cash
    drawdown = 0.
    initial = cash
    signal = int(start)
    while signal + 1 + holding < end:
        if not all(rules[f, v, signal] for f, v in zip(family, variants)):
            signal += 1
            continue
        entry = signal + 1
        exit_bar = entry + holding
        paid = opens[entry] * (1 + cost)
        units = int(np.floor(cash / paid))
        if units < 1:
            signal += 1
            continue
        pnl = units * (opens[exit_bar] * (1 - cost) - paid)
        cash += pnl
        peak = max(peak, cash)
        drawdown = max(drawdown, (peak - cash) / peak)
        trades.append({
            "signal_index": signal, "entry_index": entry, "exit_index": exit_bar,
            "units": units, "entry_open": opens[entry], "exit_open": opens[exit_bar],
            "net_pnl": pnl, "cash_after": cash,
        })
        signal = exit_bar
    wins = sum(max(trade["net_pnl"], 0.) for trade in trades)
    losses = sum(max(-trade["net_pnl"], 0.) for trade in trades)
    return [cash - initial, drawdown, wins, losses, len(trades)], trades


def replay(root, run, count):
    summary = summarize(run)
    if not summary["completed"]:
        raise ValueError("No committed results")
    manifest = json.loads((run / "manifest.json").read_bytes())
    lab = Path(__file__).parent
    if any(digest(lab / name) != expected for name, expected in manifest["engine"].items()):
        raise ValueError("Campaign code has drifted")
    spec = manifest["spec"]
    snapshot, opens, rules, splits = inputs(root, spec)
    if snapshot != manifest["data_files"]:
        raise ValueError("Campaign dataset has drifted")
    groups, capacity = space(spec["depth"])
    offsets = np.linspace(0, summary["completed"] - 1, min(count, summary["completed"]), dtype=np.int64)
    ids = np.array([sampled_ids(int(i), 1, capacity, spec["seed"])[0] for i in offsets], dtype=np.int64)
    numba.set_num_threads(1)
    rerun = evaluate(ids, groups, opens, rules, splits, spec["cash"], spec["cost_per_side"])
    with duckdb.connect(str(run / "ledger.duckdb"), read_only=True) as ledger:
        first_ids = ledger.execute("SELECT first_id FROM batches WHERE phase='complete'").fetchall()
    files = [(run / f"batch-{first:012}.parquet").as_posix() for (first,) in first_ids]
    with duckdb.connect() as db:
        original = dict(
            (row[0], row[1:]) for row in db.execute(
                "SELECT * FROM read_parquet(?) WHERE strategy_id IN (SELECT unnest(?::BIGINT[]))",
                [files, ids.tolist()],
            ).fetchall()
        )
    families = tuple(FAMILIES)
    evidence = []
    for i, identifier in enumerate(ids.tolist()):
        np.testing.assert_array_equal(rerun[i], original[identifier])
        hold, family, variants = rules_for(identifier, groups)
        record = {"strategy_id": identifier, "hold": hold, "conditions": [], "splits": {}}
        for f, v in zip(family, variants):
            rule = families[f]
            record["conditions"].append({
                "feature": rule, "window": WINDOWS[v // 4], "threshold": FAMILIES[rule][v % 4],
                "operator": ">",
            })
        for j, label in enumerate(("train", "validation")):
            metrics, trades = trades_for(opens, rules, splits[j], splits[j + 1],
                                         hold, family, variants, spec["cash"], spec["cost_per_side"])
            np.testing.assert_allclose(metrics, rerun[i, j*5:(j+1)*5], rtol=1e-12, atol=1e-10)
            net, drawdown, wins, losses, trade_count = metrics
            record["splits"][label] = {
                "net_profit": net, "closed_drawdown": drawdown, "trades": trade_count,
                "profit_factor": wins / losses if losses else None,
                "expectancy": net / trade_count if trade_count else None,
                "trade_evidence": trades,
            }
        evidence.append(record)
    return {"mode": "engineering", "manifest_sha256": summary["manifest_sha256"],
            "execution": spec, "audit_samples": evidence}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.count <= 1000:
        parser.error("Use an audit sample between 1 and 1,000")
    root = args.root.resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / "reports"):
        parser.error("Save trade evidence under the local reports directory")
    report = replay(root, args.run, args.count)
    atomic_json(output, report)
    print("Replayed", len(report["audit_samples"]), "unique strategies with matching stored metrics")
