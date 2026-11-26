"""Publish validated lab bars as an immutable Parquet dataset in a DuckDB catalog."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd


def ingest(root, bars, source, market, symbol, interval):
    dimensions = dict(source=source, market=market, symbol=symbol, interval=interval)
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", v) for v in dimensions.values()):
        raise ValueError("Invalid partition identifier")
    payload = bars.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    audit = json.loads(bars.with_suffix(".audit.json").read_text(encoding="utf-8"))
    if audit["output_sha256"] != digest or audit["symbol"] != symbol:
        raise ValueError("Importer audit does not match the input")
    frame = pd.DataFrame(json.loads(payload))
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if len(frame) != audit["bars"] or frame.timestamp.isna().any() or not frame.timestamp.is_monotonic_increasing or frame.timestamp.duplicated().any():
        raise ValueError("Invalid timestamp sequence or row count")
    if not frame.session.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Expected ISO market session dates")
    warehouse = root / "database" / "warehouse"
    partition = warehouse / "bars"
    for key, value in dimensions.items():
        partition /= f"{key}={value}"
    partition /= f"revision={digest}"
    partition.mkdir(parents=True, exist_ok=True)
    for session, group in frame.groupby("session"):
        target = partition / f"date={session}" / "bars.parquet"
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            temp = target.with_suffix(f".{uuid4().hex}.tmp")
            try:
                group.to_parquet(temp, index=False)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)
    pattern = (partition / "date=*" / "bars.parquet").as_posix()
    with duckdb.connect(str(warehouse / "catalog.duckdb")) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS datasets (
            source VARCHAR, market VARCHAR, symbol VARCHAR, bar_interval VARCHAR,
            sha256 VARCHAR, parquet_glob VARCHAR, audit JSON,
            PRIMARY KEY (source, market, symbol, bar_interval, sha256)
        )""")
        db.execute("INSERT OR IGNORE INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
                   [*dimensions.values(), digest, pattern, json.dumps(audit)])
        count, distinct = db.execute(
            "SELECT count(*), count(DISTINCT timestamp) FROM read_parquet(?)", [pattern]
        ).fetchone()
        if count != len(frame) or distinct != count:
            raise ValueError("Parquet round trip does not match the importer audit")
        db.execute("INSERT OR IGNORE INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
                   [*dimensions.values(), digest, pattern, json.dumps(audit)])
    return dict(rows=count, sessions=len(frame.session.unique()), sha256=digest, parquet_glob=pattern)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("bars", type=Path)
    for field in ("source", "market", "symbol", "interval"):
        parser.add_argument(field)
    print(json.dumps(ingest(**vars(parser.parse_args())), indent=2))
