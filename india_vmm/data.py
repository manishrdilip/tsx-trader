"""Price loaders for the India VMM bot.

offline: NSE rows from a local parquet (same format as the lab's prices.parquet).
live:    yfinance daily bars for .NS tickers (free; use Kite historical data once the Connect plan is on).
"""
import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


def load_parquet(path, tickers=None):
    cols = ["Date", "Close", "Volume", "ticker"]
    df = pd.read_parquet(path, columns=cols)
    df["ticker"] = df["ticker"].astype(str)
    keep = df["ticker"].str.endswith(".NS") | df["ticker"].str.startswith("^")
    df = df[keep]
    if tickers is not None:
        df = df[df["ticker"].isin(set(tickers))]
    closes = df.pivot_table(index="Date", columns="ticker", values="Close", aggfunc="last")
    volumes = df.pivot_table(index="Date", columns="ticker", values="Volume", aggfunc="last")
    return trim_completed(closes, volumes)


def load_yfinance(tickers, period="2y"):
    import yfinance as yf

    frames = []
    for i in range(0, len(tickers), 100):
        frames.append(yf.download(tickers[i:i + 100], period=period, interval="1d", auto_adjust=True,
                                  progress=False, group_by="ticker", threads=True))
    D = pd.concat(frames, axis=1)
    lv = D.columns.get_level_values(0).unique()
    closes = pd.DataFrame({t: D[t]["Close"] for t in lv})
    volumes = pd.DataFrame({t: D[t]["Volume"] for t in lv})
    closes = closes.dropna(how="all")
    return trim_completed(closes, volumes.reindex(closes.index))


def trim_completed(closes, volumes):
    """Drop today's (IST) session so only completed sessions are used."""
    today = dt.datetime.now(IST).date()
    keep = [d for d in closes.index if pd.Timestamp(d).date() < today]
    return closes.loc[keep], volumes.reindex(closes.index).loc[keep]
