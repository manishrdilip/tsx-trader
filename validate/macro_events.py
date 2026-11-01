"""Pre-registered event tests H1-H4 on daily closes (results/macro/closes.csv).
Train 2016-10-31..2021-12-31, test 2022-01-01..2026-10-30. Baseline = how often the target rises on any day.
Accept only if test n >= 100 and test hit rate beats baseline by >= 5 points.
"""
import pandas as pd, numpy as np
C = pd.read_csv("results/macro/closes.csv", index_col=0, parse_dates=True).sort_index()
R = C.pct_change()
TR = slice("2016-10-31", "2021-12-31"); TE = slice("2022-01-01", "2026-10-30")
tests = [
    ("H1 oil +2% day -> gold up next day", R["CL=F"] >= 0.02, R["GC=F"].shift(-1)),
    ("H2 gold +2% day -> silver up next day", R["GC=F"] >= 0.02, R["SI=F"].shift(-1)),
    ("H3 GOOGL -3% day -> NVDA down next day", R["GOOGL"] <= -0.03, R["NVDA"].shift(-1)),
    ("H4 gold +1% day -> ABX/AEM/K up same day", R["GC=F"] >= 0.01, None),
]
rows = []
for name, trig, tgt in tests:
    if tgt is None:
        outs = []
        for t in ["ABX.TO", "AEM.TO", "K.TO"]:
            outs.append((R[t] > 0).where(trig).dropna())
        for per, sl in [("train", TR), ("test", TE)]:
            vals = pd.concat([o.loc[sl] for o in outs])
            base = pd.concat([(R[t] > 0).loc[sl] for t in ["ABX.TO", "AEM.TO", "K.TO"]]).mean()
            rows.append((name, per, len(vals), round(100 * vals.mean(), 1), round(100 * base, 1)))
        continue
    hit = (tgt > 0)
    for per, sl in [("train", TR), ("test", TE)]:
        m = trig.loc[sl].fillna(False).astype(bool)
        h = hit.loc[sl][m].dropna()
        base = (tgt.loc[sl] > 0).dropna().mean()
        rows.append((name, per, len(h), round(100 * h.mean(), 1) if len(h) else None, round(100 * base, 1)))
df = pd.DataFrame(rows, columns=["test", "period", "n", "hit_rate_pct", "baseline_pct"])
df["edge_pts"] = (df.hit_rate_pct - df.baseline_pct).round(1)
print(df.to_string(index=False))
df.to_csv("results/validate/macro_events.csv", index=False)
