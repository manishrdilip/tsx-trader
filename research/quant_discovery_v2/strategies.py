"""Strategy definitions for Quant Discovery V2 (each matches PROTOCOL.md)."""
import numpy as np, pandas as pd

SECTOR_ETFS = ["XEG.TO", "XFN.TO", "XIT.TO", "XMA.TO", "ZUT.TO", "XRE.TO", "XST.TO", "XHC.TO", "XGD.TO", "XUT.TO"]


class Pre:
    """Precomputed signal tables (numpy) shared by all strategies."""
    def __init__(self, P):
        C, O, V = P.C, P.O, P.V
        self.P = P; self.tk = np.array(P.tk)
        self.c = C.values; self.e = P.elig.values; self.s200 = P.sma200.values
        self.above = (C > P.sma200).values
        self.r12 = P.r12.values
        # VMM top-40% cut per day (over eligible)
        r = P.r12.where(P.elig)
        self.top40 = r.quantile(0.6, axis=1).values; self.top10 = r.quantile(0.9, axis=1).values
        ret = C.pct_change(fill_method=None)
        vol = ret.rolling(252).std()
        # A: 12-1 momentum / vol
        a = (C.shift(21) / C.shift(252) - 1) / vol
        self.A = a.where(P.elig).values
        # B: z-score blend of 3/6/12m returns (cross-sectional each day)
        zs = []
        for n in (63, 126, 252):
            x = (C / C.shift(n) - 1).where(P.elig)
            zs.append(x.sub(x.mean(1), axis=0).div(x.std(1), axis=0))
        self.B = ((zs[0] + zs[1] + zs[2]) / 3).values
        # C: RSI(2)
        d = C.diff(); up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
        self.rsi2 = (100 - 100 / (1 + up / dn)).values
        self.s5 = P.sma5.values; self.s50 = P.sma50.values
        # D: volatility squeeze breakout
        rng = (C.rolling(20).max() - C.rolling(20).min()) / C
        self.sq = (rng.shift(1) <= rng.shift(1).rolling(252).quantile(0.10)).values
        self.hi55 = (C >= C.rolling(55).max()).values
        # E: 52w high on volume
        self.hi252 = (C >= C.rolling(252).max()).values
        self.vratio = (V / V.rolling(50).mean().shift(1)).values
        # F: gap-down reversal
        prevc = C.shift(1)
        self.gapdn = ((O <= prevc * 0.95) & (C > O)).values
        self.gapsize = (O / prevc - 1).values
        # month starts
        m = P.dates.to_period("M")
        self.mstart = np.r_[True, m[1:] != m[:-1]]
        self.r6 = (C / C.shift(126) - 1).values


def _rank(pre, i, score, mask):
    s = np.where(mask & np.isfinite(score), score, np.nan)
    ok = np.isfinite(s)
    if not ok.any(): return None
    o = np.argsort(-s[ok]); idx = np.where(ok)[0][o]
    return pd.Series(s[idx], pre.tk[idx])


def vmm_exact(pre):
    """Live RRSP 'daily' mode, current workflow settings (see PROTOCOL.md)."""
    col = {t: k for k, t in enumerate(pre.tk)}
    def scores(i):
        if not pre.P.xiu_ok[i]: return None
        m = pre.e[i] & pre.above[i] & (pre.r12[i] >= pre.top10[i])
        return _rank(pre, i, pre.r12[i], m)
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s200[i, k]: return "below 200d"
        if np.isfinite(pre.r12[i, k]) and pre.r12[i, k] < pre.top40[i]: return "out of top 40%"
    return dict(scores=scores, exit=exit_, slots=lambda eq: int(min(20, max(5, eq // 400))), max_hold=20,
                buy_day=lambda i: True, trail=28, never_rebuy_trail=True, park="VEQT.TO", guard=True, order_cap=True)


def mom_variant(pre, field, slots):
    col = {t: k for k, t in enumerate(pre.tk)}
    S = getattr(pre, field)
    q90 = np.nanquantile(S, 0.9, axis=1); q60 = np.nanquantile(S, 0.6, axis=1)
    def scores(i):
        if not pre.P.xiu_ok[i]: return None
        return _rank(pre, i, S[i], pre.e[i] & pre.above[i] & (S[i] >= q90[i]))
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s200[i, k]: return "below 200d"
        if np.isfinite(S[i, k]) and S[i, k] < q60[i]: return "out of top 40%"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True,
                trail=28, never_rebuy_trail=True)


def mean_rev(pre, thr, slots):
    col = {t: k for k, t in enumerate(pre.tk)}
    def scores(i):
        return _rank(pre, i, -pre.rsi2[i], pre.e[i] & pre.above[i] & (pre.rsi2[i] < thr))
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] > pre.s5[i, k]: return "above 5d"
        if i - p["ent"] >= 10: return "10 days"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True)


def squeeze(pre, slots):
    def scores(i):
        return _rank(pre, i, pre.r12[i], pre.e[i] & pre.sq[i] & pre.hi55[i])
    return dict(scores=scores, exit=lambda i, t, p: None, slots=lambda eq: slots, max_hold=slots,
                buy_day=lambda i: True, trail=20)


def hi_volume(pre, slots):
    col = {t: k for k, t in enumerate(pre.tk)}
    def scores(i):
        return _rank(pre, i, pre.vratio[i], pre.e[i] & pre.hi252[i] & (pre.vratio[i] >= 2))
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s50[i, k]: return "below 50d"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True)


def gap_rev(pre, slots):
    def scores(i):
        return _rank(pre, i, -pre.gapsize[i], pre.e[i] & pre.above[i] & pre.gapdn[i])
    def exit_(i, t, p):
        if i - p["ent"] >= 5: return "5 days"
    return dict(scores=scores, exit=exit_, slots=lambda eq: slots, max_hold=slots, buy_day=lambda i: True)


def sector_rot(pre, k):
    ids = [list(pre.tk).index(t) for t in SECTOR_ETFS if t in list(pre.tk)]
    cur = {"top": set()}
    def pick(i):
        s = {pre.tk[j]: pre.r6[i, j] for j in ids if np.isfinite(pre.r6[i, j]) and np.isfinite(pre.s200[i, j])
             and pre.c[i, j] > pre.s200[i, j]}
        return sorted(s, key=s.get, reverse=True)[:k]
    def scores(i):
        top = pick(i); cur["top"] = set(top)
        return pd.Series(range(len(top), 0, -1), top, dtype=float) if top else None
    def exit_(i, t, p):
        if pre.mstart[i] and t not in set(pick(i)): return "rotated out"
    return dict(scores=scores, exit=exit_, slots=lambda eq: k, max_hold=k, buy_day=lambda i: bool(pre.mstart[i]))


def ml_rank(pre, preds, n):
    """preds: DataFrame (dates x tickers) of walk-forward predicted scores, month starts only."""
    col = {t: k for k, t in enumerate(pre.tk)}
    pv = preds.reindex(index=pre.P.dates, columns=pre.tk).ffill(limit=25).values
    q60 = np.nanquantile(np.where(pre.e, pv, np.nan), 0.6, axis=1)
    def scores(i):
        return _rank(pre, i, pv[i], pre.e[i] & pre.above[i])
    def exit_(i, t, p):
        k = col[t]
        if pre.c[i, k] < pre.s200[i, k]: return "below 200d"
        if pre.mstart[i] and np.isfinite(pv[i, k]) and pv[i, k] < q60[i]: return "model rank out of top 40%"
    return dict(scores=scores, exit=exit_, slots=lambda eq: n, max_hold=n, buy_day=lambda i: bool(pre.mstart[i]),
                trail=28, never_rebuy_trail=True)
