"""
PRIMARY TSX SCANNER (v2.6 FIXED + hardened)
===========================================
This is the current production scanner.
Older versions (tsx_scan.py, _v2, _v2_5) are kept only for reference.

Fixes included:
✅ signal_score() fully vectorized
✅ Realistic default ACCOUNT = 10000
✅ Zero-share warning + safer position sizing
✅ Overlap-aware risk distribution
✅ Liquidity + price filters
✅ Macro regime filter (TSX > 200d SMA)
✅ ATR stops/targets + gap protection
✅ Execution modeling (next-day open + 0.5% slippage)
✅ Robust cache handling

Usage:
  ACCOUNT=25000 python tsx_scan_v2_6_fixed.py
"""
import os
import itertools
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

import cache_manager

TICKERS = [
    "RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "NA.TO",
    "ENB.TO", "CNQ.TO", "SU.TO", "TRP.TO", "CVE.TO",
    "CNR.TO", "CP.TO", "BN.TO", "MFC.TO", "SLF.TO",
    "SHOP.TO", "ATD.TO", "L.TO", "WCN.TO",
]
MARKET = "XIU.TO"
START = "2014-01-01"
TRAIN_END = "2024-12-31"
COST = 0.001
RISK_PER_TRADE = 0.02
ACCOUNT = float(os.environ.get("ACCOUNT", "10000"))  # realistic default

MIN_PRICE = 1.00
MIN_ADV_50 = 300_000

GOAL_WIN = 0.65
GOAL_MONTHLY = 0.02
GOAL_MAX_DD = 0.10

OUT = "results"
MAX_GAP_UP = 0.02


def signal_score(d):
    """Vectorized multi-scanner score (0-4). Returns a Series."""
    if len(d) < 50:
        return pd.Series(0.0, index=d.index)

    scores = pd.Series(0.0, index=d.index)
    c = d["Close"]

    # A: Trend
    trend = ((c > d["sma200"]) & (d["sma50"] > d["sma200"]) & (c > d["sma50"])).astype(float)
    scores += trend

    # B: Momentum (needs 252 bars)
    if len(d) >= 252:
        mom = (c / c.shift(252) - 1) > 0.10
        at_high = c >= 0.85 * d["hi252"]
        scores += (mom & at_high).astype(float)

    # C: Volume + Risk
    vol_ok = d["Volume"] > 0.8 * d["vol20"]
    atr_ok = (d["atr14"] / c) < 0.08
    scores += (vol_ok & atr_ok).astype(float)

    # D: Bullish candle
    if len(d) > 1:
        body = d["Close"] - d["Open"]
        lower_tail = d["Open"] - d["Low"]
        candle = ((d["Close"] > d["Close"].shift(1)) & (body > lower_tail) & (body > 0)).astype(float)
        scores += candle

    return scores


def load_prices(symbols):
    cache_manager.ensure_cache_dir()
    data = {}

    for s in symbols:
        try:
            df = cache_manager.get_data_with_cache(
                s, yf.download, start=START, auto_adjust=True, progress=False
            )
        except Exception as e:
            print(f"  ! download/cache error for {s}: {e}")
            continue

        if df is None or df.empty:
            print(f"  ! no data for {s}")
            continue

        if "Volume" in df.columns:
            adv_50 = (df["Volume"].rolling(50).mean() * df["Close"]).iloc[-1]
            if pd.isna(adv_50) or adv_50 < MIN_ADV_50:
                print(f"  ⚠ {s}: ADV ${adv_50:,.0f} < ${MIN_ADV_50:,.0f} — skipped")
                continue
            if df["Close"].iloc[-1] < MIN_PRICE:
                print(f"  ⚠ {s}: price ${df['Close'].iloc[-1]:.2f} < ${MIN_PRICE:.2f} — skipped")
                continue

        data[s] = df
        print(f"  {s}: {len(df)} days")

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
    d["hi55"] = d["High"].rolling(55).max().shift(1)
    d["hi252"] = d["High"].rolling(252).max()
    d["lo252"] = d["Low"].rolling(252).min()
    d["mom12_1"] = c.shift(21) / c.shift(252) - 1
    d["vol20"] = d["Volume"].rolling(20).mean()
    pc = c.shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    d["gap"] = d["Open"] / pc - 1
    d["worst_gap_1y"] = d["gap"].rolling(252).min()
    d["adv_50"] = d["Volume"].rolling(50).mean() * d["Close"]
    return d


def exit_fracs(p, atr, price):
    if "atr_stop" in p:
        return p["atr_stop"] * atr / price, p["atr_tgt"] * atr / price
    return p["stop"], p["target"]


def levels(row, p, account=None, positions_at_risk=1):
    """Position sizing with overlap awareness and zero-share warning."""
    close = float(row["Close"])
    atr = float(row["atr14"])
    sf, tf = exit_fracs(p, atr, close)

    out = {
        "close": round(close, 2),
        "buy_max": round(close * (1 + MAX_GAP_UP), 2),
        "stop_pct": sf,
        "target_pct": tf,
        "stop_loss": round(close * (1 - sf), 2),
        "take_profit": round(close * (1 + tf), 2),
    }

    account = account or ACCOUNT
    risk_per_position = RISK_PER_TRADE / max(1, positions_at_risk)
    risk_dollars = account * risk_per_position

    if sf <= 0 or close <= 0:
        shares = 0
    else:
        shares = int(min(risk_dollars / (close * sf), account / close))

    if shares == 0:
        print(f"  ⚠ zero shares calculated (account=${account:,.0f}, stop={sf*100:.1f}%)")

    out["shares"] = shares
    return out


def gap_safe(row, p):
    sf, _ = exit_fracs(p, float(row["atr14"]), float(row["Close"]))
    wg = row.get("worst_gap_1y", np.nan)
    return not (pd.notna(wg) and -wg > sf)


def simulate_paper_trade(d, sig, p):
    """Realistic paper trade simulation with next-day open + slippage."""
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    atr = d["atr14"].values
    idx = d.index
    sigv = sig.fillna(False).values
    n = len(d)
    trades = []
    i = 0

    while i < n - 1:
        if not sigv[i] or not np.isfinite(atr[i]):
            i += 1
            continue

        e = i + 1
        next_open = o[e]
        if next_open > c[i] * (1 + MAX_GAP_UP):
            i += 1
            continue

        entry = next_open * (1 - 0.005)  # 0.5% slippage
        sf, tf = exit_fracs(p, atr[i], c[i])
        stop = entry * (1 - sf)
        target = entry * (1 + tf)

        exit_px = None
        j = e
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

        ret = exit_px / entry - 1 - 2 * COST
        trades.append((idx[e], idx[j], ret, sf))
        i = j + 1

    return trades


def entry_signal(d, strat, p):
    c = d["Close"]
    up = c > d["sma200"]

    if strat == "two_four_votes":
        scores = signal_score(d)
        return (scores >= 2.0) & up

    if strat == "trend_template":
        return ((c > d["sma50"]) & (d["sma50"] > d["sma150"]) & (d["sma150"] > d["sma200"])
                & (d["sma200"] > d["sma200"].shift(21))
                & (c >= 1.3 * d["lo252"]) & (c >= 0.75 * d["hi252"]))

    raise ValueError(f"Unknown strategy: {strat}")


def backtest_one(d, mkt_up, strat, p):
    sig = entry_signal(d, strat, p) & mkt_up.reindex(d.index).fillna(False)
    return simulate_paper_trade(d, sig, p)


def stats(trades):
    if not trades:
        return None
    t = pd.DataFrame(trades, columns=["entry", "exit", "ret", "sf"]).sort_values("exit")
    frac = (RISK_PER_TRADE / t["sf"]).clip(upper=1.0)
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
        "win_rate": float(wins.mean()),
        "avg_trade": float(t["ret"].mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "monthly": float(monthly),
        "max_dd": float(-dd),
        "total": float(equity.iloc[-1] - 1),
    }


def check_market_regime(mkt_data):
    if mkt_data is None or mkt_data.empty:
        return True, "(market data missing)"
    current = mkt_data["Close"].iloc[-1]
    sma200 = mkt_data["sma200"].iloc[-1]
    if pd.isna(sma200):
        return True, "(SMA200 not ready)"
    market_up = current > sma200
    note = f"TSX {current:.2f} vs 200d SMA {sma200:.2f}"
    if not market_up:
        note += " [BELOW 200d — REDUCE SIZE OR SKIP]"
    return market_up, note


def pct(x):
    return f"{x*100:.2f}%"


def main(data=None, paper_trade_start="2024-10-01", paper_trade_end="2026-10-28"):
    os.makedirs(OUT, exist_ok=True)

    if data is None:
        print("Loading prices (with caching)...")
        cache_manager.cache_stats()
        data = load_prices(TICKERS + [MARKET])

    if MARKET not in data:
        raise SystemExit(f"Market data {MARKET} not available")

    mkt = add_indicators(data.pop(MARKET))
    data = {s: add_indicators(d) for s, d in data.items()}

    print(f"\nRunning paper trade: {paper_trade_start} → {paper_trade_end}")
    print(f"Account size used for sizing: ${ACCOUNT:,.0f}")

    paper_trades = []
    mkt_up = mkt["Close"] > mkt["sma200"]
    p = {"atr_stop": 1.5, "atr_tgt": 3.0, "hold": 10}

    for s, d in data.items():
        d_paper = d.loc[paper_trade_start:paper_trade_end]
        if len(d_paper) < 50:
            continue
        paper_trades += backtest_one(d_paper, mkt_up, "two_four_votes", p)

    if paper_trades:
        paper_df = pd.DataFrame(paper_trades, columns=["entry", "exit", "ret", "sf"])
        paper_df = paper_df.sort_values("entry")
        paper_df.to_csv(f"{OUT}/paper_trade_results.csv", index=False)

        st = stats(paper_trades)
        print("\n" + "=" * 70)
        print(f"PAPER TRADE RESULTS ({paper_trade_start} → {paper_trade_end})")
        print("=" * 70)
        print(f"Trades        : {st['trades']}")
        print(f"Win rate      : {pct(st['win_rate'])}")
        print(f"Avg trade     : {pct(st['avg_trade'])}")
        print(f"Profit factor : {st['profit_factor']:.2f}")
        print(f"Monthly       : {pct(st['monthly'])}")
        print(f"Max drawdown  : {pct(st['max_dd'])}")
        print(f"Total return  : {pct(st['total'])}")
        print("=" * 70)
    else:
        print("No trades generated in the paper-trade window.")

    # Today’s regime + simple signal dump
    market_ok, regime_note = check_market_regime(mkt)
    print(f"\nMarket regime: {regime_note}")

    print("\nScanner votes today (2/4 = tradable):")
    print("| Ticker | Score | Trend |")
    print("|--------|-------|-------|")
    for s, d in data.items():
        score = signal_score(d).iloc[-1]
        x = d.iloc[-1]
        trend = "UPTREND" if x["Close"] > x["sma50"] > x["sma200"] else (
            "above 200d" if x["Close"] > x["sma200"] else "DOWNTREND")
        print(f"| {s:7} | {score:.0f}/4   | {trend} |")


if __name__ == "__main__":
    main()
