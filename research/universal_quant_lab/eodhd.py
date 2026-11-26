"""Acquire bounded EODHD research datasets using a local token."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener
from uuid import uuid4

import pandas as pd

from warehouse import ingest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_key():
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as settings:
                value, _ = winreg.QueryValueEx(settings, "EODHD_API_KEY")
                if value.strip():
                    return value.strip()
        except FileNotFoundError:
            pass
    return os.environ.get("EODHD_API_KEY", "").strip()


def query(endpoint, **params):
    token = local_key()
    if not token:
        return "key_missing", None
    url = "https://eodhd.com/api/" + endpoint + "?" + urlencode(
        {**params, "fmt": "json", "api_token": token}
    )
    try:
        with build_opener(NoRedirect()).open(url, timeout=40) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None
    except (URLError, OSError, ValueError):
        return "transport_or_invalid_json", None


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def stage_daily(root, market, symbol, rows):
    import numpy as np

    frame = pd.DataFrame(rows).sort_values("date")
    dates = [date.fromisoformat(value).isoformat() for value in frame["date"]]
    if len(set(dates)) != len(dates):
        raise ValueError("Duplicate trading dates")
    prices = ["open", "high", "low", "close", "adjusted_close"]
    frame[prices] = frame[prices].apply(pd.to_numeric, errors="raise")
    if (frame[prices] <= 0).any().any() or not np.isfinite(frame[prices]).all().all():
        raise ValueError("Nonpositive or nonfinite price")
    if (frame.high < frame[["open", "close", "low"]].max(axis=1)).any() or (
        frame.low > frame[["open", "close"]].min(axis=1)
    ).any():
        raise ValueError("Inconsistent OHLC")
    volume = pd.to_numeric(frame.get("volume", pd.Series(index=frame.index, dtype=float)), errors="raise")
    if (volume < 0).any() or np.isinf(volume).any():
        raise ValueError("Invalid volume")
    frame["volume"] = volume.astype(object).where(volume.notna(), None)
    frame["session"] = dates
    frame["timestamp"] = [day + "T00:00:00+00:00" for day in dates]
    records = frame[["timestamp", "session", *prices, "volume"]].to_dict("records")
    source_bytes = json.dumps(rows, sort_keys=True).encode()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    dest = root / "database" / "staging" / "eodhd" / symbol / f"{source_hash}-1d.json"
    atomic_json(dest, records)
    audit = {
        "symbol": symbol, "bars": len(records), "first": dates[0], "last": dates[-1],
        "missing_volume": int(volume.isna().sum()),
        "source_sha256": source_hash,
        "output_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "timestamp_semantics": "UTC midnight date label only; no close availability timestamp",
        "price_semantics": "Provider OHLC and separate provider adjusted_close",
        "limitations": ["Exchange calendar, corporate-action reconciliation and point-in-time listing eligibility pending"],
    }
    atomic_json(dest.with_suffix(".audit.json"), audit)
    return {**ingest(root, dest, "eodhd", market, symbol, "1d"), **audit}


def acquire(root, cutoff, inputs):
    results = []
    for item in inputs:
        market, symbol = item.split(":", 1)
        if not re.fullmatch(r"[A-Za-z0-9_]+", market) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", symbol):
            raise ValueError("Invalid market or symbol")
        status, rows = query(f"eod/{symbol}", to=cutoff.isoformat(), order="a")
        result = {"market": market, "symbol": symbol, "status": status}
        if status == 200 and isinstance(rows, list) and rows:
            try:
                if any(date.fromisoformat(row["date"]) > cutoff for row in rows):
                    raise ValueError("Response contains dates after cutoff")
                result.update(stage_daily(root, market, symbol, rows))
            except (KeyError, ValueError, TypeError) as error:
                result["validation"] = type(error).__name__
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k in (
            "market", "symbol", "status", "rows", "first", "last", "validation"
        )}), flush=True)
        if status in (401, 429, "key_missing"):
            break
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    atomic_json(root / "reports" / f"eodhd-acquisition-{stamp}.json", results)
    return len(results) == len(inputs) and all("rows" in result for result in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("symbols", nargs="+", help="MARKET:PROVIDER_SYMBOL")
    parser.add_argument("--to", type=date.fromisoformat, default=datetime.now(timezone.utc).date()-timedelta(days=1))
    args = parser.parse_args()
    if args.to >= datetime.now(timezone.utc).date():
        parser.error("Use a cutoff before today's UTC date")
    raise SystemExit(0 if acquire(args.root, args.to, args.symbols) else 1)
