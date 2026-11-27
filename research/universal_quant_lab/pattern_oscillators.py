"""Causal oscillator grids for the V2 development feature cache."""
import numpy as np
import pandas as pd
from numba import njit


@njit
def mean_deviation(series, window):
    values = np.full(len(series), np.nan)
    for i in range(window-1, len(series)):
        sample = series[i-window+1:i+1]
        center = np.mean(sample)
        values[i] = np.mean(np.abs(sample-center))
    return values


def oscillator_grid(bars, periods=range(5, 51), volume_eligible=None):
    """Build numeric oscillator values; screen thresholds later without copying them."""
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("Expected ordered, unique bar times")
    high, low, close, volume = (bars[name].astype("float64") for name in ("high", "low", "close", "volume"))
    if (not np.isfinite(bars[["high", "low", "close"]].to_numpy()).all() or
            (low.le(0) | close.lt(low) | close.gt(high)).any()):
        raise ValueError("Expected valid OHLC inputs")
    eligible = volume.notna() & volume.ge(0) & np.isfinite(volume)
    if volume_eligible is not None:
        eligible &= pd.Series(volume_eligible, index=bars.index).fillna(False).astype(bool)
    change = close.diff()
    typical = (high + low + close) / 3
    raw_flow = (typical * volume).where(eligible)
    rising = typical.diff().gt(0)
    falling = typical.diff().lt(0)
    positive_flow = raw_flow.where(rising, 0).where(eligible)
    negative_flow = raw_flow.where(falling, 0).where(eligible)
    up, down = change.clip(lower=0), -change.clip(upper=0)
    values = {}
    for n in periods:
        if type(n) is not int or not 5 <= n <= 50:
            raise ValueError("Oscillator periods are 5 through 50")
        avg_gain = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        avg_loss = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        rsi = 100 * avg_gain / (avg_gain + avg_loss).replace(0, np.nan)
        recent_rsi = rsi.rolling(n)
        rsi_low, rsi_high = recent_rsi.min(), recent_rsi.max()
        peak, trough = high.rolling(n).max(), low.rolling(n).min()
        denominator = (peak - trough).replace(0, np.nan)
        typical_rolling = typical.rolling(n)
        absolute_deviation = pd.Series(mean_deviation(typical.to_numpy(), n), index=bars.index)
        positive, negative = positive_flow.rolling(n).sum(), negative_flow.rolling(n).sum()
        values.update({
            f"rsi_{n}": rsi,
            f"stochastic_{n}": 100 * (close - trough) / denominator,
            f"stoch_rsi_{n}": 100 * (rsi - rsi_low) / (rsi_high - rsi_low).replace(0, np.nan),
            f"williams_r_{n}": -100 * (peak - close) / denominator,
            f"cci_{n}": (typical - typical_rolling.mean()) / (0.015 * absolute_deviation.replace(0, np.nan)),
            f"mfi_{n}": 100 * positive / (positive + negative).replace(0, np.nan),
        })
    return pd.DataFrame(values, index=bars.index)
