"""
Experiments B and C: 10-year daily backtests on the TSX + TSX Venture universe.

Experiment B - Trend-following pullback
  - close > SMA200 and SMA50 > SMA200
  - pullback: low within last 3 bars reached within 1% of SMA20, and close back at/above SMA20
  - bullish reversal: close > open and close > prior close
  - stop = close - 1.5 x ATR14; target = close + 2R (R = close - stop)
  - exits: stop or target, 20-bar time stop

Experiment C - Momentum breakout
  - close > highest high of the prior 20 bars
  - volume > 1.5 x 20-day average volume
  - 63-day return above XIU.TO's 63-day return (relative strength)
  - stop = close - 2 x ATR14
  - trailing exit: stop trails the highest high since entry minus 2 x ATR(entry);
    60-bar time stop

Shared: signal taken at next open (skipped if it opens >1% above signal close, or at/below stop),
liquidity filter (close >= $2, 50-day avg dollar volume >= $500k), 0.1% per side costs.
Account sim: one position at a time, all cash, whole shares, fees both sides.

Research only - not financial advice.
"""
import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from pdf_candle_scan import add_indicators
from backtest_candle import stats, portfolio, load_universe, COST_PER_SIDE, NOTIONAL, BATCH

EXPERIMENT = os.environ.get("EXPERIMENT", "B").upper()
START_DL = "2006-01-01"
START_TEST = os.environ.get("START_TEST", "2016-11-01")
OUT_DIR = os.environ.get("OUT_DIR", f"results/experiment_{EXPERIMENT}")


def build_signals(d, xiu_ret):
    c, o, h, l, v = d["Close"], d["Open"], d["High"], d["Low"], d["Volume"]
    liq = (c >= 2.0) & (d["dollar_adv50"] >= 500_000)
    if EXPERIMENT == "B":
        sma20 = c.rolling(20).mean()
        pull = (l.rolling(3).min() <= sma20 * 1.01) & (c >= sma20)
        bull = (c > o) & (c > c.shift(1))
        sig = (c > d["sma200"]) & (d["sma50"] > d["sma200"]) & pull & bull & liq
        stop = c - 1.5 * d["atr"]
        target = c + 2 * (c - stop)
    else:
        hi20 = h.shift(1).rolling(20).max()
        ret63 = c.pct_change(63)
        rs = ret63 > xiu_ret.reindex(d.index).ffill()
        sig = (c > hi20) & (v > 1.5 * d["vol20"]) & rs & liq
        stop = c - 2 * d["atr"]
        target = pd.Series(np.nan, index=d.index)
    return sig.fillna(False), stop, target


def simulate(ticker, d, xiu_ret):
    sig, stop_s, target_s = build_signals(d, xiu_ret)
    o = d["Open"].values
    h = d["High"].values
    l = d["Low"].values
    cl = d["Close"].values
    atr = d["atr"].values
    stop_a = stop_s.values
    tgt_a = target_s.values
    dates = d.index
    n = len(d)
    cap = 20 if EXPERIMENT == "B" else 60
    trades, busy = [], -1
    for t in np.where(sig.values)[0]:
        if t <= busy or t + 1 >= n or dates[t] < pd.Timestamp(START_TEST):
            continue
        s = stop_a[t]
        if np.isnan(s) or np.isnan(atr[t]):
            continue
        entry = o[t + 1]
        if np.isnan(entry) or entry > cl[t] * 1.01 or entry <= s:
            continue
        last = min(t + cap, n - 1)
        exit_px, reason, j_exit = None, None, None
        if EXPERIMENT == "B":
            tg = tgt_a[t]
            for j in range(t + 1, last + 1):
                if o[j] <= s:
                    exit_px, reason = o[j], "stop_gap"
                elif l[j] <= s:
                    exit_px, reason = s, "stop"
                elif o[j] >= tg:
                    exit_px, reason = o[j], "target_gap"
                elif h[j] >= tg:
                    exit_px, reason = tg, "target"
                if exit_px is not None:
                    j_exit = j
                    break
        else:
            trail = s
            for j in range(t + 1, last + 1):
                if o[j] <= trail:
                    exit_px, reason = o[j], "trail_gap"
                elif l[j] <= trail:
                    exit_px, reason = trail, "trail"
                if exit_px is not None:
                    j_exit = j
                    break
                trail = max(trail, h[j] - 2 * atr[t])
        if exit_px is None:
            j_exit, exit_px, reason = last, cl[last], "time"
        net = exit_px / entry - 1 - 2 * COST_PER_SIDE
        busy = j_exit
        trades.append({
            "ticker": ticker,
            "signal_date": str(dates[t].date()),
            "entry_date": str(dates[t + 1].date()),
            "exit_date": str(dates[j_exit].date()),
            "entry": round(entry, 4),
            "stop": round(s, 4),
            "exit": round(exit_px, 4),
            "reason": reason,
            "hold_days": j_exit - (t + 1) + 1,
            "ret_pct": round(100 * net, 3),
            "pnl_100": round(NOTIONAL * net, 3),
        })
    return trades


def main():
    tickers = load_universe()
    print(f"Experiment {EXPERIMENT}: {len(tickers)} tickers, window {START_TEST} to today")
    xiu = yf.download("XIU.TO", start=START_DL, auto_adjust=True, progress=False)["Close"].squeeze()
    xiu_ret = xiu.pct_change(63)
    all_trades, errors = [], []
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i:i + BATCH]
        try:
            raw = yf.download(chunk, start=START_DL, interval="1d", group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            errors.append(f"batch {i}: {e}")
            continue
        for t in chunk:
            try:
                d = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
                if len(d) < 260:
                    continue
                d = add_indicators(d)
                all_trades.extend(simulate(t, d, xiu_ret))
            except Exception as e:
                errors.append(f"{t}: {e}")
        print(f"batch {i // BATCH}: trades so far {len(all_trades)}")
        time.sleep(1)

    b = yf.download("XIU.TO", start=START_TEST, auto_adjust=True, progress=False)["Close"].squeeze()
    bench = {"xiu_total_pct": round(100 * (b.iloc[-1] / b.iloc[0] - 1), 1),
             "xiu_years": round((b.index[-1] - b.index[0]).days / 365.25, 1)}

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.DataFrame(all_trades)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df.to_csv(f"{OUT_DIR}/trades_{stamp}.csv", index=False)
    overall = stats(df) if not df.empty else {}
    acct = [portfolio(df, 100.0), portfolio(df, 5000.0)] if not df.empty else []
    by_reason = df.groupby("reason").ret_pct.agg(["count", "mean"]).round(2).reset_index() if not df.empty else None
    result = {"experiment": EXPERIMENT, "overall": overall, "account": acct,
              "benchmark": bench, "errors": len(errors)}
    with open(f"{OUT_DIR}/summary_{stamp}.json", "w") as f:
        json.dump(result, f, indent=2)
    with open(f"{OUT_DIR}/errors_{stamp}.txt", "w") as f:
        f.write("\n".join(errors))

    print("RESULT", json.dumps(result))
    if by_reason is not None:
        print(by_reason.to_string(index=False))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## Experiment {EXPERIMENT} ({START_TEST} to {stamp})\n```\n")
            f.write(json.dumps(result, indent=2) + "\n```\n")
            if by_reason is not None:
                f.write("```\n" + by_reason.to_string(index=False) + "\n```\n")


if __name__ == "__main__":
    main()
