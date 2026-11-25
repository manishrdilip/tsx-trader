"""Batch 1: exact VMM + XIU benchmarks and ideas A-H on the development period (2009-2022) at all costs.
Usage: python run_batch1.py <db_dir> <vix.csv> <out_dir> [dev|eval]"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel, run, stats
import strategies as S
from ml import walk_forward

DB, VIXF, OUT, PHASE = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
os.makedirs(OUT, exist_ok=True)
P = Panel(os.path.join(DB, "panel.npz"))
vix = pd.read_csv(VIXF, index_col=0, parse_dates=True).iloc[:, 0].to_dict()
pre = S.Pre(P)
PER = {"dev": ("2009-01-02", "2022-12-30"), "eval": ("2023-01-03", str(P.dates[-1].date())),
       "full": ("2009-01-02", str(P.dates[-1].date()))}
predf = os.path.join(OUT, "ml_preds.parquet")
if os.path.exists(predf):
    preds = pd.read_parquet(predf)
else:
    preds = walk_forward(P); preds.to_parquet(predf)

configs = {"VMM_exact": lambda: S.vmm_exact(pre),
           "VMM_nopark": lambda: {**S.vmm_exact(pre), "park": None}}
for n in (10, 20):
    configs[f"A_riskadj_mom_{n}"] = (lambda n=n: S.mom_variant(pre, "A", n))
    configs[f"B_blend_mom_{n}"] = (lambda n=n: S.mom_variant(pre, "B", n))
    configs[f"H_lgbm_{n}"] = (lambda n=n: S.ml_rank(pre, preds, n))
for thr in (5, 10):
    for n in (5, 10):
        configs[f"C_rsi2_{thr}_{n}"] = (lambda thr=thr, n=n: S.mean_rev(pre, thr, n))
for n in (5, 10):
    configs[f"D_squeeze_{n}"] = (lambda n=n: S.squeeze(pre, n))
    configs[f"E_hivol_{n}"] = (lambda n=n: S.hi_volume(pre, n))
    configs[f"F_gaprev_{n}"] = (lambda n=n: S.gap_rev(pre, n))
for k in (2, 3):
    configs[f"G_sector_{k}"] = (lambda k=k: S.sector_rot(pre, k))

only = os.environ.get("ONLY")
if only: configs = {k: v for k, v in configs.items() if k in only.split(",")}
a, b = PER[PHASE]
res = []
for name, mk in configs.items():
    for cost in (0.001, 0.0025, 0.005):
        t0 = time.time()
        eq, tr = run(P, mk(), a, b, cost=cost, vix=vix)
        st = stats(eq, tr); st.update(name=name, cost=cost, phase=PHASE)
        res.append(st)
        eq.to_frame("eq").to_parquet(os.path.join(OUT, f"eq_{PHASE}_{name}_{int(cost*10000)}.parquet"))
        print(f"{name:20s} {cost*100:.2f}%  CAGR {st['cagr']:6.1f}  DD {st['max_dd']:6.1f}  "
              f"trades {st['trades']:5d}  end ${st['end']:,}  ({time.time()-t0:.0f}s)", flush=True)
x = P.C["XIU.TO"].loc[a:b]
xe = 5000 * x / x.iloc[0]
st = stats(xe, []); st.update(name="XIU_buyhold", cost=0, phase=PHASE); res.append(st)
print(f"{'XIU_buyhold':20s}         CAGR {st['cagr']:6.1f}  DD {st['max_dd']:6.1f}  end ${st['end']:,}")
pd.DataFrame(res).to_csv(os.path.join(OUT, f"results_{PHASE}{'_'+only if only else ''}.csv"), index=False)
