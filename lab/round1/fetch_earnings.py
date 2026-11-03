"""Historical earnings announcement dates per kept TSX ticker (Yahoo, runs on GitHub runner).
Coverage is limited by Yahoo (recent years only); coverage per ticker is logged."""
import pandas as pd, yfinance as yf
from concurrent.futures import ThreadPoolExecutor

kept = pd.read_csv("data/universe_kept.csv")["ticker"].tolist()
kept = [t for t in kept if t != "XIC.TO"]

def get(t):
    try:
        d = yf.Ticker(t).get_earnings_dates(limit=60)
        if d is None or len(d) == 0:
            return []
        return [(t, pd.Timestamp(x).tz_localize(None).normalize()) for x in d.index]
    except Exception:
        return []

rows = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for i, res in enumerate(ex.map(get, kept)):
        rows += res
        if i % 50 == 0:
            print("done", i, "of", len(kept), flush=True)
df = pd.DataFrame(rows, columns=["ticker", "announce_date"]).drop_duplicates()
df.to_csv("data/earnings_dates.csv", index=False)
print("tickers with dates:", df.ticker.nunique(), "events:", len(df), flush=True)
print(df.assign(y=df.announce_date.dt.year).groupby("y").size().to_string(), flush=True)
