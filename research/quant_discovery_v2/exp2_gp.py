"""Batch 2, Exp 2: genetic programming over cross-sectional rank features (dev period only for search).
Fast screen: monthly top-10 equal weight, 0.5% x turnover. Usage: python exp2_gp.py <db> <out>"""
import json, os, random, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Panel

DB, OUT = sys.argv[1:3]
random.seed(7); np.random.seed(7)
P = Panel(os.path.join(DB, "panel.npz"))
C = P.C; Vv = P.V
ret = C.pct_change(fill_method=None)
raw = {f"r{n}": C / C.shift(n) - 1 for n in (5, 20, 60, 120, 250)}
raw.update(v20=ret.rolling(20).std(), v60=ret.rolling(60).std(), d50=C / P.sma50 - 1, d200=C / P.sma200 - 1,
           h52=C / C.rolling(252).max() - 1, ldv=np.log1p((C * Vv).rolling(20).median()),
           relvol20=Vv.rolling(5).mean() / Vv.rolling(60).mean())
ms = P.dates.to_period("M"); mpos = np.where(np.r_[True, ms[1:] != ms[:-1]])[0]
mdates = P.dates[mpos]
E = P.elig.values[mpos].astype(bool)
F = {k: v.values[mpos] for k, v in raw.items()}
for k in F:  # cross-sectional pct rank among eligible, centred
    x = np.where(E, F[k], np.nan)
    F[k] = (pd.DataFrame(x).rank(axis=1, pct=True).values - 0.5)
xt = (P.xiu / P.xiu.rolling(200).mean() - 1).values[mpos]
br = (C > P.sma200).where(P.elig).mean(axis=1).values[mpos]
F["xiu_trend"] = np.repeat(xt[:, None], C.shape[1], 1); F["breadth"] = np.repeat(br[:, None] - 0.5, C.shape[1], 1)
Cf = C.ffill(limit=25).values
nxt = np.r_[mpos[1:], len(P.dates) - 1]
R = Cf[nxt] / Cf[mpos] - 1
ended = np.isfinite(Cf[mpos]) & (P.last_i[None, :] < nxt[:, None]) & (P.last_i[None, :] < len(P.dates) - 1)
R = np.where(ended, R - 0.005, R)
dev = (mdates >= "2009-01-01") & (mdates <= "2022-12-31")
FEATS = list(F); OPS = ["+", "-", "*", "max", "min", "neg"]


def rand_tree(d=0):
    if d >= 3 or (d > 0 and random.random() < 0.35):
        return random.choice(FEATS)
    op = random.choice(OPS)
    return (op, rand_tree(d + 1)) if op == "neg" else (op, rand_tree(d + 1), rand_tree(d + 1))


def ev(t):
    if isinstance(t, str): return F[t]
    if t[0] == "neg": return -ev(t[1])
    a, b = ev(t[1]), ev(t[2])
    return {"+": a + b, "-": a - b, "*": a * b, "max": np.fmax(a, b), "min": np.fmin(a, b)}[t[0]]


def size(t): return 1 if isinstance(t, str) else 1 + sum(size(c) for c in t[1:])


def depth(t): return 0 if isinstance(t, str) else 1 + max(depth(c) for c in t[1:])


def backtest(t, mask, n=10):
    s = np.where(E, np.asarray(ev(t), dtype=float), np.nan)
    rets, turn, prev = [], [], set()
    for m in np.where(mask)[0]:
        row = s[m]; ok = np.isfinite(row) & np.isfinite(R[m])
        if ok.sum() < 30: rets.append(0.0); turn.append(0.0); continue
        idx = np.where(ok)[0][np.argsort(-row[ok])[:n]]
        cur = set(idx); tw = len(cur - prev) / n if prev else 1.0
        rets.append(R[m, idx].mean() - 2 * 0.005 * tw); turn.append(tw); prev = cur
    r = np.array(rets); eq = np.cumprod(1 + r)
    sh = r.mean() / r.std() * np.sqrt(12) if r.std() > 0 else 0
    dd = (eq / np.maximum.accumulate(eq) - 1).min()
    cagr = eq[-1] ** (12 / len(r)) - 1
    return dict(sharpe=sh, cagr=cagr, dd=dd, turn=np.mean(turn) * 12, r=r)


def fitness(t):
    b = backtest(t, dev)
    return b["sharpe"] - 0.002 * size(t) - 0.1 * b["turn"] / 12 - 0.5 * abs(b["dd"]), b


def mutate(t):
    if isinstance(t, str) or random.random() < 0.3: return rand_tree(1)
    k = random.randrange(1, len(t)); c = list(t); c[k] = mutate(t[k]); return tuple(c)


def subtrees(t, out=None):
    out = [] if out is None else out; out.append(t)
    if not isinstance(t, str):
        for c in t[1:]: subtrees(c, out)
    return out


def cross(a, b):
    if isinstance(a, str): return random.choice(subtrees(b))
    k = random.randrange(1, len(a)); c = list(a); c[k] = random.choice(subtrees(b)); return tuple(c)


seen, log = {}, []
def score(t):
    key = repr(t)
    if key in seen: return seen[key][0]
    if depth(t) > 3: seen[key] = (-9, None); return -9
    f, b = fitness(t); seen[key] = (f, b)
    log.append({"tree": key, "fit": round(f, 4), "dev_sharpe": round(b["sharpe"], 3), "dev_cagr": round(b["cagr"] * 100, 1),
                "dev_dd": round(b["dd"] * 100, 1), "turn": round(b["turn"], 2), "nodes": size(t)})
    return f


pop = [rand_tree() for _ in range(250)]
gen = 0
while len(seen) < 5000 and gen < 60:
    fs = [score(t) for t in pop]
    ranked = [t for _, t in sorted(zip(fs, pop), key=lambda z: -z[0])]
    print(f"gen {gen}: evaluated {len(seen)}, best fit {max(fs):.3f} {ranked[0]}", flush=True)
    elite = ranked[:25]; newp = list(elite)
    while len(newp) < 250:
        a = max(random.sample(pop, 5), key=lambda t: seen[repr(t)][0])
        if random.random() < 0.6:
            b = max(random.sample(pop, 5), key=lambda t: seen[repr(t)][0]); newp.append(cross(a, b))
        else:
            newp.append(mutate(a))
    pop = newp; gen += 1
for t in pop: score(t)
L = pd.DataFrame(log).sort_values("fit", ascending=False)
L.to_csv(os.path.join(OUT, "exp2_gp_all.csv"), index=False)
best = L.iloc[0]
# Deflated Sharpe (Bailey & Lopez de Prado) for the best monthly dev Sharpe given N trials
from scipy.stats import norm, skew, kurtosis
N = len(L); srs = L.dev_sharpe.values / np.sqrt(12)
emax = srs.std() * ((1 - 0.5772) * norm.ppf(1 - 1 / N) + 0.5772 * norm.ppf(1 - 1 / (N * np.e)))
bt = backtest(eval(best.tree), dev)["r"]; sr = bt.mean() / bt.std()
dsr = norm.cdf((sr - emax) * np.sqrt(len(bt) - 1) / np.sqrt(1 - skew(bt) * sr + (kurtosis(bt, fisher=False) - 1) / 4 * sr ** 2))
res = {"evaluated": N, "best_tree": best.tree, "best_dev": best.to_dict(), "deflated_sharpe_prob": round(float(dsr), 3),
       "expected_max_monthly_sr_by_luck": round(float(emax), 3), "best_monthly_sr": round(float(sr), 3)}
json.dump(res, open(os.path.join(OUT, "exp2_gp_best.json"), "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
