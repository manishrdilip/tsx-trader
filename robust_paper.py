#!/usr/bin/env python3
"""
Robust full-history paper trading for Canada TSX system.
Portfolio limits, realistic costs, improved filters.

Usage:
  python robust_paper.py

Outputs:
  results/robust_paper_trades.csv
  results/robust_monthly.csv
"""
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path

TICKERS = [
    "RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "NA.TO",
    "CNQ.TO", "SU.TO", "CVE.TO", "CNR.TO", "CP.TO",
    "MFC.TO", "SLF.TO", "SHOP.TO", "L.TO", "WCN.TO",
]
MARKET = "XIU.TO"
START = "2014-01-01"
RISK = 0.012
MAX_POS = 4
MAX_OPEN_RISK = 0.06
COST = 0.001
SLIP = 0.005
HOLD = 20
OUT = Path("results")
OUT.mkdir(exist_ok=True)

def flatten(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def add_ind(df):
    d = df.copy()
    c = d["Close"]
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()
    d["hi252"] = d["High"].rolling(252).max()
    d["mom"] = c / c.shift(252) - 1
    pc = c.shift(1)
    tr = pd.concat([d["High"]-d["Low"], (d["High"]-pc).abs(), (d["Low"]-pc).abs()], axis=1).max(1)
    d["atr"] = tr.rolling(14).mean()
    return d

print("Downloading...")
raw = {}
for s in TICKERS + [MARKET]:
    try:
        df = flatten(yf.download(s, start=START, auto_adjust=True, progress=False))
        if len(df) > 300:
            raw[s] = add_ind(df)
            print(f"  {s}: {len(df)}")
    except Exception as e:
        print("skip", s)

mkt = raw.pop(MARKET)
data = raw

def is_signal(sym, dt):
    d = data[sym]
    if dt not in d.index or len(d.loc[:dt]) < 252:
        return False
    x = d.loc[dt]
    if pd.isna(x["sma200"]) or pd.isna(x["atr"]) or x["atr"] <= 0:
        return False
    trend = x["Close"] > x["sma50"] > x["sma200"]
    mom = x["mom"] > 0.05 and x["Close"] >= 0.75 * x["hi252"]
    vol_ok = (x["atr"] / x["Close"]) < 0.10
    return trend and mom and vol_ok

# Simulation
trades = []
open_pos = []
equity = 10000.0
eq_list = []
dates = mkt.index[mkt.index >= "2016-01-01"]

print(f"Simulating {len(dates)} days...")
for dt in dates:
    # Exits
    still = []
    open_risk = 0.0
    for pos in open_pos:
        sym, ed, ep, st, tg, rf = pos
        if sym not in data or dt not in data[sym].index:
            still.append(pos)
            continue
        row = data[sym].loc[dt]
        # Trail to breakeven after +1R
        if (row["Close"] - ep) / max(ep - st, 0.01) > 1.0 and st < ep:
            st = ep
        exit_px = None
        if row["Low"] <= st:
            exit_px = st
        elif row["High"] >= tg:
            exit_px = tg
        elif (dt - ed).days >= HOLD:
            exit_px = row["Close"]
        if exit_px is not None:
            ret = exit_px / ep - 1 - 2 * COST
            trades.append({"symbol": sym, "entry": ed, "exit": dt, "ret": ret, "risk_frac": rf})
            equity *= (1 + ret * rf)
        else:
            still.append((sym, ed, ep, st, tg, rf))
            open_risk += rf
    open_pos = still

    # Regime
    weak = False
    if dt in mkt.index and pd.notna(mkt.loc[dt, "sma200"]):
        weak = mkt.loc[dt, "Close"] < mkt.loc[dt, "sma200"]
    risk = RISK * (0.5 if weak else 1.0)

    # Entries
    if len(open_pos) < MAX_POS and open_risk < MAX_OPEN_RISK:
        cands = [s for s in data if not any(p[0] == s for p in open_pos) and is_signal(s, dt)]
        cands = sorted(cands, key=lambda s: data[s].loc[dt, "mom"], reverse=True)[:2]
        for sym in cands:
            if len(open_pos) >= MAX_POS or open_risk >= MAX_OPEN_RISK:
                break
            row = data[sym].loc[dt]
            ep = float(row["Close"]) * (1 - SLIP)
            atr = float(row["atr"])
            st = max(ep - 3 * atr, ep * 0.92)
            tg = ep + 6 * atr
            sp = (ep - st) / ep
            rf = min(risk / sp, 0.15) if sp > 0 else 0
            if rf > 0:
                open_pos.append((sym, dt, ep, st, tg, rf))
                open_risk += rf

    eq_list.append({"date": dt, "equity": equity})

# Results
tdf = pd.DataFrame(trades)
eq = pd.DataFrame(eq_list).set_index("date")

print("\n" + "="*60)
print("ROBUST CANADA PAPER TRADE (2016 → today)")
print("="*60)
print(f"Trades: {len(tdf)}")
if len(tdf):
    print(f"Win rate: {(tdf.ret > 0).mean():.1%}")
    print(f"Avg trade return: {tdf.ret.mean()*100:.2f}%")
    pf = tdf.loc[tdf.ret>0, "ret"].sum() / -tdf.loc[tdf.ret<=0, "ret"].sum()
    print(f"Profit factor: {pf:.2f}")
print(f"Start equity: $10,000")
print(f"Final equity: ${equity:,.0f}")
print(f"Total return: {(equity/10000 - 1):.1%}")
print(f"Max DD: {(eq.equity / eq.equity.cummax() - 1).min():.1%}")
yrs = (eq.index[-1] - eq.index[0]).days / 365.25
print(f"CAGR: {(equity/10000)**(1/yrs) - 1:.1%}")

# Monthly
eq["month"] = eq.index.to_period("M")
monthly = eq.groupby("month")["equity"].last().pct_change().dropna()
print("\nLast 24 months:")
for m, r in monthly.tail(24).items():
    print(f"  {m}: {r*100:+6.1f}%")

tdf.to_csv(OUT / "robust_paper_trades.csv", index=False)
monthly.to_csv(OUT / "robust_monthly.csv")
print("\nSaved results/robust_paper_trades.csv and robust_monthly.csv")
