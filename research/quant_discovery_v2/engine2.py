"""Batch 2 engine: Batch 1 engine (engine.py, unchanged) plus allocation options and deposits.
Extra strat keys:
  park_mode: "perm" (live) | "temp" (park ETF sold to fund buys) | None (cash)
  index_leg: True -> monthly momentum share = vol(XIU)/vol(picks), rest held in XIU (live INDEX_LEG logic)
  vol_size: True -> per-slot dollars x min(1.5, median vol / stock vol)
  dd_brake: float -> no new buys while total equity is more than this fraction below its running peak
Deposits: dict {date: amount}; returns time-weighted return series alongside equity."""
import numpy as np, pandas as pd
from engine import Panel, stats, park_ticker  # noqa: F401


def run2(P, strat, start, end, cost=0.005, cash0=5000.0, vix=None, deposits=None, vol=None):
    D = P.dates; Cv = P.C.values; Ov = P.O.values; col = {t: k for k, t in enumerate(P.tk)}
    xk = col["XIU.TO"]
    i0 = D.searchsorted(pd.Timestamp(start)); i1 = D.searchsorted(pd.Timestamp(end), side="right") - 1
    dep = {} if deposits is None else {D.searchsorted(pd.Timestamp(d)): a for d, a in deposits.items()}
    cash = cash0; pos = {}; park_v = 0.0; park_order = 0.0; park_sell = 0.0; xiu_v = 0.0; xiu_order = 0.0
    blocks = set(); trades = []; eq = []; twr = [1.0]; peak_all = cash0; share = 1.0
    pending_buy, pending_sell = [], []; eqhist = []; prev_total = None
    pm = strat.get("park_mode", "perm" if strat.get("park") else None)
    for i in range(i0, i1 + 1):
        flow = dep.get(i, 0.0) if i > i0 else 0.0
        cash += flow
        for t, why in pending_sell:
            if t not in pos: continue
            k = col[t]; px = Ov[i, k]
            if not np.isfinite(px): px = Cv[i, k] if np.isfinite(Cv[i, k]) else pos[t]["last"]
            p = pos.pop(t); cash += p["u"] * px * (1 - cost)
            trades.append((p["ent"], i, t, p["u"] * p["px"], p["u"] * px * (1 - cost) - p["u"] * p["px"] * (1 + cost), why))
        pending_sell = []
        # park / index-leg value moves with their ETF, then execute their orders
        if pm:
            pt = park_ticker(P, i, strat.get("park", "VEQT.TO")); k = col[pt]
            if i > i0 and np.isfinite(Cv[i, k]) and np.isfinite(Cv[i - 1, k]): park_v *= Cv[i, k] / Cv[i - 1, k]
            if park_sell > 0:
                amt = min(park_sell, park_v); park_v -= amt; cash += amt * (1 - cost); park_sell = 0.0
        if i > i0 and np.isfinite(Cv[i, xk]) and np.isfinite(Cv[i - 1, xk]): xiu_v *= Cv[i, xk] / Cv[i - 1, xk]
        if xiu_order:
            if xiu_order > 0:
                amt = min(xiu_order, cash); cash -= amt; xiu_v += amt * (1 - cost)
            else:
                amt = min(-xiu_order, xiu_v); xiu_v -= amt; cash += amt * (1 - cost)
            xiu_order = 0.0
        for t, u, lim in pending_buy:
            k = col[t]; px = Ov[i, k]
            if not np.isfinite(px) or px > lim or t in pos: continue
            u = min(u, int(cash // (px * (1 + cost))))
            if u <= 0: continue
            cash -= u * px * (1 + cost)
            pos[t] = {"u": u, "px": px, "ent": i, "peak": px, "last": px}
        pending_buy = []
        if pm and park_order > 0:
            amt = min(park_order, cash); cash -= amt; park_v += amt * (1 - cost); park_order = 0.0
        for t in list(pos):
            k = col[t]
            if np.isfinite(Cv[i, k]): pos[t]["last"] = Cv[i, k]
            if P.last_i[k] <= i and P.last_i[k] < len(D) - 1:
                p = pos.pop(t); v = p["u"] * p["last"] * (1 - cost - 0.005); cash += v
                trades.append((p["ent"], i, t, p["u"] * p["px"], v - p["u"] * p["px"] * (1 + cost), "data ended"))
        held = sum(p["u"] * p["last"] for p in pos.values())
        equity = cash + held; total = equity + park_v + xiu_v
        if prev_total: twr.append(twr[-1] * (total - flow) / prev_total)
        prev_total = total
        eq.append(total); eqhist.append(total); peak_all = max(peak_all, total)
        if i == i1: break
        for t, p in pos.items():
            if p["last"] > p["peak"]: p["peak"] = p["last"]
        sold = set()
        for t, p in pos.items():
            k = col[t]
            if not np.isfinite(Cv[i, k]): continue
            tr = strat.get("trail", 0); why = None
            if tr and Cv[i, k] <= p["peak"] * (1 - tr / 100):
                why = "trail"
                if strat.get("never_rebuy_trail"): blocks.add(t)
            else:
                why = strat["exit"](i, t, p)
            if why: pending_sell.append((t, why)); sold.add(t)
        guard = False
        if strat.get("guard"):
            if P.xiu.iloc[i] / P.xiu.iloc[i - 1] - 1 <= -0.02: guard = True
            if vix is not None:
                vv = vix.get(D[i]); vp = vix.get(D[i - 1])
                if vv is not None and (vv >= 30 or (vp and vv / vp - 1 >= 0.20)): guard = True
            if total < max(eqhist[-6:]) * 0.85: guard = True
        if strat.get("dd_brake") and total < peak_all * (1 - strat["dd_brake"]): guard = True
        keep = [t for t in pos if t not in sold]
        # dynamic index leg: monthly share
        mstart = i + 1 < len(D) and D[i + 1].month != D[i].month
        if strat.get("index_leg") and mstart:
            sc0 = strat["scores"](i)
            picks = list(sc0.index[:20]) if sc0 is not None else []
            if picks:
                rr = P.C[picks].iloc[i - 60:i + 1].pct_change().mean(axis=1).std()
                xr = P.C["XIU.TO"].iloc[i - 60:i + 1].pct_change().std()
                share = float(min(1.0, xr / rr)) if rr > 0 else 1.0
            target = (1 - share) * total
            if abs(target - xiu_v) >= 100: xiu_order = target - xiu_v
        mom_eq = equity if not strat.get("index_leg") else min(equity, share * total)
        bought = 0.0
        if not guard and strat["buy_day"](i):
            sc = strat["scores"](i)
            if sc is not None and len(sc):
                slots = strat["slots"](mom_eq); per = mom_eq / slots
                cap = max(800, 0.10 * equity) if strat.get("order_cap") else 1e18
                free = strat["max_hold"] - len(keep)
                c = cash - max(0.0, xiu_order)
                if pm == "temp": c += park_v
                for t in sc.index:
                    if free <= 0: break
                    if t in pos or t in blocks: continue
                    k = col[t]; lim = Cv[i, k] * 1.01
                    pp = per
                    if strat.get("vol_size") and vol is not None and np.isfinite(vol[i, k]) and vol[i, k] > 0:
                        pp = per * min(1.5, np.nanmedian(vol[i][P.elig.values[i]]) / vol[i, k])
                    if lim > c or lim > cap: continue
                    u = max(1, int(min(pp, c, cap) // lim))
                    pending_buy.append((t, u, lim)); c -= u * lim; free -= 1; bought += u * lim
        if pm == "temp" and bought > cash - 20:
            park_sell = bought - (cash - 20)   # sold at next open; buys that can't be paid for just don't fill
        if pm:
            left = cash - bought - 20 - max(0.0, xiu_order)
            if left >= 100: park_order = min(left, max(800, 0.10 * equity))
    eq = pd.Series(eq, D[i0:i0 + len(eq)])
    tw = pd.Series(twr, eq.index) * cash0
    return eq, trades, tw
