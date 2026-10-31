"""List every stock (all markets) where the 'RSI2<10 in stage-2 & strong RS' setup
triggered on the target dates. Same entry/stop/target rules as lab/export_check.py.
Writes results/signals_2026-10-08.csv. Does not alter backtest or trading logic."""
import os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators, setups  # noqa: E402

TARGET_DATES = ["2026-10-07", "2026-10-08", "2026-10-09"]
STOP_ATR, TGT_ATR, MAX_GAP = 3.0, 6.0, 0.01
NAME = "RSI2<10 in stage-2 & strong RS"


def main(path="lab/data/prices.parquet"):
    os.makedirs("results", exist_ok=True)
    P = indicators.load_panel(path)
    I = indicators.build(P)
    S, _mkt = setups.all_setups(I)
    sig, _mode, _src = S[NAME]
    dates = list(sig.index)
    rows = []
    for d0 in TARGET_DATES:
        ts = pd.Timestamp(d0)
        if ts not in sig.index:
            print(f"{d0}: no trading data in panel", flush=True)
            continue
        i = dates.index(ts)
        if i + 1 >= len(dates):
            continue
        entry_dt = dates[i + 1]
        hits = sig.loc[ts]
        for t in hits[hits.astype(bool)].index:
            close = float(I["C"].at[ts, t])
            open_next = float(I["O"].at[entry_dt, t])
            if pd.isna(open_next) or pd.isna(close):
                continue
            gap_ok = open_next <= close * (1 + MAX_GAP)
            atr = float(I["atr14"].at[ts, t])
            rows.append({
                "signal_date": d0, "ticker": t,
                "market": "TSX" if t.endswith((".TO", ".V")) else ("NSE" if t.endswith(".NS") else "US"),
                "entry_date": entry_dt.date().isoformat(),
                "entry": round(open_next, 4),
                "stop": round(open_next - STOP_ATR * atr, 4),
                "target": round(open_next + TGT_ATR * atr, 4),
                "close_signal": round(close, 4),
                "gap_ok": gap_ok,
            })
    out = pd.DataFrame(rows)
    out.to_csv("results/signals_2026-10-08.csv", index=False)
    print(f"wrote results/signals_2026-10-08.csv rows={len(out)}", flush=True)
    if len(out):
        print(out.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
