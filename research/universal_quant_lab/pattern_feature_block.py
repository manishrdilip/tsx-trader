"""Batch causal numeric features on NumPy or CuPy arrays (ticker, time)."""
import numpy as np


def feature_block(high, low, close, window, xp=np):
    """Return close-time values with a NaN warm-up for each lookback."""
    high, low, close = (xp.asarray(values, dtype=xp.float64) for values in (high, low, close))
    if close.ndim != 2 or close.shape != high.shape or close.shape != low.shape:
        raise ValueError("Expected matching ticker-by-time OHLC arrays")
    if not 2 <= window < close.shape[1]:
        raise ValueError("Window must be at least two and shorter than history")
    prices = xp.stack((high, low, close))
    if not bool(xp.isfinite(prices).all()) or bool((low <= 0).any()):
        raise ValueError("Expected finite positive OHLC")
    if bool(((high < close) | (low > close)).any()):
        raise ValueError("Inconsistent OHLC")

    prior = xp.concatenate((close[:, :1], close[:, :-1]), axis=1)
    true_range = xp.maximum(high - low, xp.maximum(xp.abs(high - prior), xp.abs(low - prior)))

    def average(values):
        totals = xp.pad(xp.cumsum(values, axis=1), ((0, 0), (1, 0)))
        result = xp.full_like(values, xp.nan)
        result[:, window - 1:] = (totals[:, window:] - totals[:, :-window]) / window
        return result

    roc = xp.full_like(close, xp.nan)
    roc[:, window:] = close[:, window:] / close[:, :-window] - 1
    return {"sma": average(close), "atr_sma": average(true_range), "roc": roc}
