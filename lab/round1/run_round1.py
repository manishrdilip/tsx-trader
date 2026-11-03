"""Round 1: E1-E5, candidates C1-C3, D-rule reference, sensitivity grid, control, XIC buy-and-hold.
Window 2016-10-31 .. 2026-10-30 (same window as earlier backtests). Survivorship-biased universe.
"""
import os, json
import numpy as np
import pandas as pd
from engine import load, indicators, signals, simulate, stats

START, END = "2016-10-31", "2026-10-30"
OUT = "results/round1"
os.makedirs(OUT, exist_ok=True)

P = load()
ind = indicators(P)
XIC = "XIC.TO"
C = ind["C"]
regime = (C[XIC] > ind["SMA200"][XIC]).fillna(False)

BASE = dict(risk=0.01, stop_mode="atr", stop_k=2.5, target_k=5.0, stop_pct=0.01, target_pct=0.03,
            T=25, partial=False, max_pos=3, max_w=0.25, cost=0.005, use_regime=False, start_cash=5000.0)

sig = {v: signals(ind, v) for v in ["C1", "C2", "C3", "E2", "E3"]}
# restrict to universe columns (drop XIC from trading)
trade_cols = [c for c in C.columns if c != XIC]
for k in sig:
    sig[k] = sig[k][trade_cols]
ind_t = {k: (v[trade_cols] if isinstance(v, pd.DataFrame) else v) for k, v in ind.items()}
ind_t["ATR"] = ind["ATR"][trade_cols]

def run(name, variant, **over):
    cfg = {**BASE, **over}
    eq, tr = simulate(ind_t, sig[variant], regime, cfg, START, END)
    st = stats(eq, tr, cfg)
    st["name"] = name
    tr.to_csv(f"{OUT}/trades_{name}.csv", index=False)
    return name, eq, st

results, equities = [], {}
runs = [
    ("C1_base", "C1", {}),
    ("E1_half_at_2R_trail10", "C1", dict(partial=True)),
    ("E2_adx25", "E2", {}),
    ("E3_volume_close", "E3", {}),
    ("E4_xic_regime_gate", "C1", dict(use_regime=True)),
    ("E5_risk_0.5pct", "C1", dict(risk=0.005)),
    ("E5_risk_2pct", "C1", dict(risk=0.02)),
    ("C2_vote_ge2", "C2", {}),
    ("C3_no_trigger", "C3", {}),
    ("REF_D_rule_1pct_stop_3pct_target_10d", "C1", dict(stop_mode="pct", T=10)),
    ("COST_0.25pct_per_side", "C1", dict(cost=0.0025)),
    ("COST_0.75pct_per_side", "C1", dict(cost=0.0075)),
]
for name, v, over in runs:
    n, eq, st = run(name, v, **over)
    results.append(st); equities[n] = eq
    print(name, round(st["cagr"], 4), round(st["max_dd"], 3), st.get("trades"), flush=True)

# sensitivity grid around C1 (stop 2/2.5/3 ATR x target 4/5/6 ATR)
sens = []
for sk in [2.0, 2.5, 3.0]:
    for tk in [4.0, 5.0, 6.0]:
        n, eq, st = run(f"SENS_stop{sk}_tgt{tk}", "C1", stop_k=sk, target_k=tk)
        sens.append(dict(stop_k=sk, target_k=tk, exp_ret=st["exp_ret"], cagr=st["cagr"], max_dd=st["max_dd"]))
sens = pd.DataFrame(sens)
sens_share_pos = (sens["exp_ret"] > 0).mean()

# controls: XIC buy & hold, and XIC held only when above its 200d SMA (control)
xic_ret = C[XIC].pct_change().fillna(0)
flag = regime.shift(1).fillna(False).astype(float)
eq_bh = BASE["start_cash"] * (1 + xic_ret.loc[START:END]).cumprod()
eq_bh = eq_bh / eq_bh.iloc[0] * BASE["start_cash"]
eq_ctl = BASE["start_cash"] * (1 + (xic_ret * flag).loc[START:END]).cumprod()
eq_ctl = eq_ctl / eq_ctl.iloc[0] * BASE["start_cash"]
for nm, eq in [("CONTROL_xic_200d_gate", eq_ctl), ("XIC_buy_hold", eq_bh)]:
    st = stats(eq, pd.DataFrame(), BASE); st["name"] = nm
    results.append(st); equities[nm] = eq

summary = pd.DataFrame(results).set_index("name")
summary["calmar_haircut_3pt"] = (summary["cagr"] - 0.03) / summary["max_dd"].abs()
summary.to_csv(f"{OUT}/summary.csv")
pd.DataFrame(equities).to_csv(f"{OUT}/equity_curves.csv")
sens.to_csv(f"{OUT}/sensitivity_C1.csv", index=False)

# ---- gates (plan section 5.6) ----
xic_calmar = summary.loc["XIC_buy_hold", "calmar"]
ctl_calmar = summary.loc["CONTROL_xic_200d_gate", "calmar"]
rows = []
for nm in summary.index:
    if nm.startswith(("SENS", "CONTROL", "XIC")):
        continue
    s = summary.loc[nm]
    g = {
        "net_exp_ci_lo_pos": bool(s["exp_ci_lo"] > 0),
        "max_dd_le_25": bool(s["max_dd"] >= -0.25),
        "mc_p95_le_35": bool(s["mc_dd_p95"] <= 0.35),
        "calmar_beats_xic": bool(s["calmar"] > xic_calmar),
        "calmar_beats_control": bool(s["calmar"] > ctl_calmar),
        "survives_3pt_haircut": bool(s["calmar_haircut_3pt"] > xic_calmar),
        "trades_ge_100": bool(s["trades"] >= 100),
    }
    g["PASS_ALL"] = all(g.values())
    rows.append(pd.Series(g, name=nm))
gates = pd.DataFrame(rows)
gates.to_csv(f"{OUT}/gates.csv")

# yearly returns
yr = pd.DataFrame({k: equities[k].resample("YE").last().pct_change() for k in ["C1_base", "CONTROL_xic_200d_gate", "XIC_buy_hold"] if k in equities})
yr.to_csv(f"{OUT}/yearly.csv")

# summary markdown
def fmt(x, pct=True):
    if pd.isna(x): return "n/a"
    return f"{x*100:.1f}%" if pct else f"{x:.2f}"
lines = ["# Round 1 results (auto-generated)", "",
         f"Window {START} to {END}. Universe: today's TSX listings with median dollar volume >= $300k (survivorship-biased).",
         f"Sensitivity share with positive expectancy (C1 grid, 9 runs): {fmt(sens_share_pos)} (gate: >= 70%).", "",
         "| Experiment | Trades | Win | Exp/trade | 95% CI | CAGR | Max DD | Calmar | MC DD p95 | 3pt-haircut Calmar | PASS |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
for nm in summary.index:
    s = summary.loc[nm]
    ok = gates.loc[nm, "PASS_ALL"] if nm in gates.index else "-"
    lines.append(f"| {nm} | {int(s['trades']) if not pd.isna(s['trades']) else '-'} | {fmt(s['win'])} | {fmt(s['exp_ret'],True)} | "
                 f"[{fmt(s['exp_ci_lo'])}, {fmt(s['exp_ci_hi'])}] | {fmt(s['cagr'])} | {fmt(s['max_dd'])} | {fmt(s['calmar'],False)} | "
                 f"{fmt(s['mc_dd_p95'])} | {fmt(s['calmar_haircut_3pt'],False)} | {ok} |")
lines += ["", "## Yearly returns", yr.to_markdown() if hasattr(yr, "to_markdown") else yr.to_string()]
open(f"{OUT}/summary.md", "w").write("\n".join(lines) + "\n")
print(open(f"{OUT}/summary.md").read())
