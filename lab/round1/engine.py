"""Portfolio-level daily engine for Round 1 experiments (TSX, long only).
Rules: signal at close t -> entry at open t+1 (skip if gap > 2%). Stop/target from ATR at t.
Same-bar stop and target: stop first. Gap through stop fills at open. Costs per side.
Sizing: shares = floor(equity * risk / stop distance), position capped at max_w of equity, max_pos open.
"""
import numpy as np
import pandas as pd

DATA = "data"


def load(data_dir=DATA):
    return {f: pd.read_parquet(f"{data_dir}/tsx_{f}.parquet") for f in ["Open", "High", "Low", "Close", "Volume"]}


def indicators(p):
    O, H, L, C, V = p["Open"], p["High"], p["Low"], p["Close"], p["Volume"]
    prevC = C.shift(1)
    tr = pd.DataFrame(np.maximum.reduce([(H - L).values, (H - prevC).abs().values, (L - prevC).abs().values]),
                      index=C.index, columns=C.columns)
    up, dn = H.diff(), -L.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    atr_w = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_w
    mdi = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr_w
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    ind = dict(
        O=O, H=H, L=L, C=C, V=V, prevC=prevC,
        ATR=tr.rolling(14).mean(), ADX=dx.ewm(alpha=1 / 14, adjust=False).mean(),
        SMA10=C.rolling(10).mean(), SMA50=C.rolling(50).mean(), SMA200=C.rolling(200).mean(),
        EMA21=C.ewm(span=21, adjust=False).mean(), HI52=H.rolling(252, min_periods=200).max(),
        RET252=C / C.shift(252) - 1, VOL20=V.rolling(20).mean(),
    )
    return ind


def signals(ind, variant):
    C, O, L, H, V, prevC = ind["C"], ind["O"], ind["L"], ind["H"], ind["V"], ind["prevC"]
    trend = (C > ind["SMA50"]) & (ind["SMA50"] > ind["SMA200"])
    base = trend & (ind["RET252"] > 0) & (C >= 0.85 * ind["HI52"])
    pull = (L <= ind["EMA21"] * 1.01) & (C >= ind["EMA21"])
    trig = C > prevC
    c1 = base & pull & trig
    if variant in ("C1", "D_RULE", "E1", "E4", "E5", "SENS", "COST"):
        s = c1
    elif variant == "C2":  # 4-scanner vote >= 2
        candle = (C > O) & (C > prevC)
        votes = (trend.astype(int) + ((ind["RET252"] > 0) & (C >= 0.9 * ind["HI52"])).astype(int)
                 + ((V >= ind["VOL20"]) & (ind["ATR"] / C < 0.08)).astype(int) + candle.astype(int))
        s = c1 & (votes >= 2)
    elif variant == "C3":  # no bullish-reclaim trigger
        s = base & pull
    elif variant == "E2":  # ADX > 25
        s = c1 & (ind["ADX"] > 25)
    elif variant == "E3":  # volume >= 1.5x and close in upper half of bar
        s = c1 & (V >= 1.5 * ind["VOL20"]) & (C >= L + 0.5 * (H - L))
    else:
        raise ValueError(variant)
    return s.fillna(False)


def simulate(ind, sig, regime, cfg, start, end):
    """cfg keys: risk, stop_mode ('atr'|'pct'), stop_k, target_k, stop_pct, target_pct, T,
    partial (bool), max_pos, max_w, cost, use_regime, start_cash."""
    O, C, L, H = ind["O"], ind["C"], ind["L"], ind["H"]
    ATR, SMA10, RET = ind["ATR"], ind["SMA10"], ind["RET252"]
    dates = C.loc[start:end].index
    cash = float(cfg.get("start_cash", 5000.0))
    pos, trades, eq_vals, pend = [], [], [], []
    cost = cfg["cost"]
    prev_d = None
    for i, d in enumerate(dates):
        # 1. exits on today's bar
        keep = []
        for p in pos:
            t = p["t"]
            if p["entry_date"] == d:
                keep.append(p); continue
            o, h, l, c = O.at[d, t], H.at[d, t], L.at[d, t], C.at[d, t]
            if np.isnan(c):
                keep.append(p); continue
            p["days"] += 1
            done, px, why = False, None, None
            if o <= p["stop"]:
                px, why, done = o, "GAP_STOP", True
            elif l <= p["stop"]:
                px, why, done = p["stop"], "STOP", True
            if not done and cfg.get("partial") and not p["partial"] and h >= p["entry_px"] + 2 * p["R"]:
                lvl = max(o, p["entry_px"] + 2 * p["R"])
                half = p["sh"] // 2
                if half >= 1:
                    proceeds = half * lvl * (1 - cost)
                    cash += proceeds; p["proceeds"] += proceeds; p["sh"] -= half
                p["partial"] = True
                p["stop"] = p["entry_px"]  # breakeven on the runner
                p["target"] = None
            if not done and not p["partial"] and p.get("target") is not None and h >= p["target"]:
                px, why, done = max(o, p["target"]), "TARGET", True
            if not done and p["partial"]:
                if c < SMA10.at[d, t]:
                    px, why, done = c, "TRAIL10", True
            if not done and p["days"] >= cfg["T"]:
                px, why, done = c, "TIME", True
            if done and p["sh"] > 0:
                proceeds = p["sh"] * px * (1 - cost)
                cash += proceeds; p["proceeds"] += proceeds; p["sh"] = 0
                trades.append(dict(t=t, entry=p["entry_date"], exit=d, why=why, days=p["days"],
                                   cost=p["cost"], pnl=p["proceeds"] - p["cost"],
                                   ret=(p["proceeds"] - p["cost"]) / p["cost"],
                                   R=(p["proceeds"] - p["cost"]) / p["risk_d"]))
            elif not done:
                keep.append(p)
        pos = keep
        # 2. entries from previous day's signals, at today's open
        held = {p["t"] for p in pos}
        for t in pend:
            if len(pos) >= cfg["max_pos"]:
                break
            if t in held:
                continue
            o = O.at[d, t]
            if np.isnan(o) or prev_d is None:
                continue
            if o > C.at[prev_d, t] * 1.02:
                continue
            a = ATR.at[prev_d, t]
            if cfg["stop_mode"] == "atr":
                stop, target = o - cfg["stop_k"] * a, o + cfg["target_k"] * a
            else:
                stop, target = o * (1 - cfg["stop_pct"]), o * (1 + cfg["target_pct"])
            R = o - stop
            if not np.isfinite(R) or R <= 0:
                continue
            eq_now = cash + sum(p["sh"] * (C.at[d, p["t"]] if not np.isnan(C.at[d, p["t"]]) else p["entry_px"]) for p in pos)
            sh = int(np.floor(eq_now * cfg["risk"] / R))
            sh = min(sh, int(np.floor(cfg["max_w"] * eq_now / o)))
            entry_px = o * (1 + cost)
            if sh < 1 or sh * entry_px > cash:
                continue
            cash -= sh * entry_px
            pos.append(dict(t=t, entry_date=d, entry_px=entry_px, stop=stop, target=target, R=R, sh=sh,
                            cost=sh * entry_px, proceeds=0.0, risk_d=eq_now * cfg["risk"], days=0, partial=False))
            held.add(t)
        # 3. mark to market
        eq = cash + sum(p["sh"] * (C.at[d, p["t"]] if not np.isnan(C.at[d, p["t"]]) else p["entry_px"]) for p in pos)
        eq_vals.append(eq)
        # 4. today's signals -> tomorrow's candidates (regime gate at close)
        if cfg.get("use_regime", False) and not bool(regime.get(d, False)):
            pend = []
        else:
            row = sig.loc[d]
            cands = row[row].index.tolist()
            cands.sort(key=lambda t: -(RET.at[d, t] if not np.isnan(RET.at[d, t]) else -9))
            pend = cands
        prev_d = d
    for p in pos:  # close at last close
        t = p["t"]; c = C.at[dates[-1], t]
        if p["sh"] > 0 and not np.isnan(c):
            proceeds = p["sh"] * c * (1 - cost)
            cash += proceeds; p["proceeds"] += proceeds
            trades.append(dict(t=t, entry=p["entry_date"], exit=dates[-1], why="EOD", days=p["days"],
                               cost=p["cost"], pnl=p["proceeds"] - p["cost"], ret=(p["proceeds"] - p["cost"]) / p["cost"],
                               R=(p["proceeds"] - p["cost"]) / p["risk_d"]))
    eq_series = pd.Series(eq_vals, index=dates)
    return eq_series, pd.DataFrame(trades)


def stats(eq, tr, cfg, seed=1):
    rng = np.random.default_rng(seed)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dd = float((eq / eq.cummax() - 1).min())
    out = dict(cagr=cagr, max_dd=dd, calmar=cagr / abs(dd) if dd < 0 else np.nan, final=eq.iloc[-1])
    if len(tr):
        r = tr["ret"].values
        out.update(trades=len(tr), win=(r > 0).mean(), exp_ret=r.mean(), avg_R=tr["R"].mean(),
                   avg_days=tr["days"].mean())
        boots = np.array([rng.choice(r, len(r)).mean() for _ in range(2000)])
        out["exp_ci_lo"], out["exp_ci_hi"] = np.percentile(boots, [2.5, 97.5])
        Rs = tr["R"].values
        mc = []
        for _ in range(2000):
            e = 1.0; pk = 1.0; m = 0.0
            for x in rng.permutation(Rs):
                e *= 1 + cfg["risk"] * x
                pk = max(pk, e); m = max(m, 1 - e / pk)
            mc.append(m)
        out["mc_dd_p95"] = float(np.percentile(mc, 95))
    else:
        out.update(trades=0, win=np.nan, exp_ret=np.nan, avg_R=np.nan, exp_ci_lo=np.nan, exp_ci_hi=np.nan, mc_dd_p95=np.nan)
    return out
