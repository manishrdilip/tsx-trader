"""
Market brake for leaders.py AND the lab backtest. One function, two forms:

    market_ok_series(close)  -> boolean Series, for the vectorised backtest
    market_ok(close)         -> bool for today, for leaders.py

Both apply the same rule, so live and backtest can't drift apart (the same
problem the +3%/-1% rule caused). The reviewer's version only changed leaders.py.
Its "34% -> under 18% drawdown, 30%+ returns" claim did not hold up. Lab re-run
(leader_pullback 3x/6x ATR, 30d, 2 slots, 2009-2026):
  sma200: CAGR 26.2%, max drawdown 34.4%, 4 losing years of 18
  dual  : CAGR 23.0%, max drawdown 46.3%, 3 losing years of 18
so the default stays "sma200".

Rule:
  "sma200": close > 200-day SMA                            (current live rule)
  "dual"  : close > 200-day SMA AND 20-day EMA > 50-day SMA (reviewer's proposal)
Missing data (too little history) counts as NOT ok, so the brake fails safe.
"""
from __future__ import annotations

import pandas as pd

BRAKE = "sma200"   # "dual" tested worse (see above); re-run the lab before changing


def market_ok_series(close: pd.Series, brake: str = BRAKE) -> pd.Series:
    close = close.astype(float)
    sma200 = close.rolling(200, min_periods=150).mean()
    macro = (close > sma200) & sma200.notna()
    if brake == "sma200":
        return macro
    if brake != "dual":
        raise ValueError(f"unknown brake {brake!r}")
    ema20 = close.ewm(span=20, adjust=False, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=40).mean()
    tactical = (ema20 > sma50) & ema20.notna() & sma50.notna()
    return macro & tactical


def market_ok(close: pd.Series, brake: str = BRAKE) -> bool:
    return bool(market_ok_series(close.dropna(), brake).iloc[-1])


# In leaders.py, replace the old two lines with:
#     from market_filter import market_ok
#     mkt_up = market_ok(C[MARKET])
#
# The lab uses market_ok_series() for I["mkt_up"] (lab/indicators.py). No shift
# is needed there: a signal on day t's close is entered at day t+1's open.
