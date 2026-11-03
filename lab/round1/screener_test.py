"""Common screener-style filters (TradingView-type screens, pre-specified) on the TSX universe.
Same engine/costs/sizing as C1_base. Signal at close t, entry next open.
Random baseline: same daily frequency per stock, 3 seeds.
Note: TradingView's preset rules are not public in sources we could read; these are representative
screen types (gainers, 52w high, volume surge, RSI oversold, golden cross, 3-month momentum).
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

d = C.diff()
up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
RSI = 100 - 100 / (1 + up / dn)
SMA50, SMA200 = ind["SMA50"][cols], ind["SMA200"][cols]
HI52 = ind["HI52"][cols]
ret1 = C.pct_change()
relvol = V / V.rolling(20).mean()
ret63 = C / C.shift(63) - 1

screens = {
    "S1_top_gainer_day>=5pct": (ret1 >= 0.05),
    "S2_new_52w_high_above200": (C >= HI52) & (C > SMA200),
    "S3_volume_surge_2x_up": (relvol >= 2) & (ret1 > 0),
    "S4_RSI<30_above200": (RSI < 30) & (C > SMA200),
    "S5_golden_cross_last5d": (SMA50 > SMA200) & (SMA50.shift(5) <= SMA200.shift(5)),
    "S6_3m_momentum>=20pct_above50": (ret63 >= 0.20) & (C > SMA50),
}
BASE = dict(risk=0.01, stop_mode="atr", stop_k=2.5, target_k=5.0, T=25, partial=False,
            max_pos=3, max_w=0.25, cost=0.005, use_regime=False, start_cash=5000.0)

rows = []
for name, s in screens.items():
    s = s.fillna(False).astype(bool)
    eq, tr = simulate(ind_t, s, regime, BASE, START, END)
    st = stats(eq, tr, BASE); st["name"] = name
    st["signal_freq_pct"] = 100 * s.loc[START:END].values.mean()
    tr.to_csv(f"{OUT}/screener_trades_{name}.csv", index=False)
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
df.to_csv(f"{OUT}/screener_summary.csv", index=False)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
