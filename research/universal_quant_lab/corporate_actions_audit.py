"""Archive development-period actions and test revisions for raw-price eligibility."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

import duckdb
import numpy as np

from eodhd import atomic_json, query


def audit(root, specs, start, end):
    report = []
    with duckdb.connect(str(root / "database/warehouse/catalog.duckdb"), read_only=True) as db:
        for job in specs:
            symbol = job["symbol"]
            row = db.execute("""
                SELECT parquet_glob FROM datasets WHERE symbol=? AND market=? AND sha256=?
            """, [symbol, job["market"], job["data_sha256"]]).fetchone()
            if row is None:
                raise ValueError("Daily data revision unavailable")
            folder = Path(row[0]).parent.parent
            files = [f.as_posix() for f in sorted(folder.glob("year=*/bars.parquet"))
                     if start.year <= int(f.parent.name[5:]) <= end.year]
            data = db.execute("""
                SELECT session, close, adjusted_close FROM read_parquet(?)
                WHERE session BETWEEN ? AND ? ORDER BY session
            """, [files, str(start), str(end)]).fetchall()
            factors = np.array([adjusted / close for _, close, adjusted in data])
            changed = [data[i + 1][0] for i in np.flatnonzero(np.abs(np.diff(np.log(factors))) > .001)]
            events = {}
            responses = {}
            for endpoint in ("splits", "div"):
                status, body = query(f"{endpoint}/{symbol}", **{"from": str(start), "to": str(end)})
                responses[endpoint] = {"status": status, "count": len(body) if isinstance(body, list) else None}
                if status == 200 and isinstance(body, list):
                    events[endpoint] = body
            event_dates = {entry.get("date") for rows in events.values() for entry in rows}
            discrepancies = sorted(set(changed) - event_dates)
            content = {"symbol": symbol, "data_sha256": job["data_sha256"],
                       "from": str(start), "to": str(end), "events": events}
            key = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            atomic_json(root / "database/eodhd/corporate-actions" / f"{key}.json", content)
            flags = []
            if len(events) != 2:
                flags.append("action_endpoint_unavailable")
            if any(events.values()):
                flags.append("cashflow_or_share_adjustment_required")
            if discrepancies:
                flags.append("unexplained_adjustment_moves")
            if not data:
                flags.append("no_bars_in_window")
            result = {"symbol": symbol, "bars": len(data), "actions": responses,
                      "factor_move_count": len(changed), "unexplained_factor_moves": discrepancies,
                      "action_snapshot_sha256": key, "raw_execution_flags": flags}
            report.append(result)
            print(json.dumps({"symbol": symbol, "actions": responses, "flags": flags}), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("Expected ordered date range")
    specs = json.loads(args.config.read_bytes())["jobs"]
    atomic_json(args.output, audit(args.root, specs, args.start, args.end))
