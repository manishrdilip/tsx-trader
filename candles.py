"""
Bullish candlestick patterns (rules from wrtrading.com candlestick pattern guide).
Scanner D fires when one of these appears in the last 2 days AND the stock is
in a long-term uptrend (scanner A handles that). Reversal patterns are only
counted after a short-term dip (close below its level 5 days earlier), i.e. a
pullback ending inside the bigger uptrend.
"""
import numpy as np
import pandas as pd


def _parts(d):
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    bull, bear = c > o, c < o
    avg_body = body.rolling(20).mean()
    return o, h, l, c, body, rng, upper, lower, bull, bear, avg_body


def patterns(d):
    """Return DataFrame of boolean columns, one per bullish pattern."""
    o, h, l, c, body, rng, upper, lower, bull, bear, ab = _parts(d)
    p = {}
    S = lambda s, k=1: s.shift(k)
    dip = c.shift(1) < c.shift(6)                       # short-term pullback before the signal
    big = body > ab                                     # "large" candle
    small = body < 0.5 * ab
    doji = body <= 0.1 * rng

    p["Hammer"] = dip & (lower >= 2 * body) & (upper <= 0.3 * body + 0.1 * rng) & ~doji
    p["Bullish Pin Bar"] = dip & (lower >= 0.6 * rng) & (body <= 0.3 * rng)
    p["Dragonfly Doji"] = dip & doji & (lower >= 0.7 * rng) & (upper <= 0.1 * rng)
    p["Bullish Engulfing"] = dip & S(bear) & bull & (o <= S(c)) & (c >= S(o)) & (body > S(body))
    p["Bullish Harami"] = dip & S(bear) & S(big) & bull & (o >= S(c)) & (c <= S(o)) & small
    p["Piercing Line"] = dip & S(bear) & S(big) & bull & (o < S(c)) & (c > (S(o) + S(c)) / 2) & (c < S(o))
    p["Tweezer Bottom"] = dip & S(bear) & bull & ((l - S(l)).abs() <= 0.002 * c)
    p["Bullish Belt Hold"] = dip & bull & big & (lower <= 0.05 * rng)
    p["Bullish Kicker"] = S(bear) & S(big) & bull & (o > S(o)) & (l > S(o))
    p["Morning Star"] = (dip & S(bear, 2) & S(big, 2) & S(small) & bull & big
                         & (c > (S(o, 2) + S(c, 2)) / 2))
    p["Three Outside Up"] = (S(bear, 2) & S(bull) & (S(o) <= S(c, 2)) & (S(c) >= S(o, 2))
                             & bull & (c > S(c)))
    p["Three White Soldiers"] = (bull & S(bull) & S(bull, 2) & (c > S(c)) & (S(c) > S(c, 2))
                                 & big & S(big) & S(big, 2) & (upper < 0.3 * body))
    # continuation patterns (valid inside an uptrend without a dip)
    p["Rising Three / Mat Hold"] = (S(bull, 4) & S(big, 4)
                                    & S(small, 3) & S(small, 2) & S(small)
                                    & (pd.concat([S(l, 3), S(l, 2), S(l)], axis=1).min(axis=1) > S(l, 4))
                                    & bull & big & (c > S(c, 4)))
    p["Gap Up"] = (o > S(h)) & bull & (o / S(c) - 1 > 0.01)
    return pd.DataFrame(p, index=d.index).fillna(False)


def signal(d):
    """True when any bullish pattern appeared today or yesterday."""
    pt = patterns(d)
    any_today = pt.any(axis=1)
    return any_today | any_today.shift(1, fill_value=False)


def latest_names(d):
    pt = patterns(d).iloc[-2:]
    return ", ".join(sorted({col for col in pt.columns if pt[col].any()}))
