"""Download daily history (2008-today) for TSX/TSXV, US (NASDAQ/NYSE/AMEX) and
NSE (India) stocks that are liquid enough to trade. Saves lab/data/prices.parquet
and lab/data/failed.csv (every ticker that was dropped, with the reason).
"""
import csv, io, json, os, time, urllib.request
import pandas as pd
import yfinance as yf

START = "2008-01-01"
BATCH = 50
RETRIES = 4
MIN_DAYS = 250

RULES = {
    "TSX":  {"min_price": 2.0,  "min_dvol": 1_000_000},
    "US":   {"min_price": 2.0,  "min_dvol": 1_000_000},
    "NSE":  {"min_price": 20.0, "min_dvol": 50_000_000},
}
BENCHMARKS = ["XIU.TO", "XIC.TO", "SPY", "NIFTYBEES.NS"]


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def tsx_universe():
    return [t for t in json.load(open("universe_tickers.json")) if t.endswith((".TO", ".V"))]


def us_universe():
    tickers = set()
    for url, sym_col in [
        ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol"),
        ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol"),
    ]:
        for r in csv.DictReader(io.StringIO(fetch_text(url)), delimiter="|"):
            sym = (r.get(sym_col) or "").strip()
            if not sym or r.get("ETF") == "Y" or r.get("Test Issue") == "Y" or "$" in sym or "." in sym:
                continue
            tickers.add(sym)
    return sorted(tickers)


def nse_universe():
    try:
        rows = csv.DictReader(io.StringIO(fetch_text(
            "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv")))
        return [f"{r['SYMBOL'].strip()}.NS" for r in rows if r.get("SYMBOL")]
    except Exception as e:
        print(f"NSE list download failed ({e}); using india_scan.py fallback", flush=True)
        import re
        src = open("india_scan.py").read()
        return sorted(set(re.findall(r'"([A-Z0-9&\-]+\.NS)"', src)))


def market_of(t):
    if t.endswith((".TO", ".V")):
        return "TSX"
    if t.endswith(".NS"):
        return "NSE"
    return "US"


def download_batch(chunk):
    for attempt in range(RETRIES):
        try:
            raw = yf.download(chunk, start=START, auto_adjust=True, group_by="ticker",
                              threads=True, progress=False)
            if raw is not None and not raw.empty:
                return raw
        except Exception as e:
            print(f"  batch retry {attempt+1}: {e}", flush=True)
        time.sleep(10 * (attempt + 1))
    return None


def download_single(t):
    for attempt in range(RETRIES):
        try:
            raw = yf.download(t, start=START, auto_adjust=True, progress=False)
            if raw is not None and not raw.empty:
                return raw
        except Exception as e:
            print(f"  single retry {t} {attempt+1}: {e}", flush=True)
        time.sleep(5 * (attempt + 1))
    return None


def process_ticker(t, raw, frames, failed, kept, is_single=False):
    m = market_of(t)
    try:
        if is_single:
            d = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
        else:
            d = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        failed.append((t, "no data returned by Yahoo"))
        return False
    if t not in BENCHMARKS:
        rule = RULES[m]
        if len(d) < 300:
            failed.append((t, f"only {len(d)} bars"))
            return False
        dv = (d["Close"] * d["Volume"]).rolling(20).mean()
        ok = (dv >= rule["min_dvol"]) & (d["Close"] >= rule["min_price"])
        if ok.sum() < MIN_DAYS:
            failed.append((t, "below liquidity filter"))
            return False
    d = d.astype({"Open": "float32", "High": "float32", "Low": "float32", "Close": "float32"})
    d["Volume"] = d["Volume"].astype("int64")
    d["ticker"] = t
    d["market"] = m if t not in BENCHMARKS else "BENCH"
    frames.append(d.reset_index().rename(columns={"index": "Date"}))
    kept[m] = kept.get(m, 0) + 1
    return True


def main():
    os.makedirs("lab/data", exist_ok=True)
    universe = {"TSX": tsx_universe(), "US": us_universe(), "NSE": nse_universe()}
    print({k: len(v) for k, v in universe.items()}, "tickers before download", flush=True)

    all_tickers = [t for m in universe for t in universe[m]] + BENCHMARKS
    frames, failed = [], []
    kept = {"TSX": 0, "US": 0, "NSE": 0}
    retry_single = []

    for k in range(0, len(all_tickers), BATCH):
        chunk = all_tickers[k:k + BATCH]
        raw = download_batch(chunk)
        if raw is None:
            failed += [(t, "batch download failed after retries") for t in chunk]
            continue
        for t in chunk:
            if not process_ticker(t, raw, frames, failed, kept):
                # If it failed with no data, queue for single retry
                if failed and failed[-1][0] == t and failed[-1][1] == "no data returned by Yahoo":
                    retry_single.append(t)
                    failed.pop()  # remove so we can re-add after retry
        print(f"{min(k+BATCH, len(all_tickers))}/{len(all_tickers)} kept={kept}", flush=True)
        time.sleep(2)

    # Retry tickers that returned no data in batch, one at a time
    if retry_single:
        print(f"Retrying {len(retry_single)} tickers one-by-one...", flush=True)
        for t in retry_single:
            raw = download_single(t)
            if raw is None:
                failed.append((t, "no data returned by Yahoo (single retry failed)"))
                continue
            process_ticker(t, raw, frames, failed, kept, is_single=True)
            time.sleep(0.5)

    if not frames:
        print("No data kept", flush=True)
        return

    df = pd.concat(frames, ignore_index=True)
    df["ticker"] = df["ticker"].astype("category")
    df["market"] = df["market"].astype("category")
    df.to_parquet("lab/data/prices.parquet", compression="zstd", index=False)

    with open("lab/data/failed.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "reason"])
        w.writerows(failed)

    print("SUMMARY", flush=True)
    for m in ("TSX", "US", "NSE"):
        print(f"  {m}: kept {kept[m]} of {len(universe[m])}", flush=True)
    print(f"  total rows {len(df)}, tickers {df['ticker'].nunique()}, dropped {len(failed)} (see lab/data/failed.csv)", flush=True)


if __name__ == "__main__":
    main()
