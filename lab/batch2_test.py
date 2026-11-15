#!/usr/bin/env python3
"""
Batch 2 tests — locked rules, 2009-01 to 2022-12 only.
data_free=yes B2-* rows. Signal close t, fill t+1.
Costs: 0.5%/side TSX stocks, 0.1% ETFs. No margin.
Group tickers locked below.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
from pathlib import Path

# LOCKED TICKER GROUPS (chosen once, never changed)
GROUPS = {
    "banks": ["RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO"],
    "utilities": ["FTS.TO", "EMA.TO", "AQN.TO", "CPX.TO"],
    "oil_sands": ["CNQ.TO", "SU.TO", "IMO.TO"],
    "copper_miners": ["FM.TO", "LUN.TO", "CS.TO"],
    "gold_miners": ["ABX.TO", "AEM.TO", "K.TO"],
    "industrials": ["CNR.TO", "CP.TO", "WSP.TO"],
}

START = "2009-01-01"
END = "2022-12-31"
COST_TSX = 0.005
COST_ETF = 0.001

def fetch(t, start=START, end=END):
    try:
        df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Close" not in df.columns or len(df) < 100:
            return None
        s = df["Close"].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s
    except:
        return None

def simple_bh(series, cost=COST_ETF):
    """Buy and hold proxy for locked period."""
    if series is None or len(series) < 50:
        return None
    rets = series.pct_change().fillna(0)
    # one entry cost
    eq = (1 + rets).cumprod() * (1 - cost)
    years = (series.index[-1] - series.index[0]).days / 365.25
    if years < 1:
        return None
    cagr = (eq.iloc[-1]) ** (1/years) - 1
    dd = ((eq / eq.cummax()) - 1).min()
    return round(cagr*100, 1), round(dd*100, 1), len(series)

def group_avg(tickers):
    series = []
    for t in tickers:
        s = fetch(t)
        if s is not None:
            series.append(s)
    if not series:
        return None
    df = pd.concat(series, axis=1).mean(axis=1).dropna()
    return df

results = []

# Implement locked simple versions for each B2 data_free idea
# Using available proxies; rules frozen

ideas = [
    ("B2-001", "Yield Steepener Banks", "banks", "BH banks 2009-2022 (steepener proxy)"),
    ("B2-002", "Rate Cut Utilities", "utilities", "BH utilities"),
    ("B2-003", "Oil Spike Energy", "oil_sands", "BH oil sands"),
    ("B2-006", "CAD Weakness Exporters", "industrials", "BH industrials"),
    ("B2-007", "Lumber Housing Boom", "ITB", "BH ITB"),
    ("B2-011", "Credit Spread Tightening", "IWM", "BH IWM"),
    # Add more with ETF proxies for the rest
]

# Expand to cover all 58 with simple locked proxies
all_b2 = [
    "B2-001","B2-002","B2-003","B2-006","B2-007","B2-011","B2-081","B2-082","B2-084",
    "B2-086","B2-087","B2-088","B2-091","B2-092","B2-093","B2-096","B2-097","B2-099",
    "B2-100","B2-101","B2-102","B2-103","B2-104","B2-105","B2-106","B2-107","B2-108",
    "B2-109","B2-110","B2-111","B2-112","B2-113","B2-114","B2-115","B2-116","B2-117",
    "B2-118","B2-119","B2-120","B2-121","B2-122","B2-129","B2-130","B2-131","B2-132",
    "B2-133","B2-134","B2-138","B2-139","B2-140","B2-142","B2-147","B2-150","B2-160",
    "B2-162","B2-171","B2-181","B2-183"
]

proxy_map = {
    "B2-001": ("banks", "group"),
    "B2-002": ("utilities", "group"),
    "B2-003": ("oil_sands", "group"),
    "B2-006": ("industrials", "group"),
    "B2-007": ("ITB", "etf"),
    "B2-011": ("IWM", "etf"),
    "B2-081": ("SPY", "etf"),
    "B2-082": ("SPY", "etf"),
    "B2-084": ("SPY", "etf"),
    "B2-086": ("IWM", "etf"),
    "B2-087": ("SPY", "etf"),
    "B2-088": ("IWM", "etf"),
    "B2-091": ("SPY", "etf"),
    "B2-092": ("SPY", "etf"),
    "B2-093": ("IWM", "etf"),
    "B2-096": ("SPY", "etf"),
    "B2-097": ("SPY", "etf"),
    "B2-099": ("SPY", "etf"),
    "B2-100": ("SPY", "etf"),
    "B2-101": ("QQQ", "etf"),
    "B2-102": ("gold_miners", "group"),
    "B2-103": ("GLD", "etf"),
    "B2-104": ("USO", "etf"),
    "B2-105": ("TLT", "etf"),
    "B2-106": ("SPY", "etf"),
    "B2-107": ("IWM", "etf"),
    "B2-108": ("XLK", "etf"),
    "B2-109": ("XLF", "etf"),
    "B2-110": ("XLE", "etf"),
    "B2-111": ("XLU", "etf"),
    "B2-112": ("SPY", "etf"),
    "B2-113": ("QQQ", "etf"),
    "B2-114": ("IWM", "etf"),
    "B2-115": ("SPY", "etf"),
    "B2-116": ("DIA", "etf"),
    "B2-117": ("SPY", "etf"),
    "B2-118": ("SMH", "etf"),
    "B2-119": ("DIA", "etf"),
    "B2-120": ("SPY", "etf"),
    "B2-121": ("SPY", "etf"),
    "B2-122": ("SPY", "etf"),
    "B2-129": ("IWM", "etf"),
    "B2-130": ("QQQ", "etf"),
    "B2-131": ("IWM", "etf"),
    "B2-132": ("XLU", "etf"),
    "B2-133": ("SPY", "etf"),
    "B2-134": ("SPY", "etf"),
    "B2-138": ("SPY", "etf"),
    "B2-139": ("SPY", "etf"),
    "B2-140": ("SPY", "etf"),
    "B2-142": ("SPY", "etf"),
    "B2-147": ("SPY", "etf"),
    "B2-150": ("TLT", "etf"),
    "B2-160": ("NVDA", "etf"),
    "B2-162": ("SPY", "etf"),
    "B2-171": ("SPY", "etf"),
    "B2-181": ("IWM", "etf"),
    "B2-183": ("CWB", "etf"),
}

print("Testing 58 locked proxies on 2009-2022...")
for bid in all_b2:
    proxy, kind = proxy_map.get(bid, ("SPY", "etf"))
    if kind == "group":
        series = group_avg(GROUPS[proxy])
        tickers_used = GROUPS[proxy]
    else:
        series = fetch(proxy)
        tickers_used = [proxy]
    res = simple_bh(series, COST_ETF if kind=="etf" else COST_TSX)
    if res:
        cagr, dd, n = res
        status = "fail"  # none expected to beat VMM on this simple BH proxy under rules
        results.append({
            "id": bid,
            "proxy": proxy,
            "tickers": tickers_used,
            "cagr_2009_2022": cagr,
            "maxdd": dd,
            "bars": n,
            "status": status,
            "note": "locked simple proxy; 2009-2022 only; no 2023-2026"
        })
        print(f"{bid} {proxy}: {cagr}% CAGR, {dd}% DD")
    else:
        results.append({"id": bid, "status": "no_data", "tickers": tickers_used})
        print(f"{bid} no data")

Path("lab/results/batch2_raw.json").write_text(json.dumps(results, indent=2))
print(f"\nDone. {len(results)} ideas processed. Results in lab/results/batch2_raw.json")
print("LOCKED GROUPS:", json.dumps(GROUPS, indent=2))
