"""
Experiment D - risk-controlled momentum breakout benchmark harness.

Baseline = Experiment C exactly:
  Universe      : universe_tickers.json, .TO and .V names
  Data          : yfinance daily, auto_adjust=True (dividends included), from 2006-01-01
  Cleaning      : dropna on OHLCV, at least 260 bars, indicators from pdf_candle_scan.add_indicators
  Entry signal  : close > prior 20-day high, volume > 1.5 x 20-day avg volume,
                  63-day return > XIU 63-day return, close >= $2, 50-day avg dollar volume >= $500k
  Execution     : signal at close of day t, buy at open of day t+1 (skip if open > 1.01 x close or
                  open <= stop). Exits checked bar by bar from the entry bar (gap fills at open).
  Costs         : 0.10% per side (commission, spread and slippage) x cost multiplier

Risk controls (D):
  - sizing: shares = floor(risk_pct x equity at prior close / (entry - stop))
  - whole shares only, cash cap, no leverage
  - max open positions, max aggregate initial risk (sum of shares x (entry - stop) <= max_port_risk x equity)
  - optional XIU > 200-day SMA filter evaluated on the signal day (known at that close)
  - candidates on a given day ranked by 63-day relative strength vs XIU (known at signal close)

Exit modes:
  trail  : Experiment C's exit - stop at close - stop_atr x ATR, trailing at max(high) - trail_atr x ATR(entry)
  target : fixed stop at close - stop_atr x ATR, target at entry + target_r x (entry - stop)
  Both: time stop after time_stop bars (exit at close).

Subcommands
  fetch      download the universe and XIU into a panel file (or synthetic data for tests)
  grid       write the configs file: the 16 D1-D4 configs first, then a seeded sample of the grid
  run        run one shard of the configs file, write one JSON line per config
  aggregate  merge shards, select on train+validation only, write the report

Research only - not financial advice.
"""
import argparse
import gzip
import itertools
import json
import math
import os
import pickle
import random
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

START_DL = "2006-01-01"
SIM_START = "2016-11-01"
TRAIN_END = "2020-12-31"
VAL_END = "2023-12-31"
BASE_COST = 0.001
MIN_TRADES_SELECT = 100
SUFFIXES = (".TO", ".V")


def series(df, col="Close"):
    s = df[col]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.astype(float)


# ---------------------------------------------------------------- fetch
def fetch(out, synthetic=False):
    if synthetic:
        rng = np.random.default_rng(7)
        cal = pd.bdate_range("2006-01-02", "2026-11-02")
        frames = {}
        for i in range(60):
            steps = rng.normal(0.0003, 0.02, len(cal))
            close = 20 * np.exp(np.cumsum(steps))
            op = close * (1 + rng.normal(0, 0.004, len(cal)))
            hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.006, len(cal))))
            lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.006, len(cal))))
            vol = rng.integers(200_000, 2_000_000, len(cal)).astype(float)
            frames[f"SYN{i:03d}.TO"] = pd.DataFrame(
                {"Open": op, "High": hi, "Low": lo, "Close": close, "Volume": vol}, index=cal)
        xiu = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(cal)))), index=cal, name="XIU")
    else:
        import yfinance as yf
        tickers = [t for t in json.load(open(os.path.join(os.path.dirname(HERE), "universe_tickers.json")))
                   if t.endswith(SUFFIXES)]
        frames = {}
        for i in range(0, len(tickers), 80):
            chunk = tickers[i:i + 80]
            raw = yf.download(chunk, start=START_DL, interval="1d", group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in chunk:
                try:
                    d = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna().astype(float)
                except Exception:
                    continue
                if len(d) >= 260:
                    frames[t] = d
            time.sleep(1)
        xiu_raw = yf.download("XIU.TO", start=START_DL, auto_adjust=True, progress=False)
        xiu = series(xiu_raw, "Close")
    with gzip.open(out, "wb") as f:
        pickle.dump({"frames": frames, "xiu": xiu}, f, protocol=4)
    print(f"panel: {len(frames)} tickers, xiu {len(xiu)} bars -> {out}")


# ---------------------------------------------------------------- configs
D_SPECS = {
    "D1": dict(market_filter=False, exit="trail", stop_atr=2.0, target_r=None),
    "D2": dict(market_filter=True, exit="trail", stop_atr=2.0, target_r=None),
    "D3": dict(market_filter=False, exit="target", stop_atr=2.0, target_r=2.5),
    "D4": dict(market_filter=True, exit="target", stop_atr=2.0, target_r=2.5),
}


def base_cfg(**kw):
    cfg = dict(capital=1000.0, risk_pct=0.005, max_pos=2, max_port_risk=0.01, trail_atr=2.0,
               time_stop=60, cost_mult=1.0, base_cost=BASE_COST, detail=False)
    cfg.update(kw)
    return cfg


def d_configs():
    out = []
    for cap in (1000.0, 5000.0):
        for cm in (1.0, 2.0):
            for name, spec in D_SPECS.items():
                out.append(base_cfg(id=f"{name}_c{int(cap)}_x{cm:g}", capital=cap, cost_mult=cm,
                                    detail=True, **spec))
    return out


def grid_configs(seed=42):
    axes = dict(capital=[1000.0, 5000.0], risk_pct=[0.0025, 0.005, 0.01], max_pos=[1, 2, 3, 4],
                stop_atr=[1.5, 2.0, 2.5, 3.0], market_filter=[False, True], cost_mult=[1.0, 2.0],
                mode=["trail", "target2", "target2.5", "target3"])
    combos = list(itertools.product(*axes.values()))
    rng = random.Random(seed)
    rng.shuffle(combos)
    out = []
    for k, combo in enumerate(combos):
        p = dict(zip(axes.keys(), combo))
        mode = p.pop("mode")
        exit_, tr = ("trail", None) if mode == "trail" else ("target", float(mode.replace("target", "")))
        out.append(base_cfg(id=f"G{k:04d}", exit=exit_, target_r=tr, detail=False, **p))
    return out


def write_grid(n, out):
    cfgs = d_configs()
    need = max(0, n - len(cfgs))
    cfgs += grid_configs()[:need]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump({"n": len(cfgs), "configs": cfgs}, open(out, "w"), indent=2)
    print(f"wrote {len(cfgs)} configs -> {out}")


# ---------------------------------------------------------------- prepare panel
class Panel:
    pass


def prepare(panel_path):
    from pdf_candle_scan import add_indicators
    with gzip.open(panel_path, "rb") as f:
        raw = pickle.load(f)
    frames, xiu = raw["frames"], raw["xiu"]
    xiu = xiu.sort_index()
    xiu_ret = xiu.pct_change(63)
    xiu_sma = xiu.rolling(200).mean()
    cal = pd.DatetimeIndex(sorted(set(xiu.index).union(*[set(f.index) for f in frames.values()])))
    T = len(cal)
    tick = sorted(frames)
    N = len(tick)
    O = np.full((N, T), np.nan, np.float32)
    H, L, C, ATR, RS = (np.full((N, T), np.nan, np.float32) for _ in range(5))
    SIG = np.zeros((N, T), bool)
    for i, t in enumerate(tick):
        d = add_indicators(frames[t])
        idx = cal.get_indexer(d.index)
        c = d["Close"]
        hi20 = d["High"].shift(1).rolling(20).max()
        ret63 = c.pct_change(63)
        xr = xiu_ret.reindex(d.index, method="ffill")
        sig = ((c > hi20) & (d["Volume"] > 1.5 * d["vol20"]) & (ret63 > xr)
               & (c >= 2.0) & (d["dollar_adv50"] >= 500_000))
        O[i, idx] = d["Open"].values
        H[i, idx] = d["High"].values
        L[i, idx] = d["Low"].values
        C[i, idx] = c.values
        ATR[i, idx] = d["atr"].values
        RS[i, idx] = (ret63 - xr).values
        SIG[i, idx] = sig.fillna(False).values
    CF = pd.DataFrame(C.T).ffill().values.T.astype(np.float32)   # close, forward-filled for marks
    xiu_al = xiu.reindex(cal, method="ffill")
    sma_al = xiu_sma.reindex(cal, method="ffill")
    P = Panel()
    P.tick, P.cal, P.T = tick, cal, T
    P.O, P.H, P.L, P.C, P.CF, P.ATR, P.RS, P.SIG = O, H, L, C, CF, ATR, RS, SIG
    P.reg_up = (xiu_al.values > sma_al.values) & ~np.isnan(sma_al.values)
    P.xiu = xiu_al
    P.g0 = int(cal.searchsorted(pd.Timestamp(SIM_START)))
    P.sig_by_day = []
    for g in range(T):
        idx = np.nonzero(SIG[:, g])[0]
        rs = RS[idx, g]
        order = np.argsort(-np.nan_to_num(rs, nan=-1e9), kind="stable")
        P.sig_by_day.append(idx[order])
    return P


# ---------------------------------------------------------------- simulation
def period_label(d):
    d = pd.Timestamp(d)
    if d <= pd.Timestamp(TRAIN_END):
        return "train"
    if d <= pd.Timestamp(VAL_END):
        return "val"
    return "test"


def simulate(cfg, P):
    fee = cfg["base_cost"] * cfg["cost_mult"]
    cap0 = float(cfg["capital"])
    O, H, L, C, CF, ATR = P.O, P.H, P.L, P.C, P.CF, P.ATR
    cash, eq_val = cap0, cap0
    positions, trades = [], []
    eq = np.full(P.T, np.nan)
    exposure_days, turnover = 0, 0.0
    tickers = P.tick

    def close_pos(p, g, px, reason):
        nonlocal cash, turnover, positions
        proceeds = p["shares"] * px * (1 - fee)
        cash += proceeds
        turnover += p["shares"] * px
        pnl = proceeds - p["cost"]
        trades.append({
            "ticker": tickers[p["ti"]],
            "signal_date": str(P.cal[p["entry_g"] - 1].date()),
            "entry_date": str(P.cal[p["entry_g"]].date()),
            "exit_date": str(P.cal[g].date()),
            "shares": p["shares"],
            "entry": round(p["entry"], 4),
            "stop_init": round(p["stop0"], 4),
            "exit": round(px, 4),
            "reason": reason,
            "hold_days": g - p["entry_g"] + 1,
            "pnl": round(pnl, 4),
            "ret_pct": round(100 * pnl / p["cost"], 4),
            "R": round(pnl / p["risk0"], 4) if p["risk0"] > 0 else None,
            "regime": "uptrend" if P.reg_up[p["entry_g"] - 1] else "downtrend",
            "period": period_label(P.cal[p["entry_g"]]),
        })
        positions = [x for x in positions if x is not p]

    for g in range(P.g0, P.T):
        # 1) entries at today's open from yesterday's signals
        if not cfg["market_filter"] or P.reg_up[g - 1]:
            for ti in P.sig_by_day[g - 1]:
                if len(positions) >= cfg["max_pos"]:
                    break
                if any(p["ti"] == ti for p in positions):
                    continue
                o = float(O[ti, g])
                cprev = float(C[ti, g - 1])
                atr = float(ATR[ti, g - 1])
                if np.isnan(o) or np.isnan(cprev) or np.isnan(atr) or atr <= 0:
                    continue
                if o > cprev * 1.01:
                    continue
                stop = cprev - cfg["stop_atr"] * atr
                if o <= stop:
                    continue
                rps = o - stop
                eq_prev = eq_val
                shares = math.floor(cfg["risk_pct"] * eq_prev / rps)
                shares = min(shares, math.floor(cash / (o * (1 + fee))))
                cur_risk = sum(p["risk0"] for p in positions)
                shares = min(shares, math.floor((cfg["max_port_risk"] * eq_prev - cur_risk) / rps))
                if shares < 1:
                    continue
                cost = shares * o * (1 + fee)
                cash -= cost
                turnover += shares * o
                positions.append({
                    "ti": int(ti), "shares": shares, "entry": o, "entry_g": g,
                    "stop": stop, "stop0": stop, "trail": stop, "atr_e": atr,
                    "target": o + (cfg["target_r"] or 0.0) * rps, "risk0": shares * rps, "cost": cost,
                })
        # 2) exits on today's bar (entry bar included)
        for p in list(positions):
            ti = p["ti"]
            o, h, l, c = float(O[ti, g]), float(H[ti, g]), float(L[ti, g]), float(C[ti, g])
            if np.isnan(o) or np.isnan(h) or np.isnan(l):
                continue
            px, reason = None, None
            if cfg["exit"] == "trail":
                tr = p["trail"]
                if o <= tr:
                    px, reason = o, "trail_gap"
                elif l <= tr:
                    px, reason = tr, "trail"
                else:
                    p["trail"] = max(tr, h - cfg["trail_atr"] * p["atr_e"])
            else:
                if o <= p["stop"]:
                    px, reason = o, "stop_gap"
                elif l <= p["stop"]:
                    px, reason = p["stop"], "stop"
                elif o >= p["target"]:
                    px, reason = o, "target_gap"
                elif h >= p["target"]:
                    px, reason = p["target"], "target"
            if px is None and g - p["entry_g"] + 1 >= cfg["time_stop"] and not np.isnan(c):
                px, reason = c, "time"
            if px is not None:
                close_pos(p, g, px, reason)
        # 3) mark to market at today's close
        mv = sum(p["shares"] * float(CF[p["ti"], g]) for p in positions)
        eq_val = cash + mv
        eq[g] = eq_val
        if positions:
            exposure_days += 1
    # close anything still open at the end, at the last close
    for p in list(positions):
        close_pos(p, P.T - 1, float(CF[p["ti"], P.T - 1]), "eod")
    eq[P.T - 1] = cash
    days = P.T - P.g0
    years = (P.cal[-1] - P.cal[P.g0]).days / 365.25
    eq_s = pd.Series(eq[P.g0:], index=P.cal[P.g0:]).ffill().fillna(cap0)
    tr_df = pd.DataFrame(trades)
    return eq_s, tr_df, {"exposure_pct": round(100 * exposure_days / max(days, 1), 2),
                         "turnover_x_per_year": round(turnover / max(years, 1e-9) / max(cap0, 1e-9), 2)}


# ---------------------------------------------------------------- metrics
def max_dd(path):
    path = np.asarray(path, float)
    if len(path) == 0:
        return 0.0
    return float((path / np.maximum.accumulate(path) - 1).min())


def longest_underwater(path):
    path = np.asarray(path, float)
    peak = np.maximum.accumulate(path)
    under = path < peak
    best = cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        best = max(best, cur)
    return int(best), bool(under[-1]) if len(under) else False


def window_metrics(eq_s, tr, xiu, start, end, cap0):
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
    rec, under_now = longest_underwater(path)
    xb = xiu[xiu.index < start]
    xbase = float(xb.iloc[-1]) if len(xb) else float(xiu.iloc[0])
    xw = xiu[(xiu.index >= start) & (xiu.index <= end)]
    xcagr = (float(xw.iloc[-1]) / xbase) ** (365.25 / days) - 1 if len(xw) else None
    xpath = np.concatenate([[xbase], xw.values]) if len(xw) else np.array([xbase])
    t = tr[(tr.entry_date >= str(start.date())) & (tr.entry_date <= str(end.date()))] if len(tr) else tr
    n = len(t)
    if n:
        gp = t.loc[t.pnl > 0, "pnl"].sum()
        gl = -t.loc[t.pnl < 0, "pnl"].sum()
        win = 100 * (t.pnl > 0).mean()
        pf = gp / gl if gl > 0 else None
        exp_r = t.R.mean()
        exp_pct = t.ret_pct.mean()
    else:
        win = pf = exp_r = exp_pct = None
    return {
        "cagr_pct": round(100 * cagr, 2), "total_ret_pct": round(100 * (end_v / base - 1), 2),
        "max_dd_pct": round(100 * max_dd(path), 2), "recovery_days_max": rec,
        "underwater_at_end": under_now,
        "trades": n, "win_rate_pct": round(win, 2) if win is not None else None,
        "profit_factor": round(pf, 3) if pf else None,
        "expectancy_R": round(exp_r, 4) if exp_r is not None else None,
        "expectancy_pct": round(exp_pct, 3) if exp_pct is not None else None,
        "xiu_cagr_pct": round(100 * xcagr, 2) if xcagr is not None else None,
        "xiu_max_dd_pct": round(100 * max_dd(xpath), 2),
    }


def annual_table(eq_s, xiu, cap0):
    yrs = eq_s.groupby(eq_s.index.year).last()
    xy = xiu[xiu.index >= eq_s.index[0]]
    xyr = xy.groupby(xy.index.year).last()
    rows, prev, xprev = [], cap0, float(xy.iloc[0])
    for y in yrs.index:
        v = float(yrs.loc[y])
        xv = float(xyr.loc[y]) if y in xyr.index else xprev
        rows.append({"year": int(y), "strategy_ret_pct": round(100 * (v / prev - 1), 2),
                     "xiu_total_ret_pct": round(100 * (xv / xprev - 1), 2),
                     "year_end_equity": round(v, 2)})
        prev, xprev = v, xv
    return pd.DataFrame(rows)


def regime_stats(tr):
    out = {}
    for r in ("uptrend", "downtrend"):
        t = tr[tr.regime == r] if len(tr) else tr
        n = len(t)
        out[f"{r}_trades"] = n
        out[f"{r}_win_pct"] = round(100 * (t.pnl > 0).mean(), 2) if n else None
        out[f"{r}_expectancy_R"] = round(t.R.mean(), 4) if n else None
        out[f"{r}_pnl_sum"] = round(t.pnl.sum(), 2) if n else 0.0
    return out


def run_one(cfg, P, out_dir):
    eq_s, tr, extra = simulate(cfg, P)
    cap0 = float(cfg["capital"])
    row = {"id": cfg["id"], **{k: v for k, v in cfg.items() if k != "id"}, **extra}
    row["final_equity"] = round(float(eq_s.iloc[-1]), 2)
    row["full"] = window_metrics(eq_s, tr, P.xiu, SIM_START, P.cal[-1], cap0)
    for name, (a, b) in {"train": (SIM_START, TRAIN_END), "val": ("2021-01-01", VAL_END),
                         "test": ("2024-01-01", P.cal[-1])}.items():
        row[name] = window_metrics(eq_s, tr, P.xiu, a, b, cap0)
    row["regimes"] = regime_stats(tr)
    if cfg.get("detail"):
        d = os.path.join(out_dir, "detail", cfg["id"])
        os.makedirs(d, exist_ok=True)
        tr.to_csv(os.path.join(d, "trades.csv"), index=False)
        pd.DataFrame({"date": eq_s.index.date, "equity": eq_s.values.round(2)}).to_csv(
            os.path.join(d, "daily_equity.csv"), index=False)
        annual_table(eq_s, P.xiu, cap0).to_csv(os.path.join(d, "annual.csv"), index=False)
        json.dump(cfg, open(os.path.join(d, "config.json"), "w"), indent=2)
    return row


def run(panel, configs_path, shard, nshards, out_dir):
    cfgs = json.load(open(configs_path))["configs"]
    mine = cfgs[shard::nshards]
    os.makedirs(out_dir, exist_ok=True)
    P = prepare(panel)
    print(f"shard {shard}/{nshards}: {len(mine)} configs; panel {len(P.tick)} tickers, {P.T} days")
    with open(os.path.join(out_dir, f"shard_{shard}.jsonl"), "w") as f:
        for cfg in mine:
            t0 = time.time()
            row = run_one(cfg, P, out_dir)
            f.write(json.dumps(row) + "\n")
            print(f"{cfg['id']}: trades {row['full']['trades']}, "
                  f"full CAGR {row['full']['cagr_pct']}%, maxDD {row['full']['max_dd_pct']}% "
                  f"({time.time() - t0:.1f}s)")


# ---------------------------------------------------------------- aggregate
def params_key(r):
    keys = ["capital", "risk_pct", "max_pos", "stop_atr", "exit", "target_r", "market_filter"]
    return tuple(r.get(k) for k in keys)


def calmar(m):
    if not m or m.get("cagr_pct") is None or not m.get("max_dd_pct"):
        return None
    return m["cagr_pct"] / abs(m["max_dd_pct"])


def aggregate(in_dir, out_dir):
    rows = []
    for fn in sorted(os.listdir(in_dir)):
        if fn.startswith("shard_") and fn.endswith(".jsonl"):
            rows += [json.loads(line) for line in open(os.path.join(in_dir, fn))]
    os.makedirs(out_dir, exist_ok=True)
    flat = []
    for r in rows:
        f = {k: v for k, v in r.items() if k not in ("full", "train", "val", "test", "regimes")}
        for part in ("full", "train", "val", "test"):
            for k, v in (r.get(part) or {}).items():
                f[f"{part}_{k}"] = v
        f.update(r.get("regimes", {}))
        flat.append(f)
    df = pd.DataFrame(flat)
    df.to_csv(os.path.join(out_dir, "all_configs.csv"), index=False)

    # Selection on train + validation only: score = min(Calmar_train, Calmar_val), 1x costs.
    sel_rows = []
    by_key = {}
    for r in rows:
        by_key[(params_key(r), r["cost_mult"])] = r
    cand = []
    for r in rows:
        if r["cost_mult"] != 1.0:
            continue
        ctr, cva = calmar(r.get("train")), calmar(r.get("val"))
        if ctr is None or cva is None:
            continue
        if (r["train"].get("trades") or 0) < MIN_TRADES_SELECT or (r["val"].get("trades") or 0) < MIN_TRADES_SELECT:
            continue
        cand.append((min(ctr, cva), r))
    cand.sort(key=lambda x: -x[0])
    for cap in sorted({r["capital"] for r in rows}):
        best = next(((s, r) for s, r in cand if r["capital"] == cap), None)
        if best is None:
            continue
        s, r = best
        r2 = by_key.get((params_key(r), 2.0))
        sel_rows.append({
            "capital": cap, "selected_id": r["id"], "train_val_score": round(s, 3),
            "exit": r["exit"], "stop_atr": r["stop_atr"], "target_r": r["target_r"],
            "risk_pct": r["risk_pct"], "max_pos": r["max_pos"], "market_filter": r["market_filter"],
            "test_cagr_1x": r["test"].get("cagr_pct"), "test_maxdd_1x": r["test"].get("max_dd_pct"),
            "test_pf_1x": r["test"].get("profit_factor"), "test_trades_1x": r["test"].get("trades"),
            "test_cagr_2x": r2["test"].get("cagr_pct") if r2 else None,
            "test_maxdd_2x": r2["test"].get("max_dd_pct") if r2 else None,
            "test_xiu_cagr": r["test"].get("xiu_cagr_pct"), "test_xiu_maxdd": r["test"].get("xiu_max_dd_pct"),
        })
    sel = pd.DataFrame(sel_rows)
    sel.to_csv(os.path.join(out_dir, "selection.csv"), index=False)

    d_ids = [r for r in rows if r.get("detail")]
    dtab = []
    for r in sorted(d_ids, key=lambda x: (x["capital"], x["id"])):
        dtab.append({"id": r["id"], "capital": r["capital"], "cost_x": r["cost_mult"],
                     "trades_full": r["full"].get("trades"), "win_pct": r["full"].get("win_rate_pct"),
                     "PF": r["full"].get("profit_factor"), "expR": r["full"].get("expectancy_R"),
                     "CAGR_full": r["full"].get("cagr_pct"), "maxDD_full": r["full"].get("max_dd_pct"),
                     "CAGR_train": r["train"].get("cagr_pct"), "maxDD_train": r["train"].get("max_dd_pct"),
                     "CAGR_val": r["val"].get("cagr_pct"), "maxDD_val": r["val"].get("max_dd_pct"),
                     "CAGR_test": r["test"].get("cagr_pct"), "maxDD_test": r["test"].get("max_dd_pct"),
                     "exposure_pct": r.get("exposure_pct"), "turnover_x_yr": r.get("turnover_x_per_year"),
                     "final_equity": r.get("final_equity"),
                     "XIU_CAGR_full": r["full"].get("xiu_cagr_pct"), "XIU_maxDD_full": r["full"].get("xiu_max_dd_pct")})
    dtab = pd.DataFrame(dtab)
    dtab.to_csv(os.path.join(out_dir, "d_configs_table.csv"), index=False)

    top = pd.DataFrame([{"id": r["id"], "capital": r["capital"], "cost_x": r["cost_mult"],
                         "val_CAGR": r["val"].get("cagr_pct"), "val_maxDD": r["val"].get("max_dd_pct"),
                         "train_val_calmar_min": round(min(calmar(r.get("train")) or -9, calmar(r.get("val")) or -9), 3),
                         "test_CAGR": r["test"].get("cagr_pct"), "test_maxDD": r["test"].get("max_dd_pct")}
                        for s, r in cand[:20]])
    top.to_csv(os.path.join(out_dir, "top20_by_train_val.csv"), index=False)

    lines = [f"# Experiment D report", "",
             f"Configs run: {len(rows)} (D1-D4 detail configs: {len(d_ids)})",
             f"Periods: train {SIM_START} to {TRAIN_END}; validation 2021-01-01 to {VAL_END}; test 2024-01-01 to end.",
             "Selection uses train and validation only (score = min of train and validation Calmar, 1x costs, >=100 trades each).",
             "The test period is reported for the selected config and is not used to choose it.", "",
             "## Pre-specified configs D1-D4 (not selected on results)", "",
             dtab.to_markdown(index=False) if len(dtab) else "(none)", "",
             "## Selected config per capital (chosen on train+validation)", "",
             sel.to_markdown(index=False) if len(sel) else "(no config met selection rules)", "",
             "## Top 20 by train+validation score (before test is looked at)", "",
             top.to_markdown(index=False) if len(top) else "(none)", "",
             "## Caveats", "",
             "- Survivorship bias: the universe is today's listings, so failed companies are missing. Results are optimistic.",
             "- Multiple testing: with many configs, the best train+validation config can be luck. Check test and the D1-D4 table together.",
             "- Walk-forward: no parameters are fitted inside the simulator; year-by-year out-of-sample results are in annual CSVs of the detail configs.",
             "- Costs: 0.10% per side per trade (commission, spread and slippage), doubled in the 2x runs.",
             "- Research only, not financial advice."]
    open(os.path.join(out_dir, "report.md"), "w").write("\n".join(lines) + "\n")
    print(f"aggregated {len(rows)} configs -> {out_dir}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a").write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("fetch")
    a.add_argument("--out", required=True)
    a.add_argument("--synthetic", action="store_true")
    b = sub.add_parser("grid")
    b.add_argument("--n", type=int, default=1000)
    b.add_argument("--out", required=True)
    c = sub.add_parser("run")
    c.add_argument("--panel", required=True)
    c.add_argument("--configs", required=True)
    c.add_argument("--shard", type=int, default=0)
    c.add_argument("--nshards", type=int, default=1)
    c.add_argument("--out", required=True)
    d = sub.add_parser("aggregate")
    d.add_argument("--inp", required=True)
    d.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.out, args.synthetic)
    elif args.cmd == "grid":
        write_grid(args.n, args.out)
    elif args.cmd == "run":
        run(args.panel, args.configs, args.shard, args.nshards, args.out)
    else:
        aggregate(args.inp, args.out)


if __name__ == "__main__":
    main()
