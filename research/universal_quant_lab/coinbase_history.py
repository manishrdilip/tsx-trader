"""Acquire public Coinbase Exchange spot candles and audit missing buckets."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from eodhd import atomic_json
from warehouse import ingest


def acquire(root, product, start, end):
    if not re.fullmatch(r"[A-Z0-9]+-USD", product):
        raise ValueError("Expected a USD spot product")
    hour = timedelta(hours=1)
    if start >= end or end > datetime.now(timezone.utc) or (end - start) > timedelta(days=366):
        raise ValueError("Expected a bounded historical window of at most one year")
    data = {}
    cursor = start
    while cursor < end:
        boundary = min(end, cursor + 299 * hour)
        options = urlencode({"granularity": 3600, "start": cursor.isoformat(), "end": boundary.isoformat()})
        request = Request(f"https://api.exchange.coinbase.com/products/{product}/candles?{options}",
                          headers={"User-Agent": "UniversalQuantLab/1"})
        with urlopen(request, timeout=30) as stream:
            block = json.load(stream)
        if not isinstance(block, list):
            raise ValueError("Unexpected candle response")
        for stamp, low, high, opening, close, volume in block:
            if not cursor.timestamp() <= stamp < boundary.timestamp():
                continue
            if stamp % 3600 or not all(math.isfinite(v) and v > 0 for v in (low, high, opening, close)):
                raise ValueError("Invalid candle timestamp or price")
            if low > min(opening, close) or high < max(opening, close) or not math.isfinite(volume) or volume < 0:
                raise ValueError("Invalid OHLCV")
            if stamp in data:
                raise ValueError("Duplicate candle timestamp")
            time = datetime.fromtimestamp(stamp, timezone.utc)
            data[stamp] = dict(timestamp=time.isoformat(), session=time.date().isoformat(),
                               open=opening, high=high, low=low, close=close, volume=volume)
        cursor = boundary
    if not data:
        raise ValueError("No historical candles in the requested window")
    records = [data[key] for key in sorted(data)]
    missing = [datetime.fromtimestamp(stamp, timezone.utc).isoformat()
               for stamp in range(int(start.timestamp()), int(end.timestamp()), 3600) if stamp not in data]
    dest = root / "database/staging/coinbase" / f"{product}-{start:%Y%m%d}-{end:%Y%m%d}-1h.json"
    atomic_json(dest, records)
    audit = {"symbol": product, "bars": len(records), "first": records[0]["timestamp"],
             "last": records[-1]["timestamp"], "missing_buckets": missing,
             "output_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
             "timestamp_semantics": "UTC bucket start; bar becomes available after bucket closes",
             "volume_semantics": "Base asset traded on Coinbase Exchange",
             "publication": "Local data only"}
    atomic_json(dest.with_suffix(".audit.json"), audit)
    ingest(root, dest, "coinbase", "Crypto", product, "1h")
    return {"product": product, "rows": len(records), "missing": len(missing),
            "first": audit["first"], "last": audit["last"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("start")
    parser.add_argument("end")
    parser.add_argument("products", nargs="+")
    args = parser.parse_args()
    start, end = (datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                  for day in (args.start, args.end))
    for product in args.products:
        print(json.dumps(acquire(args.root, product, start, end)), flush=True)
