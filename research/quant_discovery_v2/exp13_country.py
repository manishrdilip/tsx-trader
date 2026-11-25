"""Batch 7E: country ETF rotation. Usage: python exp13_country.py <etf_dir>"""
import os, sys, numpy as np, pandas as pd
D = sys.argv[1]
px = {f[:-4]: pd.read_csv(os.path.join(D, f), index_col=0, parse_dates=True)["Adjusted_close"] for f in os.listdir(D) if f.endswith(".csv")}
C = pd.DataFrame(px).sort_index(); spy = C.pop("SPY")
R = C.pct_change(fill_method=None)
ms = C.index.to_period("M"); first = np.r_[True, ms[1:] != ms[:-1]]
r12 = C / C.shift(252) - 1; above = C > C.rolling(200).mean()
w = pd.DataFrame(np.nan, C.index, C.columns)
for i in np.where(first)[0]:
    if i == 0: continue
    d = C.index[i - 1]; ok = (above.loc[d] & r12.loc[d].notna())
    top = r12.loc[d][ok].nlargest(3).index
    row = pd.Series(0.0, C.columns); row[top] = 1 / 3 if len(top) else 0
    w.iloc[i] = row
w = w.ffill().fillna(0)
cost = 0.001 * w.diff().abs().sum(axis=1)
strat = (w.shift(1) * R).sum(axis=1) - cost
ew = R.mean(axis=1)  # equal-weight of available country ETFs, daily rebalanced
def st(r):
    eq = (1 + r.fillna(0)).cumprod(); y = len(r) / 252
    return f"CAGR {((eq.iloc[-1])**(1/y)-1)*100:5.1f}  DD {(eq/eq.cummax()-1).min()*100:6.1f}  Sharpe {r.mean()/r.std()*np.sqrt(252):4.2f}"
for nm, a, b in (("dev", "2000-01-01", "2022-12-31"), ("eval", "2023-01-01", "2026-12-31")):
    print(nm, "| rotation", st(strat.loc[a:b]), "| equal-weight countries", st(ew.loc[a:b]), "| SPY", st(spy.pct_change().loc[a:b]))
