"""Vectorised indicators on wide (date x ticker) frames.
Everything uses only data up to and including the signal day (no look-ahead)."""
import numpy as np
import pandas as pd


def load_panel(path="lab/data/prices.parquet", exclude=()):
    df = pd.read_parquet(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df["ticker"] = df["ticker"].astype(str)
    df = df.drop_duplicates(["Date", "ticker"])
    df = df[~df["ticker"].isin(set(exclude))]
    df = df[(df["Volume"] > 0) & (df["High"] >= df["Low"])]
    p = {k: df.pivot(index="Date", columns="ticker", values=k).sort_index().astype("float64")
         for k in ("Open", "High", "Low", "Close", "Volume")}
    # unadjusted splits / bad prints: drop everything before the last suspicious 1-day jump
    r = p["Close"] / p["Close"].ffill().shift(1)
    bad = (r > 2.5) | (r < 0.4)
    last_bad = bad[::-1].cummax()[::-1]          # True on and before the last bad day
    for k in p:
        p[k] = p[k].mask(last_bad)
    # halted / missing days inside a listing: flat bar at the last close, zero volume
    C = p["Close"]
    inside = C.ffill().notna() & C.bfill().notna()
    Cf = C.ffill().where(inside)
    for k in ("Open", "High", "Low"):
        p[k] = p[k].where(C.notna(), Cf)
    p["Close"] = Cf
    p["Volume"] = p["Volume"].where(C.notna(), 0.0).where(inside)
    return p


def non_stocks(path="lab/data/prices.parquet", keep=("XIU.TO", "XIC.TO")):
    """Tickers that are not operating companies (ETFs, BetaPro, CDRs, split corps...)."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import stock_filter
    t = pd.read_parquet(path, columns=["ticker"])["ticker"].astype(str).unique()
    return [x for x in t if x not in keep and not stock_filter.is_stock(x)]


def sma(x, n):
    return x.rolling(n, min_periods=n).mean()


def ema(x, n):
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def true_range(h, l, c):
    pc = c.shift(1)
    return np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))


def atr(h, l, c, n=14):
    return true_range(h, l, c).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    mdm = dn.where((dn > up) & (dn > 0), 0.0)
    tr = true_range(h, l, c).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    mdi = 100 * mdm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def build(p, market="XIU.TO"):
    """Return dict of indicator frames + market series."""
    O, H, L, C, V = p["Open"], p["High"], p["Low"], p["Close"], p["Volume"]
    I = dict(O=O, H=H, L=L, C=C, V=V)
    for n in (5, 10, 20, 50, 150, 200):
        I[f"sma{n}"] = sma(C, n)
    I["ema10"], I["ema20"], I["ema50"] = ema(C, 10), ema(C, 20), ema(C, 50)
    I["rsi2"], I["rsi14"] = rsi(C, 2), rsi(C, 14)
    I["atr14"] = atr(H, L, C, 14)
    I["atr10"], I["atr50"] = atr(H, L, C, 10), atr(H, L, C, 50)
    I["adx14"] = adx(H, L, C, 14)
    rng = (H - L).replace(0, np.nan)
    I["ibs"] = (C - L) / rng
    I["vol20"], I["vol50"] = sma(V, 20), sma(V, 50)
    I["dvol20"] = sma(C * V, 20)
    I["hi20"] = H.rolling(20).max()
    I["hi252"] = H.rolling(252).max()
    I["lo252"] = L.rolling(252).min()
    I["ret21"], I["ret63"], I["ret126"] = C.pct_change(21), C.pct_change(63), C.pct_change(126)
    # cross-sectional relative-strength percentile (IBD-style weighting), among liquid names
    liquid = (I["dvol20"] >= 1_000_000) & (C >= 2)
    rs_raw = 0.4 * C.pct_change(63) + 0.2 * C.pct_change(126) + 0.2 * C.pct_change(189) + 0.2 * C.pct_change(252)
    I["rs_rank"] = rs_raw.where(liquid).rank(axis=1, pct=True)
    I["ret63_rank"] = C.pct_change(63).where(liquid).rank(axis=1, pct=True)
    I["liquid"] = liquid
    mc = C[market]
    I["mkt_up"] = (mc > sma(mc, 200))
    I["mkt_up50"] = (mc > sma(mc, 50)) & I["mkt_up"]
    return I
