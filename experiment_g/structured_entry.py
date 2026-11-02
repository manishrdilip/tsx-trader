"""Experiment G simulator: single entry vs structured three-leg entry on daily bars.
Rules are in PREREGISTERED.md. Research only. Not financial advice.
Reuses indicators and cost functions from experiment_f_short/fshort.py so the costs match F-short exactly."""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "experiment_f_short"))
import fshort as fs  # noqa: E402

CAPITAL = fs.CAPITAL
RISK_FRAC = 0.005
MAX_GROUPS = 3
MAX_POS_FRAC = 1 / 3
PARTICIPATION = 0.01
GAP_CAP = 0.01
SWING = 10
STOP_BUF_ATR = 0.1
LEG_WINDOW = 3          # sessions a limit leg stays live after the entry session
TIME_SESSIONS = 20      # time exit at the close of s + 20
MAX_PENDING_DAYS = 10
DELIST_RECOVERY = 0.5
PERIODS = fs.PERIODS
VARIANTS = {
    "B0_single_2R": dict(legs=[(0.0, 2.0)]),
    "S1_struct_025_05_1R": dict(legs=[(0.0, 0.25), (0.5, 0.5), (1.0, 1.0)]),   # (ATR offset below leg-1 fill, target R)
    "S2_struct_2R_control": dict(legs=[(0.0, 2.0), (0.5, 2.0), (1.0, 2.0)]),
}


def signals(ind):
    C = ind["C"]
    ema12, ema26 = C.ewm(span=12, adjust=False).mean(), C.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig9 = macd.ewm(span=9, adjust=False).mean()
    cross = (macd > sig9) & (macd.shift(1) <= sig9.shift(1))
    ema200 = C.ewm(span=200, adjust=False).mean()
    swing = ind["L"].rolling(SWING).min()
    return (cross & (C > ema200) & ind["liquid"] & swing.notna()), swing


def run(ind, S, swing, variant, scen):
    legs_spec = VARIANTS[variant]["legs"]
    O, H, L, Craw, CF, ATR, DV = (ind[k].values for k in ("O", "H", "L", "C", "CF", "atr", "dv50"))
    SW = swing.values
    score = ind["ret63"].values
    T, N = S.shape
    dates, tickers = ind["dates"], ind["tickers"]
    cash = CAPITAL
    groups, trades, eqc, no_fill = [], [], np.full(T, np.nan), 0

    def scost(dv):
        return fs.side_cost(scen, dv if np.isfinite(dv) else 0.0)

    def close_leg(gp, leg, px, g, why):
        nonlocal cash
        # exit cost uses the PREVIOUS session's dollar volume (no same-day look-ahead)
        exit_net = px * (1 - scost(DV[g - 1, gp["i"]]))
        cash += leg["sh"] * exit_net
        leg.update(status="closed", why=why, pnl=leg["sh"] * (exit_net - leg["fill_cost"]))

    def finish_if_done(gp, g):
        nonlocal no_fill
        if any(l["status"] in ("open", "pending") for l in gp["legs"]):
            return False
        filled = [l for l in gp["legs"] if l["status"] == "closed"]
        if not filled:
            no_fill += 1
            return True
        basis = sum(l["sh"] * l["fill_cost"] for l in filled)
        pnl = sum(l["pnl"] for l in filled)
        trades.append(dict(entry_date=str(dates[gp["s"] + 1].date()), exit_date=str(dates[g].date()),
                           ticker=gp["t"], legs_filled=len(filled), legs_total=len(gp["legs"]),
                           pnl=round(pnl, 2), ret=pnl / basis,
                           exit_reasons=";".join(sorted({l["why"] for l in filled}))))
        return True

    for g in range(1, T):
        # A) new signals from s = g-1, entry legs live from session g (leg 1 fills at g's open)
        s = g - 1
        cand = np.nonzero(S[s])[0]
        if len(cand) and len(groups) < MAX_GROUPS:
            cand = cand[np.argsort(-np.nan_to_num(score[s, cand], nan=-9.0), kind="stable")]
            held = {gp["i"] for gp in groups}
            equity_prev = cash + sum(l["sh"] * CF[s, gp["i"]] for gp in groups for l in gp["legs"]
                                     if l["status"] == "open")
            for i in cand:
                if len(groups) >= MAX_GROUPS:
                    break
                if i in held or not np.isfinite(O[g, i]) or not np.isfinite(Craw[s, i]) or not np.isfinite(ATR[s, i]):
                    continue
                if O[g, i] > Craw[s, i] * (1 + GAP_CAP) or not np.isfinite(SW[s, i]):
                    continue
                stop = SW[s, i] - STOP_BUF_ATR * ATR[s, i]
                if stop >= O[g, i]:
                    continue
                legs = [dict(status="pending", offset=off, level=O[g, i] - off * ATR[s, i], R=R)
                        for off, R in legs_spec]
                groups.append(dict(i=i, t=tickers[i], s=s, stop=stop, legs=legs, window_end=g + LEG_WINDOW - 1,
                                   exit_g=s + TIME_SESSIONS, risk_per_leg=RISK_FRAC * equity_prev / len(legs),
                                   equity0=equity_prev))
                held.add(i)
        # B) process every group for session g
        for gp in list(groups):
            i = gp["i"]
            bar = np.isfinite(O[g, i]) and np.isfinite(L[g, i]) and np.isfinite(H[g, i])
            for leg in gp["legs"]:
                if leg["status"] == "pending":
                    if g > gp["window_end"]:
                        leg["status"] = "cancelled"
                        continue
                    if not bar or L[g, i] > leg["level"]:
                        continue
                    fill = min(O[g, i], leg["level"])
                    if fill <= gp["stop"]:
                        leg["status"] = "cancelled"
                        continue
                    c_in = scost(DV[gp["s"], i])
                    sh = math.floor(min(gp["risk_per_leg"] / (fill - gp["stop"]),
                                        MAX_POS_FRAC * gp["equity0"] / fill,
                                        cash / (fill * (1 + c_in)),
                                        PARTICIPATION * DV[gp["s"], i] / (fill * (1 + c_in))
                                        if np.isfinite(DV[gp["s"], i]) else 0))
                    if sh < 1:
                        leg["status"] = "cancelled"
                        continue
                    cash -= sh * fill * (1 + c_in)
                    leg.update(status="open", fill=fill, fill_cost=fill * (1 + c_in), sh=sh, fill_g=g,
                               target=fill + leg["R"] * (fill - gp["stop"]))
                    if L[g, i] <= gp["stop"]:   # stop checked on the fill session (conservative)
                        if O[g, i] <= gp["stop"]:
                            close_leg(gp, leg, O[g, i], g, "stop_gap")
                        else:
                            close_leg(gp, leg, gp["stop"], g, "stop")
                    continue
                if leg["status"] != "open" or g <= leg["fill_g"]:
                    continue
                if g >= gp["exit_g"]:
                    if np.isfinite(Craw[g, i]):
                        close_leg(gp, leg, Craw[g, i], g, "time" if leg.get("pending_days", 0) == 0 else "time_delayed")
                        continue
                    leg["pending_days"] = leg.get("pending_days", 0) + 1
                    if leg["pending_days"] > MAX_PENDING_DAYS:
                        close_leg(gp, leg, DELIST_RECOVERY * CF[g - 1, i], g, "unresolved_writedown")
                    continue
                if not bar:
                    continue
                if O[g, i] <= gp["stop"]:
                    close_leg(gp, leg, O[g, i], g, "stop_gap")
                elif L[g, i] <= gp["stop"]:
                    close_leg(gp, leg, gp["stop"], g, "stop")
                elif O[g, i] >= leg["target"]:
                    close_leg(gp, leg, O[g, i], g, "target_gap")
                elif H[g, i] >= leg["target"]:
                    close_leg(gp, leg, leg["target"], g, "target")
            if finish_if_done(gp, g):
                groups.remove(gp)
        eqc[g] = cash + sum(l["sh"] * CF[g, gp["i"]] for gp in groups for l in gp["legs"] if l["status"] == "open")
    cols = ["entry_date", "exit_date", "ticker", "legs_filled", "legs_total", "pnl", "ret", "exit_reasons"]
    tr = pd.DataFrame(trades, columns=cols)
    eq = pd.Series(eqc, index=dates).ffill().fillna(CAPITAL)
    return tr, eq, no_fill


def stats(tr, eq, a, b):
    t = tr[(tr.entry_date >= a) & (tr.entry_date <= b)] if len(tr) else tr
    n = len(t)
    if n == 0:
        return {"trades": 0}
    wins, losses = t[t.pnl > 0], t[t.pnl <= 0]
    gw, gl = wins.pnl.sum(), -losses.pnl.sum()
    e = eq[(eq.index >= pd.Timestamp(a)) & (eq.index <= pd.Timestamp(b))]
    dd = float(((e / e.cummax()) - 1).min()) if len(e) else None
    return {"trades": n, "win_rate_pct": round(100 * len(wins) / n, 2), "win_rate_ci95": fs.wilson(len(wins), n),
            "expectancy_pct": round(100 * t.ret.mean(), 4),
            "profit_factor": round(gw / gl, 3) if gl > 0 else None,
            "max_dd_pct": round(100 * dd, 2) if dd is not None else None,
            "total_pnl": round(float(t.pnl.sum()), 2)}
