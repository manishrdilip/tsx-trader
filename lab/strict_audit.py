#!/usr/bin/env python3
"""
Strict audit tester — lab/strict-audit-2026-11-14
Rules frozen before run. Signal close t, fill close t+1.
Costs: 0.1% ETF + 1.5% FX on USD conversion (applied on position change).
No borrowing. Start years 1999-2025 + Mar2000 + Oct2007 where data allows.
Survivors-only (yfinance). No post-hoc tuning.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
from pathlib import Path

# FROZEN RULES
COST_ETF = 0.001
FX = 0.015
COST_HIGH = 0.01  # 1% per side sensitivity
START_CAP = 5000

def fetch(ticker, start="1999-01-01"):
    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Close"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df

def vol_target(df, target=0.4, look=20, maxlev=3.0):
    """Leverage only via the product itself; cap at maxlev of the ETF."""
    rets = df["Close"].pct_change()
    vol = rets.rolling(look).std() * np.sqrt(252)
    lev = (target / vol.shift(1)).clip(0, maxlev)
    return lev.fillna(0)

def sma_filter(df, n=200):
    return (df["Close"].shift(1) > df["Close"].rolling(n).mean().shift(1)).astype(float)

def run_cohorts(df, pos, cost_per_side, label):
    pos = pos.shift(1).fillna(0)  # fill next close
    rets = df["Close"].pct_change().fillna(0)
    # FX on every conversion (entry/exit from CAD cash)
    chg = pos.diff().abs().fillna(0)
    total_cost = chg * (cost_per_side + FX)
    srets = rets * pos - total_cost
    rows = []
    starts = [f"{y}-01-01" for y in range(1999, 2026)] + ["2000-03-01", "2007-10-01"]
    for st in starts:
        m = srets.index >= st
        if m.sum() < 100:
            continue
        eq = START_CAP * (1 + srets.loc[m]).cumprod()
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        if yrs < 1:
            continue
        cagr = (eq.iloc[-1] / START_CAP) ** (1 / yrs) - 1
        dd = ((eq / eq.cummax()) - 1).min()
        # worst calendar year
        ye = eq.resample("YE").last()
        yret = ye.pct_change().dropna()
        worst_yr = yret.min() if len(yret) else 0
        rows.append({
            "start": st[:7],
            "cagr": cagr * 100,
            "maxdd": dd * 100,
            "worst_year": worst_yr * 100,
            "final": eq.iloc[-1]
        })
    if not rows:
        return None
    cagrs = [r["cagr"] for r in rows]
    dds = [r["maxdd"] for r in rows]
    wy = [r["worst_year"] for r in rows]
    finals = [r["final"] for r in rows]
    beat = sum(1 for c in cagrs if c > 30)  # vs bot median ~30%
    return {
        "label": label,
        "n": len(rows),
        "med_cagr": round(np.median(cagrs), 1),
        "worst_start": round(min(cagrs), 1),
        "med_dd": round(np.median(dds), 1),
        "worst_dd": round(min(dds), 1),
        "worst_cal_year": round(min(wy), 1),
        "med_final": round(np.median(finals), 0),
        "beat_bot": f"{beat} of {len(rows)}",
        "survivors_only": True
    }

def report(res):
    if not res:
        return
    print(f"\n{res['label']}")
    print(f"median %/yr | worst start | med max drop | worst max drop | worst cal year | $5k final (med) | starts beating bot")
    print(f"{res['med_cagr']} | {res['worst_start']} | {res['med_dd']} | {res['worst_dd']} | {res['worst_cal_year']} | {res['med_final']} | {res['beat_bot']}")
    # PASS check
    # A: better return, max drop AND worst year than bot (~30, -39, -27)
    a = res["med_cagr"] > 30 and res["med_dd"] > -39 and res["worst_cal_year"] > -27
    # B: more money in >=70% starts, max drop no worse than -45, no losing start
    b_pct = int(res["beat_bot"].split()[0]) / res["n"] >= 0.7
    b = b_pct and res["worst_dd"] >= -45 and res["worst_start"] > 0
    status = "PASS" if (a or b) else "FAIL"
    print(f"Status: {status} (A={a}, B={b})")
    return status

if __name__ == "__main__":
    print("Strict audit — frozen rules, survivors-only yfinance\n")
    results = []
    # Strategy 1: QQQ vol 0.4 (capped lev 3, no margin)
    df = fetch("QQQ")
    pos = vol_target(df, 0.4, 20, 3)
    r = run_cohorts(df, pos, COST_ETF, "QQQ vol0.4 (lev<=3) @0.1%+FX")
    report(r)
    results.append(r)
    r1 = run_cohorts(df, pos, COST_HIGH, "QQQ vol0.4 @1%+FX")
    report(r1)
    # Strategy 2: XLK vol 0.45
    dfx = fetch("XLK")
    posx = vol_target(dfx, 0.45, 20, 3)
    r = run_cohorts(dfx, posx, COST_ETF, "XLK vol0.45 (lev<=3) @0.1%+FX")
    report(r)
    results.append(r)
    # Strategy 3: QQQ SMA200
    pos_sma = sma_filter(df, 200)
    r = run_cohorts(df, pos_sma, COST_ETF, "QQQ SMA200 @0.1%+FX")
    report(r)
    results.append(r)
    Path("/tmp/tsx-trader/lab/results").mkdir(exist_ok=True)
    with open("/tmp/tsx-trader/lab/results/strict_audit_partial.json", "w") as f:
        json.dump([x for x in results if x], f, indent=2)
    print("\nPartial results saved. Survivors-only. No EODHD delisted used.")
