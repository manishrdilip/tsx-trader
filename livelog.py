"""Forward-test ("paper trade") log for the Leader Pullback picks.
Every day's picks are appended to results/live_log.csv; each later run fills in what
actually happened using the same rules as the backtest (next-open entry, stop, target, 30-day exit).
This is the honest scorecard: it only contains trades chosen BEFORE the outcome was known."""
import os

import numpy as np
import pandas as pd

LOG = "results/live_log.csv"
COLS = ["signal_date", "ticker", "close", "buy_max", "stop_pct", "target_pct", "status",
        "entry_date", "entry", "exit_date", "exit", "ret"]


def _load():
    if os.path.exists(LOG):
        log = pd.read_csv(LOG, dtype=str, keep_default_na=False)
    else:
        log = pd.DataFrame(columns=COLS)
    for c in ("close", "buy_max", "stop_pct", "target_pct", "entry", "exit", "ret"):
        log[c] = pd.to_numeric(log[c], errors="coerce")
    return log.astype(object)


def add(picks, asof):
    log = _load()
    new = []
    for _, r in picks.iterrows():
        if ((log["signal_date"] == str(asof)) & (log["ticker"] == r.ticker)).any():
            continue
        new.append({"signal_date": str(asof), "ticker": r.ticker, "close": r.close, "buy_max": r.buy_max,
                    "stop_pct": round(float(r.stop_pct), 5), "target_pct": round(float(r.target_pct), 5),
                    "status": "pending"})
    if new:
        log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    log.to_csv(LOG, index=False)


def update(data, hold=30, cost=0.001):
    log = _load()
    for i, r in log.iterrows():
        if r.status in ("closed", "skipped") or r.ticker not in data:
            continue
        d = data[r.ticker]
        d = d[d.index > pd.Timestamp(r.signal_date)]
        if d.empty:
            continue
        e = d.iloc[0]
        if e["Open"] > float(r.buy_max):
            log.loc[i, ["status", "entry_date"]] = ["skipped", str(d.index[0].date())]
            continue
        entry = float(e["Open"])
        stop, tgt = entry * (1 - float(r.stop_pct)), entry * (1 + float(r.target_pct))
        log.loc[i, ["entry_date", "entry"]] = [str(d.index[0].date()), round(entry, 4)]
        status, px, xd = "open", float(d["Close"].iloc[-1]), d.index[-1]
        for k, (dt, b) in enumerate(d.iloc[:hold].iterrows()):
            if k > 0 and b["Open"] <= stop:
                status, px, xd = "closed", float(b["Open"]), dt; break
            if b["Low"] <= stop:
                status, px, xd = "closed", stop, dt; break
            if k > 0 and b["Open"] >= tgt:
                status, px, xd = "closed", float(b["Open"]), dt; break
            if b["High"] >= tgt:
                status, px, xd = "closed", tgt, dt; break
            if k == hold - 1:
                status, px, xd = "closed", float(b["Close"]), dt
        log.loc[i, ["status", "exit_date", "exit", "ret"]] = [status, str(xd.date()), round(px, 4),
                                                              round(px / entry - 1 - 2 * cost, 5)]
    log.to_csv(LOG, index=False)
    return log


def summary(log=None):
    log = _load() if log is None else log
    L = ["\n## Live paper-trade scorecard (picks logged before the outcome was known)"]
    if log.empty:
        L.append("No picks logged yet - this fills in automatically as the scanner runs.")
        return "\n".join(L)
    closed = log[log.status == "closed"].copy()
    openp = log[log.status == "open"]
    if len(closed):
        r = closed["ret"].astype(float)
        L.append(f"Closed trades: **{len(closed)}** · win rate **{(r > 0).mean():.0%}** · "
                 f"avg {r.mean():+.2%} per trade · best {r.max():+.1%} · worst {r.min():+.1%}")
    else:
        L.append("No closed trades yet.")
    L.append(f"Open: {len(openp)} · waiting for entry: {(log.status == 'pending').sum()} · "
             f"skipped (opened above buy max): {(log.status == 'skipped').sum()}")
    if len(openp):
        L.append("| Ticker | Signal | Entry | Last | Unrealized |\n|---|---|---|---|---|")
        for _, x in openp.iterrows():
            L.append(f"| {x.ticker} | {x.signal_date} | {x.entry} | {x.exit} | {float(x.ret):+.1%} |")
    if len(closed) < 30:
        L.append("_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; "
                 "expect long losing streaks along the way._")
    return "\n".join(L)
