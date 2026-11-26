"""Extended causal daily indicator registry, pinned separately from the pilot."""
from itertools import combinations

import numpy as np

from daily_engine import FAMILIES, HOLDS, RULES_PER_FAMILY, WINDOWS, feature_rules

ADDITIONAL = {
    "rsi": (30., 45., 55., 70.),
    "bollinger_z": (-1.5, -.5, .5, 1.5),
    "efficiency_ratio": (.15, .25, .4, .55),
}


def space(depth):
    count = len(FAMILIES) + len(ADDITIONAL)
    if not 1 <= depth <= count:
        raise ValueError("Unsupported exact depth")
    groups = np.array(list(combinations(range(count), depth)), dtype=np.int64)
    return groups, len(groups) * RULES_PER_FAMILY ** depth * len(HOLDS)


def signals(bars):
    out = {key: [] for key in ADDITIONAL}
    close = bars.close
    change = close.diff()
    for window in WINDOWS:
        up = change.clip(lower=0).ewm(alpha=1/window, adjust=False, min_periods=window).mean()
        down = -change.clip(upper=0).ewm(alpha=1/window, adjust=False, min_periods=window).mean()
        rsi = 100 * up / (up + down).replace(0, float("nan"))
        average = close.rolling(window)
        bollinger = (close - average.mean()) / average.std(ddof=0).replace(0, float("nan"))
        efficiency = (close - close.shift(window)).abs() / change.abs().rolling(window).sum().replace(0, float("nan"))
        for name, result in zip(ADDITIONAL, (rsi, bollinger, efficiency)):
            for threshold in ADDITIONAL[name]:
                out[name].append((result > threshold).to_numpy(dtype=np.bool_))
    return np.concatenate((feature_rules(bars), np.asarray(list(out.values()), dtype=np.bool_)))
