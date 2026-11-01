"""Clean day-by-day engine for the 4/4 TSX system. No look-ahead:
- signal uses data up to the close of day t
- entry fills at the open of day t+1 (plus slippage)
- stop/target checked on each later bar; a gap through the stop fills at the open
- whole shares, max MAX_POS positions, RISK of current equity per trade, everything reinvested
"""
import math
import numpy as np
import pandas as pd

COST = 0.001        # commission per side
SLIP = 0.0005       # slippage per side
MAX_POS, RISK = 4, 0.015
STOP_ATR, TGT_ATR, MAX_STOP, HOLD = 3.0, 6.0, 0.08, 20
BENCH = "XIU.TO"


def indicators(d):
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
    d["atr14"] = tr.rolling(14).mean()
    d["atr_pct"] = d["atr14"] / c
    d["ret63"] = c.pct_change(63)
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()
    d["vol20"] = d["Volume"].rolling(20).mean()
    return d


def load_tsx(path):
    raw = pd.read_parquet(path, columns=["Date", "Open", "High", "Low", "Close", "Volume", "ticker"])
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["ticker"] = raw["ticker"].astype(str)
    raw = raw.drop_duplicates(["ticker", "Date"])
    bench = raw[raw.ticker == BENCH].set_index("Date").sort_index()
    names = raw[raw.ticker.str.endswith((".TO", ".V")) & ~raw.ticker.isin([BENCH, "XIC.TO"])]
    bars = {}
    for t, g in names.groupby("ticker"):
        g = g.set_index("Date").sort_index()
        if len(g) >= 260:
            bars[t] = indicators(g)
    return bars, bench


def signals(bars, bench, index_filter):
    b = bench.assign(sma200=bench.Close.rolling(200).mean())
    m_up = (b.Close > b.sma200)
    m_ret = b.Close.pct_change(63)
    out = {}
    for t, d in bars.items():
        up = m_up.reindex(d.index).fillna(False) if index_filter else True
        a = (d.Close > d.sma50) & (d.sma50 > d.sma200) & up
        bb = d.rsi14.between(50, 70) & (d.macd > d.macd_sig) & (d.ret63 > m_ret.reindex(d.index))
        c = (d.Volume > d.vol20) & (d.atr_pct < 0.03)
        out[t] = (a & bb & c).fillna(False)
    return out


def simulate(bars, sig, start, end, cash0=5000.0):
    dates = sorted(set().union(*[set(d.index) for d in bars.values()]))
    dates = [x for x in dates if start <= x <= end]
    cash, pos, pend, trades, eq = cash0, {}, [], [], []
    for today in dates:
        for t in list(pos):
            p = pos[t]
            if today not in bars[t].index:
                continue
            r = bars[t].loc[today]
            p["days"] += 1
            px = None
            if r.Open <= p["stop"]:
                px, why = r.Open, "stop_gap"
            elif r.Low <= p["stop"]:
                px, why = p["stop"], "stop"
            elif r.High >= p["target"]:
                px, why = p["target"], "target"
            elif p["days"] >= HOLD:
                px, why = r.Close, "time"
            if px is not None:
                proceeds = px * (1 - SLIP) * p["sh"] * (1 - COST)
                cash += proceeds
                trades.append({"t": t, "entry": p["d0"], "exit": today, "pnl": proceeds - p["cost"], "why": why})
                del pos[t]
        for t in pend:
            if t in pos or len(pos) >= MAX_POS or today not in bars[t].index or pd.isna(bars[t].loc[today].Open):
                continue
            sd = prev[t]
            atr = bars[t].at[sd, "atr14"]
            entry = float(bars[t].loc[today].Open) * (1 + SLIP)
            if not atr > 0:
                continue
            stop = max(entry - STOP_ATR * atr, entry * (1 - MAX_STOP))
            tgt = entry + TGT_ATR * atr
            per = entry - stop
            if per <= 0:
                continue
            equity_now = cash + sum(p["sh"] * float(bars[k].loc[today].Close) for k, p in pos.items() if today in bars[k].index)
            sh = int(min(RISK * equity_now / per, (equity_now / MAX_POS) / entry))
            cost = sh * entry * (1 + COST)
            if sh < 1 or cost > cash:
                continue
            cash -= cost
            pos[t] = {"sh": sh, "stop": stop, "target": tgt, "days": 0, "d0": today, "cost": cost}
        pend, prev = [], {}
        for t, s in sig.items():
            if today in s.index and bool(s.loc[today]):
                pend.append(t)
                prev[t] = today
        mtm = sum(p["sh"] * float(bars[k].loc[today].Close) for k, p in pos.items() if today in bars[k].index)
        eq.append((today, cash + mtm))
    return pd.Series(dict(eq), dtype=float), pd.DataFrame(trades)


def metrics(eq, trades, bench, start, end):
    e = eq[(eq.index >= start) & (eq.index <= end)]
    if len(e) < 2:
        return {}
    b = bench[(bench.index >= e.index[0]) & (bench.index <= e.index[-1])].Close
    years = (e.index[-1] - e.index[0]).days / 365.25
    tot = e.iloc[-1] / e.iloc[0] - 1
    dd = ((e - e.cummax()) / e.cummax()).min()
    yearly = e.groupby(e.index.year).apply(lambda s: s.iloc[-1] / s.iloc[0] - 1)
    tr = trades[(trades.exit >= e.index[0]) & (trades.exit <= e.index[-1])] if len(trades) else trades
    return {
        "start": str(e.index[0].date()), "end": str(e.index[-1].date()),
        "final": round(float(e.iloc[-1]), 2), "return_pct": round(100 * tot, 2),
        "cagr_pct": round(100 * ((1 + tot) ** (1 / years) - 1), 2) if years > 0 else None,
        "max_dd_pct": round(100 * dd, 2),
        "bench_return_pct": round(100 * (float(b.iloc[-1]) / float(b.iloc[0]) - 1), 2),
        "trades": int(len(tr)), "win_pct": round(100 * float((tr.pnl > 0).mean()), 1) if len(tr) else None,
        "years_positive_pct": round(100 * float((yearly > 0).mean()), 1),
        "yearly_pct": {int(k): round(100 * float(v), 1) for k, v in yearly.items()},
    }
