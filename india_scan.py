"""
India (NSE) Swing Scanner — generates a daily report similar to the TSX scanner.
Uses yfinance for data. Focuses on liquid Nifty-50 / large-cap names.

Risk rules match risk_levels.py (3x ATR stop / 6x ATR target, capped at -8%).
Includes improved position sizing: scales risk down in weak regimes.

Usage:
  ACCOUNT=10000 python india_scan.py

Results written to results/india_report.md
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from risk_levels import levels as risk_levels, wilder_atr
from notifier import send_telegram

# ── Config ────────────────────────────────────────────────────────────────

ACCOUNT = float(os.environ.get("ACCOUNT", "10000"))
RISK_PER_TRADE = 0.015          # base 1.5% (slightly more conservative)
MAX_PORTFOLIO_RISK = 0.06       # never more than 6% open risk
MAX_STOP_PCT = 8.0

# Major liquid NSE names (Nifty 50 style). Add more as needed.
UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS",
    "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "BAJAJFINSV.NS",
]
MARKET = "^NSEI"   # Nifty 50 as regime filter

OUT = Path("results")
OUT.mkdir(exist_ok=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    c = d["Close"]
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()
    # Simple momentum
    d["mom63"] = c / c.shift(63) - 1
    # ATR
    tr = pd.concat([
        d["High"] - d["Low"],
        (d["High"] - c.shift(1)).abs(),
        (d["Low"] - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    return d


def score_stock(d: pd.DataFrame) -> float:
    """Simple 0-3 score: trend + momentum + not extended."""
    if len(d) < 200:
        return 0.0
    x = d.iloc[-1]
    score = 0.0
    if x["Close"] > x["sma50"] > x["sma200"]:
        score += 1.0
    if x["mom63"] > 0.05:
        score += 1.0
    # not too extended (within 15% of 50d)
    if x["Close"] < x["sma50"] * 1.15:
        score += 1.0
    return score


def regime_ok(mkt: pd.DataFrame) -> tuple[bool, str]:
    if mkt.empty or len(mkt) < 200:
        return True, "(market data incomplete)"
    current = float(mkt["Close"].iloc[-1])
    sma200 = float(mkt["sma200"].iloc[-1])
    ok = current > sma200
    note = f"Nifty {current:.0f} vs 200d {sma200:.0f}"
    if not ok:
        note += " [WEAK — size down]"
    return ok, note


def position_size(entry: float, stop_pct: float, account: float, regime_weak: bool) -> int:
    """Risk-adjusted share count. Scales down 50% in weak regime."""
    risk = RISK_PER_TRADE * (0.5 if regime_weak else 1.0)
    risk_dollars = account * risk
    if stop_pct <= 0:
        return 0
    shares = int(risk_dollars / (entry * stop_pct))
    # hard cap so we never put more than ~20% of account in one name
    max_shares = int(account * 0.20 / entry)
    return max(0, min(shares, max_shares))


def run():
    print("Loading India data...")
    data = {}
    for sym in UNIVERSE + [MARKET]:
        try:
            df = yf.download(sym, period="18mo", auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is None or df.empty or len(df) < 100:
                continue
            data[sym] = add_indicators(df)
            print(f"  {sym}: {len(df)} days")
        except Exception as e:
            print(f"  ! {sym}: {e}")

    mkt = data.get(MARKET)
    if mkt is None:
        print("No market data — aborting")
        return

    market_ok, regime_note = regime_ok(mkt)
    regime_weak = not market_ok

    signals = []
    for sym, d in data.items():
        if sym == MARKET:
            continue
        sc = score_stock(d)
        if sc < 2.0:
            continue
        x = d.iloc[-1]
        entry = float(x["Close"])
        atr = float(x["atr14"]) if pd.notna(x["atr14"]) else entry * 0.02
        lv = risk_levels(entry, atr)
        shares = position_size(entry, abs(lv["stop_pct"]) / 100, ACCOUNT, regime_weak)
        signals.append({
            "symbol": sym.replace(".NS", ""),
            "score": sc,
            "close": round(entry, 2),
            "stop": lv["stop"],
            "target": lv["target"],
            "stop_pct": lv["stop_pct"],
            "target_pct": lv["target_pct"],
            "shares": shares,
            "risk_note": "half size" if regime_weak else "full",
        })

    signals = sorted(signals, key=lambda s: s["score"], reverse=True)[:8]

    # Build report
    lines = [
        f"# India Scanner — {datetime.now().strftime('%Y-%m-%d')}",
        f"**Regime:** {regime_note}",
        f"Account size used for sizing: ₹{ACCOUNT:,.0f}",
        "",
        "## Top signals (score ≥ 2)",
        "",
    ]
    if not signals:
        lines.append("**No strong signals today.**")
    else:
        lines.append("| Symbol | Score | Close | Stop | Target | Stop% | Target% | Shares | Size |")
        lines.append("|--------|-------|-------|------|--------|-------|---------|--------|------|")
        for s in signals:
            lines.append(
                f"| {s['symbol']} | {s['score']:.0f}/3 | {s['close']} | {s['stop']} | {s['target']} | "
                f"{s['stop_pct']:+.1f}% | {s['target_pct']:+.1f}% | {s['shares']} | {s['risk_note']} |"
            )

    lines += [
        "",
        "_Risk: base 1.5% per trade, halved in weak regime. Stop = 3× ATR (capped -8%), target = 6× ATR._",
        "_Research only. Not financial advice._",
    ]

    report = "\n".join(lines)
    (OUT / "india_report.md").write_text(report, encoding="utf-8")
    print("\n" + report)

    # Optional Telegram summary
    if signals:
        summary = f"🇮🇳 *India Scan* ({len(signals)} signals)\n" + regime_note + "\n\n"
        for s in signals[:5]:
            summary += f"`{s['symbol']}` score {s['score']:.0f} | ₹{s['close']} → stop {s['stop_pct']:+.1f}% / tgt {s['target_pct']:+.1f}% | {s['shares']} sh ({s['risk_note']})\n"
        send_telegram(summary)


if __name__ == "__main__":
    run()
