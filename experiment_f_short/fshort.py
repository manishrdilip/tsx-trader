"""
Experiment F-short: four short-term families under one shared portfolio and execution model.
Rules are in PREREGISTERED.md. Research only. Not financial advice.

Usage:
  python experiment_f_short/fshort.py --panel panel.pkl.gz --equities experiment_e/universe.json --out out

Indicators use simple 14-day averages for RSI and ATR.
"""
import argparse
import gzip
import json
import math
import os
import pickle

import numpy as np
import pandas as pd

CAPITAL = 5000.0
RISK_FRAC = 0.005
MAX_SLOTS = 3
MAX_POS_FRAC = 1 / 3
STOP_ATR = 1.5
GAP_CAP = 0.01
HOLDS = (2, 3, 5)
# Cost scenarios. Commission is a per-side percentage; spread and slippage are ESTIMATES (see side_cost).
SCENARIOS = {
    "optimistic": dict(commission=0.0010, spread_mult=0.5, slippage=0.0002),
    "normal": dict(commission=0.0010, spread_mult=1.0, slippage=0.0005),
    "stress": dict(commission=0.0010, spread_mult=1.5, slippage=0.0010),
}
MAX_PENDING_DAYS = 10      # sessions a scheduled exit may wait for a traded price before write-down
DELIST_RECOVERY = 0.5      # assumed recovery on a write-down (estimate, reported separately)
PARTICIPATION = 0.01       # max shares = 1% of 50-day average dollar volume / fill price
PERIODS = {"train": ("2007-01-01", "2015-12-31"), "validation": ("2016-01-01", "2021-12-31"),
           "holdout": ("2022-01-01", "2026-12-31")}
FAMILIES = ("A_trend_pullback", "B_breakout", "C_mean_reversion", "D_relative_strength")


def wide(frames, field, cal):
    return pd.DataFrame({t: f[field] for t, f in frames.items()}).reindex(cal)


def indicators(frames, xiu, cal):
    O, H, L, C, V = (wide(frames, k, cal) for k in ("Open", "High", "Low", "Close", "Volume"))
    prevC = C.shift(1)
    a, b, c = H - L, (H - prevC).abs(), (L - prevC).abs()
    tr = a.where((a >= b) & (a >= c), b.where(b >= c, c))
    d = C.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss)
    ind = dict(O=O, H=H, L=L, C=C, V=V,
               sma5=C.rolling(5).mean(), sma20=C.rolling(20).mean(), sma50=C.rolling(50).mean(),
               sma200=C.rolling(200).mean(), hi20=H.shift(1).rolling(20).max(),
               vol20=V.rolling(20).mean(), dv50=(C * V).rolling(50).mean(),
               drop5=C / C.shift(5) - 1, ret63=C / C.shift(63) - 1, atr=tr.rolling(14).mean(), rsi=rsi)
    liquid = (C >= 1.0) & (ind["dv50"] >= 500_000)
    ind["liquid"] = liquid
    sig = {}
    sig["A_trend_pullback"] = (liquid & (C > ind["sma200"]) & (ind["sma50"] > ind["sma200"])
                               & (ind["drop5"] <= -0.03) & (C >= 0.99 * ind["sma20"]) & (C > O))
    sig["B_breakout"] = liquid & (C > ind["hi20"]) & (V > 1.5 * ind["vol20"])
    sig["C_mean_reversion"] = liquid & (ind["rsi"] < 30) & (C > ind["sma200"])
    r = ind["ret63"].where(liquid)
    q90 = r.quantile(0.9, axis=1)
    sig["D_relative_strength"] = liquid & (C > ind["sma50"]) & r.ge(q90, axis=0) & r.notna()
    ind["CF"] = C.ffill()
    return ind, sig


def side_cost(scen, dv):
    """One-way cost fraction. Commission is fixed; spread and slippage are ESTIMATES (no historical bid-ask data).
    Half-spread buckets by 50-day dollar volume: >=5M 0.10%, >=1M 0.25%, else 0.50%."""
    if not np.isfinite(dv):
        dv = 0.0
    if dv >= 5e6:
        half = 0.0010
    elif dv >= 1e6:
        half = 0.0025
    else:
        half = 0.0050
    return scen["commission"] + scen["spread_mult"] * half + scen["slippage"]


def run(ind, sig, fam, hold, scen):
    """Event simulation. Rules in PREREGISTERED.md. Missing bars are never converted into fills."""
    O, H, L, Craw, CF, ATR, DV = (ind[k].values for k in ("O", "H", "L", "C", "CF", "atr", "dv50"))
    score = ind["ret63"].values
    S = sig[fam].values
    T, N = S.shape
    cash, pos, eqc, trades = CAPITAL, [], np.full(T, np.nan), []
    dates, tickers = ind["dates"], ind["tickers"]

    def close(p, px, g, why, cost_day):
        nonlocal cash
        ex_cost = side_cost(scen, DV[cost_day, p["i"]])
        fill = px * (1 - ex_cost)
        proceeds = p["sh"] * fill
        cash += proceeds
        cost_basis = p["sh"] * p["fill_in"]
        pnl = proceeds - cost_basis
        trades.append((p["entry_date"], str(dates[g].date()), p["t"], round(p["fill_in"], 4), round(fill, 4),
                       p["sh"], round(pnl, 2), pnl / cost_basis, g - p["g_in"], why, p["pending_days"]))

    for g in range(1, T):
        for p in list(pos):
            i = p["i"]
            bar = np.isfinite(O[g, i]) and np.isfinite(L[g, i]) and np.isfinite(H[g, i])
            if bar and O[g, i] <= p["stop"]:
                close(p, O[g, i], g, "stop_gap", g - 1); pos.remove(p); continue
            if bar and L[g, i] <= p["stop"]:
                close(p, p["stop"], g, "stop", g - 1); pos.remove(p); continue
            if g < p["exit_g"]:
                continue
            if np.isfinite(Craw[g, i]):
                close(p, Craw[g, i], g, "time" if not p["pending"] else "time_delayed", g - 1); pos.remove(p); continue
            # scheduled exit with no bar: wait for the next genuinely traded price
            p["pending"] = True
            p["pending_days"] += 1
            if p["pending_days"] > MAX_PENDING_DAYS:
                # delisted/suspended/acquired: conservative documented write-down, labelled as an assumption
                last_px = CF[g - 1, i]
                close(p, DELIST_RECOVERY * last_px, g, "unresolved_writedown", g - 1)
                pos.remove(p)
        # entries at the open of g from signals on g-1
        s = g - 1
        equity_prev = cash + sum(p["sh"] * CF[s, p["i"]] for p in pos)
        cand = np.nonzero(S[s])[0]
        if len(cand) and len(pos) < MAX_SLOTS:
            cand = cand[np.argsort(-np.nan_to_num(score[s, cand], nan=-9.0), kind="stable")]
            held = {p["i"] for p in pos}
            for i in cand:
                if len(pos) >= MAX_SLOTS:
                    break
                if i in held or not np.isfinite(O[g, i]) or not np.isfinite(ATR[s, i]):
                    continue
                cs = ind["C"].values[s, i]
                if not np.isfinite(cs) or O[g, i] > cs * (1 + GAP_CAP):
                    continue
                entry_cost = side_cost(scen, DV[s, i])
                fill = O[g, i] * (1 + entry_cost)
                stop = O[g, i] - STOP_ATR * ATR[s, i]
                risk = O[g, i] - stop
                if risk <= 0:
                    continue
                liq_cap = PARTICIPATION * DV[s, i] / fill if np.isfinite(DV[s, i]) else 0
                sh = math.floor(min(RISK_FRAC * equity_prev / risk, MAX_POS_FRAC * equity_prev / fill,
                                    cash / fill, liq_cap))
                if sh < 1:
                    continue
                cash -= sh * fill
                pos.append(dict(i=i, t=tickers[i], fill_in=fill, stop=stop, sh=sh, g_in=g,
                                exit_g=g + hold - 1, entry_date=str(dates[g].date()),
                                pending=False, pending_days=0))
                held.add(i)
        # stops are live from the entry session itself
        for p in list(pos):
            if p["g_in"] == g and np.isfinite(L[g, p["i"]]) and L[g, p["i"]] <= p["stop"]:
                close(p, p["stop"], g, "stop_entry_day", g)
                pos.remove(p)
        eqc[g] = cash + sum(p["sh"] * CF[g, p["i"]] for p in pos)
    cols = ["entry_date", "exit_date", "ticker", "entry", "exit", "shares", "pnl", "ret",
            "hold_sessions", "exit_reason", "pending_days"]
    # exit_reason: stop_gap | stop | stop_entry_day | time | time_delayed | unresolved_writedown
    tr = pd.DataFrame(trades, columns=cols)
    eq = pd.Series(eqc, index=dates).ffill().fillna(CAPITAL)
    return tr, eq


def cost_breakdown():
    """Round-trip cost (%) by component and liquidity bucket for each scenario. Provisional estimates."""
    out = {}
    for name, sc in SCENARIOS.items():
        buckets = {}
        for label, dv in (("dv>=5M", 5e6), ("1M<=dv<5M", 1e6), ("dv<1M", 1e5)):
            half = 0.0010 if dv >= 5e6 else (0.0025 if dv >= 1e6 else 0.0050)
            buckets[label] = {
                "commission_per_side_pct": round(100 * sc["commission"], 3),
                "half_spread_per_side_pct": round(100 * sc["spread_mult"] * half, 3),
                "slippage_per_side_pct": round(100 * sc["slippage"], 3),
                "round_trip_pct": round(200 * side_cost(sc, dv), 3),
            }
        out[name] = buckets
    return out


BE_LO, BE_HI, BE_ITERS = 0.0, 0.05, 16   # search range for ONE-WAY uniform cost (5% per side = 10% round trip)


def _flat_scen(c):
    return dict(commission=c, spread_mult=0.0, slippage=0.0)


def expectancy_at(ind, sig, fam, hold, c, period):
    tr, eq = run(ind, sig, fam, hold, _flat_scen(c))
    st = stats(tr, eq, *PERIODS[period])
    return st.get("expectancy_pct"), st.get("trades", 0)


def breakeven(ind, sig, fam, hold, period):
    """Largest uniform per-side cost at which net expectancy is still > 0 (bisection on one-way cost).
    Reported as round-trip = 2 x per-side. Reporting metric only; it does not change any gate."""
    e0, n = expectancy_at(ind, sig, fam, hold, 0.0, period)
    if n == 0 or e0 is None or e0 <= 0:
        return {"status": "not profitable even at zero cost", "trades": n}
    eh, _ = expectancy_at(ind, sig, fam, hold, BE_HI, period)
    if eh is not None and eh > 0:
        return {"status": f">= {200 * BE_HI:.1f}% round trip (search limit)", "trades": n}
    lo, hi = BE_LO, BE_HI
    for _ in range(BE_ITERS):
        mid = (lo + hi) / 2
        e, _ = expectancy_at(ind, sig, fam, hold, mid, period)
        if e is not None and e > 0:
            lo = mid
        else:
            hi = mid
    return {"status": "ok", "round_trip_breakeven_pct": round(200 * lo, 3), "trades": n}


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * max(0, c - h), 2), round(100 * min(1, c + h), 2))


def stats(tr, eq, a, b):
    t = tr[(tr.entry_date >= a) & (tr.entry_date <= b)] if len(tr) else tr
    n = len(t)
    if n == 0:
        return {"trades": 0}
    wins = t[t.pnl > 0]
    losses = t[t.pnl <= 0]
    gw, gl = wins.pnl.sum(), -losses.pnl.sum()
    e = eq[(eq.index >= pd.Timestamp(a)) & (eq.index <= pd.Timestamp(b))]
    dd = float(((e / e.cummax()) - 1).min()) if len(e) else None
    return {"trades": n, "win_rate_pct": round(100 * len(wins) / n, 2),
            "win_rate_ci95": wilson(len(wins), n),
            "expectancy_pct": round(100 * t.ret.mean(), 4),
            "avg_win_pct": round(100 * wins.ret.mean(), 3) if len(wins) else None,
            "avg_loss_pct": round(100 * losses.ret.mean(), 3) if len(losses) else None,
            "profit_factor": round(gw / gl, 3) if gl > 0 else None,
            "total_pnl": round(float(t.pnl.sum()), 2),
            "max_dd_pct": round(100 * dd, 2) if dd is not None else None,
            "avg_hold_sessions": round(float(t.hold_sessions.mean()), 2),
            "exposure_note": "see equity curve"}


def annual(eq):
    ye = eq.groupby(eq.index.year).last()
    prev, out = CAPITAL, {}
    for y, v in ye.items():
        out[int(y)] = round(100 * (float(v) / prev - 1), 2)
        prev = float(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--equities", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raw = pickle.load(gzip.open(args.panel, "rb"))
    keep = set(json.load(open(args.equities))["equities"])
    frames = {t: f.sort_index() for t, f in raw["frames"].items() if t in keep}
    xiu = raw["xiu"].sort_index()
    cal = pd.DatetimeIndex(sorted(set(xiu.index).union(*[set(f.index) for f in frames.values()])))
    cal = cal[cal >= pd.Timestamp("2006-01-01")]
    ind, sig = indicators(frames, xiu, cal)
    ind["dates"] = cal
    ind["tickers"] = list(ind["C"].columns)
    os.makedirs(args.out, exist_ok=True)
    results = []
    for fam in FAMILIES:
        for hold in HOLDS:
            per = {}  # scenario name -> (trades, equity)
            for cname, scen in SCENARIOS.items():
                tr, eq = run(ind, sig, fam, hold, scen)
                if cname == "normal":
                    tr.to_csv(os.path.join(args.out, f"trades_{fam}_h{hold}.csv"), index=False)
                per[cname] = (tr, eq)
            tr_n, eq_n = per["normal"]
            row = {"config": f"{fam}_h{hold}", "family": fam, "hold": hold,
                   "normal": {k: stats(tr_n, eq_n, *PERIODS[k]) for k in PERIODS},
                   "full_normal": stats(tr_n, eq_n, "2007-01-01", "2026-12-31"),
                   "optimistic_holdout": stats(*per["optimistic"], *PERIODS["holdout"]),
                   "stress_holdout": stats(*per["stress"], *PERIODS["holdout"]),
                   "annual_normal": annual(eq_n),
                   "breakeven_round_trip": {k: breakeven(ind, sig, fam, hold, k) for k in PERIODS}}
            results.append(row)
            print(row["config"], "train E", row["normal"]["train"].get("expectancy_pct"),
                  "hold E", row["normal"]["holdout"].get("expectancy_pct"), flush=True)
    json.dump(results, open(os.path.join(args.out, "results.json"), "w"), indent=2, default=str)
    json.dump(cost_breakdown(), open(os.path.join(args.out, "cost_breakdown.json"), "w"), indent=2)
    lines = ["| Config | Period | Trades | Win % (95% CI) | Expectancy % net | PF | Max DD % | Avg hold |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        for k in PERIODS:
            s = r["normal"][k]
            lines.append(f"| {r['config']} | {k} | {s.get('trades')} | {s.get('win_rate_pct')} "
                         f"{s.get('win_rate_ci95')} | {s.get('expectancy_pct')} | {s.get('profit_factor')} | "
                         f"{s.get('max_dd_pct')} | {s.get('avg_hold_sessions')} |")
    lines += ["", "Break-even round-trip cost (%, provisional cost model; largest cost at which net expectancy stays > 0):",
              "| Config | " + " | ".join(PERIODS) + " |", "|---|" + "---|" * len(PERIODS)]
    for r in results:
        cells = []
        for k in PERIODS:
            b = r["breakeven_round_trip"][k]
            cells.append(str(b.get("round_trip_breakeven_pct", b["status"])))
        lines.append(f"| {r['config']} | " + " | ".join(cells) + " |")
    open(os.path.join(args.out, "report.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
