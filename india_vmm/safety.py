"""Safety checks for the India VMM bot (pure functions, unit-tested in tests/test_safety.py).

1. clean_panel  - fix the price table before signals: one row per date, drop thin rows
                  (e.g. a special/muhurat session only a few stocks traded) that turn every
                  200-day average into NaN.
2. data_health  - stop the run if the market line or most holdings' 200-day lines are missing.
3. stale        - stop the run if the newest close is too old.
4. loss_halt    - no new buys if the bot's money is 15%+ below its 7-day high.
5. price_check  - before placing, compare each order with Kite's live price; drop BUYs that are
                  more than 15% away (bad data), never block SELLs.
"""
import datetime as dt
import os

import numpy as np
import pandas as pd

STALE_BDAYS = int(os.environ.get("INDIA_VMM_STALE_BDAYS", "3"))  # NSE has more one-off holidays
LOSS_HALT_PCT = float(os.environ.get("INDIA_VMM_LOSS_HALT_PCT", "15"))
PRICE_BAND = float(os.environ.get("INDIA_VMM_PRICE_BAND_PCT", "15")) / 100
MIN_ROW_COVERAGE = 0.5  # a session must have prices for at least half the stocks


def clean_panel(closes, volumes):
    closes = closes.copy()
    idx = pd.to_datetime(closes.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    closes.index = idx.normalize()
    volumes = volumes.copy()
    volumes.index = closes.index
    closes = closes.groupby(level=0).last().sort_index()   # merge duplicate dates (mixed time zones)
    volumes = volumes.groupby(level=0).last().reindex(closes.index)
    n = closes.notna().sum(axis=1)
    keep = n >= MIN_ROW_COVERAGE * n.max()
    return closes[keep], volumes[keep]


def data_health(sig, held):
    """Return a list of problems; empty means OK."""
    probs = []
    if sig.get("market_sma") is not None and not np.isfinite(sig.get("market_sma", np.nan)):
        probs.append(f"market line ({sig.get('market')}) 200-day average is missing")
    held = [t for t in held if t in sig["sma200"].index]
    if held:
        bad = [t for t in held if not np.isfinite(sig["sma200"].get(t, np.nan))]
        if len(bad) > 0.3 * len(held):
            probs.append(f"200-day average missing for {len(bad)} of {len(held)} holdings")
    if sig.get("n_eligible", 1) == 0:
        probs.append("no eligible stocks (price data likely broken)")
    return probs


def stale(last_date, today, bdays=None):
    bdays = STALE_BDAYS if bdays is None else bdays
    return int(np.busday_count(pd.Timestamp(last_date).date(), today)) > bdays


def loss_halt(eq_hist, equity, today, pct=None):
    pct = LOSS_HALT_PCT if pct is None else pct
    recent = [v for d, v in eq_hist.items() if (today - dt.date.fromisoformat(d)).days <= 7 and v == v]
    peak = max(recent + [equity])
    return pct > 0 and equity == equity and equity < peak * (1 - pct / 100), peak


def price_check(orders, live, band=None):
    """orders: plan orders (limit = close x1.01 for BUY, x0.97 for SELL). live: {ticker: price}."""
    band = PRICE_BAND if band is None else band
    keep, warns = [], []
    for o in orders:
        ref = o["limit"] / (1.01 if o["action"] == "BUY" else 0.97)
        p = live.get(o["ticker"])
        off = abs(p / ref - 1) if p and p > 0 else None
        if o["action"] == "BUY" and (off is None or off > band):
            warns.append(f"{o['symbol']}: BUY skipped, " + ("no live price" if off is None else
                         f"live {p} vs data {ref:.2f} ({off * 100:.0f}% apart)"))
            continue
        if o["action"] == "SELL" and off is not None and off > band:
            warns.append(f"{o['symbol']}: SELL kept, live {p} vs data {ref:.2f} ({off * 100:.0f}% apart)")
        keep.append(o)
    return keep, warns
