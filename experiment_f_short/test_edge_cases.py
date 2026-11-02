"""Hand-built edge-case tests for fshort.run. Each case has known prices and expected exits."""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fshort as fs

def build(n=8, tick=("A", "B", "C", "D", "E")):
    dates = pd.bdate_range("2020-01-06", periods=n)
    T, N = n, len(tick)
    O = np.full((T, N), 10.0); H = O + 0.2; L = O - 0.2; C = O.copy()
    ATR = np.full((T, N), 1.0)
    ret63 = np.zeros((T, N))
    S = np.zeros((T, N), bool)
    return dates, tick, O, H, L, C, ATR, ret63, S

def ind_of(dates, tick, O, H, L, C, ATR, ret63):
    df = lambda a: pd.DataFrame(a, index=dates, columns=tick)
    Cdf = df(C)
    return dict(O=df(O), H=df(H), L=df(L), C=Cdf, atr=df(ATR), CF=Cdf.ffill(), ret63=df(ret63),
                dates=dates, tickers=list(tick))

def trades_of(ind, S, fam_hold=2, fee=0.001):
    sig = {"A_trend_pullback": pd.DataFrame(S, index=ind["dates"], columns=ind["tickers"])}
    tr, eq = fs.run(ind, sig, "A_trend_pullback", fam_hold, fee)
    return tr, eq

def case_gap_stop_and_stale_exit_and_entry_day_stop():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A", "B", "E"))
    # A: entry 10 at day1 open; hold 2 -> exit close of day2, but day2 bar is missing
    S[0, 0] = True
    C[2, 0] = np.nan; O[2, 0] = np.nan; H[2, 0] = np.nan; L[2, 0] = np.nan
    # B: entry 10; day2 opens at 8.0 (gap through 8.5 stop)
    S[0, 1] = True; O[2, 1] = 8.0; L[2, 1] = 7.9; H[2, 1] = 8.1; C[2, 1] = 8.0
    # E: entry 10; day1 low 8.4 hits stop 8.5 on entry day
    S[0, 2] = True; L[1, 2] = 8.4
    ind = ind_of(dates, tick, O, H, L, C, ATR, ret63)
    tr, _ = trades_of(ind, S)
    got = {r.ticker: (r.exit_reason, round(r.exit, 2)) for r in tr.itertuples()}
    assert got["A"][0] == "time_stale_no_bar", got
    assert got["B"] == ("stop_gap", 8.0), got
    assert got["E"] == ("stop_entry_day", 8.5), got
    print("ok: gap-through-stop, stale exit on missing bar, entry-day stop")

def case_competing_signals_three_slots():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A", "B", "C", "D"))
    S[0, :] = True                       # four signals on the same day
    ret63[0] = [0.10, 0.40, 0.30, 0.20] # ranking: B, C, D, A
    ind = ind_of(dates, tick, O, H, L, C, ATR, ret63)
    tr, _ = trades_of(ind, S)
    entered = sorted(set(tr.ticker))
    assert entered == ["B", "C", "D"], entered          # top three by 63-day return; A skipped
    print("ok: competing signals limited to 3 slots by ranking")

def case_cash_constraint():
    dates, tick, O, H, L, C, ATR, ret63, S = build(tick=("A",))
    O[1, 0] = 1.0; H[1:, 0] = 1.2; L[1:, 0] = 0.9; C[1:, 0] = 1.0; ATR[0, 0] = 0.01
    S[0, 0] = True
    ind = ind_of(dates, tick, O, H, L, C, ATR, ret63)
    tr, eq = trades_of(ind, S)
    # tiny ATR -> risk sizing wants huge size; 1/3 position cap must hold
    assert tr.shares.max() * 1.0 * 1.001 <= 5000 / 3 + 1, tr.shares.max()
    assert eq.min() > 0
    print("ok: position cap and cash limit respected")

if __name__ == "__main__":
    case_gap_stop_and_stale_exit_and_entry_day_stop()
    case_competing_signals_three_slots()
    case_cash_constraint()
    print("all edge cases passed")
