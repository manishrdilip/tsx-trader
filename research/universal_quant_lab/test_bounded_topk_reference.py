"""Check bounded_topk.select against an exact full-sort reference on tie-heavy data.

Run from the repository root:  python research/universal_quant_lab/test_bounded_topk_reference.py
Requires numpy. Uses only synthetic inputs; it is an engineering check, not market evidence.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounded_topk import select  # noqa: E402


def reference(ids, score, profit, drawdown, tail, stability, k):
    # Documented order: score desc, profit desc, drawdown asc, tail asc, stability desc, id asc.
    # np.lexsort treats its last key as primary.
    return np.lexsort((ids, -stability, tail, drawdown, -profit, -score))[:k]


def main(trials=400, seed=7):
    rng = np.random.default_rng(seed)
    mismatches = 0
    for trial in range(trials):
        n = int(rng.integers(1, 5000))
        k = int(rng.integers(1, 120))
        ids = rng.permutation(n * 3)[:n].astype(np.int64)
        # Small integer domains force heavy ties in every ordering field.
        score, profit, drawdown, tail, stability = (
            rng.integers(-3, 4, n).astype(float),
            rng.integers(-3, 4, n).astype(float),
            rng.integers(0, 3, n).astype(float),
            rng.integers(0, 3, n).astype(float),
            rng.integers(0, 3, n).astype(float),
        )
        got = select(ids, score, profit, drawdown, tail, stability, k=k)
        exp = reference(ids, score, profit, drawdown, tail, stability, k)
        if not np.array_equal(ids[got], ids[exp]):
            mismatches += 1
            print(f"mismatch trial={trial} n={n} k={k}")
    print(f"bounded_topk reference cases={trials} mismatches={mismatches}")
    return mismatches


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
