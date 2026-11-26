"""Run restartable local daily engineering campaigns against the lab warehouse."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import math
import msvcrt
import os
from pathlib import Path
import shutil
import time

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import numba

from daily_engine import evaluate, feature_rules, space
from eodhd import atomic_json

RESERVE = 150 * 1024**3
MILESTONES = (10_000, 100_000, 1_000_000)
METRICS = ("net", "closed_drawdown", "gross_wins", "gross_losses", "trades")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


@contextmanager
def exclusive(path):
    with path.open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def inputs(root, spec):
    catalog = root / "database/warehouse/catalog.duckdb"
    with duckdb.connect(str(catalog), read_only=True) as db:
        rows = db.execute("""
            SELECT parquet_glob FROM datasets
            WHERE source = ? AND market = ? AND symbol = ? AND bar_interval = '1d' AND sha256 = ?
        """, [spec[key] for key in ("source", "market", "symbol", "data_sha256")]).fetchall()
        if len(rows) != 1:
            raise ValueError("Select one immutable daily dataset revision")
        pattern = rows[0][0]
        files = sorted(Path(pattern).parent.parent.glob("year=*/bars.parquet"))
        if not files:
            raise ValueError("Dataset files missing")
        snapshot = {file.parent.name: digest(file) for file in files}
        bars = db.execute("""
            SELECT session, open, high, low, close
            FROM read_parquet(?) WHERE session < ? ORDER BY session
        """, [pattern, spec["holdout_start"]]).df()
    if {file.parent.name: digest(file) for file in files} != snapshot:
        raise ValueError("Dataset changed while loading")
    dates = pd.Index(bars.session)
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Invalid session ordering")
    boundaries = [spec[key] for key in ("train_start", "validation_start", "holdout_start")]
    if sorted(set(boundaries)) != boundaries or any(date.fromisoformat(x).isoformat() != x for x in boundaries):
        raise ValueError("Expected three increasing ISO dates")
    splits = np.array([dates.searchsorted(day) for day in boundaries], dtype=np.int64)
    if min(np.diff(splits)) < 100:
        raise ValueError("Each development split needs at least 100 bars")
    return snapshot, np.ascontiguousarray(bars.open, dtype=np.float64), feature_rules(bars), splits


def sampled_ids(start, count, capacity, seed):
    step = 65537
    while math.gcd(step, capacity) != 1:
        step += 2
    if start < 0 or start + count > capacity:
        raise ValueError("Search budget exceeds canonical space")
    shift = seed % capacity
    return (np.arange(start, start + count, dtype=np.int64) * step + shift) % capacity


def write_results(path, ids, values):
    if not np.isfinite(values).all() or len(np.unique(ids)) != len(ids):
        raise ValueError("Batch contains invalid or duplicate results")
    columns = {"strategy_id": ids}
    for split, label in enumerate(("train", "validation")):
        for i, metric in enumerate(METRICS):
            col = values[:, split * len(METRICS) + i]
            columns[f"{label}_{metric}"] = col.astype(np.int32) if metric == "trades" else col
    temp = path.with_suffix(".tmp")
    try:
        pq.write_table(pa.table(columns), temp, compression="zstd")
        with temp.open("r+b") as handle:
            os.fsync(handle.fileno())
        checksum = digest(temp)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return checksum


def run(root, spec_file, out, budget, batch, threads):
    if budget not in MILESTONES or not 1 <= batch <= 100_000:
        raise ValueError("Use a registered engineering milestone and a bounded batch size")
    out.mkdir(parents=True, exist_ok=True)
    with exclusive(out / "runner.lock"):
        execute(root, spec_file, out, budget, batch, threads)


def execute(root, spec_file, out, budget, batch, threads):
    spec = json.loads(spec_file.read_bytes())
    if not math.isfinite(spec["cash"]) or spec["cash"] <= 0 or not 0 <= spec["cost_per_side"] < 1:
        raise ValueError("Invalid cash or execution cost")
    groups, capacity = space(spec["depth"])
    sampled_ids(0, budget, capacity, spec["seed"])
    code = Path(__file__).parent
    fingerprint = {name: digest(code / name) for name in (
        "daily_campaign.py", "daily_engine.py", "features.py",
    )}
    snapshot, opens, rules, splits = inputs(root, spec)
    manifest = {
        "engine": fingerprint, "data_files": snapshot, "spec": spec, "budget": budget,
        "batch": batch, "threads": threads, "mode": "engineering", "official_count": 0,
        "versions": {"numba": numba.__version__, "numpy": np.__version__,
                     "pandas": pd.__version__, "pyarrow": pa.__version__, "duckdb": duckdb.__version__},
    }
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_bytes()) != manifest:
            raise ValueError("Manifest drift. Use a new run directory")
    else:
        atomic_json(manifest_path, manifest)
    numba.set_num_threads(threads)
    evaluate(np.array([0], dtype=np.int64), groups, opens, rules, splits, spec["cash"], spec["cost_per_side"])
    with duckdb.connect(str(out / "ledger.duckdb")) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                first_id BIGINT PRIMARY KEY, size INTEGER, phase VARCHAR, checksum VARCHAR,
                bytes BIGINT, elapsed DOUBLE
            )
        """)
        cursor = 0
        prior = db.execute(
            "SELECT first_id,size,phase,checksum,bytes,elapsed FROM batches ORDER BY first_id"
        ).fetchall()
        storage = 0
        elapsed = 0.
        for first, size, phase, checksum, stored_bytes, seconds in prior:
            if first != cursor or size != min(batch, budget - cursor):
                raise ValueError("Noncontiguous or invalid checkpoint range")
            if phase == "leased":
                if first != prior[-1][0]:
                    raise ValueError("Outstanding lease is not at the checkpoint tail")
                break
            path = out / f"batch-{first:012}.parquet"
            if (phase != "complete" or digest(path) != checksum or path.stat().st_size != stored_bytes
                    or pq.ParquetFile(path).metadata.num_rows != size):
                raise ValueError("Completed checkpoint verification failed")
            cursor += size
            storage += stored_bytes
            elapsed += seconds

        def progress(state):
            atomic_json(out / "progress.json", {
                "status": state, "engineering_completed": cursor, "engineering_target": budget,
                "official_completed": 0, "official_target": 1_000_000_000,
                "distinct_strategies": cursor, "dataset_count": 1,
                "failed_attempts": db.execute("SELECT count(*) FROM failures").fetchone()[0],
                "parquet_bytes": storage, "batch_seconds": round(elapsed, 3),
                "evaluations_per_second": round(cursor / elapsed, 2) if elapsed else None,
                "free_gib": round(shutil.disk_usage(root).free / 1024**3, 2),
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            })

        db.execute("CREATE TABLE IF NOT EXISTS failures (first_id BIGINT, kind VARCHAR, occurred TIMESTAMP)")
        while cursor < budget:
            if (out / "PAUSE").exists() or shutil.disk_usage(root).free < RESERVE + 256 * 1024**2:
                progress("paused")
                return
            count = min(batch, budget - cursor)
            db.execute("INSERT OR IGNORE INTO batches VALUES (?, ?, 'leased', NULL, NULL, NULL)", [cursor, count])
            started = time.perf_counter()
            try:
                ids = sampled_ids(cursor, count, capacity, spec["seed"])
                result = evaluate(ids, groups, opens, rules, splits, spec["cash"], spec["cost_per_side"])
                path = out / f"batch-{cursor:012}.parquet"
                checksum = write_results(path, ids, result)
                seconds = time.perf_counter() - started
                written = path.stat().st_size
                db.execute("""
                    UPDATE batches SET phase = 'complete', checksum = ?, bytes = ?, elapsed = ?
                    WHERE first_id = ? AND phase = 'leased'
                """, [checksum, written, seconds, cursor])
            except Exception as error:
                db.execute("INSERT INTO failures VALUES (?, ?, current_timestamp)", [cursor, type(error).__name__])
                progress("failed")
                raise
            cursor += count
            storage += written
            elapsed += seconds
            progress("running" if cursor < budget else "complete")
        progress("complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--budget", type=int, required=True, choices=MILESTONES)
    parser.add_argument("--batch", type=int, default=25_000)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    run(args.root, args.spec, args.out, args.budget, args.batch, args.threads)
