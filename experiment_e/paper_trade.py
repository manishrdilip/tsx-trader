"""
Forward paper trading for the FROZEN Experiment E configurations. No real orders are placed.

Rules (same logic as experiment_e.simulate, run forward in time):
  - Sessions: TSX trading calendar (exchange_calendars XTSE), not the data's dates.
  - Signal: last TSX session of each month s, using only data through the close of s.
  - Execution: next TSX session e after s, at the open of e, whole shares, cash-limited, sells before buys.
  - Timing guard: an order executes only once the open of e is published (run time >= open + 5 min
    AND the open price exists in the data). A mark is written only once the close is published
    (run time >= close + 30 min). If not ready, the run stops there and retries on the next run.
    No state advances before the data exists, so a retry cannot duplicate or skip a trade.
  - Costs: frozen cost multiplier x base cost per side.
  - Valuation: daily close with dividends (auto-adjusted prices). Positions missing from the data
    keep their last known price.

Idempotent: state.json stores the last executed signal date and the last marked date.

Outputs (append-only CSVs, one folder per frozen config under paper/accounts/<id>/):
  equity.csv     daily mark: date, equity, cash, positions
  trades.csv     every simulated order: signal date, execution date, ticker, side, shares, price, cash flow
  picks.csv      target weights at each signal: signal date, execution date, rank, ticker, weight
  watchlist.csv  eligible top-N as of the last COMPLETED session (monitoring only)
  state.json     overwritten each run; git history keeps every version
Plus paper/run_log.csv: one line per run, with run time, last completed session and waits.

Research only - not financial advice.
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
import traceback

import exchange_calendars as xc
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
import experiment_e as ee  # noqa: E402  (frozen logic: prepare, select)

FROZEN = os.path.join(HERE, "frozen_configs.json")
XTSE = xc.get_calendar("XTSE")
OPEN_DELAY = pd.Timedelta(minutes=5)     # open price is published shortly after the open
CLOSE_DELAY = pd.Timedelta(minutes=30)   # daily bar is final some time after the close
# Signals strictly after INITIAL_SIGNAL are executed. The first live signal is the Oct 30, 2026 close
# (last TSX session of October), executed at the Nov 2, 2026 open. Marking starts after INITIAL_MARK.
INITIAL_SIGNAL = "2026-10-29"
INITIAL_MARK = "2026-10-30"


def append_csv(path, header, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def append_csv_unique(path, header, rows, key_cols):
    """Append rows whose key (values at key_cols) is not already in the file. Existing rows are never changed."""
    seen = set()
    if os.path.exists(path):
        with open(path, newline="") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                seen.add(tuple(row[c] for c in key_cols))
    fresh, batch = [], set()
    for row in rows:
        key = tuple(str(row[c]) for c in key_cols)
        if key in seen or key in batch:
            continue
        batch.add(key)
        fresh.append(row)
    append_csv(path, header, fresh)
    return len(fresh)


def load_frozen():
    data = json.load(open(FROZEN))
    return data["version"], data["configs"]


def utc(ts):
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def open_known(P, g, now):
    d = P.cal[g]
    if not XTSE.is_session(d):
        return False
    if now < XTSE.session_open(d) + OPEN_DELAY:
        return False
    return bool(np.isfinite(P.O[:, g]).any())


def close_known(P, g, now):
    d = P.cal[g]
    if not XTSE.is_session(d):
        return False
    if now < XTSE.session_close(d) + CLOSE_DELAY:
        return False
    return bool(np.isfinite(P.C[:, g]).any())


def last_completed(P, now):
    for g in range(P.T - 1, -1, -1):
        if close_known(P, g, now):
            return g
    return None


def month_end_sessions(P):
    """Last TSX session of each month, from the calendar, within the panel's date range."""
    lo = max(pd.Timestamp(P.cal[0]), XTSE.first_session)
    hi = min(pd.Timestamp(P.cal[-1]), XTSE.last_session)
    sess = XTSE.sessions_in_range(lo, hi)
    s = pd.Series(sess)
    return list(s.groupby([s.dt.year, s.dt.month]).max())


class Account:
    def __init__(self, root, cfg):
        self.cfg = cfg
        self.dir = os.path.join(root, "paper", "accounts", cfg["id"])
        self.state_path = os.path.join(self.dir, "state.json")
        if os.path.exists(self.state_path):
            self.st = json.load(open(self.state_path))
        else:
            cap = float(cfg["capital"])
            self.st = {"id": cfg["id"], "capital": cap, "cash": cap, "holdings": {}, "last_px": {},
                       "last_signal": INITIAL_SIGNAL, "last_marked": INITIAL_MARK}

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        json.dump(self.st, open(self.state_path, "w"), indent=2)

    # ---- valuation
    def price(self, P, t, g):
        if t in P.index_of:
            x = P.CF[P.index_of[t], g]
            if not np.isnan(x):
                self.st["last_px"][t] = float(x)
                return float(x)
        return float(self.st["last_px"].get(t, 0.0))

    def value(self, P, g):
        return self.st["cash"] + sum(sh * self.price(P, t, g) for t, sh in self.st["holdings"].items())

    # ---- one monthly execution at session g, decided at signal session s (s is the prior month-end)
    def execute(self, P, s, g, fee, log):
        cal = P.cal
        eq_prev = self.value(P, s)
        w = ee.select(P, self.cfg, s)
        if self.cfg["filt"] and not P.reg_up[s]:
            w = np.zeros(P.N)
        sig_d, exe_d = str(cal[s].date()), str(cal[g].date())
        picks = []
        order = np.argsort(-w, kind="stable")
        for rank, i in enumerate([i for i in order if w[i] > 0], start=1):
            picks.append([sig_d, exe_d, rank, P.tick[i], round(float(w[i]), 6)])
        append_csv(os.path.join(self.dir, "picks.csv"),
                   ["signal_date", "exec_date", "rank", "ticker", "weight"], picks)

        target = {P.tick[i]: float(w[i]) for i in np.nonzero(w)[0]}
        tickers = set(self.st["holdings"]) | set(target)
        trades = []
        sells, buys = [], []
        for t in tickers:
            if t not in P.index_of:
                continue                       # cannot trade; keep position at last known price
            i = P.index_of[t]
            o = P.O[i, g]
            if np.isnan(o):
                continue                       # no open for this name; skipped, logged as no-trade
            want = math.floor(eq_prev * target.get(t, 0.0) / (float(o) * (1 + fee)))
            have = self.st["holdings"].get(t, 0)
            diff = want - have
            if diff < 0:
                sells.append((t, -diff, float(o)))
            elif diff > 0:
                buys.append((t, diff, float(o), target.get(t, 0.0)))
        for t, q, o in sorted(sells):
            proceeds = q * o * (1 - fee)
            self.st["cash"] += proceeds
            self.st["holdings"][t] = self.st["holdings"].get(t, 0) - q
            if self.st["holdings"][t] == 0:
                del self.st["holdings"][t]
            trades.append([sig_d, exe_d, t, "sell", q, round(o, 4), round(proceeds, 2)])
        for t, q, o, _ in sorted(buys, key=lambda x: -x[3]):
            affordable = math.floor(self.st["cash"] / (o * (1 + fee)))
            q = min(q, affordable)
            if q <= 0:
                continue
            cost = q * o * (1 + fee)
            self.st["cash"] -= cost
            self.st["holdings"][t] = self.st["holdings"].get(t, 0) + q
            trades.append([sig_d, exe_d, t, "buy", q, round(o, 4), round(-cost, 2)])
        append_csv(os.path.join(self.dir, "trades.csv"),
                   ["signal_date", "exec_date", "ticker", "side", "shares", "price", "cash_flow"], trades)
        self.st["last_signal"] = sig_d
        log["executions"] += 1
        log["trades"] += len(trades)

    def mark(self, P, g):
        eq = self.value(P, g)
        append_csv(os.path.join(self.dir, "equity.csv"),
                   ["date", "equity", "cash", "positions"],
                   [[str(P.cal[g].date()), round(eq, 2), round(self.st["cash"], 2), len(self.st["holdings"])]])
        self.st["last_marked"] = str(P.cal[g].date())
        return eq

    def watchlist(self, P, g_done):
        w = ee.select(P, self.cfg, g_done)
        idx = [i for i in np.argsort(-w, kind="stable") if w[i] > 0]
        rows = [[str(P.cal[g_done].date()), rank, P.tick[i], round(float(w[i]), 6)]
                for rank, i in enumerate(idx, 1)]
        # Idempotent: a row is written only if (as_of, ticker) is not already in the file.
        append_csv_unique(os.path.join(self.dir, "watchlist.csv"), ["as_of", "rank", "ticker", "weight"],
                          rows, key_cols=(0, 2))


def run(panel_path, equity_list, root, now=None):
    version, configs = load_frozen()
    now = utc(now) if now is not None else utc(dt.datetime.now(dt.timezone.utc))
    P = ee.prepare(panel_path, equity_list)
    P.index_of = {t: i for i, t in enumerate(P.tick)}
    cal, T = P.cal, P.T
    done = last_completed(P, now)
    run_log = {"run_utc": now.isoformat(timespec="seconds"), "frozen_version": version,
               "data_last_date": str(cal[-1].date()),
               "last_completed_session": None if done is None else str(cal[done].date()),
               "executions": 0, "trades": 0, "waiting": [], "accounts": [], "errors": []}
    signals = month_end_sessions(P)
    for cfg in configs:
        acct = Account(root, cfg)
        try:
            fee = float(cfg["base_cost"]) * float(cfg["cost_mult"])
            # Signals after last_signal whose close is published; each maps to its next-session execution.
            pending = {}
            for sd in signals:
                if str(sd.date()) <= acct.st["last_signal"]:
                    continue
                si = cal.get_indexer([sd])[0]
                if si < 0 or not close_known(P, si, now):
                    break
                ei = cal.get_indexer([XTSE.next_session(sd)])[0]
                if ei < 0:
                    break
                pending[int(ei)] = int(si)
            start = int(cal.searchsorted(pd.Timestamp(acct.st["last_marked"]), side="right"))
            last_seen = start - 1
            for g in range(start, T):
                if not XTSE.is_session(cal[g]):
                    continue
                if g in pending:
                    if not open_known(P, g, now):
                        run_log["waiting"].append({"id": cfg["id"], "exec_session": str(cal[g].date()),
                                                   "reason": "open not yet published"})
                        break
                    acct.execute(P, pending.pop(g), g, fee, run_log)
                if not close_known(P, g, now):
                    break
                acct.mark(P, g)
                last_seen = g
            stuck = [e for e in pending if e <= last_seen]
            if stuck:
                raise RuntimeError(f"signal pending for executed-past session {[str(cal[e].date()) for e in stuck]}")
            if done is not None:
                acct.watchlist(P, done)
            acct.save()
            end = done if done is not None else last_seen
            run_log["accounts"].append({"id": cfg["id"], "value": round(acct.value(P, end), 2),
                                        "cash": round(acct.st["cash"], 2),
                                        "positions": len(acct.st["holdings"]),
                                        "last_marked": acct.st["last_marked"],
                                        "last_signal": acct.st["last_signal"]})
        except Exception:
            run_log["errors"].append({"id": cfg["id"], "error": traceback.format_exc(limit=3)})
    append_csv(os.path.join(root, "paper", "run_log.csv"),
               ["run_utc", "frozen_version", "data_last_date", "last_completed_session", "executions",
                "trades", "accounts", "waiting", "errors"],
               [[run_log["run_utc"], run_log["frozen_version"], run_log["data_last_date"],
                 run_log["last_completed_session"], run_log["executions"], run_log["trades"],
                 json.dumps(run_log["accounts"]), json.dumps(run_log["waiting"]), json.dumps(run_log["errors"])]])
    print(json.dumps(run_log, indent=2))
    if run_log["errors"]:
        raise SystemExit("one or more accounts failed; see paper/run_log.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--equities", required=True)
    ap.add_argument("--root", default=REPO)
    ap.add_argument("--now", default=None, help="UTC timestamp override, for tests only")
    args = ap.parse_args()
    run(args.panel, args.equities, args.root, args.now)


if __name__ == "__main__":
    main()
