"""Batch 7B: TSX tax-loss January effect. Usage: python exp12_january.py <db>"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel
P = Panel(os.path.join(sys.argv[1], "panel.npz")); C, O = P.C, P.O; D = P.dates
rows = []
for y in range(2009, 2026):
    a = D[D.searchsorted(pd.Timestamp(f"{y}-12-15"))]          # signal day
    ia = D.get_loc(a); buy = D[ia + 1]
    jan = D[(D.year == y + 1) & (D.month == 1)]
    if not len(jan): continue
    sell = jan[-1]
    e = P.elig.loc[a]; r12 = P.r12.loc[a][e & P.r12.loc[a].notna()]
    pick = r12.nsmallest(10).index
    rets = []
    for t in pick:
        s = C[t].loc[buy:sell].dropna()
        if s.empty: rets.append(-1.0); continue
        entry = O[t].loc[buy]; entry = entry if np.isfinite(entry) else s.iloc[0]
        rets.append(s.iloc[-1] * 0.995 / (entry * 1.005) - 1)
    x = P.xiu
    rows.append(dict(window=f"Dec{y}-Jan{y+1}", losers=round(np.mean(rets) * 100, 2),
                     xiu=round((x.loc[sell] / x.loc[buy] - 1) * 100, 2), median_loser=round(np.median(rets) * 100, 2)))
df = pd.DataFrame(rows); print(df.to_string(index=False))
for nm, m in (("dev", df.window <= "Dec2022"), ("eval", df.window >= "Dec2023")):
    d = df[m]; print(nm, "avg losers", round(d.losers.mean(), 2), "avg XIU", round(d.xiu.mean(), 2),
                     "losers beat XIU in", int((d.losers > d.xiu).sum()), "of", len(d))
df.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "batch7_january.csv"), index=False)
