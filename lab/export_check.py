"""Export daily prices and leader-pullback signals for TD.TO and RY.TO.
Reads lab/data/prices.parquet (available on the runner after fetch_data.py).
Writes results/tdry_check.csv and results/tdry_signals.csv.
Does not alter any backtest or trading logic.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators, setups  # noqa: E402

TICKERS = ["TD.TO", "RY.TO"]
START = "2026-09-01"
# Leader-pullback trade rules (from leaders.py, the setup that survived lab testing)
STOP_ATR = 3.0
TGT_ATR = 6.0
MAX_GAP = 0.01


def main(path="lab/data/prices.parquet"):
    os.makedirs("results", exist_ok=True)

    # --- daily prices for the two names ---
    raw = pd.read_parquet(path)
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["ticker"] = raw["ticker"].astype(str)
    sub = raw[raw["ticker"].isin(TICKERS) & (raw["Date"] >= START)].copy()
    sub = sub.sort_values(["ticker", "Date"])
    sub = sub[["Date", "ticker", "Open", "High", "Low", "Close", "Volume"]]
    sub.to_csv("results/tdry_check.csv", index=False)
    print(f"wrote results/tdry_check.csv  rows={len(sub)}", flush=True)

    # --- leader-pullback signals (same stage-2 + strong RS + RSI2<10 as lab/setups.py) ---
    P = indicators.load_panel(path)
    I = indicators.build(P)
    S, mkt = setups.all_setups(I)
    # The lab setup that matches the leader-pullback core filters
    name = "RSI2<10 in stage-2 & strong RS"
    if name not in S:
        print(f"setup '{name}' not found; available: {list(S)[:5]}...", flush=True)
        pd.DataFrame().to_csv("results/tdry_signals.csv", index=False)
        return
    sig, mode, _src = S[name]
    # restrict to our two tickers
    cols = [c for c in sig.columns if c in TICKERS]
    if not cols:
        print("TD.TO / RY.TO not in panel", flush=True)
        pd.DataFrame().to_csv("results/tdry_signals.csv", index=False)
        return
    sig = sig[cols]
    dates = sig.index

    rows = []
    for t in cols:
        s = sig[t]
        for i, dt in enumerate(dates):
            if not bool(s.iloc[i]):
                continue
            # entry next open (mode 0), subject to max-gap
            if i + 1 >= len(dates):
                continue
            entry_dt = dates[i + 1]
            close = float(I["C"].at[dt, t])
            open_next = float(I["O"].at[entry_dt, t])
            if not (open_next <= close * (1 + MAX_GAP)):
                continue  # gap chase skipped
            atr = float(I["atr14"].at[dt, t])
            entry = open_next
            stop = entry - STOP_ATR * atr
            target = entry + TGT_ATR * atr
            rows.append({
                "signal_date": dt.date().isoformat(),
                "ticker": t,
                "entry_date": entry_dt.date().isoformat(),
                "entry": round(entry, 4),
                "stop": round(stop, 4),
                "target": round(target, 4),
                "atr14": round(atr, 4),
                "close_signal": round(close, 4),
            })

    out = pd.DataFrame(rows)
    out.to_csv("results/tdry_signals.csv", index=False)
    print(f"wrote results/tdry_signals.csv  rows={len(out)}", flush=True)
    if len(out):
        print(out.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
