"""Batch 2, Exp 4: equal-weight monthly-rebalanced mixes of strategy return streams (selection on dev only).
Usage: python exp4_combos.py <out_batch1> <db> <phase> [mix]"""
import itertools, os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel
O1, DB, PH = sys.argv[1:4]
P = Panel(os.path.join(DB, "panel.npz"))
names = {"VMM_nopark": "VMM_nopark", "D": "D_squeeze_10", "G": "G_sector_2", "F": "F_gaprev_10"}
R = {k: pd.read_parquet(os.path.join(O1, f"eq_{PH}_{v}_50.parquet"))["eq"].pct_change().fillna(0) for k, v in names.items()}
idx = R["VMM_nopark"].index
x = P.C["XIU.TO"].reindex(idx); R["XIU"] = x.pct_change().fillna(0)
R = pd.DataFrame(R)
def mix(cols):
    v = pd.Series(1.0 / len(cols), cols); w = v.copy(); out = []
    m = idx.to_period("M")
    for k, d in enumerate(idx):
        if k and m[k] != m[k - 1]: w = v * w.sum() / v.sum()  # rebalance (0.5% on traded amount ignored: small)
        w = w * (1 + R.loc[d, cols]); out.append(w.sum())
    eq = pd.Series(out, idx) * 5000; r = eq.pct_change().dropna()
    yrs = (idx[-1] - idx[0]).days / 365.25
    return dict(mix="+".join(cols), cagr=round(((eq.iloc[-1] / 5000) ** (1 / yrs) - 1) * 100, 1),
                dd=round((eq / eq.cummax() - 1).min() * 100, 1), sharpe=round(r.mean() / r.std() * np.sqrt(252), 2))
rows = []
if len(sys.argv) > 4:
    rows.append(mix(sys.argv[4].split("+")))
else:
    print(R.corr().round(2).to_string())
    for n in (2, 3):
        for c in itertools.combinations(R.columns, n): rows.append(mix(list(c)))
d = pd.DataFrame(rows).sort_values("sharpe", ascending=False); print(d.to_string(index=False))
d.to_csv(os.path.join(os.path.dirname(O1), "out2", f"exp4_{PH}.csv"), index=False)
