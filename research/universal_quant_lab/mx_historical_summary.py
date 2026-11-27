"""Download public Montreal Exchange daily derivatives summaries for research."""
import argparse
import csv
from datetime import date, timedelta
import hashlib
import io
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from campaign_watchdog import guard, health
from eodhd import atomic_json

SOURCE = "https://www.m-x.ca/en/trading/data/historical"
FIELDS = {"Date", "Symbol", "Expiry Date", "Ins. Type", "Bid Price", "Ask Price",
          "Volume", "Settlement Price", "Open Interest"}


def download(root, products, first, last):
    paths = root / "database/mx/historical-summary"
    for kind, symbol in products:
        start = first
        while start <= last:
            end = min(start + timedelta(days=89), last)
            folder = paths / f"{start.isoformat()}_{end.isoformat()}"
            path = folder / f"{symbol}-{kind}.csv"
            manifest = path.with_suffix(".json")
            if path.exists() and manifest.exists():
                start = end + timedelta(days=1)
                continue
            while guard(health(root)) or (paths / "PAUSE").exists():
                time.sleep(30)
            params = {"symbol": symbol, "o": symbol if kind == "options" else "",
                      "f": symbol if kind == "futures" else "", "from": start.isoformat(),
                      "to": end.isoformat(), "dnld": ""}
            url = f"{SOURCE}?{urlencode(params)}"
            with urlopen(url, timeout=60) as response:
                if response.headers.get_content_type() != "text/csv":
                    raise ValueError(f"Expected an MX CSV for {symbol} {start} through {end}")
                payload = response.read()
            reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
            if not FIELDS.issubset(reader.fieldnames or []):
                raise ValueError(f"Unknown MX schema for {symbol}")
            rows = 0
            contracts = set()
            dates = set()
            for row in reader:
                session = date.fromisoformat(row["Date"])
                if not start <= session <= end or not row["Symbol"]:
                    raise ValueError(f"Invalid date or symbol in MX export for {symbol}")
                dates.add(session)
                contracts.add(row["Symbol"])
                rows += 1
            folder.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_bytes(payload)
            temp.replace(path)
            info = {"source": url, "rows": rows, "contracts": len(contracts), "sessions": len(dates),
                    "first": min(dates).isoformat() if dates else None,
                    "last": max(dates).isoformat() if dates else None,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "limitations": "Public daily derivatives summary; no intraday order or execution tape."}
            atomic_json(manifest, info)
            print(f"{kind} {symbol} {start} {end}: {rows} rows, {len(contracts)} contracts", flush=True)
            time.sleep(1)
            start = end + timedelta(days=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--from", dest="first", required=True, type=date.fromisoformat)
    parser.add_argument("--to", dest="last", required=True, type=date.fromisoformat)
    parser.add_argument("products", nargs="+", help="options:SHOP futures:SXF")
    args = parser.parse_args()
    if not args.first <= args.last < date.today():
        parser.error("Expected a historical date range")
    if any(not re.fullmatch(r"(options|futures):[A-Z0-9]+", product) for product in args.products):
        parser.error("Expected an options or futures symbol from the MX historical data directory")
    download(args.root, [product.split(":", 1) for product in args.products], args.first, args.last)
