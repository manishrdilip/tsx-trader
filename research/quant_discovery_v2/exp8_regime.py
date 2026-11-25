"""Batch 4: regime switching over Batch 1 strategy streams. Usage: python exp8_regime.py <db> <vix.csv> <out_b1> <out>"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel
DB, VIXF, O1, OUT = sys.argv[1:5]; os.makedirs(OUT, exist_ok=True)
P = Panel(os.path.join(DB, "panel.npz"))
vix = pd.read_csv(VIXF, index_col=0, parse_dates=True).iloc[:, 0]
x = P.xiu; s200 = x.rolling(200).mean()
MENU = {"VMM_nopark": "VMM_nopark", "D": "D_squeeze_10", "G": "G_sector_2", "F": "F_gaprev_10"}
def streams(ph):
    R = {k: pd.read_parquet(os.path.join(O1, f"eq_{ph}_{v}_50.parquet"))["eq"].pct_change().fillna(0) for k, v in MENU.items()}
    idx = R["VMM_nopark"].index; R["XIU"] = x.reindex(idx).pct_change().fillna(0); R["cash"] = pd.Series(0.0, idx)
    return pd.DataFrame(R)
md = pd.Series(P.dates, P.dates); mp = md.dt.to_period("M")
last = md.groupby(mp).max(); first = md.groupby(mp).min()
fd_ret = pd.Series({p: x.loc[first[p]] / x.shift(1).loc[first[p]] - 1 for p in first.index})
def regime(scheme, p):  # regime for month p from info at end of month p-1
    q = p - 1
    if q not in last.index: return None
    d = last[q]; above = x.loc[d] > s200.loc[d]
    if scheme == "A":
        m3 = x.loc[d] / x.shift(63).loc[d] - 1; vv = vix.asof(d)
        if above: return "bull" if m3 > 0 else "pullback"
        return "weak" if vv < 25 else "fear"
    up = fd_ret.get(q, np.nan) > 0
    return ("fdup_" if up else "fddn_") + ("above" if above else "below")
def monthly(R):
    return (1 + R).groupby(R.index.to_period("M")).prod() - 1
def simulate(R, pick, scheme):
    M = monthly(R); out, prev = [], None
    for p in M.index:
        g = regime(scheme, p); c = pick.get(g, "VMM_nopark")
        r = M.loc[p, c] - (0.01 if prev is not None and c != prev else 0); out.append((p, g, c, r)); prev = c
    d = pd.DataFrame(out, columns=["month", "regime", "choice", "ret"]).set_index("month")
    eq = (1 + d.ret).cumprod(); yrs = len(d) / 12
    return d, dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), dd=round((eq / eq.cummax() - 1).min() * 100, 1),
                   sharpe=round(d.ret.mean() / d.ret.std() * np.sqrt(12), 2), switches=int((d.choice != d.choice.shift()).sum() - 1))
Rd = streams("dev"); Md = monthly(Rd)
res = {}
for sch in ("A", "B"):
    reg = pd.Series({p: regime(sch, p) for p in Md.index})
    tab = Md.groupby(reg).mean() * 100; cnt = reg.value_counts()
    pick = {g: (tab.loc[g].idxmax() if cnt.get(g, 0) >= 6 else "VMM_nopark") for g in tab.index}
    d, st = simulate(Rd, pick, sch)
    print(f"\nScheme {sch} dev: mean monthly return % by regime\n" + tab.round(2).assign(months=cnt).to_string())
    print("pick:", pick, "| dev", st); res[sch] = dict(pick=pick, dev=st)
single = {k: simulate(Rd, {}, "A")[1] if k == "VMM_nopark" else None for k in ["VMM_nopark"]}
print("VMM_nopark alone dev (monthly):", single["VMM_nopark"])
best = max(res, key=lambda k: res[k]["dev"]["sharpe"]); print("selected scheme:", best)
json.dump({"schemes": res, "selected": best, "vmm_nopark_dev": single["VMM_nopark"]}, open(os.path.join(OUT, "exp8_dev.json"), "w"), indent=1, default=str)
if os.environ.get("EVAL"):
    Re = streams("eval"); sel = res[best]
    d, st = simulate(Re, sel["pick"], best); base = simulate(Re, {}, "A")[1]
    print("EVAL selected", st, "| VMM_nopark", base); print(d.to_string())
    json.dump({"selected": best, "eval": st, "vmm_nopark_eval": base}, open(os.path.join(OUT, "exp8_eval.json"), "w"), indent=1)
