"""Audit observed daily sessions against a named exchange calendar."""
import argparse
from datetime import date
from importlib.metadata import version
import json
from pathlib import Path

import duckdb
import exchange_calendars as calendars

from eodhd import atomic_json


def audit(root, start, end):
    # XTSX and XNAS are library aliases for XTSE and XNYS. SPY uses XNYS.
    calendar_names = {"TSX": "XTSE", "TSXV": "XTSX", "AAPL.US": "XNAS", "SPY.US": "XNYS"}
    calendar_cache = {}
    output = []
    catalog = root / "database" / "warehouse" / "catalog.duckdb"
    with duckdb.connect(str(catalog), read_only=True) as db:
        datasets = db.execute("""
            SELECT market, symbol, sha256, parquet_glob FROM datasets
            WHERE source = 'eodhd' AND bar_interval = '1d'
            ORDER BY market, symbol, sha256
        """).fetchall()
        for market, symbol, digest, pattern in datasets:
            data = db.execute("""
                SELECT session, volume, close, adjusted_close
                FROM read_parquet(?) ORDER BY session
            """, [pattern]).fetchall()
            dates = [date.fromisoformat(row[0]) for row in data]
            name = calendar_names.get(symbol, calendar_names.get(market))
            check = {
                "market": market, "symbol": symbol, "sha256": digest,
                "rows": len(data), "first": str(dates[0]), "last": str(dates[-1]),
                "missing_volume": sum(row[1] is None for row in data),
                "zero_volume": sum(row[1] == 0 for row in data),
                "adjusted_close_differs": sum(row[2] != row[3] for row in data),
                "calendar": name,
                "calendar_resolved": None,
            }
            low, high = max(start, dates[0]), min(end, dates[-1])
            if name and low <= high:
                if name not in calendar_cache:
                    calendar_cache[name] = calendars.get_calendar(name, start=str(start), end=str(end))
                check["calendar_resolved"] = calendar_cache[name].name
                sessions = calendar_cache[name].sessions
                expected = {d.date() for d in sessions if low <= d.date() <= high}
                seen = {d for d in dates if low <= d <= high}
                check.update(
                    window_start=str(low), window_end=str(high),
                    missing_sessions=sorted(map(str, expected - seen)),
                    extra_sessions=sorted(map(str, seen - expected)),
                )
            output.append(check)
    return {"exchange_calendars_version": version("exchange-calendars"), "datasets": output}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.start >= args.end:
        parser.error("Expected start before end")
    report = audit(args.root, args.start, args.end)
    atomic_json(args.output, report)
    for row in report["datasets"]:
        print(json.dumps({"symbol": row["symbol"], "rows": row["rows"],
                          "missing_sessions": len(row["missing_sessions"]) if "missing_sessions" in row else None,
                          "extra_sessions": len(row["extra_sessions"]) if "extra_sessions" in row else None}))
