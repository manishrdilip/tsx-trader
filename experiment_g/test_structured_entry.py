"""Synthetic tests for structured_entry.run. Run: python experiment_g/test_structured_entry.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structured_entry as se  # noqa: E402
import fshort as fs  # noqa: E402

NORMAL = fs.SCENARIOS["normal"]


def build(n=30, tick=("A",)):
    dates = pd.bdate_range("2020-01-06", periods=n)
    T, N = n, len(tick)
    O = np.full((T, N), 10.0); H = O + 0.1; L = O - 0.1; C = O.copy()
    return dates, tick, O, H, L, C, np.full((T, N), 1.0), np.zeros((T, N)), np.zeros((T, N), bool)


def ind_of(dates, tick, O, H, L, C, ATR, ret63):
    df = lambda a: pd.DataFrame(a, index=dates, columns=tick)  # noqa: E731
    Cdf = df(C)
    return dict(O=df(O), H=df(H), L=df(L), C=Cdf, atr=df(ATR), CF=Cdf.ffill(), ret63=df(ret63),
                dv50=pd.DataFrame(np.full(C.shape, 1e7), index=dates, columns=tick),
                dates=dates, tickers=list(tick), liquid=pd.DataFrame(np.ones(C.shape, bool), index=dates, columns=tick))


def go(ind, S, swing_val, variant, scen=NORMAL):
    sw = pd.DataFrame(np.full(S.shape, swing_val, float), index=ind["dates"], columns=ind["tickers"])
    return se.run(ind, S, sw, variant, scen)


def case_single_target():
    dates, tick, O, H, L, C, ATR, r, S = build()
    S[0, 0] = True
    H[2, 0] = 12.5                       # target = 10 + 2R, R = 10 - 8.9 = 1.1 -> 12.2
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    tr, eq, nf = go(ind, S, 9.0, "B0_single_2R")
    assert len(tr) == 1 and tr.iloc[0].exit_reasons == "target", tr
    assert tr.iloc[0].legs_filled == 1 and tr.iloc[0].pnl > 0, tr
    print("ok: single entry hits 2R target on the bar after fill")


def case_structured_partial_fill():
    dates, tick, O, H, L, C, ATR, r, S = build()
    S[0, 0] = True
    L[1, 0] = 9.4                        # leg 2 (limit 9.5) fills; leg 3 (limit 9.0) never reached
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    tr, eq, nf = go(ind, S, 9.0, "S1_struct_025_05_1R")
    assert len(tr) == 1, tr
    assert tr.iloc[0].legs_filled == 2 and tr.iloc[0].legs_total == 3, tr
    print("ok: structured entry fills legs 1 and 2; leg 3 cancelled at window end")


def case_no_leg_beyond_window_and_no_fill_group():
    dates, tick, O, H, L, C, ATR, r, S = build()
    S[0, 0] = True
    L[1:4, 0] = 9.9                      # no limit reached; leg 1 is at the open so it fills
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    tr, eq, nf = go(ind, S, 9.0, "S1_struct_025_05_1R")
    assert tr.iloc[0].legs_filled == 1, tr
    # group that never fills: stop above the open -> skipped, no trade row
    dates, tick, O, H, L, C, ATR, r, S = build()
    S[0, 0] = True
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    tr2, _, _ = go(ind, S, 10.2, "S1_struct_025_05_1R")
    assert len(tr2) == 0, tr2
    print("ok: legs cancelled after the window; signals with stop above the open are skipped")


def case_missing_bar_at_time_exit():
    dates, tick, O, H, L, C, ATR, r, S = build(n=30)
    S[0, 0] = True
    C[20, 0] = np.nan; O[20, 0] = np.nan; H[20, 0] = np.nan; L[20, 0] = np.nan   # scheduled exit bar missing
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    tr, eq, nf = go(ind, S, 9.0, "B0_single_2R")
    row = tr.iloc[0]
    assert row.exit_reasons == "time_delayed", row
    assert row.exit_date == str(dates[21].date()), row
    print("ok: time exit on a missing bar waits for the next traded bar; no stale fill")


def case_cost_ordering():
    dates, tick, O, H, L, C, ATR, r, S = build()
    S[0, 0] = True
    ind = ind_of(dates, tick, O, H, L, C, ATR, r)
    pnl = {k: go(ind, S, 9.0, "B0_single_2R", scen=v)[0].pnl.iloc[0] for k, v in fs.SCENARIOS.items()}
    assert pnl["optimistic"] > pnl["normal"] > pnl["stress"], pnl
    print("ok: optimistic > normal > stress on identical trade")


if __name__ == "__main__":
    case_single_target()
    case_structured_partial_fill()
    case_no_leg_beyond_window_and_no_fill_group()
    case_missing_bar_at_time_exit()
    case_cost_ordering()
    print("all Experiment G tests passed")
