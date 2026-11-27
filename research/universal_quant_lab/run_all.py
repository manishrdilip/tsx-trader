"""Strict, restartable coordinator for the capped Universal Quant Lab run."""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import importlib
import json
import msvcrt
import os
from pathlib import Path
import sqlite3
import sys
import time

import duckdb

from campaign_watchdog import guard, health
from eodhd import atomic_json, query, stage_daily
from eodhd_intraday import STORAGE, backfill
from profit_admission import cpu_guard
from run_sequence_coverage import audit_intraday
from run_universe import CUTOFF, build, content_hash, read


MARKERS = ("phase1_done.json", "phase2_done.json", "phase3_sealed.json",
           "phase4_done.json", "phase5_done.json", "phase6_done.json")
INTRADAY_CUT = date(2024, 4, 17)


def utc():
    return datetime.now(timezone.utc).isoformat()


def safe_to_run(root):
    while True:
        reason = guard(health(root)) or cpu_guard(root, 85)
        if reason not in {"disk", "memory", "gpu_temperature", "cpu_temperature"}:
            return
        time.sleep(60)


def quota(root):
    while True:
        safe_to_run(root)
        status, details = query("user")
        if status != 200 or not isinstance(details, dict):
            raise RuntimeError(f"Provider quota check failed with status {status}")
        if int(details["dailyRateLimit"]) - int(details["apiRequests"]) >= 3500:
            return
        time.sleep(300)


def warehouse_audits(root):
    path = root / "database/warehouse/catalog.duckdb"
    for attempt in range(20):
        try:
            with duckdb.connect(str(path), read_only=True) as db:
                return {symbol: (int(bars), first, last) for symbol, bars, first, last in db.execute("""
                    SELECT symbol, json_extract_string(audit, '$.bars'),
                           json_extract_string(audit, '$.first'), json_extract_string(audit, '$.last')
                    FROM datasets WHERE bar_interval = '1d'
                    AND json_extract_string(audit, '$.first') IS NOT NULL
                    AND json_extract_string(audit, '$.last') <= '2024-11-26'
                    QUALIFY row_number() OVER (
                        PARTITION BY symbol ORDER BY CAST(json_extract_string(audit, '$.bars') AS INTEGER) DESC,
                        json_extract_string(audit, '$.last') DESC, sha256
                    ) = 1
                """).fetchall() if bars and first and last}
        except duckdb.IOException:
            if attempt == 19:
                raise
            time.sleep(1.5)


def canadian_outcomes(root):
    home = root / f"database/canada-daily/{CUTOFF}"
    progress = read(home / "progress.json")
    if progress["status"] != "complete":
        if progress["status"] not in {"running", "paused"}:
            raise RuntimeError(f"Canadian daily worker reported {progress['status']}")
        if progress.get("reason") and str(progress["reason"]).startswith("provider:"):
            raise RuntimeError(f"Canadian backfill stopped: {progress['reason']}")
        updated = datetime.fromisoformat(progress["utc"])
        if (datetime.now(timezone.utc) - updated).total_seconds() > 420:
            raise RuntimeError("Canadian worker checkpoint heartbeat is stale")
        return None, progress
    with sqlite3.connect(f"{(home / 'checkpoint.sqlite3').as_uri()}?mode=ro", uri=True, timeout=10) as db:
        by_symbol = {symbol: (state, bars, first, last) for symbol, state, bars, first, last
                     in db.execute("SELECT symbol,outcome,bars,first_session,last_session FROM outcomes")}
    return by_symbol, progress


def fetch_daily(root, item):
    symbol, market = item["symbol"], item["market"]
    status, rows = query(f"eod/{symbol}", to=str(CUTOFF), order="a")
    if status == 404 or rows == []:
        return "missing", 0, None, None
    if status != 200 or not isinstance(rows, list):
        # Some historical index labels have retired syntax and cannot be resolved as tickers.
        if status == 422 and item.get("provider_directory_match") is False:
            return "unresolved_alias", 0, None, None
        raise RuntimeError(f"Daily acquisition for {symbol} returned {status}")
    try:
        if any(date.fromisoformat(row["date"]) > CUTOFF for row in rows):
            raise ValueError("Date exceeds development fence")
        for attempt in range(20):
            try:
                audit = stage_daily(root, market, symbol, rows)
                return "saved", audit["rows"], audit["first"], audit["last"]
            except duckdb.IOException:
                if attempt == 19:
                    raise
                time.sleep(1.5)
    except (ValueError, KeyError, TypeError, OverflowError):
        return "failed_row_validation", 0, None, None


def phase1(root, universe, publish):
    evidence_root = root / "checkpoints/capped-sequence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    daily_path = evidence_root / "daily.json"
    intra_path = evidence_root / "intraday.json"
    done = read(daily_path) if daily_path.exists() else {}
    intra = read(intra_path) if intra_path.exists() else {}
    targets = {item["symbol"]: item for item in universe["daily"]}
    if len(targets) != len(universe["daily"]) or set(done) - set(targets):
        raise RuntimeError("Duplicate symbol or checkpoint scope mismatch")
    counts = {"daily_target": len(targets), "daily_checked": len(done),
              "intraday_symbols_checked": len(intra)}
    publish(counts)
    existing = warehouse_audits(root)
    can_scope = {"TSX", "TSXV"}
    fetched = 0
    for item in universe["daily"]:
        symbol = item["symbol"]
        if symbol in done or item["market"] in can_scope:
            continue
        if symbol in existing:
            result = ("reused", *existing[symbol])
        else:
            if fetched % 50 == 0:
                quota(root)
            result = fetch_daily(root, item)
            fetched += 1
        done[symbol] = result
        atomic_json(daily_path, done)
        if len(done) % 10 == 0:
            publish({**counts, "daily_checked": len(done)})

    while True:
        canada, progress = canadian_outcomes(root)
        if canada is not None:
            break
        publish({**counts, "daily_checked": len(done),
                 "existing_canadian_backfill_checked": progress["completed"],
                 "existing_canadian_backfill_queue": progress["queued"]})
        time.sleep(30)
    existing = warehouse_audits(root)
    for symbol, item in targets.items():
        if item["market"] in can_scope:
            if symbol in canada:
                done[symbol] = canada[symbol]
            elif symbol in existing:
                done[symbol] = ("reused", *existing[symbol])
            elif symbol not in done:
                done[symbol] = fetch_daily(root, item)
    atomic_json(daily_path, done)
    if set(done) != set(targets):
        raise RuntimeError("Daily coverage ledger does not match the frozen universe")

    intraday = [item for item in targets.values() if item["market"] in universe["intraday"]["markets"]]
    counts.update(daily_checked=len(done), intraday_target=len(intraday))
    publish(counts)
    storage = root / STORAGE
    storage.mkdir(parents=True, exist_ok=True)
    with (storage / "worker.lock").open("a+b") as lock:
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(30)
        for item in intraday:
            symbol = item["symbol"]
            if symbol in intra:
                continue
            first = done[symbol][2]
            if not first:
                intra[symbol] = "daily_missing"
            else:
                quota(root)
                # Keep the two existing chunk grids so prior downloads resume exactly.
                for start, end in ((date.fromisoformat(universe["intraday"]["provider_start"]), INTRADAY_CUT),
                                   (INTRADAY_CUT, CUTOFF + timedelta(days=1))):
                    state, _ = backfill(root, [symbol], universe["intraday"]["frequency"], start, end, 180)
                    if state != "complete":
                        raise RuntimeError(f"Intraday acquisition for {symbol} stopped: {state}")
                intra[symbol] = "checked"
            atomic_json(intra_path, intra)
            counts["intraday_symbols_checked"] = len(intra)
            publish(counts)
    audit = audit_intraday(root)
    result = {**counts, "daily_outcomes": dict(Counter(row[0] for row in done.values())),
              "intraday_outcomes": dict(Counter(intra.values())), "intraday_coverage": audit["totals"],
              "short_or_missing_daily": [{"symbol": symbol, "outcome": row[0], "bars": row[1]}
                                         for symbol, row in done.items() if row[1] < 252]}
    atomic_json(root / "data_coverage.json", {
        "phase": 1, "utc": utc(), "development_cutoff": str(CUTOFF), "counts": result, "intraday": audit,
    })
    return {**counts, "coverage_sha256": content_hash((root / "data_coverage.json").read_bytes())}


def dispatch(root, phase, previous, publish):
    if phase == 1:
        return phase1(root, build(root), publish)
    try:
        implementation = importlib.import_module(f"run_phase{phase}")
    except ModuleNotFoundError as error:
        if error.name != f"run_phase{phase}":
            raise
        raise RuntimeError(f"Phase {phase} has no verified implementation") from None
    return implementation.run(root, previous, publish)


def run(root, limit=6):
    if sys.version_info[:3] != (3, 12, 10):
        raise RuntimeError("The coordinator requires Python 3.12.10")
    inputs = {"RUN_SEQUENCE.md": content_hash((root / "RUN_SEQUENCE.md").read_bytes()),
              "SPEC.md": content_hash((root / "SPEC.md").read_bytes())}
    inputs["config/universe.json"] = content_hash((root / "config/universe.json").read_bytes())
    status_path = root / "status.json"
    phase, previous_hash, counts = 1, None, {}
    started = utc()
    def status(state, detail=None):
        record = {"phase": phase, "state": state, "counts": counts, "started": started, "updated": utc(),
                  "finished": utc() if state != "running" else None,
                  "pid": os.getpid(), "inputs_sha256": inputs}
        if detail is not None:
            record["error"] = detail
        atomic_json(status_path, record)
        print(json.dumps(record), flush=True)
    def publish(data):
        counts.update(data)
        status("running")

    try:
        for phase, name in enumerate(MARKERS, 1):
            started, counts = utc(), {}
            marker = root / name
            if marker.exists():
                raw = marker.read_bytes()
                completed = json.loads(raw)
                if (completed["phase"] != phase or completed["state"] != "complete"
                        or completed["inputs_sha256"] != inputs or completed["previous_sha256"] != previous_hash):
                    raise RuntimeError(f"Invalid or mismatched completion marker {name}")
                previous_hash = content_hash(raw)
                continue
            if any((root / tail).exists() for tail in MARKERS[phase:]):
                raise RuntimeError("Completion markers are out of order")
            if phase > limit:
                return 0
            status("running")
            counts.update(dispatch(root, phase, previous_hash, publish))
            completed = {"phase": phase, "state": "complete", "counts": counts, "started": started,
                         "finished": utc(), "inputs_sha256": inputs, "previous_sha256": previous_hash}
            atomic_json(marker, completed)
            previous_hash = content_hash(marker.read_bytes())
            status("complete")
    except Exception as exc:
        status("failed", f"{type(exc).__name__}: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    build(root)
    with (root / "checkpoints/capped-sequence.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            parser.error("A capped run coordinator already owns this workspace")
        raise SystemExit(run(root))
