"""
ATR-based stop/target levels that match the winning backtest
(leader_pullback: stop_atr=3.0, tgt_atr=6.0).

Used by both auto_trader.py (to place/monitor exits) and verifier.py
(to tell Claude what the expected levels are), so the live rules and
the backtest can never drift apart again.
"""
from __future__ import annotations

# Single source of truth. Change these only after re-running the lab backtest.
STOP_ATR = 3.0
TARGET_ATR = 6.0
ATR_PERIOD = 14
MAX_STOP_PCT = 8.0        # playbook cap: never risk more than 8% below entry


def wilder_atr(df, period: int = ATR_PERIOD) -> float:
    """Wilder ATR from a daily OHLC frame with High/Low/Close columns (oldest first)."""
    import pandas as pd   # lazy: verifier.py imports this module in workflows without pandas
    if len(df) < period + 1:
        raise ValueError(f"need at least {period + 1} bars, got {len(df)}")
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return float(atr.iloc[-1])


def round_to_tick(price: float, tick: float, side: str) -> float:
    """Round to the exchange tick. Stops round down, targets/buy limits round up,
    so rounding never makes the trade riskier than planned."""
    import math
    from decimal import Decimal
    # Keep as many decimals as the tick has (0.005 -> 3), min 2. Decimal also handles
    # ticks that str() prints in exponent form, e.g. 1e-05.
    decimals = max(2, -Decimal(str(tick)).normalize().as_tuple().exponent)
    steps = price / tick
    if abs(steps - round(steps)) < 1e-6:      # already on a tick (float noise)
        steps = round(steps)
    elif side == "down":
        steps = math.floor(steps)
    else:
        steps = math.ceil(steps)
    return round(steps * tick, decimals)


def levels(entry: float, atr: float, tick: float = 0.05) -> dict:
    """Stop and target for a long entry. Stop is capped at MAX_STOP_PCT below entry."""
    if entry <= 0 or atr <= 0:
        raise ValueError("entry and atr must be positive")
    raw_stop = entry - STOP_ATR * atr
    floor = entry * (1 - MAX_STOP_PCT / 100)
    stop = round_to_tick(max(raw_stop, floor), tick, "down")
    target = round_to_tick(entry + TARGET_ATR * atr, tick, "up")
    return {
        "entry": entry,
        "atr": round(atr, 4),
        "stop": stop,
        "target": target,
        "stop_pct": round((stop / entry - 1) * 100, 2),
        "target_pct": round((target / entry - 1) * 100, 2),
        "capped": raw_stop < floor,   # True means the 8% cap overrode 3x ATR
    }


if __name__ == "__main__":
    # Smoke test: ₹500 stock with ATR ₹12 -> stop 464.00 (-7.2%), target 572.00 (+14.4%)
    print(levels(500.0, 12.0))
    # High-volatility case: ATR ₹20 -> 3x ATR = -12%, capped at -8% -> stop 460.00
    print(levels(500.0, 20.0))
