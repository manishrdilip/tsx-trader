"""Trade simulator (numba). Signal at the close of day i; entry on day i+1.

Entry modes
  0 = buy at next open (skipped if it opens > MAX_GAP above the signal close)
  1 = buy-stop at the signal day's high (fills only if day i+1 trades above it;
      fill = max(open, trigger); skipped if it opens > MAX_GAP above the trigger)

Exit (first one hit wins, checked in this conservative order each day):
  gap through stop at open -> fill at open (real loss recorded)
  stop touched             -> fill at stop
  gap over target at open  -> fill at open
  target touched           -> fill at target
  mean-reversion exit      -> at close (1: close > SMA5, 2: close > prior day's high)
  max hold reached         -> at close
On the ENTRY day, if both stop and target are inside the bar we assume the stop
hit first (daily bars can't tell, so we take the worse case).
Costs: COST per side (spread + slippage; Wealthsimple charges no commission).
"""
import numpy as np
from numba import njit

COST = 0.001
MAX_GAP = 0.02


@njit(cache=True)
def _sim_one(O, H, L, C, S5, ATR, sig, mode, stop_pct, tgt_pct, stop_atr, tgt_atr,
             hold, mr, max_gap, cost, out_i, out_j, out_r, k):
    n = len(C)
    i = 0
    while i < n - 1:
        if not sig[i]:
            i += 1
            continue
        e = i + 1
        if mode == 0:
            if not np.isfinite(O[e]) or O[e] > C[i] * (1 + max_gap):
                i += 1
                continue
            entry = O[e]
        else:
            trig = H[i] * 1.001
            if not np.isfinite(H[e]) or H[e] < trig or O[e] > trig * (1 + max_gap):
                i += 1
                continue
            entry = max(O[e], trig)
        if stop_atr > 0:
            sd = stop_atr * ATR[i]
            td = tgt_atr * ATR[i] if tgt_atr > 0 else 1e9
            stop, tgt = entry - sd, entry + td
        else:
            stop = entry * (1 - stop_pct) if stop_pct > 0 else -1.0
            tgt = entry * (1 + tgt_pct) if tgt_pct > 0 else 1e18
        px = -1.0
        j = e
        last = min(e + hold, n) - 1
        while j <= last:
            if j > e and O[j] <= stop:
                px = O[j]
                break
            if L[j] <= stop:
                px = stop
                break
            if j > e and O[j] >= tgt:
                px = O[j]
                break
            if H[j] >= tgt:
                px = tgt
                break
            if mr == 1 and C[j] > S5[j]:
                px = C[j]
                break
            if mr == 2 and j > e and C[j] > H[j - 1]:
                px = C[j]
                break
            if j == last:
                px = C[j]
                break
            j += 1
        if px < 0:          # ran out of data
            break
        out_i[k] = i
        out_j[k] = j
        out_r[k] = px / entry - 1 - 2 * cost
        k += 1
        i = j + 1
    return k


def simulate(I, sig, mode=0, stop_pct=0.0, tgt_pct=0.0, stop_atr=0.0, tgt_atr=0.0,
             hold=10, mr=0):
    """Run one setup x exit over every ticker. Returns arrays (ticker_idx, entry_day_idx, exit_day_idx, ret)."""
    O, H, L, C = (I[k].values for k in ("O", "H", "L", "C"))
    S5, A = I["sma5"].values, I["atr14"].values
    S = sig.fillna(False).values.astype(np.bool_)
    T, N = C.shape
    out_t, out_i, out_j, out_r = [], [], [], []
    bi = np.empty(T, np.int64); bj = np.empty(T, np.int64); br = np.empty(T, np.float64)
    for t in range(N):
        if not S[:, t].any():
            continue
        k = _sim_one(O[:, t], H[:, t], L[:, t], C[:, t], S5[:, t], A[:, t], S[:, t], mode,
                     stop_pct, tgt_pct, stop_atr, tgt_atr, hold, mr, MAX_GAP, COST, bi, bj, br, 0)
        if k:
            out_t.append(np.full(k, t)); out_i.append(bi[:k].copy())
            out_j.append(bj[:k].copy()); out_r.append(br[:k].copy())
    if not out_r:
        return np.array([], int), np.array([], int), np.array([], int), np.array([])
    return (np.concatenate(out_t), np.concatenate(out_i), np.concatenate(out_j), np.concatenate(out_r))


def summarize(dates, ti, ei, xi, r, split=None):
    """Stats for a set of trades; optional split date -> (train, test) dicts."""
    def st(mask):
        rr = r[mask]
        if len(rr) == 0:
            return None
        w = rr > 0
        gw, gl = rr[w].sum(), -rr[~w].sum()
        yrs = max((dates[xi[mask]].max() - dates[ei[mask]].min()) / np.timedelta64(1, "D") / 365.25, 0.5)
        return dict(trades=int(len(rr)), win=float(w.mean()), avg=float(rr.mean()),
                    avg_win=float(rr[w].mean()) if w.any() else 0.0,
                    avg_loss=float(rr[~w].mean()) if (~w).any() else 0.0,
                    pf=float(gw / gl) if gl > 0 else float("inf"),
                    hold=float((xi[mask] - ei[mask]).mean() + 1),
                    per_year=float(len(rr) / yrs))
    allm = np.ones(len(r), bool)
    if split is None:
        return st(allm)
    sd = np.datetime64(split)
    d = dates[ei]
    return st(d < sd), st(d >= sd)
