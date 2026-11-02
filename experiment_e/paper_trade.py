"""
Forward paper trading for the FROZEN Experiment E configurations. No real orders are placed.

Rules (same logic as experiment_e.simulate, run forward in time):
  - Signal: last trading day of each month s, using only data up to the close of s.
  - Execution: next trading day's open (s+1), whole shares, cash-limited, sells before buys.
  - Costs: frozen cost multiplier x 0.10% per side.
  - Valuation: daily close with dividends (auto-adjusted prices). Positions missing from the data
    keep their last known price.

Idempotent: state.json stores the last executed signal date and the last marked date.
A run only processes days after those dates, so re-running on the same data changes nothing.

Outputs (append-only CSVs, one folder per frozen config under paper/accounts/<id>/):
  equity.csv     daily mark: date, equity, cash, positions
  trades.csv     every simulated order: signal date, execution date, ticker, side, shares, price, cash flow
  picks.csv      target weights at each signal: signal date, execution date, rank, ticker, weight
  watchlist.csv  current eligible top-N as of the latest close (monitoring only)
  state.json     overwritten each run; git history keeps every version
Plus paper/run_log.csv: one line per run.

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

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
import experiment_e as ee  # noqa: E402  (frozen logic: prepare, select)

FROZEN = os.path.join(HERE, "frozen_configs.json")
# Signals strictly after INITIAL_SIGNAL are executed. The first live signal is the Oct 30, 2026 close
# (last trading day of October), executed at the Nov 2, 2026 open. INITIAL_MARK: marking starts the day after it.
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


def load_frozen():
    data = json.load(open(FROZEN))
    return data["version"], data["configs"]


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

    # ---- one monthly execution at day g (signal day s = g-1)
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
                continue
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

    def watchlist(self, P):
        s = P.T - 1
        w = ee.select(P, self.cfg, s)
        idx = [i for i in np.argsort(-w, kind="stable") if w[i] > 0]
        rows = [[str(P.cal[s].date()), rank, P.tick[i], round(float(w[i]), 6)] for rank, i in enumerate(idx, 1)]
        append_csv(os.path.join(self.dir, "watchlist.csv"), ["as_of", "rank", "ticker", "weight"], rows)


def run(panel_path, equity_list, root):
    version, configs = load_frozen()
    P = ee.prepare(panel_path, equity_list)
    P.index_of = {t: i for i, t in enumerate(P.tick)}
    cal, T = P.cal, P.T
    run_log = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "frozen_version": version, "data_last_date": str(cal[-1].date()),
               "executions": 0, "trades": 0, "accounts": [], "errors": []}
    for cfg in configs:
        acct = Account(root, cfg)
        try:
            fee = float(cfg["base_cost"]) * float(cfg["cost_mult"])
            exec_for = {}
            for s in P.month_end:
                if str(cal[s].date()) > acct.st["last_signal"] and s + 1 <= T - 1:
                    exec_for[s + 1] = s
            start = cal.searchsorted(pd.Timestamp(acct.st["last_marked"]), side="right")
            for g in range(int(start), T):
                if g in exec_for:
                    acct.execute(P, exec_for[g], g, fee, run_log)
                acct.mark(P, g)
            acct.watchlist(P)
            acct.save()
            run_log["accounts"].append({"id": cfg["id"], "value": round(acct.value(P, T - 1), 2),
                                        "cash": round(acct.st["cash"], 2),
                                        "positions": len(acct.st["holdings"])})
        except Exception:
            run_log["errors"].append({"id": cfg["id"], "error": traceback.format_exc(limit=3)})
    append_csv(os.path.join(root, "paper", "run_log.csv"),
               ["run_utc", "frozen_version", "data_last_date", "executions", "trades", "accounts", "errors"],
               [[run_log["run_utc"], run_log["frozen_version"], run_log["data_last_date"], run_log["executions"],
                 run_log["trades"], json.dumps(run_log["accounts"]), json.dumps(run_log["errors"])]])
    print(json.dumps(run_log, indent=2))
    if run_log["errors"]:
        raise SystemExit("one or more accounts failed; see paper/run_log.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--equities", required=True)
    ap.add_argument("--root", default=REPO)
    args = ap.parse_args()
    run(args.panel, args.equities, args.root)


if __name__ == "__main__":
    main()
