"""Backfill bounded EODHD development intraday windows for US equities and crypto."""
import argparse
from datetime import date, datetime, time as midnight, timedelta, timezone
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import re
from time import sleep
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from campaign_watchdog import guard, health
from eodhd import atomic_json, query
from profit_admission import cpu_guard


DEVELOPMENT_END = date(2024, 11, 27)
STORAGE = Path("database/eodhd-intraday/development-v1")
MARKETS = {"US": "America/New_York", "CC": "UTC"}
INTERVALS = ("1m", "5m", "15m", "1h")
FIELDS = ["open", "high", "low", "close", "volume"]


def day_epoch(day):
    return int(datetime.combine(day, midnight.min, timezone.utc).timestamp())


def normalize(rows, exchange, start, end):
    frame = pd.DataFrame(rows)
    epoch = pd.to_numeric(frame["timestamp"], errors="raise")
    if not np.isfinite(epoch).all() or (epoch % 1 != 0).any():
        raise ValueError("Invalid timestamp")
    if ((epoch < day_epoch(start)) | (epoch >= day_epoch(end))).any():
        raise ValueError("Provider returned timestamps outside the requested window")
    frame["timestamp"] = pd.to_datetime(epoch, unit="s", utc=True)
    frame[FIELDS] = frame[FIELDS].apply(pd.to_numeric, errors="raise")
    frame = frame.drop_duplicates(subset=["timestamp", *FIELDS])
    frame = frame.loc[~frame.timestamp.duplicated(keep=False)].copy()
    prices = frame[FIELDS[:-1]]
    invalid = (~np.isfinite(prices) | (prices <= 0)).any(axis=1)
    invalid |= (frame.high < prices.max(axis=1)) | (frame.low > prices.min(axis=1))
    invalid |= (frame.volume < 0) | np.isinf(frame.volume)
    if invalid.any():
        frame = frame.loc[~invalid].copy()
    frame["session"] = frame.timestamp.dt.tz_convert(ZoneInfo(MARKETS[exchange])).dt.strftime("%Y-%m-%d")
    return frame[["timestamp", "session", *FIELDS]].sort_values("timestamp").reset_index(drop=True)


def backfill(root, symbols, intervals, start, end, max_requests):
    if not start < end <= DEVELOPMENT_END:
        raise ValueError(f"Expected a nonempty UTC date range ending by {DEVELOPMENT_END}")
    if max_requests <= 0 or set(intervals) - set(INTERVALS):
        raise ValueError("Expected supported intervals and a positive request budget")
    if any(not re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]*\.(US|CC)", symbol) for symbol in symbols):
        raise ValueError("Intraday candidates must be US equities or EODHD crypto symbols")

    calls = 0
    base = root / STORAGE
    for symbol in dict.fromkeys(symbols):
        exchange = symbol.rsplit(".", 1)[-1]
        for interval in dict.fromkeys(intervals):
            current = start
            while current < end:
                following = min(current + timedelta(days=28), end)
                folder = base / f"market={exchange}" / f"symbol={symbol}" / f"interval={interval}"
                checkpoint = folder / f"{current}_{following}.json"
                bars = checkpoint.with_suffix(".parquet")
                if checkpoint.exists():
                    record = json.loads(checkpoint.read_bytes())
                    if record["status"] == "saved":
                        with bars.open("rb") as source:
                            if hashlib.file_digest(source, "sha256").hexdigest() != record["sha256"]:
                                raise ValueError(f"Checkpoint integrity error: {bars.name}")
                    current = following
                    continue
                if calls == max_requests:
                    return "batch_complete", calls
                if (base / "PAUSE").exists():
                    return "operator_pause", calls
                protection = guard(health(root))
                if protection or cpu_guard(root, 85) == "cpu_temperature":
                    return protection or "cpu_temperature", calls
                status, rows = query(f"intraday/{symbol}", interval=interval,
                                     **{"from": day_epoch(current), "to": day_epoch(following) - 1})
                calls += 1
                record = {"symbol": symbol, "interval": interval, "from_utc": str(current),
                          "until_utc_exclusive": str(following), "http_status": status,
                          "acquired_utc": datetime.now(timezone.utc).isoformat(), "rows": 0}
                if status != 200 or not isinstance(rows, list):
                    print(json.dumps(record), flush=True)
                    return f"provider:{status}", calls
                frame = normalize(rows, exchange, current, following) if rows else None
                record.update(provider_rows=len(rows),
                              rejected_rows=len(rows) - len(frame) if frame is not None else 0,
                              missing_volume=int(frame.volume.isna().sum()) if frame is not None else 0)
                if frame is not None and not frame.empty:
                    folder.mkdir(parents=True, exist_ok=True)
                    temp = bars.with_suffix(f".{uuid4().hex}.tmp")
                    try:
                        frame.to_parquet(temp, index=False, compression="zstd")
                        if not pd.read_parquet(temp).equals(frame):
                            raise ValueError("Parquet round-trip mismatch")
                        with temp.open("rb") as source:
                            digest = hashlib.file_digest(source, "sha256").hexdigest()
                        temp.replace(bars)
                    finally:
                        temp.unlink(missing_ok=True)
                    record.update(status="saved", rows=len(frame), sha256=digest,
                                  first_bar=frame.timestamp.iloc[0].isoformat(),
                                  last_bar=frame.timestamp.iloc[-1].isoformat(),
                                  timestamp_semantics="Provider UTC bar start. Unadjusted OHLCV.")
                else:
                    record["status"] = "no_valid_bars" if rows else "empty"
                atomic_json(checkpoint, record)
                print(json.dumps(record), flush=True)
                sleep(0.2)
                current = following
    return "complete", calls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat, default=DEVELOPMENT_END,
                        help="Exclusive UTC cutoff, no later than 2024-11-27")
    parser.add_argument("--intervals", nargs="+", default=["5m", "1h"], choices=INTERVALS)
    parser.add_argument("--max-requests", type=int, default=60)
    args = parser.parse_args()
    base = args.root / STORAGE
    base.mkdir(parents=True, exist_ok=True)
    with (base / "worker.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            parser.error("An intraday writer already owns this workspace")
        status, calls = backfill(args.root, args.symbols, args.intervals, args.start, args.end, args.max_requests)
    print(json.dumps({"status": status, "requests": calls, "pid": os.getpid()}), flush=True)
    raise SystemExit(0 if status in {"complete", "batch_complete"} else 2)
