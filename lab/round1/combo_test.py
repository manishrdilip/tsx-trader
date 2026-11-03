"""Candle + RSI + moving-average + earnings-news combinations (pre-specified, 5 combos).
Same engine/costs/sizing as C1_base. Signal at close t, entry next open.
News proxy = company earnings announcement on day t or t-1 (data/earnings_dates.csv); no headline feed is available.
Random baseline: same daily frequency per stock, 3 seeds.
"""
import os
import numpy as np, pandas as pd
from engine import load, indicators, simulate, stats

START, END = "2016-10-31", "2026-10-30"
OUT = "results/round1"; os.makedirs(OUT, exist_ok=True)
XIC = "XIC.TO"
P = load("data"); ind = indicators(P)
cols = [c for c in P["Close"].columns if c != XIC]
O, H, L, C, V = (P[k][cols] for k in ["Open", "High", "Low", "Close", "Volume"])
regime = (ind["C"][XIC] > ind["SMA200"][XIC]).fillna(False)
ind_t = {k: (v[cols] if isinstance(v, pd.DataFrame) else v) for k, v in ind.items()}
ind_t["ATR"] = ind["ATR"][cols]

# RSI(14), Wilder
d = C.diff()
up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
RSI = 100 - 100 / (1 + up / dn)
SMA50, SMA200 = ind["SMA50"][cols], ind["SMA200"][cols]

# candle patterns (as in candle_test.py)
pO, pC = O.shift(1), C.shift(1)
rng_ = (H - L).replace(0, np.nan); body = (C - O).abs()
P1 = (C > O) & (pC < pO) & (C > pO) & (O < pC)
P2 = (np.minimum(O, C) - L >= 2 * body) & (H - np.maximum(O, C) <= body) & (C.shift(1) < C.shift(2))
P5 = (C > O) & (body >= 0.8 * rng_)
bull = (P1 | P2 | P5).fillna(False)

# news proxy: earnings announcement on t or t-1
ed = pd.read_csv("data/earnings_dates.csv", parse_dates=["announce_date"])
ear = pd.DataFrame(False, index=C.index, columns=cols)
for t, grp in ed.groupby("ticker"):
    if t not in ear.columns: continue
    for dt in grp["announce_date"]:
        pos = C.index.searchsorted(dt)
        if pos < len(C.index):
            ear.iloc[pos, ear.columns.get_loc(t)] = True
            if pos + 1 < len(C.index): ear.iloc[pos + 1, ear.columns.get_loc(t)] = True
ear = ear.fillna(False)

oversold = RSI < 40
crossup30 = (RSI > 30) & (RSI.shift(1) <= 30)
up200 = C > SMA200
up50 = C > SMA50

combos = {
    "K1_hammer_RSI<40_above200": (P2 & oversold & up200),
    "K2_engulf_RSI<40_above50": (P1 & oversold & up50),
    "K3_strongbar_RSIcross30_above200": (P5 & crossup30 & up200),
    "K4_bullcandle_RSI<40_above200_NEWS": (bull & oversold & up200 & ear),
    "K5_bullcandle_RSI<40_above200_noNEWS": (bull & oversold & up200 & ~ear),
}
BASE = dict(risk=0.01, stop_mode="atr", stop_k=2.5, target_k=5.0, T=25, partial=False,
            max_pos=3, max_w=0.25, cost=0.005, use_regime=False, start_cash=5000.0)

rows = []
for name, s in combos.items():
    s = s.fillna(False).astype(bool)
    eq, tr = simulate(ind_t, s, regime, BASE, START, END)
    st = stats(eq, tr, BASE); st["name"] = name
    st["signal_freq_pct"] = 100 * s.loc[START:END].values.mean()
    tr.to_csv(f"{OUT}/combo_trades_{name}.csv", index=False)
    rows.append(st)
    f = s.loc[START:END].values.mean()
    rb = []
    for seed in [1, 2, 3]:
        rs = pd.DataFrame(np.random.default_rng(seed).random(s.shape) < f, index=s.index, columns=s.columns)
        e2, t2 = simulate(ind_t, rs, regime, BASE, START, END)
        rb.append(stats(e2, t2, BASE, seed=seed))
    rows.append(dict(name=name + "__RANDOM", signal_freq_pct=100 * f,
                     trades=np.mean([x.get("trades", 0) for x in rb]), win=np.mean([x.get("win", np.nan) for x in rb]),
                     exp_ret=np.mean([x.get("exp_ret", np.nan) for x in rb]),
                     exp_ci_lo=np.mean([x.get("exp_ci_lo", np.nan) for x in rb]),
                     exp_ci_hi=np.mean([x.get("exp_ci_hi", np.nan) for x in rb]),
                     cagr=np.mean([x["cagr"] for x in rb]), max_dd=np.mean([x["max_dd"] for x in rb]), calmar=np.nan))
    print(name, flush=True)

df = pd.DataFrame(rows)
keep = ["name", "signal_freq_pct", "trades", "win", "exp_ret", "exp_ci_lo", "exp_ci_hi", "cagr", "max_dd", "calmar"]
df = df[[c for c in keep if c in df.columns]]
df.to_csv(f"{OUT}/combo_summary.csv", index=False)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
