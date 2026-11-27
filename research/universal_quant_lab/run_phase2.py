"""Populate the V2 development cache after the verified Phase 1 marker."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import duckdb
import numpy as np
import pandas as pd

from eodhd import atomic_json
from eodhd_intraday import FIELDS, STORAGE, replace_parquet
from forward_v2 import hash_file, preregister
from pattern_technical import feature_grid
from run_universe import read


def file_sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_series(folder, symbol, interval, bars, eligible, provenance):
    target = folder / f"symbol={symbol}" / f"{interval}.parquet"
    checkpoint = target.with_suffix(".json")
    source = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    if checkpoint.exists():
        old = read(checkpoint)
        if old["source_sha256"] != source or old["sha256"] != file_sha256(target):
            raise RuntimeError(f"Technical cache checksum or input changed for {symbol} {interval}")
        return old
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    eligible = pd.Series(eligible, index=bars.index, dtype=bool)
    if not len(bars) or not bars.timestamp.is_monotonic_increasing or bars.timestamp.duplicated().any():
        raise ValueError(f"Invalid feature source {symbol} {interval}")
    features = feature_grid(bars, eligible)
    frame = pd.concat((bars, eligible.rename("volume_features_eligible"), features), axis=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(f".{uuid4().hex}.tmp")
    try:
        frame.to_parquet(temp, index=False, compression="zstd")
        digest = file_sha256(temp)
        replace_parquet(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    result = {"path": target.relative_to(folder).as_posix(), "symbol": symbol, "interval": interval,
              "sha256": digest, "source_sha256": source, "rows": len(frame), "feature_count": len(features.columns),
              "last_observation": max(str(bars.session.iloc[-1]), bars.timestamp.iloc[-1].date().isoformat()),
              "volume_eligible_rows": int(eligible.sum())}
    atomic_json(checkpoint, result)
    return result


def weekly(bars, cutoff, crypto=False):
    frequency = "W-SUN" if crypto else "W-FRI"
    stamp = pd.to_datetime(bars.session).dt.to_period(frequency)
    good = stamp.dt.end_time.dt.normalize() <= pd.Timestamp(cutoff)
    frame = bars.loc[good].copy()
    aggregated = frame.groupby(stamp[good], sort=True).agg(
        session=("session", "last"), timestamp=("timestamp", "last"), open=("open", "first"),
        high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", lambda col: col.sum(min_count=len(col))),
    )
    return aggregated.reset_index(drop=True)


def run(root, previous_hash, publish):
    from run_all import safe_to_run

    marker = root / "phase1_done.json"
    if hash_file(marker) != previous_hash:
        raise RuntimeError("Phase 1 evidence hash changed")
    coverage_path = root / "data_coverage.json"
    if hash_file(coverage_path) != read(marker)["counts"]["coverage_sha256"]:
        raise RuntimeError("Phase 1 coverage changed")
    coverage = read(coverage_path)
    _, plan = preregister(root)
    cutoff = plan["discovery"]["development_cutoff_inclusive"]
    universe = read(root / "config/universe.json")
    folder = root / "feature_cache/capped-sequence"
    daily = read(root / "checkpoints/capped-sequence/daily.json")
    results = []
    digest = [file_sha256(Path(__file__)), file_sha256(Path(__file__).with_name("pattern_technical.py")),
              file_sha256(Path(__file__).with_name("pattern_oscillators.py"))]
    by_symbol = {item["symbol"]: item for item in universe["daily"]}
    with duckdb.connect(str(root / "database/warehouse/catalog.duckdb"), read_only=True) as db:
        available = defaultdict(list)
        for row in db.execute("""SELECT symbol, sha256, parquet_glob,
                          json_extract_string(audit,'$.bars'),
                          json_extract_string(audit,'$.first'),json_extract_string(audit,'$.last')
                          FROM datasets WHERE bar_interval='1d' ORDER BY symbol, sha256""").fetchall():
            available[row[0]].append(row[1:])
    for symbol, (_, count, first, last) in daily.items():
        if count < 252:
            continue
        safe_to_run(root)
        source = next((item for item in available[symbol] if item[2:] == (str(count), first, last)), None)
        if source is None or last > cutoff:
            raise RuntimeError(f"No exact development revision found for {symbol}")
        files = sorted(Path(source[1]).parent.parent.glob("year=*/bars.parquet"))
        bars = pd.read_parquet(files, columns=["timestamp", "session", *FIELDS])
        bars = bars.sort_values("timestamp").reset_index(drop=True)
        if len(bars) != count or bars.session.iloc[0] != first or bars.session.iloc[-1] != last:
            raise RuntimeError(f"Invalid verified daily revision for {symbol}")
        inputs = [digest, source[0], [file_sha256(file) for file in files]]
        results.append(cache_series(folder, symbol, "1d", bars, bars.volume.notna(), inputs))
        week = weekly(bars, cutoff, crypto=by_symbol[symbol]["market"] == "Crypto")
        if len(week) >= 50:
            results.append(cache_series(folder, symbol, "1w", week, week.volume.notna(), inputs))
        if len(results) % 32 < 2:
            publish({"cached_development_series": len(results)})

    for scope in coverage["intraday"]["scopes"]:
        symbol, interval = scope["symbol"], scope["interval"]
        if symbol not in by_symbol or scope["rows"] < 252:
            continue
        safe_to_run(root)
        market = "US" if by_symbol[symbol]["market"] == "US" else "CC"
        base = root / STORAGE / f"market={market}" / f"symbol={symbol}" / f"interval={interval}"
        windows, checksums = [], []
        for path in sorted(base.glob("*.json")):
            window = read(path)
            if window["status"] != "saved":
                continue
            bars_path = path.with_suffix(".parquet")
            if file_sha256(bars_path) != window["sha256"] or window["until_utc_exclusive"] > "2024-11-27":
                raise RuntimeError(f"Changed or out-of-scope intraday window for {symbol}")
            values = pd.read_parquet(bars_path)
            values["eligible"] = window["missing_volume"] == 0
            windows.append(values)
            checksums.append(window["sha256"])
        bars = pd.concat(windows, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        eligible = bars.pop("eligible")
        results.append(cache_series(folder, symbol, interval, bars, eligible, [digest, checksums]))
        if len(results) % 16 == 0:
            publish({"cached_development_series": len(results)})
    counts = {"cached_development_series": len(results), "feature_rows": sum(item["rows"] for item in results)}
    atomic_json(folder / "technical_manifest.json", {
        "datasets": results, "last_observation": max(row["last_observation"] for row in results),
        "scope": "technical features only", "counts": counts,
    })
    publish(counts)
    raise RuntimeError("Technical cache complete. Point-in-time fundamental integration is required before the full Phase 2 marker.")
