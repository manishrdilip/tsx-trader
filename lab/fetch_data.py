"""Download daily history (2008-today) for every TSX + TSXV stock that was ever
liquid enough to trade, plus the market ETF. Saves lab/data/prices.parquet.
Run on GitHub Actions (Yahoo is reachable there)."""
import json, os, time
import pandas as pd
import yfinance as yf

START = "2008-01-01"
MIN_PRICE, MIN_DVOL, MIN_DAYS = 2.0, 1_000_000, 250
os.makedirs("lab/data", exist_ok=True)
tickers = json.load(open("universe_tickers.json")) + ["XIU.TO", "XIC.TO"]
frames, kept = [], 0
for k in range(0, len(tickers), 200):
    chunk = tickers[k:k + 200]
    for attempt in range(3):
        try:
            raw = yf.download(chunk, start=START, auto_adjust=True, group_by="ticker",
                              threads=True, progress=False)
            break
        except Exception as e:
            print("retry", e); time.sleep(20)
    for t in chunk:
        try:
            d = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
        except Exception:
            continue
        if len(d) < 300:
            continue
        dv = (d["Close"] * d["Volume"]).rolling(20).mean()
        ok = (dv >= MIN_DVOL) & (d["Close"] >= MIN_PRICE)
        if t not in ("XIU.TO", "XIC.TO") and ok.sum() < MIN_DAYS:
            continue
        d = d.astype({"Open": "float32", "High": "float32", "Low": "float32", "Close": "float32"})
        d["Volume"] = d["Volume"].astype("int64")
        d["ticker"] = t
        frames.append(d.reset_index().rename(columns={"index": "Date"}))
        kept += 1
    print(f"{min(k+200, len(tickers))}/{len(tickers)} kept={kept}", flush=True)
    time.sleep(2)
df = pd.concat(frames, ignore_index=True)
df["ticker"] = df["ticker"].astype("category")
df.to_parquet("lab/data/prices.parquet", compression="zstd", index=False)
print("rows", len(df), "tickers", df["ticker"].nunique(),
      "MB", round(os.path.getsize("lab/data/prices.parquet") / 1e6, 1))
