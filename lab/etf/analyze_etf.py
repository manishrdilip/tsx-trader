"""Per-ETF stats over full available history + momentum rotation test vs XIC buy-and-hold.
Writes results/etf/etf_stats.csv and results/etf/rotation_summary.csv.
"""
import os
import numpy as np, pandas as pd

OUT = "results/etf"; os.makedirs(OUT, exist_ok=True)
C = pd.read_parquet("data/etf_Close.parquet")
H = pd.read_parquet("data/etf_High.parquet") if os.path.exists("data/etf_High.parquet") else None
C = C.ffill(limit=5)

# per-ETF stats
rows = []
for t in C.columns:
    s = C[t].dropna()
    if len(s) < 252: continue
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    dd = float((s / s.cummax() - 1).min())
    def r(n): return s.iloc[-1] / s.iloc[-1 - n] - 1 if len(s) > n else np.nan
    rows.append(dict(ticker=t, start=s.index[0].date(), years=round(yrs, 1), cagr=cagr, max_dd=dd,
                     calmar=cagr / abs(dd) if dd < 0 else np.nan, ret_1y=r(252), ret_3y=r(756), ret_5y=r(1260),
                     ret_10y=r(2520), ret_20y=r(5040)))
st = pd.DataFrame(rows).sort_values("cagr", ascending=False)
st.to_csv(f"{OUT}/etf_stats.csv", index=False)

# rotation: monthly, hold top N by trailing 12m return (skip last month), equal weight, costs 0.5%/side
def rotation(N, start, end, cost=0.005, lookback=252, skip=21):
    px = C.loc[start:end]
    mo = px.resample("ME").last().index
    px_m = px.reindex(px.index).ffill()
    eq = 1.0; curve = []; hold = []
    prev = None
    dates = px.index
    ret_lb = px.shift(skip) / px.shift(lookback) - 1
    cash_val = 1.0
    w = {}
    eqs = []
    last_rb = None
    for i, d in enumerate(dates):
        if i > 0 and w:
            day_ret = sum(wt * (px.at[d, t] / px.at[dates[i-1], t] - 1) for t, wt in w.items() if pd.notna(px.at[d, t]) and pd.notna(px.at[dates[i-1], t]))
            eq *= (1 + day_ret)
        if d in mo:
            cand = ret_lb.loc[d].dropna()
            cand = cand[px.loc[d, cand.index].notna()]
            top = cand.sort_values(ascending=False).head(N).index.tolist()
            new_w = {t: 1.0 / N for t in top} if top else {}
            turnover = sum(abs(new_w.get(t, 0) - w.get(t, 0)) for t in set(new_w) | set(w))
            eq *= (1 - cost * turnover)
            w = new_w; hold.append((d.date(), top))
        eqs.append(eq)
    eqs = pd.Series(eqs, index=dates)
    yrs = (dates[-1] - dates[0]).days / 365.25
    cagr = eqs.iloc[-1] ** (1 / yrs) - 1
    dd = float((eqs / eqs.cummax() - 1).min())
    return dict(N=N, start=str(dates[0].date()), end=str(dates[-1].date()), years=round(yrs, 1), cagr=cagr,
                max_dd=dd, calmar=cagr / abs(dd) if dd < 0 else np.nan), eqs, hold

summ = []
xic = C["XIC.TO"] if "XIC.TO" in C.columns else None
for (s, e) in [("2006-01-01", "2026-10-30"), ("2016-10-31", "2026-10-30")]:
    for N in [5, 10]:
        d, _, _ = rotation(N, s, e)
        summ.append(d)
    if xic is not None:
        x = xic.loc[s:e].dropna()
        yrs = (x.index[-1] - x.index[0]).days / 365.25
        cagr = (x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1
        dd = float((x / x.cummax() - 1).min())
        summ.append(dict(N="XIC_buy_hold", start=str(x.index[0].date()), end=str(x.index[-1].date()), years=round(yrs, 1), cagr=cagr, max_dd=dd, calmar=cagr / abs(dd)))
pd.DataFrame(summ).to_csv(f"{OUT}/rotation_summary.csv", index=False)
print(st.head(25).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print(pd.DataFrame(summ).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
