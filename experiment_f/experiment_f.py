"""
Experiment F: five pre-registered variants of the frozen Experiment E rule (see PREREGISTERED.md).
Research only. Not financial advice.

Usage:
  python experiment_f/experiment_f.py --panel panel.pkl.gz --equities experiment_e/universe.json --out out

Baseline = frozen Experiment E v1 (top 20, 252-day return, inverse-volatility weights, no filter, 0.10%/side).
Variants:
  BASE  baseline, reported unchanged
  T1    trend filter: hold only when XIU close > 200-day average, otherwise cash
  T2    volatility-scaled sizing: equal-weight picks, each capped at 0.5% of equity risked to a 2xATR stop
  T3    drawdown cut: exposure halved after a 10% drawdown from peak; full when equity regains the cut-point peak
        (checked daily, applied at the monthly rebalance)
  T4    per-stock stop: exit at the next open after a close 15% below entry; no re-entry until next rebalance
  T5    top 10 instead of top 20
Gates G1-G6 are applied as written in PREREGISTERED.md.
"""
import argparse
import copy
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "experiment_e"))
sys.path.insert(0, os.path.join(REPO, "experiment_d"))
import experiment_e as ee  # noqa: E402
import experiment_d as ed  # noqa: E402

ee.SIM_START = "2007-01-03"  # first simulated day: after a 252-day lookback from the 2006 data
TRAIN = ("2007-01-03", "2015-12-31")
VAL = ("2016-01-01", "2021-12-31")
HOLD = ("2022-01-01", "2026-12-31")
FULL = ("2007-01-03", "2026-12-31")
BASE_CFG = dict(top_n=20, lookback=252, skip=0, weight="invvol", filt=False,
                base_cost=0.001, cost_mult=1.0, capital=5000.0)
VARIANTS = {
    "BASE": dict(),
    "T1": dict(filt=True),
    "T2": dict(),
    "T3": dict(),
    "T4": dict(),
    "T5": dict(top_n=10),
}
STOP_FRAC = 0.85       # T4: exit when close <= 85% of entry
CUT_TRIGGER = 0.90     # T3: cut when equity <= 90% of peak
RISK_CAP = 0.005       # T2: at most 0.5% of equity risked per name, to a 2xATR stop
GATE_CAGR, GATE_DD = 15.0, -25.0


def target_weights(P, cfg, s, tag, cut):
    if tag == "T2":
        c = dict(cfg, weight="equal")
        w = ee.select(P, c, s)
        if not np.any(w):
            return w
        with np.errstate(divide="ignore", invalid="ignore"):
            cap_w = RISK_CAP / (2 * P.ATRP[:, s])
        cap_w = np.nan_to_num(cap_w, nan=0.0, posinf=0.0)
        w = np.minimum(w, cap_w)
    else:
        w = ee.select(P, cfg, s)
    if cfg["filt"] and not P.reg_up[s]:
        w = np.zeros(P.N)
    if tag == "T3" and cut:
        w = w * 0.5
    return w


def simulate(cfg, P, tag):
    fee = cfg["base_cost"] * cfg["cost_mult"]
    cap0 = float(cfg["capital"])
    cash, eq_prev = cap0, cap0
    shares = np.zeros(P.N)
    entry = np.full(P.N, np.nan)
    pnl = np.zeros(P.N)
    eqs = np.full(P.T, np.nan)
    exec_days = {g + 1 for g in P.month_end if g + 1 >= P.g0 and g + 1 < P.T}
    stop_pending = set()
    peak, cut, cut_peak = cap0, False, None
    reb, turnover, exposure, n_trades = [], 0.0, 0, 0
    for g in range(P.g0, P.T):
        o = P.O[:, g].astype(float)
        valid = ~np.isnan(o)
        for i in sorted(stop_pending):
            if shares[i] > 0 and valid[i]:
                q = shares[i]
                proceeds = q * o[i] * (1 - fee)
                cash += proceeds
                pnl[i] += proceeds
                turnover += q * o[i]
                shares[i] = 0
                entry[i] = np.nan
                n_trades += 1
        stop_pending = set()
        if g in exec_days:
            s = g - 1
            w = target_weights(P, cfg, s, tag, cut)
            with np.errstate(divide="ignore", invalid="ignore"):
                want = np.floor(eq_prev * w / (o * (1 + fee)))
            want = np.where(valid, want, shares)
            diff = want - shares
            for i in np.nonzero((diff < 0) & valid)[0]:
                q = -diff[i]
                proceeds = q * o[i] * (1 - fee)
                cash += proceeds
                pnl[i] += proceeds
                turnover += q * o[i]
                shares[i] -= q
                if shares[i] == 0:
                    entry[i] = np.nan
                n_trades += 1
            buys = np.nonzero((diff > 0) & valid)[0]
            buys = buys[np.argsort(-w[buys], kind="stable")]
            for i in buys:
                q = min(diff[i], math.floor(cash / (o[i] * (1 + fee))))
                if q > 0:
                    cost = q * o[i] * (1 + fee)
                    cash -= cost
                    pnl[i] -= cost
                    turnover += q * o[i]
                    if shares[i] == 0:
                        entry[i] = o[i]
                    shares[i] += q
                    n_trades += 1
            reb.append(g)
        C = P.CF[:, g].astype(float)
        eqv = cash + float(np.dot(shares, np.nan_to_num(C)))
        eqs[g] = eqv
        eq_prev = eqv
        if shares.any():
            exposure += 1
        if tag == "T4":
            for i in np.nonzero(shares > 0)[0]:
                if not np.isnan(C[i]) and C[i] <= STOP_FRAC * entry[i]:
                    stop_pending.add(int(i))
        if tag == "T3":
            if cut and eqv >= cut_peak:
                cut, cut_peak = False, None
            if not cut and eqv <= CUT_TRIGGER * peak:
                cut, cut_peak = True, peak
            peak = max(peak, eqv)
    pnl += shares * np.nan_to_num(P.CF[:, P.T - 1].astype(float))
    eq_s = pd.Series(eqs[P.g0:], index=P.cal[P.g0:]).ffill().fillna(cap0)
    days = P.T - P.g0
    years = (P.cal[-1] - P.cal[P.g0]).days / 365.25
    info = {"trades": n_trades, "rebalances": len(reb),
            "turnover_x_yr": round(turnover / max(years, 1e-9) / cap0, 2),
            "exposure_pct": round(100 * exposure / max(days, 1), 2)}
    return eq_s, reb, pnl, info


def calendar_years(eq_s, cap0):
    ye = eq_s.groupby(eq_s.index.year).last()
    prev, out = cap0, {}
    for y, v in ye.items():
        out[int(y)] = round(100 * (float(v) / prev - 1), 2)
        prev = float(v)
    return out


def masked(P, names_idx):
    Q = copy.copy(P)
    for attr in ("O", "C", "CF", "ATRP", "DV"):
        arr = getattr(P, attr).copy()
        arr[names_idx, :] = np.nan
        setattr(Q, attr, arr)
    return Q


def run_variant(P, name, overrides):
    cfg = dict(BASE_CFG, **overrides)
    tag = name if name in ("T2", "T3", "T4") else "BASE"
    eq_s, reb, pnl, info = simulate(cfg, P, tag)
    res = {"variant": name, "cfg": cfg, "info": info}
    res["full"] = ee.window_eq(eq_s, reb, P, *FULL, cfg["capital"])
    res["train"] = ee.window_eq(eq_s, reb, P, *TRAIN, cfg["capital"])
    res["val"] = ee.window_eq(eq_s, reb, P, *VAL, cfg["capital"])
    res["hold"] = ee.window_eq(eq_s, reb, P, *HOLD, cfg["capital"])
    cy = calendar_years(eq_s, cfg["capital"])
    res["calendar_years"] = cy
    full_years = {y: r for y, r in cy.items() if 2007 <= y <= 2025}
    res["negative_full_years"] = sum(1 for r in full_years.values() if r < 0)
    res["worst_full_year_pct"] = min(full_years.values()) if full_years else None
    res["full_years_count"] = len(full_years)
    # G5: remove the five largest contributors (by per-stock P&L in this run) and rerun
    top5 = np.argsort(-pnl)[:5]
    res["top5_contributors"] = [P.tick[i] for i in top5]
    Q = masked(P, top5)
    eq_x, reb_x, _, _ = simulate(cfg, Q, tag)
    res["ex_top5"] = ee.window_eq(eq_x, reb_x, P, *FULL, cfg["capital"])
    # G3: doubled costs
    cfg2 = dict(cfg, cost_mult=2.0)
    eq_c, reb_c, _, _ = simulate(cfg2, P, tag)
    res["double_cost"] = ee.window_eq(eq_c, reb_c, P, *FULL, cfg["capital"])
    res["gates"] = gates(res)
    return res


def gates(r):
    g = {}
    g["G1_full_cagr_ge_15"] = r["full"].get("cagr_pct", -1e9) >= GATE_CAGR
    g["G2_full_maxdd_ge_-25"] = r["full"].get("max_dd_pct", -1e9) >= GATE_DD
    g["G3_double_cost_cagr_gt_0"] = r["double_cost"].get("cagr_pct", -1e9) > 0
    g["G4_neg_years_le_1_and_worst_ge_-10"] = (r["negative_full_years"] <= 1
                                              and (r["worst_full_year_pct"] or -1e9) >= -10)
    g["G5_ex_top5_cagr_gt_0"] = r["ex_top5"].get("cagr_pct", -1e9) > 0
    g["G6_holdout_cagr_ge_15_and_dd_ge_-25"] = (r["hold"].get("cagr_pct", -1e9) >= GATE_CAGR
                                               and r["hold"].get("max_dd_pct", -1e9) >= GATE_DD)
    g["PASS_ALL"] = all(v for k, v in g.items())
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--equities", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    P = ee.prepare(args.panel, args.equities)
    os.makedirs(args.out, exist_ok=True)
    results = []
    for name, ov in VARIANTS.items():
        r = run_variant(P, name, ov)
        results.append(r)
        print(name, "CAGR", r["full"].get("cagr_pct"), "maxDD", r["full"].get("max_dd_pct"),
              "PASS" if r["gates"]["PASS_ALL"] else "FAIL", flush=True)
    json.dump(results, open(os.path.join(args.out, "results.json"), "w"), indent=2, default=str)
    lines = ["| Variant | Trials | CAGR 2007-26 | Max DD | Train CAGR | Val CAGR | Holdout CAGR | Holdout DD | "
             "Neg yrs | Worst yr | Ex-top5 CAGR | 2x cost CAGR | XIU CAGR | Exposure % | Gates |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        f = r["full"]
        lines.append(f"| {r['variant']} | 6 | {f.get('cagr_pct')} | {f.get('max_dd_pct')} | "
                     f"{r['train'].get('cagr_pct')} | {r['val'].get('cagr_pct')} | {r['hold'].get('cagr_pct')} | "
                     f"{r['hold'].get('max_dd_pct')} | {r['negative_full_years']} | {r['worst_full_year_pct']} | "
                     f"{r['ex_top5'].get('cagr_pct')} | {r['double_cost'].get('cagr_pct')} | "
                     f"{f.get('xiu_cagr_pct')} | {r['info']['exposure_pct']} | "
                     f"{'PASS' if r['gates']['PASS_ALL'] else 'FAIL'} |")
    report = "\n".join(lines)
    open(os.path.join(args.out, "report.md"), "w").write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
