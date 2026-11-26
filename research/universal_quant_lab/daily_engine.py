"""Compiled daily swing screening with deterministic canonical strategy IDs."""
from itertools import combinations

import numpy as np
from numba import njit, prange
import pandas as pd

from features import compute_features

WINDOWS = (5, 8, 13, 20, 30, 45, 65, 90)
HOLDS = (2, 5, 10)
FAMILIES = {
    "sma": (-.02, -.01, .01, .02),
    "ema": (-.03, -.015, .015, .03),
    "atr_sma": (.005, .012, .02, .035),
    "roc": (-.04, -.02, .02, .04),
    "close_location": (.35, .45, .55, .65),
    "prior_range_high": (-.07, -.04, -.015, 0.),
    "prior_range_low": (.01, .03, .06, .10),
}
RULES_PER_FAMILY = len(WINDOWS) * 4


def space(depth):
    if not 1 <= depth <= len(FAMILIES):
        raise ValueError("Unsupported exact depth")
    groups = np.array(list(combinations(range(len(FAMILIES)), depth)), dtype=np.int64)
    return groups, len(groups) * RULES_PER_FAMILY ** depth * len(HOLDS)


def feature_rules(bars):
    close = bars.close
    outputs = {family: [] for family in FAMILIES}
    for window in WINDOWS:
        features = compute_features(bars, window)
        values = {
            "sma": close / features.sma - 1,
            "ema": close / features.ema - 1,
            "atr_sma": features.atr_sma / close,
            "roc": features.roc,
            "close_location": features.close_location.rolling(window).mean(),
            "prior_range_high": close / features.prior_range_high - 1,
            "prior_range_low": close / features.prior_range_low - 1,
        }
        for name, thresholds in FAMILIES.items():
            for threshold in thresholds:
                outputs[name].append((values[name] > threshold).to_numpy(dtype=np.bool_))
    return np.ascontiguousarray([outputs[name] for name in FAMILIES], dtype=np.bool_)


@njit(cache=True)
def simulate(opens, rules, families, variants, start, end, hold, cash, cost):
    """Close signal, next-open entry, exit after hold open-to-open intervals."""
    initial = cash
    peak = cash
    worst = 0.
    wins = 0.
    losses = 0.
    trades = 0
    signal = start
    while signal + 1 + hold < end:
        match = True
        for k in range(len(families)):
            if not rules[families[k], variants[k], signal]:
                match = False
                break
        if not match:
            signal += 1
            continue
        entry = signal + 1
        exit_bar = entry + hold
        paid = opens[entry] * (1 + cost)
        units = np.floor(cash / paid)
        if units < 1:
            signal += 1
            continue
        pnl = units * (opens[exit_bar] * (1 - cost) - paid)
        cash += pnl
        peak = max(peak, cash)
        worst = max(worst, (peak - cash) / peak)
        wins += max(pnl, 0.)
        losses += max(-pnl, 0.)
        trades += 1
        signal = exit_bar
    return (cash - initial, worst, wins, losses, trades)


@njit(cache=True, parallel=True)
def evaluate(ids, groups, opens, rules, splits, cash, cost):
    output = np.empty((len(ids), 10), dtype=np.float64)
    depth = groups.shape[1]
    variants_per_group = RULES_PER_FAMILY ** depth
    for i in prange(len(ids)):
        candidate = ids[i]
        hold = HOLDS[candidate % len(HOLDS)]
        encoded = candidate // len(HOLDS)
        family = groups[encoded // variants_per_group]
        variants = np.empty(depth, dtype=np.int64)
        for k in range(depth):
            variants[k] = encoded % RULES_PER_FAMILY
            encoded //= RULES_PER_FAMILY
        for j in range(2):
            result = simulate(opens, rules, family, variants, splits[j], splits[j+1], hold, cash, cost)
            base = j * 5
            output[i, base] = result[0]
            output[i, base + 1] = result[1]
            output[i, base + 2] = result[2]
            output[i, base + 3] = result[3]
            output[i, base + 4] = result[4]
    return output


def selftest():
    bars = pd.DataFrame({
        "open": [10., 12., 8., 15., 20., 22.],
        "high": [12., 13., 10., 16., 22., 23.],
        "low": [9., 11., 7., 14., 19., 21.],
        "close": [11., 12., 9., 15., 21., 22.],
    })
    rules = np.ones((1, 1, len(bars)), dtype=np.bool_)
    opens = bars.open.to_numpy()
    selected = np.array([0], dtype=np.int64)
    # Signal at 0, enter at 1 for 12, exit at 3 for 15. No boundary crossing.
    result = simulate(opens, rules, selected, selected, 0, 4, 2, 120., 0.)
    assert result == (30., 0., 30., 0., 1)
    assert simulate(opens, rules, selected, selected, 0, 3, 2, 120., 0.)[-1] == 0
    cost_result = simulate(opens, rules, selected, selected, 0, 4, 2, 120., .01)
    assert np.isclose(cost_result[0], 9 * (15 * .99 - 12 * 1.01))
    frame = pd.concat([bars] * 35, ignore_index=True)
    assert np.array_equal(feature_rules(frame)[:, :, :150], feature_rules(frame.iloc[:150]))
    return "PASS: next-open fills, overnight holds, split isolation, costs, causal feature prefix"


if __name__ == "__main__":
    print(selftest())
