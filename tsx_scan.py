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
ACCOUNT = float(os.environ.get("ACCOUNT", "100"))   # account size for share counts (CAD)

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
    for n in (5, 20, 50, 150, 200):
        d[f"sma{n}"] = c.rolling(n).mean()
    delta = c.diff()
    up = delta.clip(lower=0).rolling(2).mean()
    dn = (-delta.clip(upper=0)).rolling(2).mean()
    d["rsi2"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    d["hi20"] = d["High"].rolling(20).max().shift(1)
    d["hi55"] = d["High"].rolling(55).max().shift(1)          # Turtle / Donchian
    d["hi252"] = d["High"].rolling(252).max()                  # 52-week high
    d["lo252"] = d["Low"].rolling(252).min()
    d["mom12_1"] = c.shift(21) / c.shift(252) - 1              # 12-1 month momentum
    d["vol20"] = d["Volume"].rolling(20).mean()
    pc = c.shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    d["gap"] = d["Open"] / pc - 1
    d["worst_gap_1y"] = d["gap"].rolling(252).min()            # biggest overnight drop in a year
    return d


# ---------------------------------------------------------------- signals
# Strategies with published evidence behind them:
#   pullback / rsi2   - short-term mean reversion inside a long uptrend (Connors)
#   breakout          - 20-day high on volume
#   donchian          - 55-day high breakout (Turtle trading rules)
#   momentum52        - near 52-week high + strong 12-1 month momentum
#                       (Jegadeesh & Titman 1993; George & Hwang 2004)
#   trend_template    - Minervini stage-2 trend template
def entry_signal(d, strat, p):
    c = d["Close"]
    up = c > d["sma200"]
    if strat == "pullback":
        return up & (d["Low"] <= d["sma20"]) & (c > d["sma20"])
    if strat == "rsi2":
        return up & (d["rsi2"] < p["rsi"])
    if strat == "breakout":
        return up & (c > d["hi20"]) & (d["Volume"] > 1.5 * d["vol20"])
    if strat == "donchian":
        return up & (c > d["hi55"])
    if strat == "momentum52":
        return up & (c > d["sma50"]) & (c >= 0.95 * d["hi252"]) & (d["mom12_1"] > 0.10)
    if strat == "trend_template":
        return ((c > d["sma50"]) & (d["sma50"] > d["sma150"]) & (d["sma150"] > d["sma200"])
                & (d["sma200"] > d["sma200"].shift(21)) & (c >= 1.3 * d["lo252"])
                & (c >= 0.75 * d["hi252"]))
    raise ValueError(strat)


MAX_GAP_UP = 0.02      # skip the trade if it opens > 2% above the signal close


def exit_fracs(p, atr, price):
    """Stop / target distance as a fraction of price. ATR-based when p has atr_stop."""
    if "atr_stop" in p:
        return p["atr_stop"] * atr / price, p["atr_tgt"] * atr / price
    return p["stop"], p["target"]


def levels(row, p, account=None):
    """Live trading levels for a signal row (last bar of indicator frame)."""
    close = float(row["Close"])
    sf, tf = exit_fracs(p, float(row["atr14"]), close)
    out = {"close": round(close, 2), "buy_max": round(close * (1 + MAX_GAP_UP), 2),
           "stop_pct": sf, "target_pct": tf,
           "stop_loss": round(close * (1 - sf), 2), "take_profit": round(close * (1 + tf), 2)}
    account = account or ACCOUNT
    risk_dollars = account * RISK_PER_TRADE
    shares = int(min(risk_dollars / (close * sf), account / close)) if sf > 0 else 0
    out["shares"] = shares
    return out


def gap_safe(row, p):
    """Exclude stocks whose worst overnight gap in the last year was bigger than the stop."""
    sf, _ = exit_fracs(p, float(row["atr14"]), float(row["Close"]))
    wg = row.get("worst_gap_1y", np.nan)
    return not (pd.notna(wg) and -wg > sf)


def simulate(d, sig, p):
    """Signal at close -> buy next open (skip if gaps up > 2%).
    Exit: stop, target, or max hold. Stops/targets are measured from the ACTUAL entry price.
    A gap down through the stop fills at the open (real-world loss is recorded)."""
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    atr = d["atr14"].values
    idx, sigv, n = d.index, sig.fillna(False).values, len(d)
    trades, i = [], 0
    while i < n - 1:
        if not sigv[i] or not np.isfinite(atr[i]):
            i += 1
            continue
        e = i + 1
        entry = o[e]
        if entry > c[i] * (1 + MAX_GAP_UP):
            i += 1
            continue
        sf, tf = exit_fracs(p, atr[i], c[i])
        stop, target = entry * (1 - sf), entry * (1 + tf)
        exit_px, j = None, e
        for j in range(e, min(e + p["hold"], n)):
            if l[j] <= stop:
                exit_px = min(o[j], stop) if j > e else stop
                break
            if h[j] >= target:
                exit_px = max(o[j], target) if j > e else target
                break
        if exit_px is None:
            j = min(e + p["hold"] - 1, n - 1)
            exit_px = c[j]
        trades.append((idx[e], idx[j], exit_px / entry - 1 - 2 * COST, sf))
        i = j + 1
    return trades


def backtest_one(d, mkt_up, strat, p):
    sig = entry_signal(d, strat, p) & mkt_up.reindex(d.index).fillna(False)
    return simulate(d, sig, p)


def stats(trades, stop=None):
    if not trades:
        return None
    t = pd.DataFrame(trades, columns=["entry", "exit", "ret", "sf"]).sort_values("exit")
    frac = (RISK_PER_TRADE / t["sf"]).clip(upper=1.0)        # size each trade so the stop = 2% risk
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


_ATR = [dict(atr_stop=s, atr_tgt=t, hold=h)
        for s, t, h in itertools.product([2, 3], [3, 4, 6], [10, 20])]
GRID = {
    "pullback": [dict(stop=s, target=t, hold=h)
                 for s, t, h in itertools.product([0.03, 0.05, 0.08], [0.02, 0.03, 0.05], [5, 10])] + _ATR,
    "rsi2": [dict(rsi=r, stop=s, target=t, hold=h)
             for r, s, t, h in itertools.product([5, 10], [0.05, 0.08], [0.02, 0.03], [5, 10])]
            + [dict(rsi=10, **a) for a in _ATR],
    "breakout": [dict(stop=s, target=t, hold=h)
                 for s, t, h in itertools.product([0.03, 0.05], [0.04, 0.06, 0.08], [10])] + _ATR,
    "donchian": _ATR,
    "momentum52": _ATR,
    "trend_template": _ATR,
}


def run_all(data, mkt_up, start=None, end=None):
    rows = []
    for strat, plist in GRID.items():
        for p in plist:
            all_tr = []
            for s, d in data.items():
                dd_ = d.loc[start:end] if (start or end) else d
                all_tr += backtest_one(dd_, mkt_up, strat, p)
            st = stats(all_tr)
            if st:
                rows.append({"strategy": strat, "params": p, **st})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def pct(x):
    return f"{x*100:.2f}%"


RULES_NOTE = ("**How to enter:** buy at the next open with a limit order no higher than *Buy max* "
              "(skip if it opens above). After your order fills, set the stop and target as "
              "**percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps "
              f"your loss at {RISK_PER_TRADE:.0%} of the account if the stop is hit.\n")


def level_table(df, extra_cols=()):
    hdr = ["Ticker", *[c for c, _ in extra_cols], "Close", "Buy max", "Stop %", "Target %",
           "Stop (from close)", "Target (from close)", f"Shares (${ACCOUNT:,.0f} acct)", "Max hold"]
    out = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for _, r in df.iterrows():
        cells = [r.ticker, *[str(r[k]) for _, k in extra_cols], r.close, r.buy_max,
                 f"-{r.stop_pct*100:.1f}%", f"+{r.target_pct*100:.1f}%", r.stop_loss, r.take_profit,
                 r.shares, f"{r.max_hold_days}d"]
        out.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(out)


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
        st = stats(tr)
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
        if sig and market_ok and gap_safe(x, champ["params"]):
            sig_rows.append({"ticker": s, **levels(x, champ["params"]),
                             "max_hold_days": champ["params"]["hold"]})
    trend_df = pd.DataFrame(trend_rows).sort_values("trend", ascending=False)
    sig_df = pd.DataFrame(sig_rows, columns=["ticker", "close", "buy_max", "stop_pct", "target_pct",
                                             "stop_loss", "take_profit", "shares", "max_hold_days"])
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
        L.append(RULES_NOTE)
        L.append(level_table(sig_df))
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
    L.append(cons_md)
    if os.environ.get("SKIP_UNIVERSE") != "1":
        import universe
        print("Scanning all TSX + TSX Venture stocks...")
        try:
            all_md, all_picks, all_df = universe.scan_all(mkt, champ["params"], add_indicators, consensus, pct)
            all_picks.to_csv(f"{OUT}/all_canada_buys.csv", index=False)
            all_df.to_csv(f"{OUT}/all_canada_votes.csv", index=False)
            L.insert(1, all_md + "\n")
        except Exception as e:
            L.insert(1, f"\n## ALL CANADA scan failed today: {e}\n")
    L.insert(1, cons_md.split("\n### Does")[0] + "\n")   # watchlist consensus at the top
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
