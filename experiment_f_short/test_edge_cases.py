"""Hand-built and randomized synthetic tests for fshort.run. Run: python experiment_f_short/test_edge_cases.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fshort as fs  # noqa: E402

NORMAL = fs.SCENARIOS["normal"]
FAM = "A_trend_pullback"


def build(n=8, tick=("A", "B", "C", "D", "E")):
    dates = pd.bdate_range("2020-01-06", periods=n)
    T, N = n, len(tick)
    O = np.full((T, N), 10.0)
    H, L, C = O + 0.2, O - 0.2, O.copy()
    return dates, tick, O, H, L, C, np.full((T, N), 1.0), np.zeros((T, N)), np.zeros((T, N), bool)


def ind_of(dates, tick, O, H, L, C, ATR, ret63, dv=1e7):
    df = lambda a: pd.DataFrame(a, index=dates, columns=tick)  # noqa: E731
    Cdf = df(C)
    return dict(O=df(O), H=df(H), L=df(L), C=Cdf, atr=df(ATR), CF=Cdf.ffill(), ret63=df(ret63),
                dv50=pd.DataFrame(np.full(C.shape, dv), index=dates, columns=tick),
                dates=dates, tickers=list(tick))


def trades_of(ind, S, hold=2, scen=NORMAL, fam=FAM):
    sig = {fam: pd.DataFrame(S, index=ind["dates"], columns=ind["tickers"])}
    return fs.run(ind, sig, fam, hold, scen)


def case_gap_stop_entry_and_stale_exit():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A", "B", "E"))
    S[0, 0] = True
    C[2, 0] = O[2, 0] = H[2, 0] = L[2, 0] = np.nan       # A: scheduled exit day has no bar
    S[0, 1] = True; O[2, 1] = 8.0; L[2, 1] = 7.9; H[2, 1] = 8.1; C[2, 1] = 8.0   # B: gap through stop
    S[0, 2] = True; L[1, 2] = 8.4                          # E: stop hit on entry session
    tr, _ = trades_of(ind_of(dates, tick, O, H, L, C, ATR, ret63), S)
    got = {r.ticker: r for r in tr.itertuples()}
    assert got["B"].exit_reason == "stop_gap" and abs(got["B"].exit - 8.0 * (1 - side_cost_norm(1e7))) < 0.01
    assert got["E"].exit_reason == "stop_entry_day"
    assert got["A"].exit_reason == "time_delayed", got["A"]
    assert got["A"].exit_date == str(dates[3].date()), "exit must wait for first traded bar"
    assert np.isfinite(got["A"].exit)
    print("ok: gap-through-stop, stop on entry session, stale exit waits for a traded bar")


def side_cost_norm(dv):
    return fs.side_cost(NORMAL, dv)


def case_writedown_after_ten_sessions():
    dates, tick, O, H, L, C, ATR, ret63, S = build(n=20, tick=("A",))
    S[0, 0] = True
    C[2:, 0] = O[2:, 0] = H[2:, 0] = L[2:, 0] = np.nan   # delisted-like: no bars after day 1
    tr, _ = trades_of(ind_of(dates, tick, O, H, L, C, ATR, ret63), S)
    r = tr.iloc[0]
    assert r.exit_reason == "unresolved_writedown", r.exit_reason
    assert r.pending_days == fs.MAX_PENDING_DAYS + 1, r.pending_days
    assert abs(r.exit - fs.DELIST_RECOVERY * 10.0 * (1 - side_cost_norm(1e7))) < 0.01, r.exit
    print("ok: unresolved exit written down after the pending limit, never at a stale price")


def case_gap_above_one_percent_skipped_and_nan_signal_close():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A", "B"))
    S[0, :] = True
    O[1, 0] = 10.2                                        # 2% above signal close 10 -> skip
    C[0, 1] = np.nan                                      # missing signal close -> skip
    tr, _ = trades_of(ind_of(dates, tick, O, H, L, C, ATR, ret63), S)
    assert len(tr) == 0, tr
    print("ok: open >1% above signal close skipped; missing signal close never enters")


def case_competing_signals_three_slots():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A", "B", "C", "D"))
    S[0, :] = True
    ret63[0] = [0.10, 0.40, 0.30, 0.20]
    tr, _ = trades_of(ind_of(dates, tick, O, H, L, C, ATR, ret63), S)
    assert sorted(set(tr.ticker)) == ["B", "C", "D"], set(tr.ticker)
    print("ok: competing signals limited to 3 slots by 63-day return")


def case_cash_and_position_cap():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A",))
    O[1, 0] = 1.0; H[1:, 0] = 1.2; L[1:, 0] = 0.9; C[1:, 0] = 1.0; ATR[0, 0] = 0.01
    C[0, 0] = 1.0; O[0, 0] = 1.0
    S[0, 0] = True
    tr, eq = trades_of(ind_of(dates, tick, O, H, L, C, ATR, ret63), S)
    fill = 1.0 * (1 + side_cost_norm(1e7))
    assert tr.shares.max() * fill <= 5000 / 3 + 1e-9, (tr.shares.max(), fill)
    assert eq.min() > 0
    print("ok: position cap and cash limit respected")


def case_cost_scenarios_order():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A",))
    S[0, 0] = True
    base = ind_of(dates, tick, O, H, L, C, ATR, ret63)
    pnl = {}
    for name, scen in fs.SCENARIOS.items():
        tr, _ = trades_of(base, S, scen=scen)
        pnl[name] = tr.pnl.iloc[0]
    assert pnl["optimistic"] > pnl["normal"] > pnl["stress"], pnl
    print("ok: optimistic > normal > stress on identical flat trade", {k: round(v, 2) for k, v in pnl.items()})


def case_random_no_fill_on_missing_bar():
    rng = np.random.default_rng(7)
    n, N = 300, 12
    dates = pd.bdate_range("2019-01-01", periods=n)
    tick = tuple(f"T{i}" for i in range(N))
    px = 20 * np.exp(np.cumsum(rng.normal(0, 0.02, (n, N)), axis=0))
    O = px * (1 + rng.normal(0, 0.005, (n, N)))
    H = np.maximum(O, px) * 1.01
    L = np.minimum(O, px) * 0.99
    C = px.copy()
    miss = rng.random((n, N)) < 0.08
    for a in (O, H, L, C):
        a[miss] = np.nan
    ATR = np.full((n, N), 0.5)
    ret63 = rng.normal(0, 1, (n, N))
    S = rng.random((n, N)) < 0.05
    ind = ind_of(dates, tick, O, H, L, C, ATR, ret63)
    ind["CF"] = pd.DataFrame(C, index=dates, columns=tick).ffill()
    ind["C"] = pd.DataFrame(C, index=dates, columns=tick)
    checked = 0
    for hold in fs.HOLDS:
        tr, _ = trades_of(ind, S, hold=hold)
        for r in tr.itertuples():
            assert np.isfinite(r.exit) and r.exit > 0, r
            if r.exit_reason in ("time", "time_delayed", "stop", "stop_gap", "stop_entry_day"):
                i = tick.index(r.ticker)
                d = dates.get_loc(pd.Timestamp(r.exit_date))
                assert np.isfinite(ind["O"].values[d, i]) or np.isfinite(ind["C"].values[d, i]), r
                checked += 1
    print(f"ok: randomized panel, 8% missing bars: every exit priced from a traded bar ({checked} checked)")


if __name__ == "__main__":
    case_gap_stop_entry_and_stale_exit()
    case_writedown_after_ten_sessions()
    case_gap_above_one_percent_skipped_and_nan_signal_close()
    case_competing_signals_three_slots()
    case_cash_and_position_cap()
    case_cost_scenarios_order()
    case_random_no_fill_on_missing_bar()
    print("all edge cases passed")
