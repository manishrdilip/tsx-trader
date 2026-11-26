"""Causal research features available at the current bar close."""
import pandas as pd


def compute_features(bars, window=20):
    if window < 2:
        raise ValueError("window must be at least 2")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("bars must be strictly chronological")
    close, high, low = (bars[column].astype(float) for column in ("close", "high", "low"))
    prior_close = close.shift()
    true_range = pd.concat([high - low, (high - prior_close).abs(),
                            (low - prior_close).abs()], axis=1).max(axis=1)
    lookback = close.rolling(window)
    span = (high - low).replace(0, float("nan"))
    return pd.DataFrame({
        "sma": lookback.mean(),
        "ema": close.ewm(span=window, adjust=False, min_periods=window).mean(),
        "atr_sma": true_range.rolling(window).mean(),
        "roc": close / close.shift(window) - 1,
        "close_location": (close - low) / span,
        "prior_range_high": high.shift().rolling(window).max(),
        "prior_range_low": low.shift().rolling(window).min(),
    }, index=bars.index)
