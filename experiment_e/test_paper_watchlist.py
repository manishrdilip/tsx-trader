"""Idempotency test: running the same watchlist write twice must leave exactly one copy of each (as_of, ticker).
Run: python experiment_e/test_paper_watchlist.py"""
import csv
import os
import sys
import tempfile
import types

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import paper_trade as pt  # noqa: E402


def fake_panel(dates, tick):
    cal = pd.DatetimeIndex(dates)
    return types.SimpleNamespace(cal=cal, tick=list(tick))


def main():
    tick = ["AAA.TO", "BBB.TO", "CCC.TO"]
    P = fake_panel(["2026-10-29", "2026-10-30"], tick)
    weights = {"2026-10-30": np.array([0.5, 0.3, 0.2])}
    old_select = pt.ee.select
    pt.ee.select = lambda P_, cfg, g: weights["2026-10-30"]
    try:
        with tempfile.TemporaryDirectory() as root:
            acct = pt.Account.__new__(pt.Account)
            acct.dir = os.path.join(root, "acct")
            acct.cfg = {}
            os.makedirs(acct.dir, exist_ok=True)
            acct.watchlist(P, 1)
            acct.watchlist(P, 1)   # same session, second run
            path = os.path.join(acct.dir, "watchlist.csv")
            rows = list(csv.reader(open(path)))[1:]
            keys = [(r[0], r[2]) for r in rows]
            assert len(keys) == 3 and len(set(keys)) == 3, keys
            assert keys == [("2026-10-30", t) for t in tick], keys
            # a later session with a different list must still append
            weights["2026-10-30"] = np.array([0.1, 0.0, 0.0])
            P2 = fake_panel(["2026-10-29", "2026-10-30", "2026-11-02"], tick)
            acct.watchlist(P2, 2)
            acct.watchlist(P2, 2)
            rows = list(csv.reader(open(path)))[1:]
            assert len(rows) == 3 + 1, rows   # 2026-11-02 only ticker AAA; old rows untouched
            assert rows[0][0] == "2026-10-30" and rows[0][3] == "0.5"
            assert sum(1 for r in rows if r[0] == "2026-11-02") == 1
    finally:
        pt.ee.select = old_select
    print("ok: repeated watchlist writes create one copy per (as_of, ticker); history untouched")


if __name__ == "__main__":
    main()
