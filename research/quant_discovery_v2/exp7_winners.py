"""Batch 3: winner anatomy (PROTOCOL_batch3_winners.md). Usage: python exp7_winners.py <db> <out>"""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel

DB, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
P = Panel(os.path.join(DB, "panel.npz")); C, V = P.C, P.V
r = C.pct_change(fill_method=None)
fmax = C[::-1].rolling(60, min_periods=1).max()[::-1].shift(-1)   # max close over next 60 days
fmin = C[::-1].rolling(60, min_periods=1).min()[::-1].shift(-1)
win = (fmax / C - 1 >= 0.5); blow = (fmin / C - 1 <= -0.3)
feat = {f"r{n}": C / C.shift(n) - 1 for n in (5, 20, 60, 120, 250)}
feat.update(v20=r.rolling(20).std(), v60=r.rolling(60).std(), d50=C / P.sma50 - 1, d200=C / P.sma200 - 1,
            h52=C / C.rolling(252).max() - 1, ldv=np.log1p((C * V).rolling(20).median()),
            relvol=V.rolling(5).mean() / V.rolling(60).mean(),
            comp=(C.rolling(20).max() - C.rolling(20).min()) / (C.rolling(120).max() - C.rolling(120).min()),
            price=C)
xo = pd.Series(P.xiu_ok, P.dates); br = (C > P.sma200).where(P.elig).mean(axis=1)
rows = []
samp = P.dates[::5]
for d in samp:
    e = P.elig.loc[d]; tk = e.index[e.values]
    if not len(tk): continue
    x = pd.DataFrame({k: v.loc[d, tk].values for k, v in feat.items()})
    x["xiu_ok"] = float(xo.loc[d]); x["breadth"] = br.loc[d]
    x["win"] = win.loc[d, tk].values; x["blow"] = blow.loc[d, tk].values
    x["fwd60"] = (C.shift(-60).loc[d, tk] / C.loc[d, tk] - 1).values
    x["date"] = d; x["ticker"] = tk.values; rows.append(x)
df = pd.concat(rows, ignore_index=True)
df = df[df.date <= P.dates[-61]].replace([np.inf, -np.inf], np.nan).dropna(subset=list(feat) + ["breadth"])
dev = df[(df.date >= "2009-01-01") & (df.date <= "2022-12-31")]
base_w, base_b = dev.win.mean(), dev.blow.mean()
print(f"dev rows {len(dev):,}  winner base rate {base_w*100:.2f}%  blow-up base rate {base_b*100:.2f}%")
cols = list(feat) + ["breadth"]
dec = []
for c in cols:
    q = pd.qcut(dev[c], 10, labels=False, duplicates="drop")
    g = dev.groupby(q).agg(lo=(c, "min"), hi=(c, "max"), win=("win", "mean"), blow=("blow", "mean"), fwd=("fwd60", "median"), n=("win", "size"))
    g["feature"] = c; g["decile"] = g.index; dec.append(g)
dec = pd.concat(dec)
dec["win_lift"] = dec.win / base_w; dec["blow_lift"] = dec.blow / base_b
dec.to_csv(os.path.join(OUT, "exp7_deciles_dev.csv"), index=False)
top = dec.sort_values("win_lift", ascending=False).head(12)
print(top[["feature", "decile", "lo", "hi", "win", "blow", "win_lift", "blow_lift", "fwd"]].round(3).to_string(index=False))
X = dev[cols].values; y = dev.win.values
t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=int(0.02 * len(dev)), random_state=0).fit(X, y)
txt = export_text(t, feature_names=cols, decimals=3); print(txt)
leaf = t.apply(X); L = pd.DataFrame({"leaf": leaf, "win": dev.win.values, "blow": dev.blow.values, "fwd": dev.fwd60.values})
lg = L.groupby("leaf").agg(n=("win", "size"), win=("win", "mean"), blow=("blow", "mean"), fwd=("fwd", "median"))
lg["edge"] = lg.win - lg.blow; lg = lg[lg.n >= 500].sort_values("edge", ascending=False)
print(lg.round(3).to_string())
# extract path to best leaf
best = int(lg.index[0]); tr = t.tree_; path = []
def walk(n, conds):
    if n == best: path.extend(conds); return True
    if tr.children_left[n] == -1: return False
    f, th = cols[tr.feature[n]], float(tr.threshold[n])
    return walk(tr.children_left[n], conds + [(f, "<=", th)]) or walk(tr.children_right[n], conds + [(f, ">", th)])
walk(0, [])
res = {"base_win": base_w, "base_blow": base_b, "best_leaf": best, "rule": path, "leaf_stats": lg.loc[best].to_dict()}
json.dump(res, open(os.path.join(OUT, "exp7_rule.json"), "w"), indent=1, default=float)
print(json.dumps(res, indent=1, default=float))
