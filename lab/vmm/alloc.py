import os, sys, json, numpy as np, pandas as pd

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

# ---- Allocation sweep (5 Nov 2026, rules fixed before run) ----
# $500 start. Momentum share w from 2% ($10) to 100% in 2% steps, rest XIU+3% div.
# Fixed split rebalanced each January (0.5% cost on the moved amount). Fractional shares (per-$ curves).
# Also: VMM (60-day volatility match, monthly). Window Jan 2009 - latest; sub-windows 2009-17, 2018-latest.
M = momentum_curve()
mr = (M / M.shift(1)).fillna(1).values
xr = XB.reindex(M.index).fillna(1).values
dates = M.index

def fixed(w, amount=500.0, cost=0.005, lo=None, hi=None):
    sel = np.ones(len(dates), bool)
    if lo: sel &= dates >= pd.Timestamp(lo)
    if hi: sel &= dates <= pd.Timestamp(hi)
    ii = np.where(sel)[0]
    m, x = amount * w, amount * (1 - w); out = []; yr = dates[ii[0]].year
    for k, i in enumerate(ii):
        if k: m *= mr[i]; x *= xr[i]
        if dates[i].year != yr:
            yr = dates[i].year; tot = m + x; move = abs(m - tot * w)
            tot -= move * cost; m, x = tot * w, tot * (1 - w)
        out.append(m + x)
    return pd.Series(out, index=dates[ii])

def st(s):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    y = s.resample("YE").last(); y = pd.concat([pd.Series([s.iat[0]], [s.index[0]]), y]).pct_change().dropna()
    return dict(final=round(s.iat[-1]), cagr=round(((s.iat[-1]/s.iat[0])**(1/yrs)-1)*100, 2),
                maxdd=round((s/s.cummax()-1).min()*100, 1), worst_yr=round(y.min()*100, 1))

rows = []
for w in np.round(np.arange(0, 1.0001, 0.02), 2):
    a = st(fixed(w)); a1 = st(fixed(w, hi="2017-12-31")); a2 = st(fixed(w, lo="2018-01-01"))
    rows.append(dict(mom_pct=int(w*100), mom_start=round(500*w), **a,
                     cagr_09_17=a1["cagr"], cagr_18_now=a2["cagr"], dd_18_now=a2["maxdd"]))
df = pd.DataFrame(rows); df["calmar"] = (df.cagr / -df.maxdd).round(3)
pd.set_option("display.width", 200); print(df.to_string(index=False))
x0 = df.iloc[0]
print("\nXIU only:", x0.to_dict())
print("Best final:", df.loc[df.final.idxmax()].to_dict())
print("Best return/drop:", df.loc[df.calmar.idxmax()].to_dict())
ok = df[(df.maxdd >= x0.maxdd) & (df.worst_yr >= x0.worst_yr - 5)]
print("Highest final with drop no worse than XIU and worst year within 5 pts:", ok.loc[ok.final.idxmax()].to_dict() if len(ok) else None)
print("Highest final with drop no worse than XIU:", df[df.maxdd >= x0.maxdd].loc[lambda d: d.final.idxmax()].to_dict())
print("Both halves beat XIU:", df[(df.cagr_09_17 > x0.cagr_09_17) & (df.cagr_18_now > x0.cagr_18_now)].mom_pct.tolist())
os.makedirs("results/vmm_alloc", exist_ok=True); df.to_csv("results/vmm_alloc/alloc.csv", index=False)
