"""Exact bounded top-K selection on numeric result columns."""
import numpy as np


def select(ids, score, profit, drawdown, tail, stability, k=100):
    """Use canonical ID as the final tie breaker within a frozen job."""
    if k < 1:
        raise ValueError("Expected a positive retention limit")
    keys = np.rec.fromarrays(
        [-score, -profit, drawdown, tail, -stability, ids],
        names="score,profit,drawdown,tail,stability,identifier",
    )
    if len(keys) > k:
        # Numeric partial selection avoids sorting the common case. Resolve
        # boundary ties using every remaining ordering field.
        threshold = np.partition(score, len(score) - k)[len(score) - k]
        above = np.flatnonzero(score > threshold)
        equal = np.flatnonzero(score == threshold)
        need = k - len(above)
        if len(equal) > need:
            equal = equal[np.argpartition(keys[equal], need - 1)[:need]]
        chosen = np.concatenate((above, equal))
    else:
        chosen = np.arange(len(keys))
    return chosen[np.argsort(keys[chosen])]


if __name__ == "__main__":
    import time
    rng = np.random.default_rng(6031)
    ids = np.arange(1_000_000)
    profit = rng.integers(-50, 50, len(ids))
    risk = rng.integers(0, 10, len(ids))
    start = time.perf_counter()
    result = select(ids, profit, profit, risk, risk, profit)
    elapsed = time.perf_counter() - start
    start = time.perf_counter()
    expected = np.lexsort((ids, -profit, risk, risk, -profit, -profit))[:100]
    assert np.array_equal(result, expected)
    print("Million-row tie regression passed. Partial/full-sort seconds:", elapsed, time.perf_counter()-start)
