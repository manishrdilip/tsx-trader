"""Reconcile engineering Parquet and ledgers into a compact publishable report."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess

import duckdb

from eodhd import atomic_json

REMOTE = "repos/manishrdilip/tsx-trader/contents/research/universal_quant_lab/BILLION_CAMPAIGN_PROGRESS.json"
BRANCH = "research/universal-quant-lab"


def summarize(directory):
    def checksum(file):
        with file.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    with duckdb.connect(str(directory / "ledger.duckdb"), read_only=True) as db:
        batches = db.execute("""
            SELECT first_id,size,checksum,bytes,elapsed FROM batches
            WHERE phase='complete' ORDER BY first_id
        """).fetchall()
        failures = db.execute("SELECT count(*) FROM failures").fetchone()[0]
    cursor = stored = 0
    elapsed = 0.
    files = []
    for first, size, expected_hash, expected_size, seconds in batches:
        file = directory / f"batch-{first:012}.parquet"
        if first != cursor or file.stat().st_size != expected_size or checksum(file) != expected_hash:
            raise ValueError("Invalid committed batch")
        files.append(file.as_posix())
        cursor += size
        stored += expected_size
        elapsed += seconds
    if files:
        with duckdb.connect() as db:
            rows, distinct = db.execute("""
                SELECT count(*), count(DISTINCT strategy_id) FROM read_parquet(?)
            """, [files]).fetchone()
        if cursor != rows or rows != distinct:
            raise ValueError("Ledger and unique result counts differ")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    return {
        "completed": cursor, "target": manifest["budget"], "threads": manifest["threads"],
        "dataset_count": 1, "distinct_strategy_ids": cursor, "failed_attempts": failures,
        "parquet_bytes": stored, "batch_seconds": round(elapsed, 3),
        "eval_per_second": round(cursor / elapsed, 1) if elapsed else None,
        "manifest_sha256": checksum(directory / "manifest.json"),
    }


def publish(report):
    latest = subprocess.run(
        ["gh", "api", f"{REMOTE}?ref={BRANCH}", "--jq", ".sha"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    payload = {
        "branch": BRANCH, "sha": latest, "message": "Update reconciled research campaign progress",
        "content": base64.b64encode((json.dumps(report, indent=2) + "\n").encode()).decode(),
    }
    result = subprocess.run(
        ["gh", "api", "-X", "PUT", REMOTE, "--input", "-"],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("GitHub did not accept the progress update")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    report = {
        "status": "not_started", "official_target": 1_000_000_000, "official_completed": 0,
        "engineering_runs": [summarize(directory) for directory in args.runs],
    }
    atomic_json(args.output, report)
    if args.publish:
        publish(report)
