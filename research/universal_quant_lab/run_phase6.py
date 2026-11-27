"""Render the final report exclusively from the completed validation evidence."""
from datetime import datetime, timezone
import hashlib
import os
from uuid import uuid4

from run_universe import read


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, previous_hash, publish):
    marker = root / "phase5_done.json"
    if hashlib.sha256(marker.read_bytes()).hexdigest() != previous_hash:
        raise RuntimeError("The Phase 5 completion marker changed")
    result_path = root / "results/capped-sequence/validation.json"
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    result = read(result_path)
    phase5 = read(marker)
    if digest != phase5["counts"]["validation_sha256"]:
        raise RuntimeError("Validation results do not match Phase 5")
    if result["state"] != "complete" or result["holdout_status"] != "PASS":
        raise RuntimeError("No completed independent holdout validation")
    tested, replayed = result["candidates_tested"], result["candidates_replayed"]
    rows = result["survivors"]
    if not isinstance(tested, int) or not isinstance(replayed, int) or not 0 <= len(rows) <= replayed <= tested:
        raise RuntimeError("Inconsistent campaign counts")
    phase4 = read(root / "phase4_done.json")
    if tested != phase4["counts"]["candidates_tested"]:
        raise RuntimeError("Reported tests do not reconcile to the search ledger")
    for row in rows:
        if (row["independent_trades"] < 100 or row["profitable_tickers"] < 10
                or row["holdout_benchmark_delta"] <= 0 or not 0 <= row["corrected_p"] <= 0.05
                or row["status"] != "PASS"):
            raise RuntimeError("The validation evidence contains an ineligible survivor")

    counts = {"candidates_tested": tested, "candidates_replayed": replayed, "survivors": len(rows)}
    now = datetime.now(timezone.utc).isoformat()
    header = [
        "# Universal Quant Lab survivors", "",
        f"Completed {now}. The locked holdout was independently validated.", "",
        f"- Unique candidates tested: {tested:,}", f"- Candidates replayed on holdout: {replayed:,}",
        f"- Search space: {phase4['counts']['search_space']:,}",
        f"- Survivors: {len(rows):,}", "",
    ]
    if not rows:
        header.append("**ZERO PASSED.**")
    else:
        header.extend([
            "| Rule | Timeframe | Training net return | Validation net return | Holdout net return | Holdout drawdown | Independent trades | Profitable tickers | t-stat | Corrected p | Buy-and-hold delta |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in sorted(rows, key=lambda r: (-r["holdout_net_return"], r["holdout_drawdown"], r["id"])):
            rule = row["rule"].replace("|", "&#124;").replace("\n", " ")
            header.append(
                f"| {rule} | {row['timeframe']} | {row['train_net_return']:.2%} | "
                f"{row['validation_net_return']:.2%} | {row['holdout_net_return']:.2%} | "
                f"{row['holdout_drawdown']:.2%} | {row['independent_trades']:,} | "
                f"{row['profitable_tickers']:,} | {row['t_stat']:.4f} | "
                f"{row['corrected_p']:.4g} | {row['holdout_benchmark_delta']:+.2%} |"
            )
    publish(counts)
    marks = ("phase1_done.json", "phase2_done.json", "phase3_sealed.json",
             "phase4_done.json", "phase5_done.json")
    summary = ["# Universal Quant Lab run summary", "", f"Final report written {now}.", "",
               "| Phase | Started UTC | Finished UTC |", "|---|---|---|"]
    for index, name in enumerate(marks, 1):
        item = read(root / name)
        summary.append(f"| {index} | {item['started']} | {item['finished']} |")
    intake = read(root / "data_coverage.json")
    summary.extend(["", "Daily coverage and excluded intraday windows are recorded in data_coverage.json.",
                    f"The intake covered {intake['counts']['daily_checked']:,} daily symbols.",
                    f"Validation evidence SHA-256: {digest}", ""])
    counts["run_summary_sha256"] = write(root / "reports/RUN_SUMMARY.md", "\n".join(summary))
    counts["survivors_sha256"] = write(root / "reports/SURVIVORS.md", "\n".join(header) + "\n")
    return counts
