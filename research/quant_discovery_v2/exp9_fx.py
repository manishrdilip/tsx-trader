"""Batch 5: forex strategies (PROTOCOL_batch5_fx.md). Usage: python exp9_fx.py <fx_dir> <out> [eval]"""
import json, os, sys
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis

FX, OUT = sys.argv[1:3]; EVAL = len(sys.argv) > 3; os.makedirs(OUT, exist_ok=True)
PAIRS = "EURUSD GBPUSD AUDUSD NZDUSD USDJPY USDCAD USDCHF USDNOK USDSEK EURJPY EURGBP EURCHF AUDJPY GBPJPY".split()
px = {}
for p in PAIRS:
    d = pd.read_csv(os.path.join(FX, p + ".csv")).dropna(subset=["Close"])
    d = d[d.Close > 0]; d["Date"] = pd.to_datetime(d["Date"]); s = d.set_index("Date")["Close"]
    s = s[~s.index.duplicated()]; s = s[s.index.dayofweek < 5]
    r = s.pct_change()
    s = s[~((r.abs() > 0.15) & (r.shift(-1).abs() > 0.10))]  # one-day spike prints
    px[p] = s
C = pd.DataFrame(px).sort_index().loc["1990-01-01":].ffill(limit=3)
R = C.pct_change(fill_method=None).fillna(0)
vol = R.rolling(60).std() * np.sqrt(252)
w_vol = (0.10 / vol).clip(upper=5)   # 10% vol target, max 5x


def run(pos, cost=0.0002):
    """pos: target signed position (-1..1) at close t (unscaled). Lag 1 day, vol-scale, equal weight over active pairs."""
    sig = pos.reindex(R.index).fillna(0)
    lev = (sig * w_vol).shift(1)                       # decided at t, held from t+1
    n = lev.abs().gt(0).sum(axis=1).replace(0, np.nan)
    gross = (lev * R).sum(axis=1) / n
    turn = lev.diff().abs().sum(axis=1) / n
    return (gross - turn * cost).fillna(0)


def ts_mom(n): return np.sign(C / C.shift(n) - 1)
def ma(f, s): return np.sign(C.rolling(f).mean() - C.rolling(s).mean())
def donch(n, m):
    hi, lo = C.rolling(n).max(), C.rolling(n).min(); xh, xl = C.rolling(m).max(), C.rolling(m).min()
    out = pd.DataFrame(0.0, C.index, C.columns); cur = np.zeros(C.shape[1])
    Cv, H, L, XH, XL = C.values, hi.values, lo.values, xh.values, xl.values
    for i in range(len(C)):
        for j in range(C.shape[1]):
            c = Cv[i, j]
            if not np.isfinite(c): continue
            if cur[j] == 0:
                if c >= H[i, j]: cur[j] = 1
                elif c <= L[i, j]: cur[j] = -1
            elif cur[j] == 1 and c <= XL[i, j]: cur[j] = 0
            elif cur[j] == -1 and c >= XH[i, j]: cur[j] = 0
        out.iloc[i] = cur
    return out
def zfade():
    z = (C - C.rolling(5).mean()) / C.rolling(20).std()
    out = pd.DataFrame(0.0, C.index, C.columns); cur = np.zeros(C.shape[1]); Z = z.values
    for i in range(len(C)):
        for j in range(C.shape[1]):
            v = Z[i, j]
            if not np.isfinite(v): continue
            if cur[j] == 0 and abs(v) > 1.5: cur[j] = -np.sign(v)
            elif cur[j] != 0 and np.sign(v) != -cur[j]: cur[j] = 0
        out.iloc[i] = cur
    return out
def rsi2fade():
    d = C.diff(); up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    e = (rsi < 10).astype(float) - (rsi > 90).astype(float)
    return e.replace(0, np.nan).ffill(limit=2).fillna(0)  # hold 3 days
USD_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCAD", "USDCHF", "USDNOK", "USDSEK"]
def ccy_returns_sign():  # +1 if the pair is CCY/USD (long pair = long currency), -1 if USD/CCY
    return pd.Series({p: (1 if p.endswith("USD") else -1) for p in USD_PAIRS})
def xs_mom(n):
    sg = ccy_returns_sign(); cm = (C[USD_PAIRS] / C[USD_PAIRS].shift(n) - 1) * sg
    ms = C.index.to_period("M"); first = pd.Series(np.r_[True, ms[1:] != ms[:-1]], C.index)
    out = pd.DataFrame(np.nan, C.index, C.columns)
    for d in C.index[first.values]:
        row = cm.loc[d].dropna()
        if len(row) < 7: continue
        o = row.sort_values(); pos = pd.Series(0.0, C.columns)
        for p in o.index[-3:]: pos[p] = sg[p]
        for p in o.index[:3]: pos[p] = -sg[p]
        out.loc[d] = pos
    return out.ffill().fillna(0)
def month_end_usd():
    sg = ccy_returns_sign(); ms = pd.Series(C.index.to_period("M"), C.index)
    rank_from_end = ms.groupby(ms).cumcount(ascending=False)
    on = rank_from_end.isin([3, 2, 1])  # signal on the 4th..2nd last day -> held over the last 3 days
    out = pd.DataFrame(0.0, C.index, C.columns)
    for p in USD_PAIRS: out.loc[on, p] = -sg[p]   # long USD
    return out

S = {f"T_mom{n}": (lambda n=n: ts_mom(n)) for n in (63, 126, 252)}
S.update({"MA_50_200": lambda: ma(50, 200), "MA_20_100": lambda: ma(20, 100)})
S.update({f"DON_{n}_{m}": (lambda n=n, m=m: donch(n, m)) for n, m in ((20, 10), (55, 20), (100, 50))})
S.update({"MR_z5": zfade, "MR_rsi2": rsi2fade, "XS_mom63": lambda: xs_mom(63), "XS_mom252": lambda: xs_mom(252),
          "SEAS_monthend_usd": month_end_usd})


def st(r):
    r = r[r.index >= r.ne(0).idxmax()]
    eq = (1 + r).cumprod(); yrs = len(r) / 252
    return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2), sharpe=round(r.mean() / r.std() * np.sqrt(252), 2),
                dd=round((eq / eq.cummax() - 1).min() * 100, 1))


rows, rets = [], {}
for name, f in S.items():
    pos = f()
    for cost in (0.0002, 0.0005):
        r = run(pos, cost); rets[(name, cost)] = r
        a, b1, b2 = r.loc["1990":"2022"], r.loc["1990":"2006"], r.loc["2007":"2022"]
        row = dict(name=name, cost=cost, **{f"dev_{k}": v for k, v in st(a).items()},
                   sh_1990_06=st(b1)["sharpe"], sh_2007_22=st(b2)["sharpe"])
        rows.append(row); print(row, flush=True)
D = pd.DataFrame(rows); D.to_csv(os.path.join(OUT, "fx_dev.csv"), index=False)
d2 = D[D.cost == 0.0002].sort_values("dev_sharpe", ascending=False); best = d2.iloc[0]["name"]
# Deflated Sharpe for the best (daily), N = 13 + 5
N = 18; srs = d2.dev_sharpe.values / np.sqrt(252)
emax = np.std(srs) * ((1 - 0.5772) * norm.ppf(1 - 1 / N) + 0.5772 * norm.ppf(1 - 1 / (N * np.e)))
rb = rets[(best, 0.0002)].loc["1990":"2022"]; rb = rb[rb.index >= rb.ne(0).idxmax()]; sr = rb.mean() / rb.std()
dsr = norm.cdf((sr - emax) * np.sqrt(len(rb) - 1) / np.sqrt(1 - skew(rb) * sr + (kurtosis(rb, fisher=False) - 1) / 4 * sr ** 2))
sel = dict(selected=best, dev=d2.iloc[0].to_dict(), deflated_sharpe=round(float(dsr), 3))
print("SELECTED", sel); json.dump(sel, open(os.path.join(OUT, "fx_selection.json"), "w"), indent=1, default=str)
if EVAL:
    out = {}
    for name in S:
        out[name] = st(rets[(name, 0.0002)].loc["2023":])
    print("EVAL selected", best, out[best]); json.dump({"selected": best, "eval": out[best], "all_eval_for_record": out},
                                                       open(os.path.join(OUT, "fx_eval.json"), "w"), indent=1)
