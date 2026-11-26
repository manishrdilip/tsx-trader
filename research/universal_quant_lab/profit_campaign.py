"""Multi-job profit-first engineering runner. Official admission remains sealed."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import shutil
import time

import duckdb
import numba
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from campaign_plan import hashed
from campaign_watchdog import guard, health
from daily_campaign import digest, exclusive
from execution_actions import actions
from profit_features import signals, space
from eodhd import atomic_json
from profit_admission import admit, cpu_guard
from profit_engine import METRICS, evaluate
from profit_ledger import Ledger


def load(root, job, dates):
    with duckdb.connect(str(root / "database/warehouse/catalog.duckdb"), read_only=True) as db:
        row = db.execute("""
            SELECT parquet_glob FROM datasets
            WHERE source=? AND market=? AND symbol=? AND bar_interval='1d' AND sha256=?
        """, [job[k] for k in ("source", "market", "symbol", "data_sha256")]).fetchone()
        if not row:
            raise ValueError("Unknown immutable warehouse revision")
        folder = Path(row[0]).parent.parent
        final_year = int(dates[2][:4]) - int(dates[2][5:] == "01-01")
        files = [x for x in sorted(folder.glob("year=*/bars.parquet")) if int(x.parent.name[5:]) <= final_year]
        if not files:
            raise ValueError("No development partitions")
        hashes = {f.parent.name: digest(f) for f in files}
        bars = db.execute("""
            SELECT session,open,high,low,close,volume,adjusted_close FROM read_parquet(?)
            WHERE session < ? ORDER BY session
        """, [[f.as_posix() for f in files], dates[2]]).df()
    if any(digest(f) != hashes[f.parent.name] for f in files):
        raise ValueError("Development input changed while loading")
    initial_session = int(pd.Index(bars.session).searchsorted(dates[0]))
    bars = bars.iloc[max(0, initial_session - 120):].reset_index(drop=True)
    sessions = pd.Index(bars.session)
    if sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("Invalid daily session sequence")
    splits = np.array([sessions.searchsorted(day) for day in dates], np.int64)
    if min(np.diff(splits)) < 100:
        raise ValueError("Insufficient development history")
    prices = np.ascontiguousarray(bars[["open", "low", "close"]], dtype=np.float64)
    if not np.isfinite(prices).all() or not (prices > 0).all():
        raise ValueError("Invalid execution prices")
    participation = job.get("prior_turnover_fraction")
    if participation is not None:
        if not 0 < participation <= .001:
            raise ValueError("Invalid prior turnover participation limit")
        # Conservative dollar-turnover proxy; exclude the current session.
        turnover = bars.volume * bars.adjusted_close
        cap = turnover.where(turnover > 0).rolling(20).min().shift(1).fillna(0) * participation
        prices = np.column_stack((prices, cap.to_numpy(dtype=np.float64)))
    last_dev = (pd.Timestamp(dates[2]) - pd.Timedelta(days=1)).date().isoformat()
    corporate = actions(root, job, sessions, last_dev)
    scaled = bars.copy()
    scaled[["open", "high", "low", "close"]] = scaled[["open", "high", "low", "close"]].mul(
        np.cumprod(corporate[0]), axis=0
    )
    return hashes, prices, signals(scaled), splits, corporate


def prepare(root, config):
    dates = config["dates"]
    if len(dates) != 3 or dates != sorted(set(dates)) or any(
        datetime.strptime(day, "%Y-%m-%d").date().isoformat() != day for day in dates
    ):
        raise ValueError("Dates must be common ordered ISO session labels")
    if not 1 <= config["batch"] <= 50_000 or not 1 <= config["threads"] <= numba.config.NUMBA_NUM_THREADS:
        raise ValueError("Invalid batch or CPU thread count")
    mode = config.get("mode", "engineering")
    if mode not in ("engineering", "official") or not config["jobs"]:
        raise ValueError("Invalid campaign mode or empty allocation")
    acceptance = None
    if mode == "official":
        acceptance = admit(root, config)
    elif type(config["target"]) is not int or not 0 < config["target"] <= 10_000_000:
        raise ValueError("Engineering target is out of bounds")
    datasets = {}
    jobs = []
    scopes = set()
    for job in config["jobs"]:
        depth, quota, seed = (job[key] for key in ("depth", "quota", "seed"))
        if any(type(x) is not int for x in (depth, quota, seed)):
            raise ValueError("Depth, quota and seed must be integers")
        groups, capacity = space(depth)
        if not 1 <= quota <= capacity:
            raise ValueError("Quota exceeds canonical domain")
        currency = job["currency"]
        spread, slip, fee = (job[k] for k in ("half_spread_bps", "slippage_bps", "fee_per_order"))
        if currency not in ("CAD", "USD") or not all(math.isfinite(v) and v >= 0 for v in (spread, slip, fee)):
            raise ValueError("Invalid local-currency cost model")
        if spread + slip >= 10_000 or fee >= 5_000:
            raise ValueError("Costs exceed account limits")
        scope = hashed([job["data_sha256"], depth, currency, dates])
        if scope in scopes:
            raise ValueError("Duplicate dataset/depth scope, including alternate seeds and cost aliases")
        scopes.add(scope)
        hashes, prices, rules, splits, corporate = load(root, job, dates)
        identity = hashed([scope, spread, slip, fee, job.get("action_snapshot_sha256"), "daily-actions-10"])
        jobs.append({**job, "id": identity, "capacity": capacity, "development_hashes": hashes})
        datasets[identity] = (groups, prices, rules, splits, corporate)
    if sum(job["quota"] for job in jobs) != config["target"]:
        raise ValueError("Campaign allocations do not sum to the exact target")
    lab = Path(__file__).parent
    code = {name: digest(lab / name) for name in (
        "profit_campaign.py", "profit_engine.py", "profit_ledger.py", "daily_engine.py",
        "daily_campaign.py", "features.py", "campaign_watchdog.py",
        "execution_actions.py", "profit_features.py", "profit_admission.py", "profit_retention.py",
    )}
    versions = {name: version(name) for name in ("numpy", "pandas", "numba", "duckdb", "pyarrow")}
    return {**config, "jobs": jobs, "runtime": versions, "code": code, "mode": mode,
            "acceptance_sha256": acceptance, "retention": True}, datasets


def write_batch(path, ids, metrics):
    if not np.isfinite(metrics).all():
        raise ValueError("Nonfinite campaign results")
    columns = {"strategy_id": ids}
    for j, split in enumerate(("train", "validation")):
        for k, metric in enumerate(METRICS):
            columns[f"{split}_{metric}"] = metrics[:, j * len(METRICS) + k]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    try:
        pq.write_table(pa.table(columns), temp, compression="zstd")
        with temp.open("r+b") as handle:
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def run(root, config, out):
    out.mkdir(parents=True, exist_ok=True)
    with exclusive(out / "runner.lock"):
        started = time.perf_counter()
        manifest, datasets = prepare(root, config)
        path = out / "manifest.json"
        if path.exists() and json.loads(path.read_bytes()) != manifest:
            raise ValueError("Run manifest drift")
        if not path.exists():
            atomic_json(path, manifest)
        numba.set_num_threads(manifest["threads"])
        ledger = Ledger(out, manifest)
        try:
            ledger.reconcile()
            official = manifest["mode"] == "official"
            baseline = sum(ledger.counts().values())
            last_sample = 0.
            resources = {}

            def progress(status):
                counts = ledger.counts()
                rows, elapsed, size = ledger.db.execute("""
                    SELECT coalesce(sum(size),0),coalesce(sum(compute_seconds),0),coalesce(sum(bytes),0)
                    FROM ranges WHERE state='complete'
                """).fetchone()
                wall = time.perf_counter() - started
                atomic_json(out / "progress.json", {
                    "status": status, "engineering_completed": 0 if official else rows,
                    "engineering_target": 0 if official else ledger.target,
                    "official_completed": rows if official else 0, "official_target": 1_000_000_000,
                    "dataset_count": len({job["data_sha256"] for job in manifest["jobs"]}),
                    "failed_attempts": ledger.db.execute("SELECT count(*) FROM errors").fetchone()[0],
                    "compute_seconds": elapsed, "session_wall_seconds": wall,
                    "compute_evaluations_per_second": rows / elapsed if elapsed else None,
                    "session_evaluations_per_second": (rows - baseline) / wall,
                    "parquet_bytes": size, "completed_by_job": counts,
                    "free_gib": round(shutil.disk_usage(root).free / 1024**3, 2),
                    "updated_utc": datetime.now(timezone.utc).isoformat(),
                })

            progress("running")
            while sum(ledger.counts().values()) < ledger.target:
                for job in manifest["jobs"]:
                    if sum(ledger.counts().values()) == ledger.target:
                        break
                    if time.monotonic() - last_sample >= 5:
                        resources = health(root)
                        atomic_json(out / "resources.json", resources)
                        last_sample = time.monotonic()
                    # Disk is checked at every batch even when other metrics are cached.
                    resources["free_bytes"] = shutil.disk_usage(root).free
                    thermal = cpu_guard(root, config.get("max_cpu_celsius")) if official else None
                    if (out / "PAUSE").exists() or guard(resources) or thermal:
                        progress("paused")
                        return
                    identity = job["id"]
                    lease = ledger.reserve(identity, manifest["batch"])
                    if not lease:
                        continue
                    first, size = lease
                    try:
                        groups, prices, rules, splits, corporate = datasets[identity]
                        friction = (job["half_spread_bps"] + job["slippage_bps"]) / 10_000
                        fee = job["fee_per_order"]
                        if not evaluate.signatures:
                            evaluate(np.array([0], np.int64), groups, prices, rules, splits, 5000., friction, fee, corporate)
                        ids = ledger.ids(identity, first, size)
                        begin = time.perf_counter()
                        metrics = evaluate(ids, groups, prices, rules, splits, 5000., friction, fee, corporate)
                        compute = time.perf_counter() - begin
                        write_batch(ledger.file(identity, first), ids, metrics)
                        ledger.commit(identity, first, compute)
                        progress("running")
                    except Exception as error:
                        ledger.failure(identity, first, error)
                        progress("failed")
                        raise
            if sum(ledger.counts().values()) != ledger.target:
                raise ValueError("Completed ledger does not equal campaign target")
            if official:
                freeze = {
                    "mode": "official", "completed": ledger.target,
                    "manifest_sha256": digest(path), "holdout_unlocked": False,
                }
                freeze_path = out / "freeze.json"
                if freeze_path.exists() and json.loads(freeze_path.read_bytes()) != freeze:
                    raise ValueError("Campaign freeze does not match the ledger")
                if not freeze_path.exists():
                    atomic_json(freeze_path, freeze)
            progress("complete")
        finally:
            ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.out.resolve()
    if not output.is_relative_to(root / "results"):
        parser.error("Campaign files belong under the local results directory")
    numba.config.CACHE_DIR = str(root / "feature_cache/numba")
    run(root, json.loads(args.config.read_bytes()), output)
