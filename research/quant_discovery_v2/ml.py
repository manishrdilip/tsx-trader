"""Walk-forward LightGBM ranker (idea H). For each year Y, train on month-start rows whose 20-day label
window ends at least 20 trading days before Y starts; predict month starts in Y. No future data in features."""
import numpy as np, pandas as pd, lightgbm as lgb


def features(P):
    C, V = P.C, P.V
    ret = C.pct_change(fill_method=None)
    f = {}
    for n in (5, 20, 60, 120, 250):
        f[f"r{n}"] = C / C.shift(n) - 1
    f["v20"] = ret.rolling(20).std(); f["v60"] = ret.rolling(60).std()
    f["d200"] = C / P.sma200 - 1; f["d50"] = C / P.sma50 - 1
    f["h52"] = C / C.rolling(252).max() - 1
    f["ldv"] = np.log1p((C * V).rolling(20).median())
    return f


def walk_forward(P, first_pred_year=2009, last_year=2026):
    f = features(P)
    fwd = P.C.shift(-20) / P.C - 1
    ms = P.dates.to_period("M"); mstart = np.r_[True, ms[1:] != ms[:-1]]
    days = P.dates[mstart]
    rows = []
    for d in days:
        e = P.elig.loc[d]
        tk = e.index[e.values]
        if len(tk) < 30: continue
        X = pd.DataFrame({k: v.loc[d, tk] for k, v in f.items()})
        # cross-sectional rank-normalise features (robust to regime level shifts)
        X = X.rank(pct=True)
        y = fwd.loc[d, tk].rank(pct=True)
        X["date"] = d; X["ticker"] = tk; X["y"] = y.values
        rows.append(X)
    df = pd.concat(rows, ignore_index=True)
    feats = list(f)
    preds = []
    di = {d: k for k, d in enumerate(P.dates)}
    for Y in range(first_pred_year, last_year + 1):
        ystart = pd.Timestamp(f"{Y}-01-01")
        k0 = P.dates.searchsorted(ystart)
        cutoff = P.dates[max(0, k0 - 40)]  # label (20d) + embargo (20d)
        tr = df[(df.date <= cutoff) & df.y.notna()]
        te = df[(df.date >= ystart) & (df.date < pd.Timestamp(f"{Y+1}-01-01"))]
        if len(tr) < 2000 or not len(te): continue
        m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=15, min_child_samples=200,
                              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=1)
        m.fit(tr[feats], tr.y)
        te = te.copy(); te["p"] = m.predict(te[feats])
        preds.append(te[["date", "ticker", "p"]])
    p = pd.concat(preds)
    return p.pivot(index="date", columns="ticker", values="p")
