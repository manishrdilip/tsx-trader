"""Technical features computed using information available at the close of each bar."""
import numpy as np
import pandas as pd
from numba import njit

from pattern_oscillators import oscillator_grid


@njit
def parabola(high, low, step, cap):
    result = np.full(len(high), np.nan)
    if len(high) < 2:
        return result
    rising = high[1] >= high[0]
    extreme = max(high[0], high[1]) if rising else min(low[0], low[1])
    stop = min(low[0], low[1]) if rising else max(high[0], high[1])
    acceleration = step
    for i in range(2, len(high)):
        value = stop + acceleration * (extreme - stop)
        if rising:
            value = min(value, low[i-1], low[i-2])
            if low[i] <= value:
                rising, value, extreme, acceleration = False, extreme, low[i], step
            elif high[i] > extreme:
                extreme, acceleration = high[i], min(cap, acceleration + step)
        else:
            value = max(value, high[i-1], high[i-2])
            if high[i] >= value:
                rising, value, extreme, acceleration = True, extreme, high[i], step
            elif low[i] < extreme:
                extreme, acceleration = low[i], min(cap, acceleration + step)
        result[i] = value
        stop = value
    return result


@njit
def supertrend(high, low, close, atr, multiple):
    result = np.full(len(close), np.nan)
    upper, lower, upward = 0., 0., True
    for i in range(1, len(close)):
        if not np.isfinite(atr[i]):
            continue
        middle = (high[i] + low[i]) / 2
        u, l = middle + multiple * atr[i], middle - multiple * atr[i]
        if not np.isfinite(atr[i-1]):
            upper, lower = u, l
        else:
            upper = u if u < upper or close[i-1] > upper else upper
            lower = l if l > lower or close[i-1] < lower else lower
            upward = close[i] >= lower if upward else close[i] > upper
        result[i] = lower if upward else upper
    return result


def weighted(series, weights):
    out = np.full(len(series), np.nan)
    if len(series) >= len(weights):
        out[len(weights)-1:] = np.convolve(series.to_numpy(), weights[::-1]/weights.sum(), mode="valid")
    return pd.Series(out, index=series.index)


@njit
def aroon(values, n, upper):
    result = np.full(len(values), np.nan)
    for i in range(n, len(values)):
        best = i
        for j in range(i-1, i-n-1, -1):
            if (upper and values[j] > values[best]) or (not upper and values[j] < values[best]):
                best = j
        result[i] = 100*(1-(i-best)/n)
    return result


def feature_grid(bars, volume_eligible):
    features = oscillator_grid(bars, volume_eligible=volume_eligible)
    high, low, close, volume = (bars[k].astype(float) for k in ("high", "low", "close", "volume"))
    prior = close.shift()
    tr = pd.concat([high-low, (high-prior).abs(), (low-prior).abs()], axis=1).max(axis=1)
    typical = (high + low + close) / 3
    allowed = pd.Series(volume_eligible, index=bars.index).astype(bool) & volume.notna() & volume.ge(0)
    volume = volume.where(allowed)
    group = (~allowed).cumsum()
    flow_ratio = ((2*close-high-low)/(high-low).replace(0, np.nan)).where(high.ne(low), 0)
    flow = flow_ratio * volume
    gain, loss = high.diff(), -low.diff()
    plus, minus = gain.where((gain > loss) & (gain > 0), 0), loss.where((loss > gain) & (loss > 0), 0)
    columns = {
        "obv": (np.sign(close.diff()).fillna(0)*volume).groupby(group).cumsum(),
        "ad": flow.groupby(group).cumsum(),
        "force": close.diff()*volume,
        "psar": parabola(high.to_numpy(), low.to_numpy(), .02, .2),
        "fvg_up": low - high.shift(2),
        "fvg_down": low.shift(2) - high,
    }
    for n in (5, 10, 14, 20, 30, 40, 50, 100, 200):
        fast = close.ewm(span=n, min_periods=n, adjust=False).mean()
        atr = tr.ewm(alpha=1/n, min_periods=n, adjust=False).mean()
        w = np.arange(1, n+1, dtype=float)
        half = np.arange(1, n//2+1, dtype=float)
        final = np.arange(1, int(n**.5)+1, dtype=float)
        hull = weighted(2*weighted(close, half)-weighted(close, w), final)
        top, bottom = high.shift(1).rolling(n).max(), low.shift(1).rolling(n).min()
        up_break, down_break = close.gt(top), close.lt(bottom)
        previous_break = pd.Series(np.where(up_break, 1., np.where(down_break, -1., np.nan)), index=bars.index).ffill().shift()
        average = close.rolling(n).mean()
        std = close.rolling(n).std(ddof=0)
        plus_dm = 100 * plus.ewm(alpha=1/n, min_periods=n, adjust=False).mean() / atr.replace(0, np.nan)
        minus_dm = 100 * minus.ewm(alpha=1/n, min_periods=n, adjust=False).mean() / atr.replace(0, np.nan)
        dx = 100*(plus_dm-minus_dm).abs()/(plus_dm+minus_dm).replace(0, np.nan)
        total_volume = volume.rolling(n).sum().replace(0, np.nan)
        columns.update({
            f"sma_{n}": average, f"ema_{n}": fast, f"hma_{n}": hull,
            f"atr_{n}": atr, f"adx_{n}": dx.ewm(alpha=1/n, min_periods=n, adjust=False).mean(),
            f"supertrend_{n}": supertrend(high.to_numpy(), low.to_numpy(), close.to_numpy(), atr.to_numpy(), 3.),
            f"aroon_up_{n}": aroon(high.to_numpy(), n, True),
            f"aroon_down_{n}": aroon(low.to_numpy(), n, False),
            f"donchian_upper_{n}": top, f"donchian_lower_{n}": bottom,
            f"keltner_upper_{n}": fast + 2*atr, f"keltner_lower_{n}": fast - 2*atr,
            f"vwap_{n}": (typical*volume).rolling(n).sum()/total_volume,
            f"cmf_{n}": flow.rolling(n).sum()/total_volume,
            f"bos_up_{n}": (close-top), f"bos_down_{n}": (bottom-close),
            f"sweep_high_{n}": (high-top).where(close < top),
            f"sweep_low_{n}": (bottom-low).where(close > bottom),
            f"choch_up_{n}": (close-top).where(previous_break < 0),
            f"choch_down_{n}": (bottom-close).where(previous_break > 0),
            f"equal_high_distance_{n}": (high-top).abs()/atr.replace(0, np.nan),
            f"equal_low_distance_{n}": (low-bottom).abs()/atr.replace(0, np.nan),
        })
        for width in (1.5, 2., 2.5):
            columns[f"boll_up_{n}_{width}"] = average + width*std
            columns[f"boll_down_{n}_{width}"] = average - width*std
    bearish = close.lt(bars.open)
    bullish = close.gt(bars.open)
    columns["order_block_bull_proxy"] = low.where(bearish).ffill().shift().where(close.gt(high.shift().rolling(20).max()))
    columns["order_block_bear_proxy"] = high.where(bullish).ffill().shift().where(close.lt(low.shift().rolling(20).min()))
    for short, long, signal in ((8, 17, 6), (12, 26, 9), (19, 39, 9)):
        a = close.ewm(span=short, min_periods=short, adjust=False).mean()
        b = close.ewm(span=long, min_periods=long, adjust=False).mean()
        line = a-b
        columns[f"macd_{short}_{long}"] = line
        columns[f"macd_hist_{short}_{long}"] = line-line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    def midpoint(n):
        return (high.rolling(n).max()+low.rolling(n).min())/2
    columns.update(ichimoku_conversion=midpoint(9), ichimoku_base=midpoint(26),
                   ichimoku_cloud_a=((midpoint(9)+midpoint(26))/2).shift(26),
                   ichimoku_cloud_b=midpoint(52).shift(26))
    return pd.concat((features, pd.DataFrame(columns, index=bars.index)), axis=1)
