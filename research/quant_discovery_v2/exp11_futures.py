"""Batch 7A: managed-futures trend + carry on pysystemtrade data. Usage: python exp11_futures.py <pst/data/futures> <out>"""
import json, os, re, sys
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis
SRC, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
adj_dir, mult_dir = os.path.join(SRC, "adjusted_prices_csv"), os.path.join(SRC, "multiple_prices_csv")
P, CARRY = {}, {}
for f in sorted(os.listdir(adj_dir)):
    name = f[:-4]
    if re.search(r"_(micro|mini|MICRO|MINI|SMALL|small)", name): continue
    a = pd.read_csv(os.path.join(adj_dir, f), index_col=0, parse_dates=True).iloc[:, 0]
    a.index = a.index.normalize(); a = a.groupby(level=0).last()
    if (a.index[-1] - a.index[0]).days < 3650: continue
    P[name] = a
    mf = os.path.join(mult_dir, f)
    if os.path.exists(mf):
        m = pd.read_csv(mf, index_col=0, parse_dates=True); m.index = m.index.normalize(); m = m.groupby(level=0).last()
        def ym(x): x = pd.to_numeric(x, errors="coerce"); return (x // 10000) + ((x // 100) % 100 - 1) / 12
        dy = ym(m.PRICE_CONTRACT) - ym(m.CARRY_CONTRACT)
        c = (m.CARRY - m.PRICE) / dy.replace(0, np.nan) / m.PRICE
        CARRY[name] = c.where(dy.abs() > 0).rolling(5, min_periods=1).mean()
C = pd.DataFrame(P).sort_index(); C = C[C.index.dayofweek < 5].ffill(limit=5)
D = C.diff()                      # back-adjusted: use price differences
vol = D.rolling(60).std() * np.sqrt(252)
vol = vol.where(vol >= 0.5 * vol.rolling(252, min_periods=60).median())   # stale/flat data -> no position
units = (0.10 / vol)              # scale so each market runs at 10%/yr vol on $1
R = (D * units.shift(1)).clip(-0.10, 0.10)   # daily return of a 10%-vol position; extreme prints capped
pv = (D / C.shift(1).abs()).rolling(60).std() * np.sqrt(252)
lev = (0.10 / pv).clip(upper=10)  # notional / capital, for costs only
K = pd.DataFrame(CARRY).reindex(C.index).ffill(limit=5)
sig = {"A1_trend12m": np.sign(C - C.shift(252)), "A2_carry": np.sign(K).reindex(columns=C.columns),
       "A3_trend_carry": (0.5 * np.sign(C - C.shift(252)) + 0.5 * np.sign(K).reindex(columns=C.columns).fillna(0))}
def run(s, cost=0.0003):
    pos = s.shift(1)              # signal at t, held from t+1
    n = pos.notna().sum(axis=1).replace(0, np.nan)
    g = (pos * R).sum(axis=1) / n
    pos = pos.where(units.shift(1).notna())
    turn = (pos.fillna(0).diff().abs() * lev.shift(1).fillna(1)).sum(axis=1) / n
    return (g - turn * cost).fillna(0)
def st(r):
    r = r[r.ne(0).idxmax():]; eq = (1 + r).cumprod(); yrs = len(r) / 252
    return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2), sharpe=round(r.mean() / r.std() * np.sqrt(252), 2),
                dd=round((eq / eq.cummax() - 1).min() * 100, 1))
res = {"markets": int(C.shape[1]), "markets_with_carry": int(K.notna().any().sum())}
rets = {}
for k, s in sig.items():
    r = run(s); rets[k] = r
    res[k] = {"dev_1990_2014": st(r.loc["1990":"2014"]), "eval_2015_2024": st(r.loc["2015":])}
best = max(sig, key=lambda k: res[k]["dev_1990_2014"]["sharpe"])
rb = rets[best].loc["1990":"2014"]; sr = rb.mean() / rb.std(); N = 3
srs = np.array([res[k]["dev_1990_2014"]["sharpe"] for k in sig]) / np.sqrt(252)
emax = np.std(srs) * ((1 - 0.5772) * norm.ppf(1 - 1 / N) + 0.5772 * norm.ppf(1 - 1 / (N * np.e)))
res["selected"] = best
res["deflated_sharpe"] = float(norm.cdf((sr - emax) * np.sqrt(len(rb) - 1) / np.sqrt(1 - skew(rb) * sr + (kurtosis(rb, fisher=False) - 1) / 4 * sr ** 2)))
yr = rets[best].groupby(rets[best].index.year).apply(lambda x: (1 + x).prod() - 1).round(3)
res["by_year_selected"] = {int(k): float(v) for k, v in yr.items() if k >= 2005}
json.dump(res, open(os.path.join(OUT, "futures.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "by_year_selected"}, indent=1))
print(res["by_year_selected"])
