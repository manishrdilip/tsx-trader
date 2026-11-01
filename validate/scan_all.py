"""Broad pattern scan on all TSX names in the snapshot.
Features: ~40 continuous indicators plus candle patterns. For each feature, the top and bottom
deciles (cutoffs set on TRAIN only) are tested. Outcome: next-open entry, 10-day hold, open-to-open,
0.2% round-trip cost. Multiple testing: Benjamini-Hochberg FDR 10% on TRAIN p-values.
Survivors are then checked once on TEST (2022-01-01 .. 2026-10-30).
"""
import os, sys
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import engine, candles

H, COST, FDR = 10, 0.002, 0.10
TR_END, TE_START = pd.Timestamp("2021-12-31"), pd.Timestamp("2022-01-01")


def feats(d):
    c, o, h, l, v = d.Close, d.Open, d.High, d.Low, d.Volume
    f = {}
    for k in (1, 3, 5, 10, 20, 60, 120, 252):
        f[f"ret{k}"] = c.pct_change(k)
    for k in (20, 50, 100, 200):
        f[f"dist_sma{k}"] = c / c.rolling(k).mean() - 1
    g = c.diff()
    for k in (2, 5, 14):
        up = g.clip(lower=0).rolling(k).mean(); dn = (-g.clip(upper=0)).rolling(k).mean()
        f[f"rsi{k}"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    f["atr_pct"] = d.atr_pct
    f["vol_ratio20"] = v / v.rolling(20).mean()
    f["vol_ratio60"] = v / v.rolling(60).mean()
    f["dollar_vol20"] = np.log1p((c * v).rolling(20).mean())
    f["dist_52w_hi"] = c / c.rolling(252).max() - 1
    f["dist_52w_lo"] = c / c.rolling(252).min() - 1
    f["range_pct"] = (h - l) / c
    f["close_in_range"] = (c - l) / (h - l).replace(0, np.nan)
    f["gap_open"] = o / c.shift(1) - 1
    f["macd_hist"] = (d.macd - d.macd_sig) / c
    f["bb_pos20"] = (c - c.rolling(20).mean()) / (2 * c.rolling(20).std())
    f["ret_vol20"] = c.pct_change().rolling(20).std()
    f["ret_skew60"] = c.pct_change().rolling(60).skew()
    f["ibs"] = (c - l) / (h - l).replace(0, np.nan)
    f["sma50_sma200"] = d.sma50 / d.sma200 - 1
    F = pd.DataFrame(f, index=d.index).astype("float32")
    B = {}
    try:
        cp = candles.patterns(d)
        if isinstance(cp, pd.DataFrame):
            for col in cp.columns:
                B[f"candle_{col}"] = cp[col].reindex(d.index).fillna(False).astype(bool).values
        elif isinstance(cp, dict):
            for k, s in cp.items():
                B[f"candle_{k}"] = pd.Series(s, index=d.index).reindex(d.index).fillna(False).astype(bool).values
    except Exception as e:
        print("candle patterns skipped:", e, flush=True)
    return F, B


def main(path):
    bars, _ = engine.load_tsx(path)
    print("tickers", len(bars), flush=True)
    frames = []
    for t, d in bars.items():
        F, B = feats(d)
        F["_y"] = (d.Open.shift(-(H + 1)) / d.Open.shift(-1) - 1 - COST).astype("float32").values
        F["_t"] = t
        for k, s in B.items():
            F[k] = s
        F["Date"] = d.index
        frames.append(F)
    P = pd.concat(frames, ignore_index=True)
    P = P[P._y.notna()]
    tr = P[P.Date <= TR_END]; te = P[P.Date >= TE_START]
    print("rows train", len(tr), "test", len(te), flush=True)
    names = [c for c in P.columns if c not in ("Date", "_y", "_t")]
    hyps = []
    for n in names:
        if tr[n].dtype == bool:
            hyps.append((f"{n}==True", lambda df, n=n: df[n].values.astype(bool)))
        else:
            lo, hi = tr[n].quantile(0.10), tr[n].quantile(0.90)
            hyps.append((f"{n}<=p10", lambda df, n=n, q=lo: (df[n] <= q).values))
            hyps.append((f"{n}>=p90", lambda df, n=n, q=hi: (df[n] >= q).values))
    ytr, yte = tr._y.values, te._y.values
    rows = []
    for lab, fn in hyps:
        m = fn(tr); mt = fn(te)
        k = int(m.sum())
        if k < 200 or (~m).sum() < 200:
            continue
        a, b = ytr[m], ytr[~m]
        _, p = stats.ttest_ind(a, b, equal_var=False)
        rows.append({"hypothesis": lab, "n_train": k,
                     "train_edge_pct": 100 * (a.mean() - ytr.mean()), "train_p": p,
                     "test_n": int(mt.sum()),
                     "test_edge_pct": 100 * (yte[mt].mean() - yte.mean()) if mt.sum() else np.nan})
    R = pd.DataFrame(rows).sort_values("train_p").reset_index(drop=True)
    m_h = len(R)
    R["bh_threshold"] = FDR * (np.arange(1, m_h + 1)) / m_h
    R["survives_fdr_train"] = R.train_p <= R.bh_threshold
    surv = R[R.survives_fdr_train]
    print(f"hypotheses tested on train: {m_h}; survive FDR {FDR:.0%} on train: {len(surv)}", flush=True)
    os.makedirs("results/validate", exist_ok=True)
    R.to_csv("results/validate/scan_all_train.csv", index=False)
    cols = ["hypothesis", "n_train", "train_edge_pct", "train_p", "test_n", "test_edge_pct"]
    if len(surv):
        ok = surv[np.sign(surv.test_edge_pct) == np.sign(surv.train_edge_pct)]
        print(f"survivors with same sign on test: {len(ok)} of {len(surv)}", flush=True)
        print(surv[cols].round(4).to_string(index=False), flush=True)
    print("TOP 15 by train p:", flush=True)
    print(R.head(15)[cols].round(4).to_string(index=False), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
