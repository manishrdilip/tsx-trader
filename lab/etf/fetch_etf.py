"""Fetch ~20 years of adjusted daily prices for the Canadian ETF list (Yahoo, .TO tickers) on GitHub runners.
Writes data/etf_{Close,Open,High,Low,Volume}.parquet and data/etf_failed.csv.
"""
import os
import pandas as pd
import yfinance as yf

os.makedirs("data", exist_ok=True)
tick = [t.strip() for t in open("lab/etf/etf_tickers.txt") if t.strip()]
tick = sorted(set(tick))
frames = {f: [] for f in ["Open", "High", "Low", "Close", "Volume"]}
failed = []
for i in range(0, len(tick), 40):
    chunk = tick[i:i + 40]
    df = yf.download(chunk, start="2004-01-01", end="2026-11-03", group_by="ticker",
                     auto_adjust=True, progress=False, threads=True)
    for t in chunk:
        try:
            sub = df[t]
        except KeyError:
            failed.append(t); continue
        if sub.dropna(how="all").empty:
            failed.append(t); continue
        for f in frames:
            frames[f].append(sub[f].rename(t))
    print("chunk", i, "done", flush=True)

for f, lst in frames.items():
    out = pd.concat(lst, axis=1).sort_index()
    out.to_parquet(f"data/etf_{f}.parquet", compression="zstd")
    print(f, out.shape, out.index.min(), out.index.max())
pd.Series(failed, name="ticker").to_csv("data/etf_failed.csv", index=False)
print("failed", len(failed))
