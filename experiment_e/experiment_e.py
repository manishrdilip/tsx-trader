"""
Experiment E - cross-sectional momentum (monthly rebalance) on the TSX + TSXV universe.

Different hypothesis from B/C/D: rank stocks against each other on momentum, hold the top N,
rebalance monthly. Not a chart-pattern or breakout signal.

Rules (all decisions use data up to the signal day's close; trades execute at the next open):
  Signal day   : last trading day of each month (s)
  Eligibility  : close >= $2, 50-day avg dollar volume >= $500k, valid momentum and ATR
  Momentum     : return from bar s-skip-L to bar s-skip  (L = 126 or 252; skip = 0 or 21)
  Selection    : top N by momentum
  Weights      : equal, or inverse ATR% (volatility weighting)
  Regime filter: optional, XIU close > XIU 200-day SMA on the signal day; otherwise hold cash
  Execution    : trade at the next day's open, whole shares, cash-limited, sells before buys
  Costs        : 0.10% per side x cost multiplier, on traded notional
  Valuation    : daily close, dividends included (auto_adjust prices)

Reuses the panel, metrics and annual-table code from experiment_d (not modified).

Subcommands
  run       simulate every config in the grid (fetches the panel first if needed)
  aggregate merge results, select on train + validation only, write the report

Research only - not financial advice.
"""
import argparse
import gzip
import itertools
import json
import math
import os
import pickle
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "experiment_d"))
import experiment_d as ed  # noqa: E402

SIM_START = ed.SIM_START
TRAIN_END = ed.TRAIN_END
VAL_END = ed.VAL_END
MIN_REB_SELECT = 12        # rebalances per period needed for selection
DETAIL_FILTER = dict(cost_mult=1.0, top_n=10, weight="equal")


class Panel:
    pass


def prepare(panel_path):
    from pdf_candle_scan import add_indicators
    with gzip.open(panel_path, "rb") as f:
        raw = pickle.load(f)
    frames, xiu = raw["frames"], raw["xiu"].sort_index()
    xiu_ret = None
    cal = pd.DatetimeIndex(sorted(set(xiu.index).union(*[set(f.index) for f in frames.values()])))
    T = len(cal)
    tick = sorted(frames)
    N = len(tick)
    O, C, ATRP, DV = (np.full((N, T), np.nan, np.float32) for _ in range(4))
    for i, t in enumerate(tick):
        d = add_indicators(frames[t])
        idx = cal.get_indexer(d.index)
        O[i, idx] = d["Open"].values
        C[i, idx] = d["Close"].values
        ATRP[i, idx] = (d["atr"] / d["Close"]).values
        DV[i, idx] = d["dollar_adv50"].values
    xiu_al = xiu.reindex(cal, method="ffill")
    sma_al = xiu.rolling(200).mean().reindex(cal, method="ffill")
    P = Panel()
    P.tick, P.cal, P.T, P.N = tick, cal, T, N
    P.O, P.C, P.ATRP, P.DV = O, C, ATRP, DV
    P.CF = pd.DataFrame(C.T).ffill().values.T.astype(np.float32)
    P.reg_up = (xiu_al.values > sma_al.values) & ~np.isnan(sma_al.values)
    P.xiu = xiu_al
    P.g0 = int(cal.searchsorted(pd.Timestamp(SIM_START)))
    P.month_end = [g for g in range(T - 1) if cal[g].month != cal[g + 1].month]
    return P


def grid():
    axes = dict(capital=[1000.0, 5000.0], top_n=[5, 10, 20], lookback=[126, 252], skip=[0, 21],
                weight=["equal", "invvol"], filt=[False, True], cost_mult=[1.0, 2.0])
    out = []
    for combo in itertools.product(*axes.values()):
        p = dict(zip(axes.keys(), combo))
        p["id"] = (f"E_c{int(p['capital'])}_n{p['top_n']}_L{p['lookback']}_s{p['skip']}_"
                   f"{p['weight']}_f{int(p['filt'])}_x{p['cost_mult']:g}")
        p["base_cost"] = ed.BASE_COST
        out.append(p)
    return out


def select(P, cfg, s):
    """Weights (length N) decided at signal day s using only data up to s."""
    w = np.zeros(P.N)
    skip, L = cfg["skip"], cfg["lookback"]
    a, b = s - skip, s - L - skip
    if b < 0:
        return w
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = P.C[:, a] / P.C[:, b] - 1
    ok = (~np.isnan(ret) & (P.C[:, s] >= 2.0) & (P.DV[:, s] >= 500_000)
          & ~np.isnan(P.ATRP[:, s]) & (P.ATRP[:, s] > 0))
    idx = np.nonzero(ok)[0]
    if len(idx) == 0:
        return w
    idx = idx[np.argsort(-ret[idx], kind="stable")][: cfg["top_n"]]
    if cfg["weight"] == "equal":
        w[idx] = 1.0 / len(idx)
    else:
        inv = 1.0 / P.ATRP[idx, s]
        w[idx] = inv / inv.sum()
    return w


def simulate(cfg, P):
    fee = cfg["base_cost"] * cfg["cost_mult"]
    cap0 = float(cfg["capital"])
    cash, eq_prev = cap0, cap0
    shares = np.zeros(P.N)
    eqs = np.full(P.T, np.nan)
    exec_days = {g + 1 for g in P.month_end if g + 1 >= P.g0 and g + 1 < P.T}
    reb_dates, trades, turnover, exposure = [], [], 0.0, 0
    detail = all(cfg.get(k) == v for k, v in DETAIL_FILTER.items())
    for g in range(P.g0, P.T):
        if g in exec_days:
            s = g - 1
            w = select(P, cfg, s)
            if cfg["filt"] and not P.reg_up[s]:
                w = np.zeros(P.N)
            o = P.O[:, g].astype(float)
            valid = ~np.isnan(o)
            with np.errstate(divide="ignore", invalid="ignore"):
                want = np.floor(eq_prev * w / (o * (1 + fee)))
            want = np.where(valid, want, shares)
            diff = want - shares
            for i in np.nonzero((diff < 0) & valid)[0]:
                q = -diff[i]
                proceeds = q * o[i] * (1 - fee)
                cash += proceeds
                turnover += q * o[i]
                shares[i] -= q
                if detail:
                    trades.append((P.cal[g].date(), P.tick[i], "sell", q, round(o[i], 4), round(proceeds, 2)))
            buys = np.nonzero((diff > 0) & valid)[0]
            buys = buys[np.argsort(-w[buys], kind="stable")]
            for i in buys:
                q = min(diff[i], math.floor(cash / (o[i] * (1 + fee))))
                if q > 0:
                    cash -= q * o[i] * (1 + fee)
                    turnover += q * o[i]
                    shares[i] += q
                    if detail:
                        trades.append((P.cal[g].date(), P.tick[i], "buy", q, round(o[i], 4),
                                       round(-q * o[i] * (1 + fee), 2)))
            reb_dates.append(g)
        eqv = cash + float(np.dot(shares, np.nan_to_num(P.CF[:, g].astype(float))))
        eqs[g] = eqv
        eq_prev = eqv
        if shares.any():
            exposure += 1
    eq_s = pd.Series(eqs[P.g0:], index=P.cal[P.g0:]).ffill().fillna(cap0)
    years = (P.cal[-1] - P.cal[P.g0]).days / 365.25
    days = P.T - P.g0
    res = {"exposure_pct": round(100 * exposure / max(days, 1), 2),
           "turnover_x_yr": round(turnover / max(years, 1e-9) / cap0, 2),
           "rebalances": len(reb_dates), "final_equity": round(float(eq_s.iloc[-1]), 2)}
    return eq_s, reb_dates, trades, res


def window_eq(eq_s, reb_dates, P, start, end, cap0):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    idx = eq_s.index
    before = eq_s[idx < start]
    base = float(before.iloc[-1]) if len(before) else cap0
    w = eq_s[(idx >= start) & (idx <= end)]
    if w.empty:
        return {}
    days = max((w.index[-1] - w.index[0]).days, 1)
    end_v = float(w.iloc[-1])
    cagr = (end_v / base) ** (365.25 / days) - 1 if base > 0 and end_v > 0 else -1.0
    path = np.concatenate([[base], w.values])
    rec, under = ed.longest_underwater(path)
    xser = P.xiu
    xb = xser[xser.index < start]
    xbase = float(xb.iloc[-1]) if len(xb) else float(xser.iloc[0])
    xw = xser[(xser.index >= start) & (xser.index <= end)]
    xcagr = (float(xw.iloc[-1]) / xbase) ** (365.25 / days) - 1
    xpath = np.concatenate([[xbase], xw.values])
    n_reb = sum(1 for g in reb_dates if start <= P.cal[g] <= end)
    return {"cagr_pct": round(100 * cagr, 2), "total_ret_pct": round(100 * (end_v / base - 1), 2),
            "max_dd_pct": round(100 * ed.max_dd(path), 2), "recovery_days_max": rec,
            "underwater_at_end": under, "rebalances": n_reb,
            "xiu_cagr_pct": round(100 * xcagr, 2), "xiu_max_dd_pct": round(100 * ed.max_dd(xpath), 2)}


def latest_picks(P, cfg):
    s = P.T - 1
    w = select(P, cfg, s)
    idx = np.nonzero(w)[0]
    return ", ".join(f"{P.tick[i]} {w[i]:.3f}" for i in idx[np.argsort(-w[idx])])


def run(panel, out_dir):
    P = prepare(panel)
    cfgs = grid()
    os.makedirs(out_dir, exist_ok=True)
    print(f"{len(cfgs)} configs; {P.N} tickers; {P.T} days; {len(P.month_end)} month ends")
    with open(os.path.join(out_dir, "results.jsonl"), "w") as f:
        for cfg in cfgs:
            t0 = time.time()
            eq_s, reb, trades, extra = simulate(cfg, P)
            cap0 = cfg["capital"]
            row = {**cfg, **extra}
            row["full"] = window_eq(eq_s, reb, P, SIM_START, P.cal[-1], cap0)
            row["train"] = window_eq(eq_s, reb, P, SIM_START, TRAIN_END, cap0)
            row["val"] = window_eq(eq_s, reb, P, "2021-01-01", VAL_END, cap0)
            row["test"] = window_eq(eq_s, reb, P, "2024-01-01", P.cal[-1], cap0)
            row["latest_picks"] = latest_picks(P, cfg)
            if all(cfg.get(k) == v for k, v in DETAIL_FILTER.items()):
                d = os.path.join(out_dir, "detail", cfg["id"])
                os.makedirs(d, exist_ok=True)
                pd.DataFrame({"date": eq_s.index.date, "equity": eq_s.values.round(2)}).to_csv(
                    os.path.join(d, "daily_equity.csv"), index=False)
                pd.DataFrame(trades, columns=["date", "ticker", "side", "shares", "price", "cash_flow"]).to_csv(
                    os.path.join(d, "trades.csv"), index=False)
                ed.annual_table(eq_s, P.xiu, cap0).to_csv(os.path.join(d, "annual.csv"), index=False)
                json.dump(cfg, open(os.path.join(d, "config.json"), "w"), indent=2)
            f.write(json.dumps(row) + "\n")
            print(f"{cfg['id']}: rebal {extra['rebalances']}, CAGR {row['full'].get('cagr_pct')}%, "
                  f"maxDD {row['full'].get('max_dd_pct')}% ({time.time() - t0:.1f}s)")
    xs = P.xiu[P.g0:]
    xs_norm = pd.Series((xs / xs.iloc[0]).values, index=P.cal[P.g0:])
    xiu_full = window_eq(xs_norm, [], P, SIM_START, P.cal[-1], 1.0)
    json.dump({"xiu_full": xiu_full}, open(os.path.join(out_dir, "benchmark.json"), "w"), indent=2)


def aggregate(in_dir, out_dir):
    rows = [json.loads(l) for l in open(os.path.join(in_dir, "results.jsonl"))]
    bench = json.load(open(os.path.join(in_dir, "benchmark.json")))["xiu_full"]
    os.makedirs(out_dir, exist_ok=True)
    flat = []
    for r in rows:
        f = {k: v for k, v in r.items() if k not in ("full", "train", "val", "test")}
        for part in ("full", "train", "val", "test"):
            for k, v in (r.get(part) or {}).items():
                f[f"{part}_{k}"] = v
        flat.append(f)
    df = pd.DataFrame(flat)
    df.to_csv(os.path.join(out_dir, "all_configs.csv"), index=False)

    def calmar(m):
        if not m or m.get("cagr_pct") is None or not m.get("max_dd_pct"):
            return None
        return m["cagr_pct"] / abs(m["max_dd_pct"])

    by_key = {(r["capital"], r["top_n"], r["lookback"], r["skip"], r["weight"], r["filt"], r["cost_mult"]): r
              for r in rows}
    cand = []
    for r in rows:
        if r["cost_mult"] != 1.0:
            continue
        ctr, cva = calmar(r["train"]), calmar(r["val"])
        if ctr is None or cva is None:
            continue
        if r["train"].get("rebalances", 0) < MIN_REB_SELECT or r["val"].get("rebalances", 0) < MIN_REB_SELECT:
            continue
        cand.append((min(ctr, cva), r))
    cand.sort(key=lambda x: -x[0])
    sel = []
    for cap in sorted({r["capital"] for r in rows}):
        best = next(((s, r) for s, r in cand if r["capital"] == cap), None)
        if not best:
            continue
        s, r = best
        r2 = by_key.get((r["capital"], r["top_n"], r["lookback"], r["skip"], r["weight"], r["filt"], 2.0))
        sel.append({"capital": cap, "id": r["id"], "train_val_score": round(s, 3), "top_n": r["top_n"],
                    "lookback": r["lookback"], "skip": r["skip"], "weight": r["weight"],
                    "filter": r["filt"], "test_cagr_1x": r["test"].get("cagr_pct"),
                    "test_maxdd_1x": r["test"].get("max_dd_pct"), "test_cagr_2x": r2["test"].get("cagr_pct") if r2 else None,
                    "test_maxdd_2x": r2["test"].get("max_dd_pct") if r2 else None,
                    "test_xiu_cagr": r["test"].get("xiu_cagr_pct"), "test_xiu_maxdd": r["test"].get("xiu_max_dd_pct"),
                    "latest_picks_1x": r["latest_picks"]})
    selt = pd.DataFrame(sel)
    selt.to_csv(os.path.join(out_dir, "selection.csv"), index=False)
    top = pd.DataFrame([{"id": r["id"], "val_CAGR": r["val"].get("cagr_pct"), "val_maxDD": r["val"].get("max_dd_pct"),
                         "train_val_calmar_min": round(s, 3), "test_CAGR": r["test"].get("cagr_pct"),
                         "test_maxDD": r["test"].get("max_dd_pct")} for s, r in cand[:20]])
    top.to_csv(os.path.join(out_dir, "top20_by_train_val.csv"), index=False)
    lines = ["# Experiment E report - cross-sectional momentum", "",
             f"Configs: {len(rows)}. Selection: min(train, validation) Calmar at 1x costs, "
             f"at least {MIN_REB_SELECT} rebalances per period. Test is reported, not used for selection.", "",
             f"## XIU benchmark ({SIM_START} to today, total return)", "",
             f"CAGR {bench.get('cagr_pct')}%, max drawdown {bench.get('xiu_max_dd_pct', bench.get('max_dd_pct'))}%", "",
             "## Selected config per capital (train + validation only)", "",
             selt.to_markdown(index=False) if len(selt) else "(none met the selection rules)", "",
             "## Top 20 by train + validation score", "",
             top.to_markdown(index=False) if len(top) else "(none)", "",
             "## Caveats", "",
             "- Survivorship bias: today's listings only, so failed companies are missing. Results are optimistic.",
             "- Multiple testing: 192 configs; the best train + validation config can be luck.",
             "- Not point-in-time: the eligible universe is not restricted to stocks listed at each date.",
             "- No sector data: sector rotation is not tested.",
             "- Research only, not financial advice."]
    open(os.path.join(out_dir, "report.md"), "w").write("\n".join(lines) + "\n")
    print(f"aggregated {len(rows)} configs -> {out_dir}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a").write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--panel", required=True)
    r.add_argument("--out", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--inp", required=True)
    a.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.panel, args.out)
    else:
        aggregate(args.inp, args.out)


if __name__ == "__main__":
    main()
