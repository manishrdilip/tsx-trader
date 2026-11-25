"""Batch 2: Exp 2 (GP best tree in full engine), 3, 5, 6 at all costs.
Usage: python exp_rest.py <db> <vix.csv> <out> <dev|eval> [names...]"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel, run, stats
import strategies as S, strategies2 as S2

DB, VIXF, OUT, PH = sys.argv[1:5]; ONLY = sys.argv[5:]
P = Panel(os.path.join(DB, "panel.npz")); pre = S.Pre(P)
vix = pd.read_csv(VIXF, index_col=0, parse_dates=True).iloc[:, 0].to_dict()
PER = {"dev": ("2009-01-02", "2022-12-30"), "eval": ("2023-01-03", str(P.dates[-1].date()))}
a, b = PER[PH]


def gp_daily_score(tree):
    C, Vv = P.C, P.V; r = C.pct_change(fill_method=None)
    raw = {f"r{n}": C / C.shift(n) - 1 for n in (5, 20, 60, 120, 250)}
    raw.update(v20=r.rolling(20).std(), v60=r.rolling(60).std(), d50=C / P.sma50 - 1, d200=C / P.sma200 - 1,
               h52=C / C.rolling(252).max() - 1, ldv=np.log1p((C * Vv).rolling(20).median()),
               relvol20=Vv.rolling(5).mean() / Vv.rolling(60).mean())
    F = {k: v.where(P.elig).rank(axis=1, pct=True).values - 0.5 for k, v in raw.items()}
    xt = (P.xiu / P.xiu.rolling(200).mean() - 1).values; br = (C > P.sma200).where(P.elig).mean(axis=1).values
    F["xiu_trend"] = np.repeat(xt[:, None], C.shape[1], 1); F["breadth"] = np.repeat(br[:, None] - 0.5, C.shape[1], 1)
    def ev(t):
        if isinstance(t, str): return F[t]
        if t[0] == "neg": return -ev(t[1])
        x, y = ev(t[1]), ev(t[2])
        return {"+": x + y, "-": x - y, "*": x * y, "max": np.fmax(x, y), "min": np.fmin(x, y)}[t[0]]
    return np.asarray(ev(tree), float)


cfg = {}
st = S2.Stat(P)
for w in ("S1_residual_mom", "S2_sharpe6", "S3_lowcorr", "S4_illiquid"):
    cfg["E3_" + w] = (lambda w=w: S2.exp3(pre, st, w))
asy = S2.Asym(P)
for q in (0.6, 0.8):
    for m in (1.0, 1.5):
        for br in (0.0, 0.5):
            cfg[f"E6_q{q}_m{m}_b{br}"] = (lambda q=q, m=m, br=br: S2.asym(pre, asy, q, m, br))
gpf = os.path.join(OUT, "exp2_gp_best.json")
if os.path.exists(gpf):
    tree = eval(json.load(open(gpf))["best_tree"])
    gsc = gp_daily_score(tree)
    cfg["E2_gp_best_20"] = lambda: S2.gp_tree(pre, gsc, 20)
need_rz = (not ONLY) or any(n.startswith("E5") for n in ONLY)
if need_rz:
    sig_f = os.path.join(OUT, "rizzy_sig.npz")
    if os.path.exists(sig_f):
        z = np.load(sig_f); sig = (z["e"], z["t"], z["s"])
    else:
        t0 = time.time(); sig = S2.rizzy_signals(P); np.savez_compressed(sig_f, e=sig[0], t=sig[1], s=sig[2])
        print(f"rizzy signals {sig[0].sum()} in {time.time()-t0:.0f}s", flush=True)
    for n in (5, 10):
        cfg[f"E5_rizzy_{n}"] = (lambda n=n: S2.rizzy(pre, sig, n))
if ONLY: cfg = {k: v for k, v in cfg.items() if k in ONLY}
rows = []
for name, mk in cfg.items():
    for cost in (0.001, 0.0025, 0.005):
        eq, tr = run(P, mk(), a, b, cost=cost, vix=vix)
        s = stats(eq, tr); s.update(name=name, cost=cost, phase=PH); rows.append(s)
        eq.to_frame("eq").to_parquet(os.path.join(OUT, f"eq_{PH}_{name}_{int(cost*10000)}.parquet"))
        print(f"{name:24s} {cost*100:.2f}% CAGR {s['cagr']:6.1f} DD {s['max_dd']:6.1f} trades {s['trades']:5d} end ${s['end']:,}", flush=True)
pd.DataFrame(rows).to_csv(os.path.join(OUT, f"exp_rest_{PH}{'_sel' if ONLY else ''}.csv"), index=False)
