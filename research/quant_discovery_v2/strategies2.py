"""Batch 2 strategies: Exp 3 (statistical ranking), Exp 5 (Little Rizzy), Exp 6 (vol/trend asymmetry), Exp 2 (GP tree)."""
import numpy as np, pandas as pd
from strategies import _rank


def _vmm_like(pre, S, slots, base_mask=None):
    col = {t: k for k, t in enumerate(pre.tk)}
    q90 = np.nanquantile(np.where(pre.e, S, np.nan), 0.9, axis=1)
    def scores(i):
        if not pre.P.xiu_ok[i]: return None
        m = pre.e[i] & pre.above[i] & (S[i] >= q90[i])
        if base_mask is not None: m &= base_mask[i]
        return _rank(pre, i, S[i], m)
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s200[i, k]: return "below 200d"
        if np.isfinite(pre.r12[i, k]) and pre.r12[i, k] < pre.top40[i]: return "out of top 40%"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True,
                trail=28, never_rebuy_trail=True)


class Stat:
    def __init__(self, P):
        C, V = P.C, P.V
        r = C.pct_change(fill_method=None); x = P.xiu.pct_change()
        mr, mx = r.rolling(252).mean(), x.rolling(252).mean()
        cov = r.mul(x, axis=0).rolling(252).mean() - mr.mul(mx, axis=0)
        varx = x.rolling(252).var(ddof=0)
        beta = cov.div(varx, axis=0)
        sd = r.rolling(252).std(ddof=0)
        self.corr = (cov.div(sd.mul(np.sqrt(varx), axis=0))).values
        x12 = P.xiu / P.xiu.shift(252) - 1
        self.resid = (P.r12 - beta.mul(x12, axis=0)).values
        self.sharpe6 = ((C / C.shift(126) - 1) / (r.rolling(126).std() * np.sqrt(126))).values
        self.amihud = (r.abs() / (C * V)).rolling(60).mean().values
        rk = P.r12.where(P.elig).rank(axis=1, pct=True)
        self.tophalf = (rk >= 0.5).values


def exp3(pre, st, which):
    if which == "S1_residual_mom": return _vmm_like(pre, st.resid, 20)
    if which == "S2_sharpe6": return _vmm_like(pre, st.sharpe6, 20)
    if which == "S3_lowcorr": return _vmm_like(pre, -st.corr, 20, base_mask=st.tophalf)
    if which == "S4_illiquid": return _vmm_like(pre, st.amihud, 20, base_mask=st.tophalf)


def rizzy_signals(P, k=5):
    """Causal measured-move breakout signals on closes. Returns entry flag, target, stop arrays (days x tickers)."""
    C = P.C.values; n, m = C.shape
    sma20 = P.C.rolling(20).mean().values
    ent = np.zeros((n, m), bool); tgt = np.full((n, m), np.nan); stp = np.full((n, m), np.nan)
    for j in range(m):
        c = C[:, j]; ok = np.isfinite(c)
        if ok.sum() < 100: continue
        highs, lows = [], []
        prev_line = None
        for i in range(2 * k, n):
            p = i - k  # pivot candidate becomes confirmed at day i
            w = c[p - k:p + k + 1]
            if np.isfinite(w).all():
                if c[p] == w.max(): highs.append((p, c[p]))
                if c[p] == w.min(): lows.append((p, c[p]))
            if len(highs) < 2 or not np.isfinite(c[i]):
                prev_line = None; continue
            (j1, v1), (j2, v2) = highs[-2], highs[-1]
            if not v2 < v1 or j2 <= j1:
                prev_line = None; continue
            line = v2 + (v2 - v1) / (j2 - j1) * (i - j2)
            if prev_line is not None and c[i] > line and c[i - 1] <= prev_line and c[i] > sma20[i, j]:
                seg = c[j1:i]; lo = np.nanmin(seg)
                sl = [v for (q, v) in lows if q > j1 and v < c[i]]
                if sl and line - lo > 0:
                    ent[i, j] = True; tgt[i, j] = c[i] + (line - lo); stp[i, j] = sl[-1]
            prev_line = line
    return ent, tgt, stp


def rizzy(pre, sig, slots):
    ent, tgt, stp = sig; col = {t: k for k, t in enumerate(pre.tk)}
    def scores(i):
        up = (tgt[i] / pre.c[i] - 1)
        return _rank(pre, i, up, pre.e[i] & ent[i])
    def exit_(i, t, p):
        k = col[t]; s = p["ent"] - 1; c = pre.c[i, k]
        if np.isfinite(stp[s, k]) and c <= stp[s, k]: return "stop"
        if np.isfinite(tgt[s, k]) and c >= tgt[s, k]: return "target"
        if i - p["ent"] >= 30: return "30 days"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True)


class Asym:
    def __init__(self, P):
        C, V = P.C, P.V
        r = C.pct_change(fill_method=None)
        self.vc = (r.rolling(20).std() / r.rolling(120).std()).values
        self.acc = ((C / C.shift(60) - 1) - (C / C.shift(120) - 1) / 2).values
        self.rv = (V.rolling(20).mean() / V.rolling(120).mean()).values
        self.nh = (C >= 0.95 * C.rolling(252).max()).values
        self.r60 = (C / C.shift(60) - 1).values
        self.breadth = (C > P.sma200).where(P.elig).mean(axis=1).values


def asym(pre, a, q, mult, b, slots=10):
    col = {t: k for k, t in enumerate(pre.tk)}
    def scores(i):
        if a.breadth[i] < b: return None
        m = pre.e[i] & (a.vc[i] <= q) & (a.acc[i] > 0) & (a.rv[i] >= mult) & a.nh[i]
        return _rank(pre, i, a.r60[i], m)
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s50[i, k]: return "below 50d"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True, trail=20)


def gp_tree(pre, score_arr, slots=20):
    return _vmm_like(pre, score_arr, slots)
