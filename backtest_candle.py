"""
19-year daily backtest of the candle + indicator method (pdf_candle_scan.py rules).

For EVERY trading day from START_TEST to today, the same rules are checked on each
stock's close. A signal is taken at the NEXT day's open (skipped if it opens more
than 1% above the signal close or below the stop). Exit rules, checked bar by bar:
  - stop gap / stop: open or low at or below stop
  - target: high at or above target (gap-up open above target fills at open)
  - if stop and target are both inside one bar, the stop is assumed hit first
  - time stop: 20 bars, exit at close
Costs: 0.1% per side. Each trade is treated as a $100 notional bet (for comparison),
and every signal is taken (no capital limit), so this measures the method's edge.

Research only - not financial advice.
"""
import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from pdf_candle_scan import add_indicators, candle_patterns

START_DL = "2006-01-01"           # warm-up for 200-day SMA
START_TEST = os.environ.get("START_TEST", "2007-11-01")   # default 19 years to today
EXIT_MODE = os.environ.get("EXIT_MODE", "atr")       # "atr" or "pct"
STOP_PCT = float(os.environ.get("STOP_PCT", "0.02"))
TARGET_PCT = float(os.environ.get("TARGET_PCT", "0.05"))
HOLD_MAX = 20
COST_PER_SIDE = 0.001
NOTIONAL = 100.0
BATCH = 80
OUT_DIR = os.environ.get("OUT_DIR", "results/backtest_candle")
SUFFIXES = tuple(os.environ.get("SUFFIXES", ".TO,.V").split(","))


def signals(d):
    """Vectorized: True on each bar where the scan rules would fire (close-time)."""
    c = d["Close"]
    trend = (c > d["sma50"]) & (d["sma50"] > d["sma200"]) & (d["ema9"] > d["ema21"])
    pats = candle_patterns(d)
    any_pat = pats.any(axis=1)
    recent = any_pat | any_pat.shift(1, fill_value=False)
    rsi_ok = d["rsi"].between(40, 70) & (d["rsi"] > d["rsi"].shift(1))
    macd_ok = (d["macd_hist"] > 0) & (d["macd_hist"] > d["macd_hist"].shift(1))
    touched = (d["Low"] <= d["bb_low"]).astype(float).rolling(3).max().fillna(0).astype(bool)
    bb_ok = touched & (c > d["bb_low"])
    adx_ok = (d["adx"] > 20) & (d["plus_di"] > d["minus_di"])
    vol_ok = d["Volume"] >= d["vol20"]
    n_conf = rsi_ok.astype(int) + macd_ok.astype(int) + bb_ok.astype(int) + adx_ok.astype(int) + vol_ok.astype(int)
    liq = (c >= 2.0) & (d["dollar_adv50"] >= 500_000)
    risk = c - np.minimum(d["Low"], c - 1.5 * d["atr"])
    sig = trend & recent & (n_conf >= 3) & liq & (risk > 0)
    return sig.fillna(False), pats


def simulate(ticker, d):
    sig, pats = signals(d)
    o = d["Open"].values
    h = d["High"].values
    l = d["Low"].values
    cl = d["Close"].values
    atr = d["atr"].values
    dates = d.index
    n = len(d)
    trades = []
    busy_until = -1
    for t in np.where(sig.values)[0]:
        if t <= busy_until or t + 1 >= n:
            continue
        if dates[t] < pd.Timestamp(START_TEST):
            continue
        if EXIT_MODE == "pct":
            stop = cl[t] * (1 - STOP_PCT)
            target = cl[t] * (1 + TARGET_PCT)
        else:
            stop = min(l[t], cl[t] - 1.5 * atr[t])
            risk = cl[t] - stop
            target = cl[t] + 2 * risk
        entry = o[t + 1]
        if entry > cl[t] * 1.01 or entry <= stop or np.isnan(entry):
            continue
        exit_px, reason, j_exit = None, None, None
        last = min(t + HOLD_MAX, n - 1)
        for j in range(t + 1, last + 1):
            if o[j] <= stop:
                exit_px, reason = o[j], "stop_gap"
            elif l[j] <= stop:
                exit_px, reason = stop, "stop"
            elif o[j] >= target:
                exit_px, reason = o[j], "target_gap"
            elif h[j] >= target:
                exit_px, reason = target, "target"
            if exit_px is not None:
                j_exit = j
                break
        if exit_px is None:
            j_exit = last
            exit_px, reason = cl[last], "time"
        gross = exit_px / entry - 1
        net = gross - 2 * COST_PER_SIDE
        busy_until = j_exit
        trades.append({
            "ticker": ticker,
            "signal_date": str(dates[t].date()),
            "entry_date": str(dates[t + 1].date()),
            "exit_date": str(dates[j_exit].date()),
            "patterns": ", ".join(c for c in pats.columns if pats.iloc[t][c]),
            "entry": round(entry, 4),
            "stop": round(stop, 4),
            "target": round(target, 4),
            "exit": round(exit_px, 4),
            "reason": reason,
            "hold_days": j_exit - (t + 1) + 1,
            "ret_pct": round(100 * net, 3),
            "pnl_100": round(NOTIONAL * net, 3),
        })
    return trades


def portfolio(df, start, fee=COST_PER_SIDE):
    """Real account: one position at a time, all cash in, whole shares, fees both sides."""
    t = df.sort_values(["entry_date", "ticker"]).reset_index(drop=True)
    cash, busy_until, taken, wins, skipped = start, "0000", 0, 0, 0
    peak, mdd = start, 0.0
    for _, r in t.iterrows():
        if r.entry_date <= busy_until:
            continue
        sh = int(cash // r.entry)
        if sh < 1:
            skipped += 1
            continue
        cash = cash - sh * r.entry * (1 + fee) + sh * r.exit * (1 - fee)
        busy_until = r.exit_date
        taken += 1
        wins += int(r.exit > r.entry)
        peak = max(peak, cash)
        mdd = min(mdd, (cash - peak) / peak)
    return {"start": start, "end": round(cash, 2),
            "return_pct": round(100 * (cash / start - 1), 1),
            "trades_taken": taken,
            "win_rate_pct": round(100 * wins / taken, 1) if taken else None,
            "skipped_cannot_afford_1_share": skipped,
            "max_drawdown_pct": round(100 * mdd, 1)}


def load_universe():
    tickers = json.load(open("universe_tickers.json"))
    return [t for t in tickers if t.endswith(SUFFIXES)]


def stats(df):
    if df.empty:
        return {}
    w = df[df.ret_pct > 0]
    l_ = df[df.ret_pct <= 0]
    gp = df.loc[df.pnl_100 > 0, "pnl_100"].sum()
    gl = -df.loc[df.pnl_100 < 0, "pnl_100"].sum()
    eq = df.sort_values("exit_date").pnl_100.cumsum()
    dd = (eq - eq.cummax()).min()
    return {
        "trades": len(df),
        "win_rate_pct": round(100 * len(w) / len(df), 2),
        "avg_ret_pct": round(df.ret_pct.mean(), 3),
        "avg_win_pct": round(w.ret_pct.mean(), 2) if len(w) else None,
        "avg_loss_pct": round(l_.ret_pct.mean(), 2) if len(l_) else None,
        "expectancy_pct": round(df.ret_pct.mean(), 3),
        "profit_factor": round(gp / gl, 2) if gl else None,
        "total_pnl_100_each": round(df.pnl_100.sum(), 2),
        "max_dd_100_each": round(dd, 2),
        "avg_hold_days": round(df.hold_days.mean(), 1),
    }


def main():
    tickers = load_universe()
    print(f"Universe: {len(tickers)} tickers, window {START_TEST} to today")
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
                all_trades.extend(simulate(t, d))
            except Exception as e:
                errors.append(f"{t}: {e}")
        print(f"batch {i // BATCH}: trades so far {len(all_trades)}")
        time.sleep(1)

    # benchmark: XIU.TO buy and hold over the test window
    bench = {}
    try:
        b = yf.download("XIU.TO", start=START_TEST, auto_adjust=True, progress=False)
        b_close = b["Close"].squeeze()
        bench = {"xiu_total_pct": round(100 * (b_close.iloc[-1] / b_close.iloc[0] - 1), 1),
                 "xiu_years": round((b_close.index[-1] - b_close.index[0]).days / 365.25, 1)}
    except Exception as e:
        errors.append(f"benchmark: {e}")

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.DataFrame(all_trades)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    df.to_csv(f"{OUT_DIR}/trades_{stamp}.csv", index=False)
    overall = stats(df)
    df["year"] = df.entry_date.str[:4]
    by_year = (df.groupby("year")
               .apply(lambda g: pd.Series({
                   "trades": len(g),
                   "win_pct": round(100 * (g.ret_pct > 0).mean(), 1),
                   "avg_ret_pct": round(g.ret_pct.mean(), 2),
                   "pnl_100_each": round(g.pnl_100.sum(), 1)}))
               .reset_index())
    by_reason = df.groupby("reason").ret_pct.agg(["count", "mean"]).round(2).reset_index()
    with open(f"{OUT_DIR}/summary_{stamp}.json", "w") as f:
        json.dump({"overall": overall, "benchmark": bench, "errors": len(errors)}, f, indent=2)
    with open(f"{OUT_DIR}/errors_{stamp}.txt", "w") as f:
        f.write("\n".join(errors))
    by_year.to_csv(f"{OUT_DIR}/by_year_{stamp}.csv", index=False)

    acct = [portfolio(df, 100.0), portfolio(df, 5000.0)]
    print("ACCOUNT_SIM", json.dumps(acct))
    print(json.dumps(overall, indent=2))
    print(json.dumps(bench, indent=2))
    print(by_year.to_string(index=False))
    print(by_reason.to_string(index=False))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## 19-year candle + indicator backtest ({START_TEST} to {stamp})\n\n")
            f.write("```\n" + json.dumps(overall, indent=2) + "\n```\n\n")
            f.write("### Account simulation (one position at a time, all cash)\n```\n" + json.dumps(acct, indent=2) + "\n```\n")
            f.write("Benchmark XIU.TO: " + json.dumps(bench) + "\n\n")
            f.write("### By year\n```\n" + by_year.to_string(index=False) + "\n```\n")
            f.write("### By exit reason\n```\n" + by_reason.to_string(index=False) + "\n```\n")


if __name__ == "__main__":
    main()
