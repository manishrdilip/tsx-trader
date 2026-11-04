"""Fixed-slot portfolio accounting for a list of backtest trades.

Why this exists: the old stats() in the tsx_scan*.py scripts compounded every
trade one after another in exit order, even when trades overlapped in time.
That treats each signal as if the WHOLE account were available to it, i.e.
unlimited leverage, which inflates both returns and drawdowns.

This module replays the trades as a real account would:
  * trades are taken in entry-date order;
  * at most MAX_POSITIONS are open at once; extra signals are skipped;
  * each trade gets  min(equity * risk / stop_fraction, equity / MAX_POSITIONS,
    free cash)  -- the same "risk 2% to the stop" sizing, capped by the slot size;
  * on the trade's exit date its cash comes back with its return.

Limitation: trades carry only an entry date, exit date and total return, so an
open position is held at cost until it closes. Drawdown is therefore measured
at entry/exit events and can understate losses inside a trade.
"""
import os

import numpy as np
import pandas as pd

MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "10"))


def slot_equity(t, risk, max_positions=None, start=1.0):
    """t: DataFrame with columns entry, exit, ret, sf.
    Returns (equity Series indexed by event date, boolean mask of trades taken)."""
    max_positions = max_positions or MAX_POSITIONS
    t = t.sort_values(["entry", "exit"]).reset_index(drop=True)
    cash, open_pos = float(start), []          # open_pos: list of (exit_date, alloc, ret)
    taken = np.zeros(len(t), dtype=bool)
    points = [(t["entry"].min(), cash)]

    def close_until(day):
        nonlocal cash, open_pos
        due = sorted([p for p in open_pos if p[0] <= day], key=lambda p: p[0])
        for ex, alloc, r in due:
            cash += alloc * (1 + r)
            open_pos.remove((ex, alloc, r))
            points.append((ex, cash + sum(a for _, a, _ in open_pos)))

    for i, row in t.iterrows():
        close_until(row["entry"])
        if len(open_pos) >= max_positions:
            continue
        equity = cash + sum(a for _, a, _ in open_pos)
        sf = row["sf"] if row["sf"] and row["sf"] > 0 else np.inf
        alloc = min(equity * risk / sf, equity / max_positions, cash)
        if alloc <= 0:
            continue
        cash -= alloc
        open_pos.append((row["exit"], alloc, row["ret"]))
        taken[i] = True
    close_until(pd.Timestamp.max)
    eq = pd.Series([v for _, v in points], index=[d for d, _ in points]).groupby(level=0).last()
    return eq, pd.Series(taken, index=t.index), t


def summary(trades, risk, max_positions=None):
    """Drop-in replacement for the old stats() body. Same keys, plus 'skipped'."""
    if not trades:
        return None
    t = pd.DataFrame(trades, columns=["entry", "exit", "ret", "sf"])
    t["entry"], t["exit"] = pd.to_datetime(t["entry"]), pd.to_datetime(t["exit"])
    eq, taken, t = slot_equity(t, risk, max_positions)
    used = t[taken.values]
    if used.empty:
        return None
    dd = (eq / eq.cummax() - 1).min()
    months = max(1.0, (t["exit"].max() - t["entry"].min()).days / 30.44)
    monthly = eq.iloc[-1] ** (1 / months) - 1
    wins = used["ret"] > 0
    gross_win = used.loc[wins, "ret"].sum()
    gross_loss = -used.loc[~wins, "ret"].sum()
    return {
        "trades": int(len(used)),
        "skipped": int(len(t) - len(used)),
        "win_rate": float(wins.mean()),
        "avg_trade": float(used["ret"].mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "monthly": float(monthly),
        "max_dd": float(-dd),
        "total": float(eq.iloc[-1] - 1),
    }
