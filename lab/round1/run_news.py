"""Round 1b: volume-spike test (S) and earnings-news test (N).
S1 = all spikes: day up >=5% close-to-close on >=3x 20d avg volume; long next open.
S2 = spikes with NO earnings announcement within +-3 days (non-news spikes).
N1 = earnings reaction spikes: earnings announcement day or next day with up >=5% and >=2x volume.
Same engine and exits as Round 1 C1 base (ATR 2.5 stop / 5 target / 25 days, 1% risk, max 3 slots, 0.5%/side).
Windows: full 2016-10-31..2026-10-30, plus 2016-21 and 2022-26 sub-periods.
"""
import os
import numpy as np, pandas as pd
from engine import load, indicators, simulate, stats

OUT = "results/round1"; os.makedirs(OUT, exist_ok=True)
P = load("data"); ind = indicators(P)
XIC = "XIC.TO"
cols = [c for c in ind["C"].columns if c != XIC]
C, O, H, L, V = [ind[k][cols] for k in ["C", "O", "H", "L", "V"]]
ind_t = {k: (ind[k][cols] if isinstance(ind[k], pd.DataFrame) else ind[k]) for k in ind}
ind_t["ATR"] = ind["ATR"][cols]
ind_t["SMA10"] = ind["SMA10"][cols]
ind_t["RET252"] = ind["RET252"][cols]
ind_t["C"] = C; ind_t["O"] = O; ind_t["H"] = H; ind_t["L"] = L

ret = C.pct_change()
relvol = V / V.rolling(20).mean()

# earnings flags: announcement day or the next trading day
ed = pd.read_csv("data/earnings_dates.csv", parse_dates=["announce_date"])
ear = pd.DataFrame(False, index=C.index, columns=cols)
ear_near = pd.DataFrame(False, index=C.index, columns=cols)   # within +-3 trading days
idx = C.index
for t, grp in ed.groupby("ticker"):
    if t not in ear.columns:
        continue
    for d in grp.announce_date:
        pos = idx.searchsorted(d)
        if pos >= len(idx):
            continue
        ear.iloc[pos, ear.columns.get_loc(t)] = True
        if pos + 1 < len(idx):
            ear.iloc[pos + 1, ear.columns.get_loc(t)] = True
        lo, hi = max(0, pos - 3), min(len(idx), pos + 4)
        ear_near.iloc[lo:hi, ear_near.columns.get_loc(t)] = True

# reaction-day flag: earnings day (or next) with up >=5% on >=2x volume
react = ear & (ret >= 0.05) & (relvol >= 2)
spike = (ret >= 0.05) & (relvol >= 3)
S1 = spike.fillna(False)
S2 = (spike & ~ear_near).fillna(False)
N1 = react.fillna(False)

BASE = dict(risk=0.01, stop_mode="atr", stop_k=2.5, target_k=5.0, T=25, partial=False,
            max_pos=3, max_w=0.25, cost=0.005, use_regime=False, start_cash=5000.0)
regime = pd.Series(False, index=C.index)

rows = []
def run(name, sig):
    for lab, s, e in [("full", "2016-10-31", "2026-10-30"), ("2016-21", "2016-10-31", "2021-12-31"), ("2022-26", "2022-01-01", "2026-10-30")]:
        eq, tr = simulate(ind_t, sig, regime, BASE, s, e)
        st = stats(eq, tr, BASE)
        st.update(name=name, period=lab, signals=int(sig.loc[s:e].values.sum()))
        rows.append(st)
        if lab == "full":
            tr.to_csv(f"{OUT}/news_trades_{name}.csv", index=False)

run("S1_all_spikes", S1)
run("S2_nonnews_spikes", S2)
run("N1_earnings_reaction", N1)

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/news_summary.csv", index=False)
cov = ed.assign(y=ed.announce_date.dt.year).groupby("y").size()
lines = ["# Round 1b: spike and earnings-news tests (auto-generated)", "",
         "Earnings coverage (events per year, Yahoo): " + ", ".join(f"{y}: {n}" for y, n in cov.items()), "",
         "| Test | Period | Signals | Trades | Win | Exp/trade | 95% CI | CAGR | Max DD | Calmar | MC DD p95 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
f = lambda x, p=True: "n/a" if pd.isna(x) else (f"{x*100:.1f}%" if p else f"{x:.2f}")
for _, s in df.iterrows():
    lines.append(f"| {s['name']} | {s['period']} | {s['signals']} | {int(s['trades']) if not pd.isna(s['trades']) else '-'} | {f(s['win'])} | "
                 f"{f(s['exp_ret'])} | [{f(s['exp_ci_lo'])}, {f(s['exp_ci_hi'])}] | {f(s['cagr'])} | {f(s['max_dd'])} | {f(s['calmar'],False)} | {f(s['mc_dd_p95'])} |")
open(f"{OUT}/news_summary.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
