"""Download TSX daily prices from Yahoo (runs on GitHub Actions), keep liquid names, save parquet.
Survivorship: universe = today's listings (yfinance has no delisted names). Label results accordingly.
"""
import json, os
import pandas as pd
import yfinance as yf

START = "2014-01-01"
FIELDS = ["Open", "High", "Low", "Close", "Volume"]
MIN_MEDIAN_DOLLAR_VOL = 300_000  # CAD per day, 2016-2026 median (plan rule)
OUT = "data"

tick = [t for t in json.load(open("universe_tickers.json")) if t.endswith(".TO")]
tick = sorted(set(t for t in tick if t != "XIC.TO")) + ["XIC.TO"]
frames = {f: [] for f in FIELDS}
failed = []

for i in range(0, len(tick), 150):
    chunk = tick[i:i + 150]
    df = yf.download(chunk, start=START, auto_adjust=True, progress=False,
                     group_by="ticker", threads=True, ignore_tz=True)
    if not isinstance(df.columns, pd.MultiIndex):
        df = pd.concat({chunk[0]: df}, axis=1)
    got = set(df.columns.get_level_values(0))
    failed += [t for t in chunk if t not in got]
    for f in FIELDS:
        frames[f].append(pd.DataFrame({t: df[t][f] for t in chunk if t in got}))
    print(f"chunk {i}: {len(got)} ok", flush=True)

wide = {f: pd.concat(frames[f], axis=1) for f in FIELDS}
close, vol = wide["Close"], wide["Volume"]
recent = close.loc["2016-01-01":]
med_dv = (recent * vol.loc["2016-01-01":]).median()
bars = recent.notna().sum()
keep = [t for t in close.columns if t != "XIC.TO"
        and med_dv.get(t, 0) >= MIN_MEDIAN_DOLLAR_VOL and bars.get(t, 0) >= 1000]
keep = keep + ["XIC.TO"]

os.makedirs(OUT, exist_ok=True)
for f in FIELDS:
    wide[f][keep].astype("float32").to_parquet(f"{OUT}/tsx_{f}.parquet", compression="zstd")
pd.DataFrame({"ticker": keep, "median_dollar_vol_2016_26": [med_dv.get(t) for t in keep]}).to_csv(f"{OUT}/universe_kept.csv", index=False)
pd.Series(failed, name="failed_download").to_csv(f"{OUT}/failed_downloads.csv", index=False)
print("requested", len(tick), "kept", len(keep), "failed", len(failed), flush=True)
