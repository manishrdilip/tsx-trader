"""
Three independent scanners + consensus.
A stock is a CONSENSUS BUY only when all three agree:
  A - Trend:      close > SMA50 > SMA200 and TSX (XIU) above its 200-day
  B - Momentum:   RSI(14) 50-70, MACD above signal, beating XIU over 3 months
  C - Volume/Risk: volume above 20-day avg, ATR < 3% of price,
                  no earnings in the next 10 days (live scan only)
The consensus rule is also backtested so you can see if agreement helps.
Research only - not financial advice.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd


def add_extra(d):
    d = d.copy()
    c = d["Close"]
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["macd"], d["macd_sig"] = macd, macd.ewm(span=9, adjust=False).mean()
    pc = c.shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    d["atr_pct"] = tr.rolling(14).mean() / c
    d["ret63"] = c.pct_change(63)
    return d


def scanners(d, mkt):
    m_up = (mkt["Close"] > mkt["sma200"]).reindex(d.index).fillna(False)
    m_ret = mkt["Close"].pct_change(63).reindex(d.index)
    a = (d["Close"] > d["sma50"]) & (d["sma50"] > d["sma200"]) & m_up
    b = d["rsi14"].between(50, 70) & (d["macd"] > d["macd_sig"]) & (d["ret63"] > m_ret)
    c = (d["Volume"] > d["vol20"]) & (d["atr_pct"] < 0.03)
    return a, b, c


def earnings_soon(ticker, days=10):
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else []
        today = date.today()
        return any(today <= pd.Timestamp(x).date() <= today + timedelta(days=days) for x in dates)
    except Exception:
        return False   # unknown -> not blocked; check manually


def run(data, mkt, params, backtest_one, stats, pct, live=True):
    data = {s: add_extra(d) for s, d in data.items()}
    rows, consensus_sig = [], {}
    for s, d in data.items():
        a, b, c = scanners(d, mkt)
        consensus_sig[s] = a & b & c
        A, B, C = bool(a.iloc[-1]), bool(b.iloc[-1]), bool(c.iloc[-1])
        earn = earnings_soon(s) if (live and A and B and C) else False
        rows.append({"ticker": s, "A_trend": A, "B_momentum": B, "C_volume_risk": C and not earn,
                     "earnings_soon": earn, "close": round(d["Close"].iloc[-1], 2)})
    scan = pd.DataFrame(rows)
    scan["votes"] = scan[["A_trend", "B_momentum", "C_volume_risk"]].sum(axis=1)
    buys = scan[scan["votes"] == 3].copy()
    buys["stop_loss"] = (buys["close"] * (1 - params["stop"])).round(2)
    buys["take_profit"] = (buys["close"] * (1 + params["target"])).round(2)
    buys = buys.sort_values("ticker").head(5)

    # backtest the consensus rule with the same exits as the main strategy
    def bt(start):
        tr = []
        for s, d in data.items():
            sig = consensus_sig[s]
            dd = d.loc[start:].assign(_sig=sig.loc[start:])
            tr += _bt_sig(dd, params)
        return stats(tr, params["stop"])

    full, oos = bt("2016-01-01"), bt("2023-01-01")

    L = ["\n## CONSENSUS BUY (all 3 scanners agree)"]
    if buys.empty:
        L.append("**No consensus today - no trade.** This is the safety rule working.")
    else:
        L.append("| Ticker | Close | Stop-loss | Take-profit | Max hold |\n|---|---|---|---|---|")
        for _, r in buys.iterrows():
            L.append(f"| {r.ticker} | {r.close} | {r.stop_loss} | {r.take_profit} | {params['hold']}d |")
    L.append("\n### Does requiring agreement help? (consensus rule backtest)")
    L.append("| Period | Win | Monthly | Max DD | PF | Trades |\n|---|---|---|---|---|---|")
    for name, st in (("2016-today", full), ("2023-today (out-of-sample)", oos)):
        if st:
            L.append(f"| {name} | {pct(st['win_rate'])} | {pct(st['monthly'])} | {pct(st['max_dd'])} "
                     f"| {st['profit_factor']:.2f} | {st['trades']} |")
        else:
            L.append(f"| {name} | no trades | | | | |")
    L.append("\n### Scanner votes")
    L.append("| Ticker | A Trend | B Momentum | C Volume/Risk | Votes |\n|---|---|---|---|---|")
    for _, r in scan.sort_values("votes", ascending=False).iterrows():
        e = " (earnings soon)" if r.earnings_soon else ""
        L.append(f"| {r.ticker} | {'✅' if r.A_trend else '—'} | {'✅' if r.B_momentum else '—'} "
                 f"| {'✅' if r.C_volume_risk else '—'}{e} | {r.votes}/3 |")
    return "\n".join(L), buys, scan


def _bt_sig(d, p):
    """Same exit logic as tsx_scan.backtest_one, driven by a precomputed signal."""
    from tsx_scan import COST
    o, h, l, c = (d[k].values for k in ("Open", "High", "Low", "Close"))
    sigv, idx, n = d["_sig"].fillna(False).values, d.index, len(d)
    trades, i = [], 0
    while i < n - 1:
        if not sigv[i]:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        stop, target = entry * (1 - p["stop"]), entry * (1 + p["target"])
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
        trades.append((idx[e], idx[j], exit_px / entry - 1 - 2 * COST))
        i = j + 1
    return trades
