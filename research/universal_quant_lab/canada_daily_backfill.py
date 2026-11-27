"""Resume a daily-bar backfill from frozen EODHD exchange directories."""
import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from itertools import zip_longest
import json
import os
from pathlib import Path
import re
import sqlite3
import time

import duckdb

from campaign_watchdog import guard, health
from eodhd import atomic_json, query, stage_daily

EXCHANGES = {"TO": "TSX", "V": "TSXV", "CN": "CSE", "NEO": "CboeCanada"}
OTHER_EXCHANGES = {"US": "US", "CC": "Crypto", "FOREX": "FX", "INDX": "Indices"}
SYMBOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def now():
    return datetime.now(timezone.utc).isoformat()


def snapshot(root, path, exchanges):
    if path.exists():
        return json.loads(path.read_bytes())
    with duckdb.connect(str(root / "database/warehouse/catalog.duckdb"), read_only=True) as db:
        existing = {symbol.upper() for (symbol,) in db.execute(
            "SELECT DISTINCT symbol FROM datasets WHERE bar_interval = '1d' AND market IN (?, ?, ?, ?)",
            list(exchanges.values()),
        ).fetchall()}
    directories, groups = {}, []
    for delisted in (False, True):
        for suffix, market in exchanges.items():
            status, rows = query(f"exchange-symbol-list/{suffix}", **({"delisted": 1} if delisted else {}))
            if status != 200 or not isinstance(rows, list) or not rows:
                raise RuntimeError(f"Incomplete provider directory for {suffix}: {status}")
            key = f"{market}/{'delisted' if delisted else 'active'}"
            directories[key] = rows
            # Equities and funds first within each exchange and listing status.
            group = []
            for row in sorted(rows, key=lambda item: (
                str(item.get("Type", "")).lower() not in {"common stock", "etf"},
                str(item.get("Code", "")),
            )):
                code = str(row.get("Code", ""))
                if SYMBOL.fullmatch(code):
                    group.append((market, f"{code}.{suffix}", key))
            groups.append(group)
    seen = set(existing)
    queue = []
    for entries in zip_longest(*groups):
        for entry in entries:
            if entry and entry[1].upper() not in seen:
                seen.add(entry[1].upper())
                queue.append(entry)
    data = {"created_utc": now(), "directories": directories, "queue": queue,
            "existing_daily_symbols": len(existing)}
    atomic_json(path, data)
    return data


def run(root, cutoff, limit, scope="canada"):
    state = root / "database" / f"{scope}-daily" / cutoff.isoformat()
    state.mkdir(parents=True, exist_ok=True)
    progress = state / "progress.json"
    universe = snapshot(root, state / "universe.json",
                        EXCHANGES if scope == "canada" else OTHER_EXCHANGES)
    queue = universe["queue"]
    with closing(sqlite3.connect(state / "checkpoint.sqlite3", timeout=0)) as db:
        # One worker exclusively owns this queue. The lock releases on process exit.
        db.execute("PRAGMA locking_mode=EXCLUSIVE")
        db.execute("""CREATE TABLE IF NOT EXISTS outcomes (
            symbol TEXT PRIMARY KEY, market TEXT, membership TEXT,
            outcome TEXT, bars INTEGER, first_session TEXT, last_session TEXT
        )""")
        db.execute("BEGIN EXCLUSIVE")
        completed = {symbol for (symbol,) in db.execute("SELECT symbol FROM outcomes")}
        before = len(completed)
        db.commit()
        def publish(status, reason=None):
            summary = db.execute("""SELECT membership, outcome, count(*), sum(bars)
                                      FROM outcomes GROUP BY membership, outcome ORDER BY 1, 2""").fetchall()
            atomic_json(progress, {"utc": now(), "status": status, "reason": reason, "pid": os.getpid(),
                                   "cutoff": cutoff.isoformat(), "queued": len(queue),
                                   "completed": len(completed), "outcomes": summary,
                                   "directory_rows": {k: len(v) for k, v in universe["directories"].items()}})
        publish("running")
        for market, symbol, membership in queue:
            if symbol in completed:
                continue
            if limit and len(completed) - before >= limit:
                publish("batch_complete")
                return
            if len(completed) == before or (len(completed) - before) % 10 == 0:
                while (reason := guard(health(root))) or (state / "PAUSE").exists():
                    publish("paused", reason or "operator")
                    time.sleep(30)
                publish("running")
            status, rows = query(f"eod/{symbol}", to=cutoff.isoformat(), order="a")
            if status in (401, 403, 429, "key_missing") or (
                status not in (200, 404)
            ):
                publish("paused", f"provider:{status}")
                return
            report = {}
            if status == 404 or rows == []:
                outcome = "no_history"
            else:
                try:
                    if not isinstance(rows, list) or any(date.fromisoformat(row["date"]) > cutoff for row in rows):
                        raise ValueError("Invalid history or development cutoff")
                    for attempt in range(6):
                        try:
                            report = stage_daily(root, market, symbol, rows)
                            break
                        except duckdb.IOException:
                            if attempt == 5:
                                raise
                            time.sleep(1 + attempt)
                    outcome = "ingested"
                except (ValueError, KeyError, TypeError, OverflowError):
                    outcome = "failed_validation"
                except (duckdb.IOException, OSError):
                    publish("paused", "warehouse_io")
                    raise
            with db:
                db.execute("INSERT INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (symbol, market, membership, outcome, report.get("rows", 0),
                            report.get("first"), report.get("last")))
            completed.add(symbol)
        publish("complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--to", required=True, type=date.fromisoformat)
    parser.add_argument("--limit", default=0, type=int)
    parser.add_argument("--scope", choices=("canada", "other"), default="canada")
    args = parser.parse_args()
    if args.to >= date.today() or args.limit < 0:
        parser.error("Expected a past cutoff and nonnegative limit")
    run(args.root, args.to, args.limit, args.scope)
