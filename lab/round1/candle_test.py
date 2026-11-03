"""Candlestick-only long tests on TSX universe, same engine/costs/sizing as Round 1 C1_base.
Signal at close t (pattern bar), entry at open t+1. Random-entry baseline at the same daily frequency.
"""
import os
import numpy as np
import pandas as pd
from engine import load, indicators, simulate, stats

START, END = "2016-10-31", "2026-10-30"
OUT = "results/round1"; os.makedirs(OUT, exist_ok=True)
XIC = "XIC.TO"

P = load(); ind = indicators(P)
cols = [c for c in P["Close"].columns if c != XIC]
O, H, L, C = (P[k][cols] for k in ["Open", "High", "Low", "Close"])
regime = (ind["C"][XIC] > ind["SMA200"][XIC]).fillna(False)
ATR = ind["ATR"][cols]
ind_t = {k: (v[cols] if isinstance(v, pd.DataFrame) else v) for k, v in ind.items()}
ind_t["ATR"] = ATR

pO, pC, pH, pL = O.shift(1), C.shift(1), H.shift(1), L.shift(1)
rng_ = (H - L).replace(0, np.nan)
body = (C - O).abs()
pats = {
    "P1_bull_engulfing": (C > O) & (pC < pO) & (C > pO) & (O < pC),
    "P2_hammer_after_down": (np.minimum(O, C) - L >= 2 * body) & (H - np.maximum(O, C) <= body) & (C.shift(1) < C.shift(2)),
    "P3_doji_after_down3": (body <= 0.1 * rng_) & (C.shift(1) < C.shift(2)) & (C.shift(2) < C.shift(3)) & (C.shift(3) < C.shift(4)),
    "P4_three_up_closes": (C > pC) & (pC > C.shift(2)) & (C.shift(2) > C.shift(3)),
    "P5_strong_bull_bar": (C > O) & (body >= 0.8 * rng_),
}
BASE = dict(risk=0.01, stop_mode="atr", stop_k=2.5, target_k=5.0, T=25, partial=False,
            max_pos=3, max_w=0.25, cost=0.005, use_regime=False, start_cash=5000.0)

rows = []
for name, s in pats.items():
    s = s.fillna(False).astype(bool)
    eq, tr = simulate(ind_t, s, regime, BASE, START, END)
    st = stats(eq, tr, BASE); st["name"] = name
    st["signal_freq_pct"] = 100 * s.loc[START:END].values.mean()
    tr.to_csv(f"{OUT}/candle_trades_{name}.csv", index=False)
    rows.append(st)
    print(name, "done", flush=True)
    # random baseline: same daily frequency per stock, 3 seeds
    f = s.loc[START:END].values.mean()
    rb = []
    for seed in [1, 2, 3]:
        rr = np.random.default_rng(seed).random(s.shape) < f
        rs = pd.DataFrame(rr, index=s.index, columns=s.columns)
        e2, t2 = simulate(ind_t, rs, regime, BASE, START, END)
        rb.append(stats(e2, t2, BASE, seed=seed))
    rows.append(dict(name=name + "__RANDOM_same_freq_avg3", cagr=np.mean([x["cagr"] for x in rb]),
                     max_dd=np.mean([x["max_dd"] for x in rb]), trades=np.mean([x.get("trades", 0) for x in rb]),
                     win=np.mean([x.get("win", np.nan) for x in rb]), exp_ret=np.mean([x.get("exp_ret", np.nan) for x in rb]),
                     exp_ci_lo=np.mean([x.get("exp_ci_lo", np.nan) for x in rb]), exp_ci_hi=np.mean([x.get("exp_ci_hi", np.nan) for x in rb]),
                     calmar=np.nan, signal_freq_pct=100 * f))
    print(name, "random done", flush=True)

df = pd.DataFrame(rows)
cols_out = ["name", "signal_freq_pct", "trades", "win", "exp_ret", "exp_ci_lo", "exp_ci_hi", "cagr", "max_dd", "calmar"]
df = df[[c for c in cols_out if c in df.columns]]
df.to_csv(f"{OUT}/candle_summary.csv", index=False)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
