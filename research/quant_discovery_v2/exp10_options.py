"""Batch 6: SPY options (PROTOCOL_batch6_options.md). Usage: python exp10_options.py <dir with oYYYY.parquet, spy.csv, vix.csv> <out> [eval]"""
import json, os, sys
import numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis

D, OUT = sys.argv[1:3]; EVAL = len(sys.argv) > 3; os.makedirs(OUT, exist_ok=True)
spy = pd.read_csv(os.path.join(D, "spy.csv"), parse_dates=["Date"]).set_index("Date")
raw, adj = spy["Close"], spy["Adjusted_close"]
vix = pd.read_csv(os.path.join(D, "vix.csv"), parse_dates=["Date"]).set_index("Date")["Close"]
cols = ["contract_id", "date", "expiration", "strike", "type", "bid", "ask", "delta"]
parts = []
for y in range(2008, 2026):
    x = pd.read_parquet(os.path.join(D, f"o{y}.parquet"), columns=cols)
    x["date"] = pd.to_datetime(x["date"]); x["expiration"] = pd.to_datetime(x["expiration"])
    x["dte"] = (x.expiration - x.date).dt.days
    x = x[(x.dte <= 460) & (x.ask > 0)]
    parts.append(x)
O = pd.concat(parts, ignore_index=True)
O["call"] = O["type"].str.lower().str.startswith("c")
days = pd.DatetimeIndex(sorted(O.date.unique())).intersection(raw.index)
byday = {d: g for d, g in O.groupby("date")}
priceof = O.set_index(["date", "contract_id"])["bid"]


def settle(exp):
    k = raw.index.searchsorted(exp, side="right") - 1
    return raw.iloc[k], raw.index[k]


def pick(d, call, delta, lo, hi):
    g = byday.get(d)
    if g is None: return None
    g = g[(g.call == call) & (g.dte >= lo) & (g.dte <= hi) & (g.bid > 0)]
    if g.empty: return None
    tgt = 0.5 * (lo + hi)
    e = g.loc[(g.dte - tgt).abs().idxmin(), "expiration"]; g = g[g.expiration == e]
    return g.loc[(g.delta - delta).abs().idxmin()]


def next_day(after):
    k = days.searchsorted(after, side="right")
    return days[k] if k < len(days) else None


def simulate(kind, tenor=(21, 45), months=None, vixmin=None, start="2008-01-01", end="2025-12-31"):
    lo, hi = tenor; d = next_day(pd.Timestamp(start) - pd.Timedelta(days=1)); end = pd.Timestamp(end)
    pot = 10000.0; curve = [(d, pot)]
    while d is not None and d <= end:
        S0 = raw.loc[d]; active = (months is None or d.month in months) and (vixmin is None or vix.asof(d) >= vixmin)
        if kind == "leaps":
            c = pick(d, True, 0.80, 270, 450)
            if c is None: d = next_day(d); continue
            exit_d = next_day(c.expiration - pd.Timedelta(days=90)); exit_d = min(exit_d or end, end)
            n = pot / S0; px = priceof.get((exit_d, c.contract_id), np.nan)
            if not np.isfinite(px): px = max(raw.asof(exit_d) - c.strike, 0)
            pot = pot + n * (px - c.ask); curve.append((exit_d, pot)); d = next_day(exit_d); continue
        if kind in ("pcs", "ic"):
            sd = 0.30 if kind == "pcs" else 0.20; ld = 0.15 if kind == "pcs" else 0.10
            sp, lp = pick(d, False, -sd, lo, hi), pick(d, False, -ld, lo, hi)
            legs = [(sp, lp, False)]
            if kind == "ic": legs.append((pick(d, True, sd, lo, hi), pick(d, True, ld, lo, hi), True))
            if any(a is None or b is None for a, b, _ in legs):
                d = next_day(d); continue
            exp = legs[0][0].expiration; ST, sd_ = settle(exp)
            if active:
                credit = sum(a.bid - b.ask for a, b, _ in legs)
                width = max(abs(a.strike - b.strike) for a, b, _ in legs)
                maxloss = width - credit
                if maxloss > 0 and credit > 0:
                    u = 0.20 * pot / maxloss
                    pay = 0.0
                    for a, b, call in legs:
                        if call: pay += max(ST - a.strike, 0) - max(ST - b.strike, 0)
                        else: pay += max(a.strike - ST, 0) - max(b.strike - ST, 0)
                    pot += u * (credit - pay)
            curve.append((sd_, pot)); d = next_day(exp); continue
        call = kind in ("cc", "longcall")
        o = pick(d, call, 0.30 if call else -0.30, lo, hi)
        if o is None: d = next_day(d); continue
        ST, sd_ = settle(o.expiration)
        if kind == "cc":
            tr = adj.asof(sd_) / adj.loc[d] - 1
            r = tr + ((o.bid - max(ST - o.strike, 0)) / S0 if active else 0)
        elif kind == "csp":
            r = (o.bid - max(o.strike - ST, 0)) / o.strike if active else 0
        else:
            r = 0.05 * (max(ST - o.strike, 0) / o.ask - 1) if active else 0
        pot *= 1 + r; curve.append((sd_, pot)); d = next_day(o.expiration)
    s = pd.Series(dict(curve)).sort_index(); s = s[~s.index.duplicated(keep="last")]
    return s


def stats(s):
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    r = s.pct_change().dropna(); per = len(r) / yrs
    return dict(cagr=round(((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1) * 100, 1),
                dd=round((s / s.cummax() - 1).min() * 100, 1),
                sharpe=round(r.mean() / r.std() * np.sqrt(per), 2) if r.std() > 0 else 0, trades=len(r))


W, M, Q = (4, 10), (21, 45), (60, 120)
WIN, SUM = {11, 12, 1, 2, 3, 4}, {5, 6, 7, 8, 9, 10}
cfg = {}
for k in ("cc", "csp", "longcall"):
    for nm, t in (("weekly", W), ("monthly", M), ("quarterly", Q)):
        cfg[f"{k}_{nm}"] = dict(kind=k, tenor=t)
    cfg[f"{k}_NovApr"] = dict(kind=k, tenor=M, months=WIN); cfg[f"{k}_MayOct"] = dict(kind=k, tenor=M, months=SUM)
cfg["leaps_80d"] = dict(kind="leaps")
for k in ("pcs", "ic"):
    cfg[f"{k}_monthly"] = dict(kind=k, tenor=M); cfg[f"{k}_vix20"] = dict(kind=k, tenor=M, vixmin=20)


def bench(a, b):
    s = adj.loc[a:b]; return 10000 * s / s.iloc[0]


ph = ("2023-01-01", "2025-12-31") if EVAL else ("2008-01-01", "2022-12-31")
rows = [dict(name="SPY_total_return", **stats(bench(*ph).resample("ME").last()))]
print(rows[0], flush=True)
sel = json.load(open(os.path.join(OUT, "opt_selection.json"))) if EVAL else None
curves = {}
for name, c in cfg.items():
    if EVAL and name != sel["selected"]: continue
    s = simulate(**c, start=ph[0], end=ph[1]); curves[name] = s
    st = stats(s); st["name"] = name; rows.append(st); print(st, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, f"opt_{'eval' if EVAL else 'dev'}.csv"), index=False)
if not EVAL:
    spy_dd = rows[0]["dd"]
    ok = R[(R.name != "SPY_total_return") & (R.dd >= spy_dd)].sort_values("cagr", ascending=False)
    best = ok.iloc[0]["name"] if len(ok) else None
    dsr = None
    if best:
        r = curves[best].pct_change().dropna(); N = 56
        srs = R[R.name != "SPY_total_return"].sharpe.values / np.sqrt(12); sr = r.mean() / r.std()
        emax = np.std(srs) * ((1 - 0.5772) * norm.ppf(1 - 1 / N) + 0.5772 * norm.ppf(1 - 1 / (N * np.e)))
        dsr = float(norm.cdf((sr - emax) * np.sqrt(len(r) - 1) / np.sqrt(1 - skew(r) * sr + (kurtosis(r, fisher=False) - 1) / 4 * sr ** 2)))
    out = dict(selected=best, spy_dev=rows[0], best_dev=ok.iloc[0].to_dict() if len(ok) else None, deflated_sharpe=dsr)
    json.dump(out, open(os.path.join(OUT, "opt_selection.json"), "w"), indent=1, default=str); print("SELECTED", out)
