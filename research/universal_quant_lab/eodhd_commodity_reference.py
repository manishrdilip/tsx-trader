"""Archive EODHD daily energy reference observations separately from tradable bars."""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import pandas as pd

from eodhd import atomic_json, query


CODES = ("WTI", "BRENT", "NATURAL_GAS", "DIESEL_USGULF", "HEATING_OIL_NYH",
         "JET_FUEL_USGULF", "PROPANE_MBTX")


def download(root, cutoff):
    base = root / "database/eodhd-reference/commodities"
    summary = {}
    for code in CODES:
        folder = base / f"symbol={code}"
        target = folder / f"daily-through-{cutoff}.parquet"
        checkpoint = target.with_suffix(".json")
        if checkpoint.exists():
            evidence = json.loads(checkpoint.read_bytes())
            if hashlib.sha256(target.read_bytes()).hexdigest() != evidence["sha256"]:
                raise ValueError(f"Commodity checksum mismatch for {code}")
            summary[code] = evidence
            continue
        offset, seen, records = 0, set(), []
        while True:
            status, body = query(f"commodities/historical/{code}", interval="daily", **{"page[offset]": offset, "page[limit]": 1000})
            if status != 200 or not isinstance(body, dict):
                raise RuntimeError(f"Commodity {code} returned {status}")
            metadata, rows = body["meta"], body["data"]
            if int(metadata["offset"]) != offset or not rows or not metadata["unit"]:
                raise ValueError(f"Invalid commodity page for {code} at offset {offset}")
            for row in rows:
                session, value = date.fromisoformat(row["date"]), float(row["value"])
                if session in seen or not math.isfinite(value):
                    raise ValueError(f"Invalid commodity record for {code}")
                seen.add(session)
                if session <= cutoff:
                    records.append((session.isoformat(), value))
            offset += len(rows)
            if offset >= int(metadata["total"]):
                break
        frame = pd.DataFrame(sorted(records), columns=["observation_date", "value"])
        if frame.empty:
            raise ValueError(f"No commodity reference observations for {code}")
        folder.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(f".{uuid4().hex}.tmp")
        try:
            frame.to_parquet(temp, index=False, compression="zstd")
            if not frame.equals(pd.read_parquet(temp)):
                raise ValueError(f"Commodity Parquet mismatch for {code}")
            digest = hashlib.sha256(temp.read_bytes()).hexdigest()
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        evidence = {"code": code, "unit": metadata["unit"], "rows": len(frame), "sha256": digest,
                    "first": frame.observation_date.iloc[0], "last": frame.observation_date.iloc[-1],
                    "kind": "Reference observations. No published timestamp or contract OHLCV."}
        atomic_json(checkpoint, evidence)
        summary[code] = evidence
        print(f"{code}: {len(frame)} verified reference observations", flush=True)
    atomic_json(base / "coverage.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--to", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    if args.to >= date.today():
        parser.error("Expected a historical cutoff")
    download(args.root, args.to)
