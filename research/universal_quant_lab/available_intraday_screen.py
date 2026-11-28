"""Bounded cross-symbol, real-data intraday development screen."""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
from time import perf_counter, sleep

import exchange_calendars as xc
from numba import njit
import numpy as np
import pandas as pd

from campaign_watchdog import guard, health
from eodhd import atomic_json
from eodhd_intraday import STORAGE
from profit_admission import cpu_guard
from run_universe import read


START, SPLIT, END = "2023-01-01", "2024-01-01", "2024-11-27"
CAPITAL, FRICTION, FEE = 5000., .003, 1.
FAMILIES = ("rsi_reclaim_5_30", "rsi_reclaim_14_35", "rsi5_reclaim_with_ema_trend",
            "rsi14_reclaim_with_macd", "range_breakout_12", "range_breakout_24",
            "range_breakout_with_ema_trend", "range_breakout_with_macd",
            "ema_crossover_8_21", "ema_crossover_with_macd")
EXITS = ((1., 1., 6), (1.5, 1., 12), (2., 1., 18), (2., 1.5, 24))
CANDIDATES = list(product(range(len(FAMILIES)), EXITS))
PACK = ("open", "high", "low", "close")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check(root):
    while guard(health(root)) or cpu_guard(root, 85) == "cpu_temperature":
        sleep(20)


def freeze(root, out, limit, interval, cohort):
    ledger = read(root / "checkpoints/capped-sequence/intraday.json")
    scanned = ([(symbol, ledger[symbol]) for symbol in cohort] if cohort is not None
               else list(ledger.items())[:limit])
    selection = {}
    for symbol, status in scanned:
        if status != "checked" or not symbol.endswith(".US"):
            selection[symbol] = []
            continue
        folder = root / STORAGE / "market=US" / f"symbol={symbol}" / f"interval={interval}"
        windows = []
        for path in sorted(folder.glob("*.json")):
            record = read(path)
            if (record["status"] == "saved" and record["from_utc"] < END
                    and record["until_utc_exclusive"] > START):
                windows.append([path.with_suffix(".parquet").relative_to(root).as_posix(), record["sha256"]])
        selection[symbol] = windows
    plan = {"created_utc": now(), "status": "development_only", "official_v2": False,
            "code_sha256": digest(Path(__file__)), "interval": interval, "first_inclusive": START,
            "validation_start": SPLIT, "end_exclusive": END,
            "minimum_complete_sessions_each_split": 35,
            "execution": {"starting_sleeve_usd": CAPITAL, "friction_per_side": FRICTION,
                          "fee_per_fill": FEE, "prior_8_bar_min_turnover_fraction": .001,
                          "fill": "Next bar open. Worse open on a stop gap; stop first on dual hits.",
                          "expiry": "No overnight positions. Remaining holding exits by final bar open."},
            "rules": FAMILIES, "exits": EXITS, "source_windows": selection}
    atomic_json(out / "plan.json", plan)
    return plan


def frame(root, windows, sessions):
    parts = []
    for name, expected in windows:
        path = root / name
        if digest(path) != expected:
            raise RuntimeError(f"Input window changed: {path.name}")
        parts.append(pd.read_parquet(path, columns=["timestamp", "session", *PACK, "volume"]))
    if not parts:
        return None
    bars = pd.concat(parts, ignore_index=True).sort_values("timestamp")
    bars = bars[(bars.session >= START) & (bars.session < END)]
    if bars.timestamp.duplicated().any():
        raise ValueError("Overlapping input windows")
    complete = []
    for session, block in bars.groupby("session", sort=True):
        if session not in sessions:
            continue
        opening, closing, expected = sessions[session]
        active = block[(block.timestamp >= opening) & (block.timestamp < closing)]
        if pd.DatetimeIndex(active.timestamp).equals(expected):
            complete.append(active)
    return pd.concat(complete, ignore_index=True) if complete else None


def signal_arrays(bars):
    c, h, l = (bars[field] for field in ("close", "high", "low"))
    group = bars.session
    last = c.groupby(group).shift(1)
    change = c-last
    tr = pd.concat([h-l, (h-last).abs(), (l-last).abs()], axis=1).max(axis=1)
    def rolling(values, n, operation):
        return values.groupby(group).transform(lambda x: getattr(x.rolling(n), operation)())
    def ema(values, n):
        return values.groupby(group).transform(lambda x: x.ewm(span=n, adjust=False, min_periods=n).mean())
    def reclaim_rsi(n, level):
        up = rolling(change.clip(lower=0), n, "mean")
        down = rolling(-change.clip(upper=0), n, "mean")
        value = 100*up/(up+down).replace(0, np.nan)
        return value.gt(level) & value.groupby(group).shift().le(level)
    fast, slow = ema(c, 8), ema(c, 21)
    trend = fast.gt(slow)
    diff = ema(c, 12) - ema(c, 26)
    macd = diff.gt(ema(diff, 9))
    rsi5, rsi14 = reclaim_rsi(5, 30), reclaim_rsi(14, 35)
    b12 = c.gt(rolling(h.groupby(group).shift(), 12, "max"))
    b24 = c.gt(rolling(h.groupby(group).shift(), 24, "max"))
    cross = trend & fast.groupby(group).shift().le(slow.groupby(group).shift())
    liquid = rolling((bars.volume*c).where(bars.volume.gt(0)), 8, "min").fillna(0) * .001
    return np.column_stack((rsi5,rsi14,rsi5&trend,rsi14&macd,b12,b24,b12&trend,b24&macd,cross,cross&macd)), rolling(tr, 8, "mean").to_numpy(), liquid.to_numpy()


@njit
def simulate(prices, end_bar, signal, atr, cap, take, stop, hold, first, last):
    cash, quantity, entry_cash = CAPITAL, 0., 0.
    target, floor, filled, buys, tied = 0., 0., 0, 0, 0
    peak, drawdown, holding_total, wins = CAPITAL, 0., 0, 0
    for i in range(first, last):
        current_open, high, low, close = prices[i]
        if quantity == 0 and i > first and not end_bar[i-1] and not end_bar[i] and signal[i-1]:
            loss = atr[i-1]
            notional = min(max(0., cash-FEE), cap[i-1])
            if np.isfinite(loss) and loss > 0 and notional >= 100:
                entry_cash = cash
                quantity = np.floor(notional / (current_open * (1 + FRICTION)))
                if quantity > 0:
                    cash -= quantity*current_open*(1+FRICTION)+FEE
                    floor, target = current_open - stop*loss, current_open + take*loss
                    filled = i
                    buys += 1
        if quantity > 0:
            exit_price = 0.
            if end_bar[i] or i-filled >= hold:
                exit_price = current_open
            elif current_open <= floor:
                exit_price = current_open
            elif current_open >= target:
                exit_price = target
            elif low <= floor:
                exit_price = max(floor, .01)
                tied += int(high >= target)
            elif high >= target:
                exit_price = target
            if exit_price > 0:
                cash += quantity*exit_price*(1-FRICTION)-FEE
                wins += int(cash > entry_cash)
                holding_total += i-filled+1
                quantity = 0.
        equity = cash if quantity == 0 else cash + quantity*close*(1-FRICTION)-FEE
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak-equity)/peak)
    return cash/CAPITAL-1, drawdown, buys, holding_total, tied, wins


def calendar(interval):
    cal = xc.get_calendar("XNYS", start=START, end=END)
    days = {}
    for sess in cal.sessions:
        opening, closing = cal.session_open(sess), cal.session_close(sess)
        days[sess.date().isoformat()] = (opening, closing,
            pd.date_range(opening, closing, freq=f"{interval[:-1]}min", inclusive="left"))
    return days


def run(root, out, limit, interval="5m", cohort=None):
    out.mkdir(parents=True, exist_ok=True)
    plan = read(out / "plan.json") if (out / "plan.json").exists() else freeze(root, out, limit, interval, cohort)
    if plan["code_sha256"] != digest(Path(__file__)) or plan["interval"] != interval:
        raise ValueError("Run code changed")
    result_path = out / "progress.json"
    prior = read(result_path) if result_path.exists() else {"symbols": {}, "excluded": {}}
    admitted, excluded = prior["symbols"], prior["excluded"]
    days, start_time = calendar(interval), perf_counter()
    for symbol, windows in plan["source_windows"].items():
        if symbol in admitted or symbol in excluded:
            continue
        check(root)
        bars = frame(root, windows, days)
        if bars is None:
            excluded[symbol] = "No complete regular sessions with saved bars"
        else:
            counts = bars.groupby(bars.session >= SPLIT).session.nunique()
            if len(counts) != 2 or counts.min() < 35:
                excluded[symbol] = {"reason": "Insufficient complete sessions", "train": int(counts.get(False,0)),
                                    "validation": int(counts.get(True,0))}
            else:
                signal, atr, cap = signal_arrays(bars)
                prices = np.ascontiguousarray(bars[list(PACK)].to_numpy())
                endings = (bars.session != bars.session.shift(-1)).to_numpy()
                boundary = int(bars.session.searchsorted(SPLIT))
                scores = [list(simulate(prices,endings,signal[:,idx],atr,cap,*exit_,first,last))
                          for idx, exit_ in CANDIDATES for first,last in ((0,boundary),(boundary,len(bars)))]
                admitted[symbol] = {"train_sessions": int(counts[False]),"validation_sessions": int(counts[True]),
                                    "scores": scores}
        atomic_json(result_path, {"state": "running", "symbols": admitted, "excluded": excluded,
                                  "official_v2_evaluations": 0, "updated_utc": now()})
    if not admitted:
        raise RuntimeError("No symbols met the registered data minimum")
    combined = np.asarray([item["scores"] for item in admitted.values()]).reshape(len(admitted),len(CANDIDATES),2,6)
    rows = []
    for i, (rule, exit_) in enumerate(CANDIDATES):
        details = {}
        for j, name in enumerate(("train","validation")):
            values = combined[:,i,j,:]
            trades = int(values[:,2].sum())
            details[name] = {"equal_weight_net_return": float(values[:,0].mean()),
                             "median_sleeve_drawdown": float(np.median(values[:,1])),
                             "worst_sleeve_drawdown": float(values[:,1].max()),
                             "profitable_symbols": int((values[:,0]>0).sum()),
                             "trades": trades,
                             "mean_hold_minutes": float(values[:,3].sum()*int(interval[:-1])/trades) if trades else None,
                             "win_rate": float(values[:,5].sum()/trades) if trades else None}
        rows.append({"rule": FAMILIES[rule], "atr_tp_sl_max_hold_bars": exit_, **details})
    rows.sort(key=lambda r: (-r["train"]["equal_weight_net_return"],r["rule"],r["atr_tp_sl_max_hold_bars"]))
    report = {"status":"complete","stage":"provisional_development","official_v2_evaluations":0,
              "interval":interval,"cross_symbol_candidates":len(rows), "symbol_candidate_replays":len(rows)*len(admitted),
              "eligible_symbols":list(admitted),"excluded_symbols":excluded,"plan_sha256":digest(out/"plan.json"),
              "elapsed_seconds_this_process":perf_counter()-start_time,"train_ranked_results":rows,
              "limitations":["Equal USD capital per symbol sleeve with no cross-symbol competition.",
                             "Coverage-selected cohort; validation is previously available data, not a forward holdout.",
                             "No formal multiple-testing or buy-and-hold comparison in this bounded screen."]}
    atomic_json(out/"report.json",report)
    atomic_json(result_path, {"state":"complete","symbols":admitted,"excluded":excluded,
                              "official_v2_evaluations":0,"updated_utc":now()})
    print(json.dumps({"tested":len(rows),"symbols":len(admitted),"first":rows[0]}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--limit",type=int,default=57)
    parser.add_argument("--interval",choices=("1m","5m"),default="5m")
    args=parser.parse_args()
    run(args.root,args.out,args.limit,args.interval)
