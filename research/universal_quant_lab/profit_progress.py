"""Reconcile local multi-job engineering runs into permitted public progress fields."""
import argparse
import json
from pathlib import Path

from campaign_progress import publish
from eodhd import atomic_json
from profit_ledger import Ledger

FIELDS = (
    "engineering_completed", "dataset_count", "failed_attempts", "compute_seconds",
    "session_wall_seconds", "compute_evaluations_per_second",
    "session_evaluations_per_second", "parquet_bytes",
)


def reconcile(run):
    manifest = json.loads((run / "manifest.json").read_bytes())
    progress = json.loads((run / "progress.json").read_bytes())
    if manifest["mode"] != "engineering" or progress["status"] != "complete":
        raise ValueError("This exporter accepts completed engineering runs")
    ledger = Ledger(run, manifest)
    try:
        ledger.reconcile()
        counts = ledger.counts()
        rows, size, seconds = ledger.db.execute("""
            SELECT sum(size),sum(bytes),sum(compute_seconds) FROM ranges WHERE state='complete'
        """).fetchone()
        if (rows, size, counts) != (
            progress["engineering_completed"], progress["parquet_bytes"], progress["completed_by_job"]
        ) or rows != manifest["target"] or abs(seconds - progress["compute_seconds"]) > .001:
            raise ValueError("Compact progress does not match the global ledger")
        return {field: progress[field] for field in FIELDS}
    finally:
        ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.summary.read_bytes())
    if report["status"] != "not_started" or report["official_completed"] != 0:
        raise SystemExit("Official reporting is outside this engineering exporter")
    items = report.setdefault("profit_first_engineering", {})
    for run in args.runs:
        # Publish allowlisted report labels instead of names supplied by a caller.
        if run.name not in {"profit-10m", "profit-cross-job-restart", "profit-actions-pilot",
                            "profit-actions-1m-final"}:
            parser.error("Use a known engineering report directory")
        items[run.name] = reconcile(run)
    atomic_json(args.summary, report)
    if args.publish:
        publish(report)
