"""
TSX swing-trading backtester + daily scanner (runs on GitHub Actions).

1. Downloads ~10 years of daily data for liquid TSX stocks (yfinance).
2. Tests 3 swing strategies x a parameter grid.
   Tuned on 2016-2022, then checked OUT-OF-SAMPLE on 2023-today.
3. Checks the goal: win rate >= 65%, ~2%/month, max drawdown < 10%.
4. Scans today's data and lists stocks that give a signal NOW
   (only under the best strategy, and only if the TSX itself is in an uptrend).

Outputs: results/report.md, results/signals.csv, results/trend.csv
Research/education only - not financial advice.
"""
import os
import itertools
from datetime import datetime

import numpy as np
import pandas as pd

TICKERS = [
    "RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "NA.TO",   # banks
    "ENB.TO", "CNQ.TO", "SU.TO", "TRP.TO", "CVE.TO",          # energy
    "CNR.TO", "CP.TO", "BN.TO", "MFC.TO", "SLF.TO",           # rail/financials
    "SHOP.TO", "ATD.TO", "L.TO", "WCN.TO",                    # other large caps
]
MARKET = "XIU.TO"          # TSX 60 ETF used as the market-trend filter
START = "2014-01-01"
TRAIN_END = "2022-12-31"
COST = 0.001               # 0.1% per side (spread/slippage, Wealthsimple has no commission)
RISK_PER_TRADE = 0.02      # risk 2% of account per trade

GOAL_WIN = 0.65
GOAL_MONTHLY = 0.02
GOAL_MAX_DD = 0.10

OUT = "results"


# ---------------------------------------------------------------- data
def load_prices(symbols):
    import yfinance as yf
    data = {}
    for s in symbols:
        df = yf.download(s, start=START, auto_adjust=True, progress=False)
        if df is None or df.empty:
            print(f"  ! no data for {s}")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        data[s] = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        print(f"  {s}: {len(data[s])} days")
    return data


def add_indicators(df):
    d = df.copy()
    c = d["Close"]
    d["sma5"] = c.rolling(5).mean()
    d["sma20"] = c.rolling(20).mean()
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()
    delta = c.diff()
    up = delta.clip(lower=0).rolling(2).mean()
    dn = (-delta.clip(upper=0)).rolling(2).mean()
    d["rsi2"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    d["hi20"] = d["High"].rolling(20).max().shift(1)
    d["vol20"] = d["Volume"].rolling(20).mean()
    return d


# ---------------------------------------------------------------- signals
def entry_signal(d, strat, p):
    up = d["Close"] > d["sma200"]
    if strat == "pullback":
        return up & (d["Low"] <= d["sma20"]) & (d["Close"] > d["sma20"])
    if strat == "rsi2":
        return up & (d["rsi2"] < p["rsi"])
    if strat == "breakout":
        return up & (d["Close"] > d["hi20"]) & (d["Volume"] > 1.5 * d["vol20"])
    raise ValueError(strat)


def backtest_one(d, mkt_up, strat, p):
    """Signal at close -> buy next open. Exit on stop, target, or max hold."""
    sig = entry_signal(d, strat, p) & mkt_up.reindex(d.index).fillna(False)
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    idx = d.index
    sigv = sig.values
    trades = []
    i, n = 0, len(d)
    while i < n - 1:
        if not sigv[i]:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        stop = entry * (1 - p["stop"])
        target = entry * (1 + p["target"])
        exit_px, j = None, e
        for j in range(e, min(e + p["hold"], n)):
            if l[j] <= stop:                  # stop first (conservative)
                exit_px = min(o[j], stop) if j > e else stop
                break
            if h[j] >= target:
                exit_px = max(o[j], target) if j > e else target
                break
        if exit_px is None:
            j = min(e + p["hold"] - 1, n - 1)
            exit_px = c[j]
        ret = exit_px / entry - 1 - 2 * COST
        trades.append((idx[e], idx[j], ret))
        i = j + 1
    return trades


def stats(trades, stop):
    if not trades:
        return None
    t = pd.DataFrame(trades, columns=["entry", "exit", "ret"]).sort_values("exit")
    frac = min(1.0, RISK_PER_TRADE / stop)          # position size from 2% risk
    acct = t["ret"] * frac
    equity = (1 + acct).cumprod()
    dd = (equity / equity.cummax() - 1).min()
    months = max(1.0, (t["exit"].max() - t["entry"].min()).days / 30.44)
    monthly = equity.iloc[-1] ** (1 / months) - 1
    wins = t["ret"] > 0
    gross_win = t.loc[wins, "ret"].sum()
    gross_loss = -t.loc[~wins, "ret"].sum()
    return {
        "trades": len(t),
        "win_rate": wins.mean(),
        "avg_trade": t["ret"].mean(),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "monthly": monthly,
        "max_dd": -dd,
        "total": equity.iloc[-1] - 1,
    }


GRID = {
    "pullback": [dict(stop=s, target=t, hold=h)
                 for s, t, h in itertools.product([0.03, 0.05, 0.08], [0.02, 0.03, 0.05], [5, 10])],
    "rsi2": [dict(rsi=r, stop=s, target=t, hold=h)
             for r, s, t, h in itertools.product([5, 10], [0.05, 0.08], [0.02, 0.03], [5, 10])],
    "breakout": [dict(stop=s, target=t, hold=h)
                 for s, t, h in itertools.product([0.03, 0.05], [0.04, 0.06, 0.08], [10])],
}


def run_all(data, mkt_up, start=None, end=None):
    rows = []
    for strat, plist in GRID.items():
        for p in plist:
            all_tr = []
            for s, d in data.items():
                dd_ = d.loc[start:end] if (start or end) else d
                all_tr += backtest_one(dd_, mkt_up, strat, p)
            st = stats(all_tr, p["stop"])
            if st:
                rows.append({"strategy": strat, "params": p, **st})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def pct(x):
    return f"{x*100:.2f}%"


def main(data=None):
    os.makedirs(OUT, exist_ok=True)
    if data is None:
        print("Downloading prices...")
        data = load_prices(TICKERS + [MARKET])
    mkt = add_indicators(data.pop(MARKET))
    mkt_up = mkt["Close"] > mkt["sma200"]
    data = {s: add_indicators(d) for s, d in data.items()}

    print("Tuning on 2016-2022...")
    train = run_all(data, mkt_up, "2016-01-01", TRAIN_END)
    train = train[train["trades"] >= 50]
    if train.empty:
        raise SystemExit("Not enough trades in training data.")
    best = train.sort_values(["profit_factor", "win_rate"], ascending=False).head(5)

    print("Testing out-of-sample (2023-today)...")
    test_rows = []
    for _, r in best.iterrows():
        tr = []
        for s, d in data.items():
            tr += backtest_one(d.loc["2023-01-01":], mkt_up, r["strategy"], r["params"])
        st = stats(tr, r["params"]["stop"])
        if st:
            test_rows.append({"strategy": r["strategy"], "params": r["params"], **st})
    test = pd.DataFrame(test_rows)
    champ = test.sort_values("profit_factor", ascending=False).iloc[0]

    passed = (champ["win_rate"] >= GOAL_WIN and champ["monthly"] >= GOAL_MONTHLY
              and champ["max_dd"] < GOAL_MAX_DD)

    # ---- today's scan
    market_ok = bool(mkt_up.iloc[-1])
    last_date = mkt.index[-1].date()
    trend_rows, sig_rows = [], []
    for s, d in data.items():
        x = d.iloc[-1]
        trend = ("UPTREND" if x["Close"] > x["sma50"] > x["sma200"]
                 else "above 200d" if x["Close"] > x["sma200"] else "DOWNTREND")
        trend_rows.append({"ticker": s, "close": round(x["Close"], 2),
                           "sma50": round(x["sma50"], 2), "sma200": round(x["sma200"], 2),
                           "trend": trend})
        sig = entry_signal(d, champ["strategy"], champ["params"]).iloc[-1]
        if sig and market_ok:
            p = champ["params"]
            sig_rows.append({"ticker": s, "close": round(x["Close"], 2),
                             "stop_loss": round(x["Close"] * (1 - p["stop"]), 2),
                             "take_profit": round(x["Close"] * (1 + p["target"]), 2),
                             "max_hold_days": p["hold"]})
    trend_df = pd.DataFrame(trend_rows).sort_values("trend", ascending=False)
    sig_df = pd.DataFrame(sig_rows, columns=["ticker", "close", "stop_loss",
                                             "take_profit", "max_hold_days"])
    trend_df.to_csv(f"{OUT}/trend.csv", index=False)
    sig_df.to_csv(f"{OUT}/signals.csv", index=False)

    # ---- report
    L = []
    L.append(f"# TSX Scanner - data up to {last_date}")
    L.append(f"_Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC. Research only, not financial advice._\n")
    L.append("## Goal check (out-of-sample 2023-today)")
    L.append(f"**Best strategy:** `{champ['strategy']}` {champ['params']}\n")
    L.append("| Metric | Result | Goal |\n|---|---|---|")
    L.append(f"| Win rate | {pct(champ['win_rate'])} | >= {pct(GOAL_WIN)} |")
    L.append(f"| Avg monthly (2% risk sizing) | {pct(champ['monthly'])} | >= {pct(GOAL_MONTHLY)} |")
    L.append(f"| Max drawdown | {pct(champ['max_dd'])} | < {pct(GOAL_MAX_DD)} |")
    L.append(f"| Profit factor | {champ['profit_factor']:.2f} | > 1.3 |")
    L.append(f"| Trades | {champ['trades']} | 50+ |")
    L.append(f"\n**Verdict:** {'PASSES the goal' if passed else 'Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT'}\n")
    L.append("## Top 5 from training, re-tested out-of-sample")
    L.append("| Strategy | Params | Win | Monthly | Max DD | PF | Trades |\n|---|---|---|---|---|---|---|")
    for _, r in test.sort_values("profit_factor", ascending=False).iterrows():
        L.append(f"| {r['strategy']} | {r['params']} | {pct(r['win_rate'])} | {pct(r['monthly'])} "
                 f"| {pct(r['max_dd'])} | {r['profit_factor']:.2f} | {r['trades']} |")
    L.append(f"\n## Today's signals ({'TSX in uptrend' if market_ok else 'TSX BELOW 200-day - no trades'})")
    if sig_df.empty:
        L.append("No setups today. Doing nothing is a valid trade.")
    else:
        L.append("Buy at next open only if you choose to; levels are from today's close.\n")
        L.append("| Ticker | Close | Stop-loss | Take-profit | Max hold |\n|---|---|---|---|---|")
        for _, r in sig_df.iterrows():
            L.append(f"| {r.ticker} | {r.close} | {r.stop_loss} | {r.take_profit} | {r.max_hold_days}d |")
    L.append("\n## Trend status of watchlist")
    L.append("| Ticker | Close | 50d | 200d | Trend |\n|---|---|---|---|---|")
    for _, r in trend_df.iterrows():
        L.append(f"| {r.ticker} | {r.close} | {r.sma50} | {r.sma200} | {r.trend} |")
    import consensus
    cons_md, cons_buys, cons_scan = consensus.run(
        data, mkt, champ["params"], backtest_one, stats, pct,
        live=os.environ.get("GITHUB_ACTIONS") == "true")
    cons_buys.to_csv(f"{OUT}/consensus_buys.csv", index=False)
    cons_scan.to_csv(f"{OUT}/scanner_votes.csv", index=False)
    L.insert(1, cons_md.split("\n### Does")[0] + "\n")   # consensus buys at the top
    L.append(cons_md)
    report = "\n".join(L)
    with open(f"{OUT}/report.md", "w") as f:
        f.write(report)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a") as f:
            f.write(report)
    print(report)


if __name__ == "__main__":
    main()
