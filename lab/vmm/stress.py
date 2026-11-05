"""VMM v1 stress battery. Pre-registered 4 Nov 2026, before any run. Goal: try to BREAK VMM v1.

VMM v1 (claude/vm-momentum-plan-v1.md): momentum part = v3 rules (TSX .TO, $1-100, 20d median $vol >= 300k,
252+ days history; buy if 12M return in top 10% of eligible, close > SMA200, XIU > SMA200, free slot of 20,
strongest first; sell if close < SMA200 or 12M rank falls out of top 40%; act at next close; 0.5%/side).
Blend: first trading day of each month, momentum share = vol60(XIU) / vol60(momentum), capped at 100%.
Lump $5,000, Jan 2009 to latest. Benchmark: XIU + 3%/yr dividends, same blend costs ignored for XIU.

Data: data-latest prices.parquet (survivors only; cleaning per C1 v1.1). Survivorship is NOT fixed here:
EODHD delisted file is not in the repo. T6 applies a bankruptcy haircut instead.

Tests and kill criteria (VMM "survives" a test only if it meets the bar):
  T1 Random control   momentum ranking replaced by random ranking (same filters, slots, exits), 30 seeds.
                      Survive: real VMM final value beats >= 95% of random runs.
  T2 Neighbours       lookback 6/9/12M x entry top 5/10/20% x exit top 30/40/50% x slots 10/20/30 (81 runs).
                      Survive: >= 70% of neighbours beat XIU+div on final value.
  T3 Costs            0.25 / 0.5 / 1.0 / 1.5% per side. Survive: beats XIU+div at 1.0%.
  T4 Start year       start each Jan 2009..2021, hold to latest. Survive: beats XIU+div in >= 70% of starts.
  T5 Significance     monthly excess return vs XIU+div: t-test and 10,000 block-bootstrap (6-month blocks).
                      Survive: one-sided p < 0.05.
  T6 Bankruptcy drag  each year, 3% of momentum holdings (random) go to zero; 50 seeds. Survive: median beats XIU+div.
  T7 Sub-periods      2009-2014, 2015-2020, 2021-latest separately. Survive: beats XIU+div in >= 2 of 3.
Verdict: VMM is "robust (backtest)" only if it survives all 7. It still would not be proven until forward trading.
"""
import sys, json, numpy as np, pandas as pd

P = pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "prices.parquet")
P["Date"] = pd.to_datetime(P["Date"])
P = P.drop_duplicates(["ticker", "Date"])
xiu = P[P.ticker == "XIU.TO"].set_index("Date")["Close"].sort_index()
S = P[P.ticker.str.endswith(".TO") & ~P.ticker.isin(["XIU.TO", "XIC.TO"])]
bad = S.groupby("ticker")["Close"].min() <= 0
S = S[~S.ticker.isin(bad[bad].index)]
mv = S.sort_values("Date").groupby("ticker")["Close"].pct_change().abs()
big = S.loc[mv > 0.40, "ticker"].unique()
S = S[~S.ticker.isin(big)]
C = S.pivot(index="Date", columns="ticker", values="Close").sort_index()
V = S.pivot(index="Date", columns="ticker", values="Volume").reindex(C.index)
idx = C.index[C.index >= "2008-01-01"]
C, V = C.loc[idx], V.loc[idx]
xiu = xiu.reindex(idx).ffill()
C = C.ffill(limit=5)
print("tickers", C.shape[1], "days", len(idx), idx[0].date(), idx[-1].date())

DV = (C * V).rolling(20, min_periods=15).median()
SMA200 = C.rolling(200, min_periods=200).mean()
HIST = C.notna().cumsum()
XIU200 = xiu.rolling(200).mean()
RET = {L: C / C.shift(L) - 1 for L in (126, 189, 252)}
Cv, S200v, DVv, Hv = C.values, SMA200.values, DV.values, HIST.values
tick = np.array(C.columns)
XIUv, XIU200v = xiu.values, XIU200.values
START = np.searchsorted(idx, pd.Timestamp("2009-01-01"))

def momentum_curve(look=252, entry=0.10, exit_=0.40, slots=20, cost=0.005, rng=None, bankrupt=0.0, brng=None):
    """Daily equity curve (per $1) of the momentum part alone, v3 rules."""
    Rv = RET[look].values
    cash, pos, rscore = 1.0, {}, None  # pos: col -> shares
    eq = np.full(len(idx), np.nan); pend_buy, pend_sell = [], []
    last_bk_year = None
    for d in range(START, len(idx)):
        px = Cv[d]
        # fills at today's close
        for j in pend_sell:
            if j in pos and not np.isnan(px[j]):
                cash += pos.pop(j) * px[j] * (1 - cost)
        val = cash + sum(s * px[j] for j, s in pos.items() if not np.isnan(px[j]))
        for j in pend_buy:
            if len(pos) >= slots or j in pos or np.isnan(px[j]): continue
            amt = min(val / slots, cash)
            sh = amt / (px[j] * (1 + cost))
            if sh > 0: pos[j] = sh; cash -= sh * px[j] * (1 + cost)
        pend_buy, pend_sell = [], []
        # bankruptcy drag: once a year, each holding dies with prob `bankrupt`
        if bankrupt and idx[d].year != last_bk_year:
            last_bk_year = idx[d].year
            for j in list(pos):
                if brng.random() < bankrupt: pos.pop(j)
        held_val = sum(s * px[j] for j, s in pos.items() if not np.isnan(px[j]))
        eq[d] = cash + held_val
        # signals for tomorrow
        elig = (px >= 1) & (px <= 100) & (DVv[d] >= 3e5) & (Hv[d] >= 252) & ~np.isnan(Rv[d])
        if elig.sum() < 20: continue
        r = Rv[d].copy()
        if rng is not None:  # random control: random score per stock, redrawn monthly (like a slow ranking)
            if d == START or idx[d].month != idx[d-1].month:
                rscore = rng.random(len(r))
            r = np.where(elig, rscore, np.nan)
        rank = np.full(len(r), np.nan)
        er = r[elig]; order = er.argsort().argsort()
        rank[elig] = 1 - order / (len(er) - 1)  # 0 = best
        for j in pos:
            if np.isnan(px[j]) or px[j] <= S200v[d][j] or not (rank[j] <= exit_):
                pend_sell.append(j)
        if XIUv[d] > XIU200v[d]:
            cand = np.where(elig & (rank <= entry) & (px > S200v[d]))[0]
            cand = [j for j in cand[np.argsort(rank[cand])] if j not in pos]
            free = slots - (len(pos) - len(pend_sell))
            pend_buy = cand[:max(free, 0)]
    return pd.Series(eq, index=idx).iloc[START:]

XB = (xiu / xiu.shift(1)).fillna(1) * (1.03 ** (1 / 252))  # XIU + 3%/yr dividends, daily factor

def blend(mom, start=None, end=None, amount=5000.0, cost=0.005):
    m = mom.copy()
    if start: m = m[m.index >= start]
    if end: m = m[m.index <= end]
    mr = (m / m.shift(1)).fillna(1).values; xr = XB.reindex(m.index).fillna(1).values
    dates = m.index; vm, vx = amount * 0.5, amount * 0.5; out = []
    hist_m, hist_x = [], []
    for k in range(len(dates)):
        if k > 0 and dates[k].month != dates[k - 1].month:
            tot = vm + vx
            if len(hist_m) >= 60:
                sm, sx = np.std(hist_m[-60:]), np.std(hist_x[-60:])
                w = min(1.0, sx / sm) if sm > 0 else 1.0
            else: w = 0.5
            tm = tot * w; tc = abs(tm - vm) * cost
            vm, vx = tm - tc / 2, tot - tm - tc / 2
        vm *= mr[k]; vx *= xr[k]
        hist_m.append(mr[k] - 1); hist_x.append(xr[k] - 1)
        out.append(vm + vx)
    return pd.Series(out, index=dates)

def xiu_curve(start=None, end=None, amount=5000.0):
    x = XB.iloc[START:]
    if start: x = x[x.index >= start]
    if end: x = x[x.index <= end]
    return amount * x.cumprod() / x.iloc[0]

def stats(s):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    return dict(final=round(s.iat[-1]), cagr=round(((s.iat[-1] / s.iat[0]) ** (1 / yrs) - 1) * 100, 1),
                dd=round((s / s.cummax() - 1).min() * 100, 1))

R = {}
import os
ONLY = os.environ.get("ONLY")
base_m = momentum_curve(); base = blend(base_m); X = xiu_curve()
R["base"] = {"VMM": stats(base), "XIU+div": stats(X)}
print("BASE", R["base"])

# T1 random control
rnd = [blend(momentum_curve(rng=np.random.default_rng(s))).iat[-1] for s in range(30)]
pct = np.mean(np.array(rnd) < base.iat[-1]) * 100
R["T1"] = dict(vmm=round(base.iat[-1]), random_median=round(np.median(rnd)), random_p95=round(np.percentile(rnd, 95)),
               beats_pct=round(pct, 1), survive=bool(pct >= 95))
print("T1", R["T1"])
if ONLY == "T1":
    print("T1 random finals", sorted(round(v) for v in rnd)); sys.exit(0)

# T2 neighbours
nb = []
for L in (126, 189, 252):
    for en in (0.05, 0.10, 0.20):
        for ex in (0.30, 0.40, 0.50):
            for sl in (10, 20, 30):
                f = blend(momentum_curve(look=L, entry=en, exit_=ex, slots=sl)).iat[-1]
                nb.append(dict(look=L, entry=en, exit=ex, slots=sl, final=round(f)))
nbd = pd.DataFrame(nb); share = (nbd.final > X.iat[-1]).mean() * 100
R["T2"] = dict(n=len(nbd), beat_xiu_pct=round(share, 1), median_final=round(nbd.final.median()),
               worst=round(nbd.final.min()), survive=bool(share >= 70))
print("T2", R["T2"])

# T3 costs
t3 = {c: round(blend(momentum_curve(cost=c / 100), cost=c / 100).iat[-1]) for c in (0.25, 0.5, 1.0, 1.5)}
R["T3"] = dict(finals=t3, xiu=round(X.iat[-1]), survive=bool(t3[1.0] > X.iat[-1]))
print("T3", R["T3"])

# T4 start years (momentum curve already running; blend from each start)
t4 = []
for y in range(2009, 2022):
    b = blend(base_m, start=f"{y}-01-01"); x = xiu_curve(start=f"{y}-01-01")
    t4.append(dict(start=y, vmm=round(b.iat[-1]), xiu=round(x.iat[-1]), win=bool(b.iat[-1] > x.iat[-1])))
w4 = np.mean([r["win"] for r in t4]) * 100
R["T4"] = dict(rows=t4, win_pct=round(w4, 1), survive=bool(w4 >= 70))
print("T4", R["T4"]["win_pct"], [ (r['start'], r['win']) for r in t4])

# T5 significance
bm = base.resample("ME").last().pct_change().dropna(); xm = X.resample("ME").last().pct_change().dropna()
ex = (bm - xm).dropna().values
t = ex.mean() / (ex.std(ddof=1) / np.sqrt(len(ex)))
from math import erf, sqrt
p_t = 1 - 0.5 * (1 + erf(t / sqrt(2)))
rng = np.random.default_rng(7); B = 6; nb_ = len(ex) // B; boots = []
for _ in range(10000):
    starts = rng.integers(0, len(ex) - B, nb_)
    boots.append(np.concatenate([ex[s:s + B] for s in starts]).mean())
p_b = float(np.mean(np.array(boots) <= 0))
R["T5"] = dict(months=len(ex), mean_excess_pct=round(ex.mean() * 100, 3), t=round(t, 2), p_t=round(p_t, 4),
               p_boot=round(p_b, 4), survive=bool(max(p_t, p_b) < 0.05))
print("T5", R["T5"])

# T6 bankruptcy drag
t6 = [blend(momentum_curve(bankrupt=0.03, brng=np.random.default_rng(100 + s))).iat[-1] for s in range(50)]
R["T6"] = dict(median=round(np.median(t6)), p10=round(np.percentile(t6, 10)), xiu=round(X.iat[-1]),
               survive=bool(np.median(t6) > X.iat[-1]))
print("T6", R["T6"])

# T7 sub-periods
t7 = []
for a, b_ in (("2009-01-01", "2014-12-31"), ("2015-01-01", "2020-12-31"), ("2021-01-01", None)):
    v = blend(base_m, start=a, end=b_); x = xiu_curve(start=a, end=b_)
    t7.append(dict(period=f"{a[:4]}-{(b_ or 'now')[:4]}", vmm=stats(v), xiu=stats(x), win=bool(v.iat[-1] > x.iat[-1])))
R["T7"] = dict(rows=t7, survive=bool(sum(r["win"] for r in t7) >= 2))
print("T7", R["T7"])

R["survived"] = [k for k in ("T1","T2","T3","T4","T5","T6","T7") if R[k]["survive"]]
R["verdict"] = "robust (backtest)" if len(R["survived"]) == 7 else "NOT robust"
print("SURVIVED", R["survived"], "VERDICT", R["verdict"])
import os; os.makedirs("results/vmm_stress", exist_ok=True)
json.dump(R, open("results/vmm_stress/stress.json", "w"), indent=1, default=str)
nbd.to_csv("results/vmm_stress/neighbours.csv", index=False)
