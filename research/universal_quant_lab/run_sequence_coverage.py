"""Verify acquisition checkpoints and materialize Phase 1 coverage evidence."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

from eodhd import atomic_json
from eodhd_intraday import STORAGE


def load(path):
    return json.loads(path.read_bytes())


def audit_intraday(root):
    totals = Counter()
    scopes = defaultdict(lambda: {"windows": 0, "rows": 0, "rejected": 0, "missing_volume": 0,
                                  "missing_volume_windows": [], "empty_windows": []})
    files = sorted((root / STORAGE).glob("market=*/symbol=*/interval=*/*.json"))
    for path in files:
        record = load(path)
        symbol, interval = record["symbol"], record["interval"]
        first, until = record["from_utc"], record["until_utc_exclusive"]
        scope = scopes[(symbol, interval)]
        scope["windows"] += 1
        totals["windows"] += 1
        removed = record.get("rejected_rows", 0)
        scope["rejected"] += removed
        totals["rejected"] += removed
        if record["status"] in {"empty", "no_valid_bars"}:
            scope["empty_windows"].append([first, until, record["status"]])
            totals["empty_windows"] += 1
            continue
        if record["status"] != "saved":
            raise ValueError(f"Unexpected checkpoint status for {symbol} {interval} {first}")
        bars = path.with_suffix(".parquet")
        with bars.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Parquet checksum mismatch for {symbol} {interval} {first}")
        sample = pd.read_parquet(bars, columns=["timestamp", "volume"])
        ts = sample.timestamp
        if (len(sample) != record["rows"] or ts.isna().any() or ts.duplicated().any()
                or not ts.is_monotonic_increasing
                or ts.iloc[0] < pd.Timestamp(first, tz="UTC")
                or ts.iloc[-1] >= pd.Timestamp(until, tz="UTC")):
            raise ValueError(f"Invalid saved bars for {symbol} {interval} {first}")
        missing = ts[sample.volume.isna()]
        if len(missing) != record["missing_volume"]:
            raise ValueError(f"Volume audit mismatch for {symbol} {interval} {first}")
        if len(missing):
            scope["missing_volume_windows"].append({
                "start_utc": first, "end_utc_exclusive": until, "missing_rows": len(missing),
                "first_missing_utc": missing.iloc[0].isoformat(), "last_missing_utc": missing.iloc[-1].isoformat(),
            })
        scope["rows"] += len(sample)
        scope["missing_volume"] += len(missing)
        totals["rows"] += len(sample)
        totals["missing_volume"] += len(missing)
    totals["symbols"] = len({symbol for symbol, _ in scopes})
    totals["symbol_intervals"] = len(scopes)
    return {"totals": dict(totals), "scopes": [
        {"symbol": symbol, "interval": interval, **data}
        for (symbol, interval), data in sorted(scopes.items())
    ], "volume_feature_policy": "Exclude flagged windows and reset lookback after each gap."}


def evidence(root):
    daily = {}
    for scope, path in (
        ("canada", root / "database/canada-daily/2024-11-26/progress.json"),
        ("us_and_other", root / "database/other-daily/2024-11-26/progress.json"),
    ):
        if path.exists():
            daily[scope] = load(path)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "phase": 1,
              "development_cutoff": "2024-11-26", "daily": daily, "intraday": audit_intraday(root)}
    atomic_json(root / "data_coverage.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    report = evidence(parser.parse_args().root)
    print(json.dumps(report["intraday"]["totals"]))
