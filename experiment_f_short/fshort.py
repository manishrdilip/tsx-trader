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
COSTS = {"normal": 0.001, "doubled": 0.002, "stress": 0.003}
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


def run(ind, sig, fam, hold, fee):
    O, H, L, CF, ATR = ind["O"].values, ind["H"].values, ind["L"].values, ind["CF"].values, ind["atr"].values
    Cs = ind["C"].values
    score = ind["ret63"].values
    S = sig[fam].values
    T, N = S.shape
    cash, pos, equity_curve, trades = CAPITAL, [], np.full(T, np.nan), []
    for g in range(1, T):
        # exits at day g: stop (gap at open, else at stop level), or time exit at close
        keep = []
        for p in pos:
            i = p["i"]
            px = None
            if np.isfinite(O[g, i]) and O[g, i] <= p["stop"]:
                px = O[g, i]
            elif np.isfinite(L[g, i]) and L[g, i] <= p["stop"]:
                px = p["stop"]
            elif g >= p["exit_g"]:
                px = CF[g, i]
            if px is not None and np.isfinite(px):
                proceeds = p["sh"] * px * (1 - fee)
                cash += proceeds
                cost = p["sh"] * p["px_in"] * (1 + fee)
                trades.append((p["entry_date"], ind["dates"][g], p["t"], p["px_in"], px, p["sh"],
                               proceeds - cost, (proceeds - cost) / cost, g - p["g_in"]))
            else:
                keep.append(p)
        pos = keep
        equity_prev = cash + sum(p["sh"] * CF[g - 1, p["i"]] for p in pos)
        # entries at open of g from signals on g-1
        s = g - 1
        cand = np.nonzero(S[s])[0]
        if len(cand) and len(pos) < MAX_SLOTS:
            cand = cand[np.argsort(-np.nan_to_num(score[s, cand], nan=-9.0), kind="stable")]
            held = {p["i"] for p in pos}
            for i in cand:
                if len(pos) >= MAX_SLOTS:
                    break
                if i in held or not np.isfinite(O[g, i]) or not np.isfinite(ATR[s, i]):
                    continue
                entry = O[g, i]
                if entry > Cs[s, i] * (1 + GAP_CAP):
                    continue
                stop = entry - STOP_ATR * ATR[s, i]
                risk = entry - stop
                if risk <= 0:
                    continue
                sh = math.floor(min(RISK_FRAC * equity_prev / risk,
                                    MAX_POS_FRAC * equity_prev / (entry * (1 + fee)),
                                    cash / (entry * (1 + fee))))
                if sh < 1:
                    continue
                cash -= sh * entry * (1 + fee)
                pos.append(dict(i=i, t=ind["tickers"][i], px_in=entry, stop=stop, sh=sh, g_in=g,
                                exit_g=g + hold - 1, entry_date=str(ind["dates"][g].date())))
                held.add(i)
        # stops are live from the entry session itself (intraday low on the entry day)
        for p in list(pos):
            if p["g_in"] == g and np.isfinite(L[g, p["i"]]) and L[g, p["i"]] <= p["stop"]:
                proceeds = p["sh"] * p["stop"] * (1 - fee)
                cash += proceeds
                cost = p["sh"] * p["px_in"] * (1 + fee)
                trades.append((p["entry_date"], ind["dates"][g], p["t"], p["px_in"], p["stop"], p["sh"],
                               proceeds - cost, (proceeds - cost) / cost, 1))
                pos.remove(p)
        equity_curve[g] = cash + sum(p["sh"] * CF[g, p["i"]] for p in pos)
    tr = pd.DataFrame(trades, columns=["entry_date", "exit_date", "ticker", "entry", "exit", "shares",
                                       "pnl", "ret", "hold_sessions"])
    eq = pd.Series(equity_curve, index=ind["dates"]).ffill().fillna(CAPITAL)
    return tr, eq


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
            per = {}
            for cname, fee in COSTS.items():
                tr, eq = run(ind, sig, fam, hold, fee)
                if cname == "normal":
                    tr.to_csv(os.path.join(args.out, f"trades_{fam}_h{hold}.csv"), index=False)
                    eq_normal = eq
                per[cname] = (tr, eq)
            tr_n, eq_n = per["normal"]
            row = {"config": f"{fam}_h{hold}", "family": fam, "hold": hold,
                   "normal": {k: stats(tr_n, eq_n, *PERIODS[k]) for k in PERIODS},
                   "full_normal": stats(tr_n, eq_n, "2007-01-01", "2026-12-31"),
                   "doubled_holdout": stats(*per["doubled"], *PERIODS["holdout"]),
                   "stress_holdout": stats(*per["stress"], *PERIODS["holdout"]),
                   "annual_normal": annual(eq_n)}
            results.append(row)
            print(row["config"], "train E", row["normal"]["train"].get("expectancy_pct"),
                  "hold E", row["normal"]["holdout"].get("expectancy_pct"), flush=True)
    json.dump(results, open(os.path.join(args.out, "results.json"), "w"), indent=2, default=str)
    lines = ["| Config | Period | Trades | Win % (95% CI) | Expectancy % net | PF | Max DD % | Avg hold |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        for k in PERIODS:
            s = r["normal"][k]
            lines.append(f"| {r['config']} | {k} | {s.get('trades')} | {s.get('win_rate_pct')} "
                         f"{s.get('win_rate_ci95')} | {s.get('expectancy_pct')} | {s.get('profit_factor')} | "
                         f"{s.get('max_dd_pct')} | {s.get('avg_hold_sessions')} |")
    open(os.path.join(args.out, "report.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
