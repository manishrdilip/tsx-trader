"""Portfolio simulator for Quant Discovery V2 (rules in PROTOCOL.md).
Signals at close i, fills at open i+1, whole shares, no leverage, $5,000 start, cost per side."""
import numpy as np, pandas as pd

ETFS = {"XIU.TO", "XIC.TO", "VEQT.TO", "VFV.TO", "XEG.TO", "XFN.TO", "XIT.TO", "XMA.TO", "ZUT.TO", "XRE.TO",
        "XST.TO", "XHC.TO", "XGD.TO", "XUT.TO", "ZIN.TO"}


class Panel:
    def __init__(self, path):
        z = np.load(path, allow_pickle=True)
        self.dates = pd.DatetimeIndex(z["dates"]); self.tk = list(z["tickers"])
        self.C = pd.DataFrame(z["close"].astype("float64"), self.dates, self.tk)
        self.O = pd.DataFrame(z["open"].astype("float64"), self.dates, self.tk)
        self.V = pd.DataFrame(z["vol"].astype("float64"), self.dates, self.tk)
        C = self.C
        self.sma200 = C.rolling(200).mean(); self.sma50 = C.rolling(50).mean(); self.sma5 = C.rolling(5).mean()
        self.r12 = C / C.shift(252) - 1
        dv = (C * self.V).rolling(20).median()
        hist = C.notna().cumsum()
        stock = np.array([t not in ETFS for t in self.tk])
        self.elig = (C.ge(1) & C.le(100) & dv.ge(300_000) & hist.ge(253)) & stock
        # last day each ticker has data (for forced exits when data ends)
        lv = C.apply(lambda s: s.last_valid_index())
        self.last_i = np.array([self.dates.get_loc(d) if d is not None else -1 for d in lv])
        self.xiu = C["XIU.TO"]; self.xiu_ok = (self.xiu > self.xiu.rolling(200).mean()).values


def run(P, strat, start, end, cost=0.005, cash0=5000.0, vix=None):
    """strat: dict with
       scores(i) -> pd.Series (higher = better) of buy candidates at close i (already filtered), or None
       exit(i, t, pos) -> reason str or None   (pos: dict entry_i, peak, units)
       slots(equity) -> int, max_hold, buy_day(i) -> bool, trail (pct or 0), never_rebuy_trail,
       park (ticker or None), guard (bool), order_cap (bool)"""
    D = P.dates; Cv = P.C.values; Ov = P.O.values; col = {t: k for k, t in enumerate(P.tk)}
    i0 = D.searchsorted(pd.Timestamp(start)); i1 = D.searchsorted(pd.Timestamp(end), side="right") - 1
    cash = cash0; pos = {}; park_v = 0.0; park_order = 0.0; blocks = set(); trades = []; eq = []
    pending_buy, pending_sell = [], []
    eqhist = []
    for i in range(i0, i1 + 1):
        # 1) execute yesterday's orders at today's open
        for t, why in pending_sell:
            if t not in pos: continue
            k = col[t]; px = Ov[i, k]
            if not np.isfinite(px): px = Cv[i, k] if np.isfinite(Cv[i, k]) else pos[t]["last"]
            p = pos.pop(t); cash += p["u"] * px * (1 - cost)
            trades.append((p["ent"], i, t, p["u"] * p["px"], p["u"] * px * (1 - cost) - p["u"] * p["px"] * (1 + cost), why))
        pending_sell = []
        for t, u, lim in pending_buy:
            k = col[t]; px = Ov[i, k]
            if not np.isfinite(px) or px > lim or t in pos: continue
            u = min(u, int(cash // (px * (1 + cost))))
            if u <= 0: continue
            cash -= u * px * (1 + cost)
            pos[t] = {"u": u, "px": px, "ent": i, "peak": px, "last": px}
        pending_buy = []
        if strat.get("park"):
            pt = park_ticker(P, i, strat["park"]); k = col[pt]
            if i > i0 and np.isfinite(Cv[i, k]) and np.isfinite(Cv[i - 1, k]):
                park_v *= Cv[i, k] / Cv[i - 1, k]
            if park_order > 0:
                amt = min(park_order, cash); cash -= amt; park_v += amt * (1 - cost); park_order = 0.0
        # 2) forced exits: data ended
        for t in list(pos):
            k = col[t]
            if np.isfinite(Cv[i, k]): pos[t]["last"] = Cv[i, k]
            if P.last_i[k] <= i and P.last_i[k] < len(D) - 1:
                p = pos.pop(t); v = p["u"] * p["last"] * (1 - cost - 0.005); cash += v
                trades.append((p["ent"], i, t, p["u"] * p["px"], v - p["u"] * p["px"] * (1 + cost), "data ended"))
        # 3) mark to market
        held = sum(p["u"] * p["last"] for p in pos.values())
        equity = cash + held; total = equity + park_v
        eq.append(total); eqhist.append(total)
        if i == i1: break
        # 4) decisions at close i
        for t, p in pos.items():
            if p["last"] > p["peak"]: p["peak"] = p["last"]
        sold = set()
        for t, p in pos.items():
            k = col[t]
            if not np.isfinite(Cv[i, k]): continue
            why = None
            tr = strat.get("trail", 0)
            if tr and Cv[i, k] <= p["peak"] * (1 - tr / 100):
                why = "trail"
                if strat.get("never_rebuy_trail"): blocks.add(t)
            else:
                why = strat["exit"](i, t, p)
            if why: pending_sell.append((t, why)); sold.add(t)
        guard = False
        if strat.get("guard"):
            xr = P.xiu.iloc[i] / P.xiu.iloc[i - 1] - 1
            if xr <= -0.02: guard = True
            if vix is not None:
                vv = vix.get(D[i]); vp = vix.get(D[i - 1])
                if vv is not None and (vv >= 30 or (vp and vv / vp - 1 >= 0.20)): guard = True
            recent = eqhist[-6:]
            if total < max(recent) * 0.85: guard = True
        keep = [t for t in pos if t not in sold]
        if not guard and strat["buy_day"](i):
            sc = strat["scores"](i)
            if sc is not None and len(sc):
                slots = strat["slots"](equity); per = equity / slots
                cap = max(800, 0.10 * equity) if strat.get("order_cap") else 1e18
                free = strat["max_hold"] - len(keep)
                c = cash  # live bot: proceeds of today's sells are not spent the same run
                for t in sc.index:
                    if free <= 0: break
                    if t in pos or t in blocks: continue
                    lim = Cv[i, col[t]] * 1.01
                    if lim > c or lim > cap: continue
                    u = max(1, int(min(per, c, cap) // lim))
                    pending_buy.append((t, u, lim)); c -= u * lim; free -= 1
        if strat.get("park"):
            left = cash - sum(u * l for _, u, l in pending_buy) - 20
            if left >= 100:
                park_order = min(left, max(800, 0.10 * equity))
    eq = pd.Series(eq, D[i0:i0 + len(eq)])
    return eq, trades



def park_ticker(P, i, want):
    k = P.tk.index(want)
    return want if np.isfinite(P.C.values[i, k]) else "XIC.TO"


def stats(eq, trades, cash0=5000.0):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    dd = (eq / eq.cummax() - 1).min()
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else 0
    dn = r[r < 0].std() * np.sqrt(252)
    pnl = np.array([t[4] for t in trades]) if trades else np.array([0.0])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    m = eq.resample("ME").last().pct_change().dropna(); y = eq.resample("YE").last().pct_change().dropna()
    return {"end": round(eq.iloc[-1]), "net_profit": round(eq.iloc[-1] - eq.iloc[0]), "cagr": round(cagr * 100, 1),
            "avg_day_profit": round((eq.iloc[-1] - eq.iloc[0]) / max(1, len(eq)), 2),
            "max_dd": round(dd * 100, 1), "sharpe": round(r.mean() / r.std() * np.sqrt(252), 2) if r.std() > 0 else 0,
            "sortino": round(r.mean() * 252 / dn, 2) if dn > 0 else 0, "calmar": round(cagr / -dd, 2) if dd < 0 else 0,
            "trades": len(trades), "win_rate": round(len(wins) / max(1, len(pnl)) * 100, 1),
            "pf": round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else 0,
            "expectancy": round(pnl.mean(), 1), "avg_win": round(wins.mean(), 1) if len(wins) else 0,
            "avg_loss": round(losses.mean(), 1) if len(losses) else 0,
            "worst_day": round(r.min() * 100, 1), "worst_month": round(m.min() * 100, 1) if len(m) else 0,
            "worst_year": round(y.min() * 100, 1) if len(y) else 0}
