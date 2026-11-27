"""Freeze the capped acquisition universe from explicit, reproducible inputs."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import median
from urllib.request import urlopen

from canada_daily_backfill import SYMBOL
from eodhd import atomic_json, query


CUTOFF = date(2024, 11, 26)
START = "2016-01-01"
NASDAQ_SOURCE = ("https://raw.githubusercontent.com/thuningxu/sp500nq100/"
                 "1cc1de2770874293597a418b41b079e5337b260c/nasdaq100_components_history.csv")
FX = "EURUSD USDJPY GBPUSD USDCHF AUDUSD USDCAD NZDUSD EURGBP EURJPY EURCHF GBPJPY AUDJPY EURCAD CADJPY"
INDICES = ("GSPTSE", "GSPC", "NDX", "VIX")


def read(path):
    return json.loads(path.read_bytes())


def content_hash(payload):
    return hashlib.sha256(payload).hexdigest()


def get(endpoint, **params):
    status, result = query(endpoint, **params)
    if status != 200 or not result:
        raise RuntimeError(f"Required universe source {endpoint}: HTTP {status} or empty data")
    return result


def memberships():
    intervals = defaultdict(list)
    sp500 = get("fundamentals/GSPC.INDX", filter="HistoricalTickerComponents")
    for row in sp500.values():
        first, last = row["StartDate"], row.get("EndDate")
        if first and first <= str(CUTOFF) and (not last or last >= START):
            intervals[row["Code"]].append({"index": "SP500", "start": max(first, START),
                                            "end": last if last and last <= str(CUTOFF) else None,
                                            "provider_delisted": bool(int(row["IsDelisted"]))})
    with urlopen(NASDAQ_SOURCE, timeout=30) as source:
        payload = source.read()
    snapshots = [(row["date"], set(row["tickers"].split(",")))
                 for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
                 if row["date"] <= str(CUTOFF)]
    if not snapshots or any(not 89 <= len(members) <= 112 for _, members in snapshots):
        raise ValueError("Nasdaq-100 input did not pass membership counts")
    if [day for day, _ in snapshots] != sorted({day for day, _ in snapshots}):
        raise ValueError("Nasdaq-100 membership dates must be unique and chronological")
    current = {}
    for day, names in snapshots:
        for ticker in current.keys() - names:
            first = current.pop(ticker)
            if day >= START:
                intervals[ticker].append({"index": "NASDAQ100", "start": max(first, START), "end": day})
        for ticker in names - current.keys():
            current[ticker] = day
    for ticker, first in current.items():
        intervals[ticker].append({"index": "NASDAQ100", "start": max(first, START), "end": None})
    return dict(intervals), {"url": NASDAQ_SOURCE, "sha256": content_hash(payload),
                             "snapshot_count": len(snapshots), "community_reconstruction": True}


def crypto_rank():
    def one(day):
        bars = get("eod-bulk-last-day/CC", date=day)
        if any(row.get("date") != day for row in bars):
            raise ValueError(f"Crypto bulk snapshot date mismatch for {day}")
        return bars
    days = [(CUTOFF - timedelta(days=i)).isoformat() for i in range(7)]
    volumes = defaultdict(dict)
    with ThreadPoolExecutor(3) as pool:
        for day, rows in zip(days, pool.map(one, days)):
            for row in rows:
                symbol = row["code"]
                close, volume = row.get("close"), row.get("volume")
                if not symbol.endswith("-USD") or not SYMBOL.fullmatch(symbol) or close is None or volume is None:
                    continue
                turnover = float(close) * float(volume)
                if turnover > 0 and math.isfinite(turnover):
                    volumes[symbol][day] = max(volumes[symbol].get(day, 0), turnover)
    ranks = sorted(((median(days.values()), ticker) for ticker, days in volumes.items() if len(days) >= 4),
                   key=lambda record: (-record[0], record[1]))[:50]
    if len(ranks) != 50:
        raise RuntimeError(f"Only {len(ranks)} crypto symbols had usable liquidity evidence")
    return [{"market": "Crypto", "symbol": f"{ticker}.CC", "median_usd_turnover": liquidity}
            for liquidity, ticker in ranks]


def build(root):
    path = root / "config/universe.json"
    if path.exists():
        existing = read(path)
        if existing.get("version") != "capped-research-v1":
            raise ValueError("Existing universe.json is not this run's frozen data scope")
        return existing
    canada_path = root / f"database/canada-daily/{CUTOFF}/universe.json"
    other_path = root / f"database/other-daily/{CUTOFF}/universe.json"
    canada, other = read(canada_path)["directories"], read(other_path)["directories"]
    canadian = {}
    for key, listing in canada.items():
        market, state = key.split("/")
        if market not in ("TSX", "TSXV"):
            continue
        suffix = "TO" if market == "TSX" else "V"
        for row in listing:
            code = row.get("Code")
            if isinstance(code, str) and SYMBOL.fullmatch(code):
                symbol = f"{code}.{suffix}"
                item = canadian.setdefault(symbol, {"market": market, "symbol": symbol, "memberships": []})
                if state not in item["memberships"]:
                    item["memberships"].append(state)

    index_membership, nasdaq_provenance = memberships()
    directories = {key: {row["Code"].upper() for row in listing if row.get("Code")}
                   for key, listing in other.items()}
    us = []
    for code, intervals in sorted(index_membership.items()):
        options = [code, code.replace(".", "-"), code.replace("-", ".")]
        resolved = next((ticker for ticker in options if ticker.upper() in
                         directories["US/active"] | directories["US/delisted"]), None)
        us.append({"market": "US", "symbol": f"{resolved or code}.US",
                   "index_code": code, "index_memberships": intervals,
                   "provider_directory_match": resolved is not None,
                   "provider_delisted_directory": bool(resolved and resolved.upper() in directories["US/delisted"])})
    day_entries = list(canadian.values()) + us + crypto_rank()
    day_entries.extend({"market": "FX", "symbol": f"{code}.FOREX"} for code in FX.split())
    day_entries.extend({"market": "Indices", "symbol": f"{code}.INDX", "tradable": False} for code in INDICES)
    payload = {
        "version": "capped-research-v1", "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "development_cutoff_inclusive": str(CUTOFF), "us_membership_start": START,
        "daily": day_entries,
        "intraday": {"markets": ["US", "Crypto"], "frequency": ["5m", "1h"], "provider_start": "2020-10-01"},
        "commodity_reference_only": True,
        "provenance": {"nasdaq100": nasdaq_provenance, "sp500": "EODHD HistoricalTickerComponents",
                       "canadian_provider_snapshot_sha256": content_hash(canada_path.read_bytes()),
                       "us_provider_snapshot_sha256": content_hash(other_path.read_bytes()),
                       "crypto": "Median close times volume on seven EODHD USD bulk snapshots ending at cutoff"},
        "limitations": ["Acquisition membership. Trading eligibility requires independent timing and security identity audit.",
                        "Crypto scope chosen on a development-period snapshot. Earlier crypto test results need a cohort-selection bias flag.",
                        "Nasdaq-100 community snapshots and ticker aliases require reconciliation before formal validation."],
    }
    atomic_json(path, payload)
    return payload


if __name__ == "__main__":
    import argparse
    from collections import Counter
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(dict(Counter(item["market"] for item in build(parser.parse_args().root)["daily"])))
