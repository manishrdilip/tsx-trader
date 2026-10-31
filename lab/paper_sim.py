"""Day-by-day paper trading of the 4/4 TSX consensus system, Oct 2025 - Oct 2026.
Start $5,000 CAD. Each day: manage open positions with that day's prices, then
enter yesterday's 4/4 signals at today's open. Costs 0.1% per side.
Rules copied from consensus.py (A trend, B momentum, C volume/risk, D candle)
and risk_levels.py (stop 3xATR, target 6xATR, max stop 8%).
Gap-chase, earnings and live-only checks are not replayed (no history for them).
Writes {OUT}/paper_sim_daily.csv, {OUT}/paper_sim_trades.csv, {OUT}/paper_sim_summary.txt
"""
import os, sys, math
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import candles  # noqa: E402

START = pd.Timestamp(os.environ.get("SIM_START", "2016-10-31"))
END = pd.Timestamp(os.environ.get("SIM_END", "2026-10-30"))
OUT = os.environ.get("SIM_OUT", "results")
CASH0, MAX_POS, RISK, COST = 5000.0, 4, 0.015, 0.001
STOP_ATR, TGT_ATR, MAX_STOP, HOLD = 3.0, 6.0, 0.08, 20


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
    d["atr14"] = tr.rolling(14).mean()
    d["atr_pct"] = d["atr14"] / c
    d["ret63"] = c.pct_change(63)
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()
    d["vol20"] = d["Volume"].rolling(20).mean()
    return d


def main(path=os.environ.get("PRICES", "lab/data/prices.parquet")):
    raw = pd.read_parquet(path)
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["ticker"] = raw["ticker"].astype(str)
    mkt_raw = raw[raw.ticker == "XIU.TO"].drop_duplicates("Date").set_index("Date").sort_index()
    mkt = mkt_raw.assign(sma200=mkt_raw.Close.rolling(200).mean())
    tsx = raw[raw.ticker.str.endswith((".TO", ".V")) & (raw.ticker != "XIU.TO") & (raw.ticker != "XIC.TO")]
    data = {}
    for t, g in tsx.groupby("ticker"):
        g = g.drop_duplicates("Date").set_index("Date").sort_index()
        if len(g) < 260:
            continue
        data[t] = add_extra(g)
    print(f"TSX tickers with enough history: {len(data)}", flush=True)

    m_up = (mkt["Close"] > mkt["sma200"])
    m_ret = mkt["Close"].pct_change(63)

    sig, bars = {}, {}
    for t, d in data.items():
        a = (d.Close > d.sma50) & (d.sma50 > d.sma200) & m_up.reindex(d.index).fillna(False)
        b = d.rsi14.between(50, 70) & (d.macd > d.macd_sig) & (d.ret63 > m_ret.reindex(d.index))
        c = (d.Volume > d.vol20) & (d.atr_pct < 0.03)
        dd = candles.signal(d)
        sig[t] = (a & b & c & dd.reindex(d.index).fillna(False)).fillna(False)
        bars[t] = d

    dates = sorted(set().union(*[set(d.index) for d in bars.values()]))
    dates = [x for x in dates if START <= x <= END]
    cash, equity = CASH0, CASH0
    positions = {}   # ticker -> dict
    pending = []     # signals from prior close, to enter at today's open
    prev_day = {}
    trades, daily = [], []

    for today in dates:
        # 1) manage open positions on today's bar
        for t in list(positions):
            p = positions[t]
            if today not in bars[t].index:
                continue
            r = bars[t].loc[today]
            p["days"] += 1
            exit_px, why = None, None
            if r.Open <= p["stop"]:
                exit_px, why = r.Open, "stop (gap)"
            elif r.Low <= p["stop"]:
                exit_px, why = p["stop"], "stop"
            elif r.High >= p["target"]:
                exit_px, why = p["target"], "target"
            elif p["days"] >= HOLD:
                exit_px, why = r.Close, "time"
            if exit_px is not None:
                proceeds = exit_px * p["shares"] * (1 - COST)
                cash += proceeds
                trades.append({"ticker": t, "entry_date": p["entry_date"].date(), "entry": round(p["entry"], 4),
                               "exit_date": today.date(), "exit": round(exit_px, 4), "shares": p["shares"],
                               "pnl_cad": round(proceeds - p["cost"], 2),
                               "ret_pct": round(100 * (exit_px / p["entry"] - 1), 2), "reason": why})
                del positions[t]

        # 2) enter yesterday's signals at today's open
        for t in pending:
            if t in positions or len(positions) >= MAX_POS or today not in bars[t].index:
                continue
            r = bars[t].loc[today]
            entry = float(r.Open)
            atr = float(bars[t].at[prev_day[t], "atr14"]) if prev_day.get(t) in bars[t].index else float("nan")
            if not (atr > 0) or math.isnan(entry):
                continue
            stop = max(entry - STOP_ATR * atr, entry * (1 - MAX_STOP))
            target = entry + TGT_ATR * atr
            risk_per_sh = entry - stop
            if risk_per_sh <= 0:
                continue
            equity_now = cash + sum(p["shares"] * float(bars[k].loc[today].Close)
                                    for k, p in positions.items() if today in bars[k].index)
            shares = int(min(RISK * equity_now / risk_per_sh, (equity_now / MAX_POS) / entry))
            cost = shares * entry * (1 + COST)
            if shares < 1 or cost > cash:
                continue
            cash -= cost
            positions[t] = {"entry": entry, "stop": stop, "target": target, "shares": shares,
                            "entry_date": today, "days": 0, "cost": cost}
        pending = []
        prev_day = {}

        # 3) collect today's signals to enter tomorrow
        for t, s in sig.items():
            if today in s.index and bool(s.loc[today]):
                pending.append(t)
                prev_day[t] = today

        # 4) mark to market at close
        mtm = sum(p["shares"] * float(bars[k].loc[today].Close) for k, p in positions.items() if today in bars[k].index)
        equity = cash + mtm
        daily.append({"date": today.date(), "cash": round(cash, 2), "open_positions": len(positions),
                      "equity": round(equity, 2)})

    dfd = pd.DataFrame(daily)
    dft = pd.DataFrame(trades)
    os.makedirs(OUT, exist_ok=True)
    dfd.to_csv(f"{OUT}/paper_sim_daily.csv", index=False)
    dft.to_csv(f"{OUT}/paper_sim_trades.csv", index=False)

    peak = dfd.equity.cummax()
    mdd = ((dfd.equity - peak) / peak).min() * 100
    wins = (dft.pnl_cad > 0).sum() if len(dft) else 0
    lines = [
        f"Start $5,000 CAD, {START.date()} to {END.date()}",
        f"Final equity: ${dfd.equity.iloc[-1]:,.2f}  ({100*(dfd.equity.iloc[-1]/CASH0-1):+.2f}%)",
        f"Max drawdown: {mdd:.2f}%",
        f"Trades: {len(dft)}  winners: {wins}  win rate: {100*wins/len(dft) if len(dft) else 0:.1f}%",
        f"Open at end: {len(positions)} positions, value ${sum(p['shares']*float(bars[k].loc[dates[-1]].Close) for k,p in positions.items()):,.2f}",
    ]
    open(f"{OUT}/paper_sim_summary.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
