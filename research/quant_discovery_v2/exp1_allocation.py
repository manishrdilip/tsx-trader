"""Batch 2, Exp 1: VMM capital allocation. Usage: python exp1_allocation.py <db> <vix.csv> <out> <dev|eval>"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel, stats
from engine2 import run2
import strategies as S

DB, VIXF, OUT, PH = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True)
P = Panel(os.path.join(DB, "panel.npz")); pre = S.Pre(P)
vix = pd.read_csv(VIXF, index_col=0, parse_dates=True).iloc[:, 0].to_dict()
vol = P.C.pct_change(fill_method=None).rolling(60).std().values
PER = {"dev": ("2009-01-02", "2022-12-30"), "eval": ("2023-01-03", str(P.dates[-1].date()))}
a, b = PER[PH]
base = lambda **kw: {**S.vmm_exact(pre), **kw}
V = {"P0_perm_park": base(park_mode="perm"), "P1_temp_park": base(park_mode="temp"), "P2_cash": base(park_mode=None, park=None),
     "P3_dynamic_xiu": base(park_mode=None, park=None, index_leg=True),
     "P4_volsize_perm": base(park_mode="perm", vol_size=True), "P4_volsize_cash": base(park_mode=None, park=None, vol_size=True),
     "P5_ddbrake_perm": base(park_mode="perm", dd_brake=0.20), "P5_ddbrake_cash": base(park_mode=None, park=None, dd_brake=0.20)}
only = os.environ.get("ONLY")
if only: V = {k: v for k, v in V.items() if k in only.split(",")}
# monthly contributions: $3,500 start + $350 first business day of each month
months = pd.Series(P.dates[(P.dates >= a) & (P.dates <= b)]).groupby(lambda k: 0).apply(lambda s: s)
md = pd.Series(P.dates).loc[lambda s: (s >= a) & (s <= b)]
first_days = md.groupby(md.dt.to_period("M")).min().iloc[1:]
deps = {d: 350.0 for d in first_days}
rows = []
for name, st in V.items():
    for cost in (0.001, 0.0025, 0.005):
        eq, tr, tw = run2(P, st, a, b, cost=cost, vix=vix, vol=vol)
        s = stats(eq, tr); s.update(name=name, cost=cost, phase=PH, scenario="fixed_5000"); rows.append(s)
        print(f"{name:18s} {cost*100:.2f}% fixed   CAGR {s['cagr']:6.1f} DD {s['max_dd']:6.1f} trades {s['trades']:4d} end ${s['end']:,}", flush=True)
    eq, tr, tw = run2(P, st, a, b, cost=0.005, cash0=3500.0, vix=vix, deposits=deps, vol=vol)
    s = stats(tw, tr, cash0=3500.0); s.update(name=name, cost=0.005, phase=PH, scenario="3500+350/mo TWR",
                                                end_balance=round(eq.iloc[-1]), deposited=3500 + 350 * len(deps))
    rows.append(s)
    print(f"{name:18s} 0.50% deposits TWR {s['cagr']:6.1f} DD {s['max_dd']:6.1f} balance ${s['end_balance']:,} (deposited ${s['deposited']:,})", flush=True)
pd.DataFrame(rows).to_csv(os.path.join(OUT, f"exp1_{PH}.csv"), index=False)
