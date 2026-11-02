"""
Experiment H - base rate of the "+2% before -1%" trade, with NO signal selection.

Question: if every liquid stock is bought at the next session's open, what fraction of trades reach +2%
before -1% within 5 sessions, and what is the expectancy? Any predictor must beat this base rate.

Rules (fixed before running):
  - Universe: equities from experiment_e/universe.json (frozen list).
  - Liquidity at the signal close s: close >= $1 and 50-day average dollar volume >= $500k (no look-ahead).
  - Entry: next session's open. Stop = entry x 0.99. Target = entry x 1.02. Time stop after 5 sessions
    (including the entry session) at that session's close.
  - Intrabar order (conservative): gap checks at the open first; within a bar, the stop is checked before
    the target, so a bar touching both counts as a loss.
  - Costs: 0.10% per side, so 0.20% per round trip, deducted from each trade.
  - Each signal day is one trade. Trades overlap, so these are per-trade statistics, not a portfolio.
  - Periods (reported, not selected): 2007-2015, 2016-2021, 2022-2026.

Research only. Not financial advice.
"""
import argparse
import gzip
import json
import os
import pickle

import numpy as np
import pandas as pd

COST = 0.002          # round trip
TARGET, STOP, HORIZON = 0.02, 0.01, 5
PERIODS = {"train_2007_2015": ("2007-01-01", "2015-12-31"),
           "val_2016_2021": ("2016-01-01", "2021-12-31"),
           "holdout_2022_2026": ("2022-01-01", "2026-12-31")}


def outcomes(d):
    """Return (dates, net_return, valid) for each signal day of one stock's OHLCV frame d."""
    o, h, l, c = (d[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
    n = len(c)
    dv = pd.Series(c * d["Volume"].values.astype(float)).rolling(50, min_periods=50).mean().values
    liq = (c >= 1.0) & (dv >= 500_000)
    res = np.full(n, np.nan)
    if n < HORIZON + 2:
        return res
    sig = np.arange(n - HORIZON - 1)            # s such that s+1..s+5 exist
    entry = o[sig + 1]
    stop = entry * (1 - STOP)
    tgt = entry * (1 + TARGET)
    ret = np.full(len(sig), np.nan)
    done = np.zeros(len(sig), bool)
    for k in range(HORIZON):
        bar = sig + 1 + k
        ok = ~done & np.isfinite(o[bar]) & np.isfinite(h[bar]) & np.isfinite(l[bar])
        gap_loss = ok & (o[bar] <= stop)
        gap_win = ok & ~gap_loss & (o[bar] >= tgt)
        stop_hit = ok & ~gap_loss & ~gap_win & (l[bar] <= stop)
        tgt_hit = ok & ~gap_loss & ~gap_win & ~stop_hit & (h[bar] >= tgt)
        ret[gap_loss] = o[bar][gap_loss] / entry[gap_loss] - 1
        ret[gap_win] = o[bar][gap_win] / entry[gap_win] - 1
        ret[stop_hit] = -STOP
        ret[tgt_hit] = TARGET
        done |= gap_loss | gap_win | stop_hit | tgt_hit
    last = sig + HORIZON
    timeout = ~done & np.isfinite(c[last])
    ret[timeout] = c[last][timeout] / entry[timeout] - 1
    ok_entry = np.isfinite(entry) & (entry > 0)
    ret = np.where(ok_entry, ret, np.nan)
    res[sig] = ret - COST
    res[~liq] = np.nan
    return res


def summarize(x):
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"trades": 0}
    w, l = x[x > 0], x[x <= 0]
    gross_w, gross_l = w.sum(), -l.sum()
    return {"trades": int(len(x)), "win_rate_pct": round(100 * len(w) / len(x), 2),
            "avg_win_pct": round(100 * w.mean(), 3) if len(w) else None,
            "avg_loss_pct": round(100 * l.mean(), 3) if len(l) else None,
            "expectancy_pct": round(100 * x.mean(), 4),
            "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--equities", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raw = pickle.load(gzip.open(args.panel, "rb"))
    keep = set(json.load(open(args.equities))["equities"])
    dates, rets, tick = [], [], []
    for t, d in raw["frames"].items():
        if t not in keep:
            continue
        d = d.sort_index()
        r = outcomes(d)
        m = np.isfinite(r)
        dates.append(d.index.values[m])
        rets.append(r[m])
        tick.append(np.full(m.sum(), t, dtype=object))
    dates = np.concatenate(dates)
    rets = np.concatenate(rets)
    tick = np.concatenate(tick)
    df = pd.DataFrame({"date": pd.to_datetime(dates), "ticker": tick, "net": rets})
    out = {"overall": summarize(df.net.values), "periods": {}}
    for name, (a, b) in PERIODS.items():
        m = (df.date >= a) & (df.date <= b)
        out["periods"][name] = summarize(df.net[m].values)
    os.makedirs(args.out, exist_ok=True)
    json.dump(out, open(os.path.join(args.out, "base_rate.json"), "w"), indent=2)
    lines = ["| Period | Trades | Win rate % | Avg win % | Avg loss % | Expectancy % (net) | Profit factor |",
             "|---|---|---|---|---|---|---|"]
    for name, s in [("ALL 2007-2026", out["overall"])] + list(out["periods"].items()):
        lines.append(f"| {name} | {s.get('trades')} | {s.get('win_rate_pct')} | {s.get('avg_win_pct')} | "
                     f"{s.get('avg_loss_pct')} | {s.get('expectancy_pct')} | {s.get('profit_factor')} |")
    report = "\n".join(lines)
    open(os.path.join(args.out, "report.md"), "w").write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
