"""ATR 3/6 leader-dip portfolio on NSE only.
Market filter = NIFTYBEES.NS above its 200-day SMA.
RS rank computed among liquid NSE names.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators, sim, portfolio  # noqa: E402

SLOTS = int(os.environ.get("SLOTS", "2"))
START_CAP = 2000.0  # in local currency units for scaling; report both
BENCH = "NIFTYBEES.NS"


def main(path="lab/data/prices.parquet"):
    # load and keep only NSE + benchmark
    raw = pd.read_parquet(path)
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["ticker"] = raw["ticker"].astype(str)
    raw = raw[raw.ticker.str.endswith(".NS") | (raw.ticker == BENCH)]
    if BENCH not in raw.ticker.unique():
        print("NIFTYBEES.NS missing; aborting")
        return
    # write a temporary filtered parquet for load_panel
    tmp = "/tmp/nse_prices.parquet"
    raw.to_parquet(tmp, index=False)

    P = indicators.load_panel(tmp)
    I = indicators.build(P, market=BENCH)
    for k, v in list(I.items()):
        if isinstance(v, (pd.DataFrame, pd.Series)):
            I[k] = v.loc["2009-01-01":]

    C = I["C"]
    stage2 = ((C > I["sma50"]) & (I["sma50"] > I["sma150"]) & (I["sma150"] > I["sma200"])
              & (I["sma200"] > I["sma200"].shift(21))
              & (C >= 1.3 * I["lo252"]) & (C >= 0.75 * I["hi252"]))
    # market up using the same rule as indicators (mkt_up already built with BENCH)
    mkt = I["mkt_up"].reindex(C.index).fillna(False)
    mktc = pd.DataFrame(np.repeat(mkt.values[:, None], C.shape[1], 1),
                        index=C.index, columns=C.columns)
    lead = (stage2 & (I["rs_rank"] > 0.8) & (I["rsi2"] < 10) & I["liquid"] & mktc).fillna(False)
    # drop the benchmark itself from signals
    if BENCH in lead.columns:
        lead[BENCH] = False

    dates = C.index.values
    ti, ei, xi, r = sim.simulate(I, lead, mode=0, stop_atr=3, tgt_atr=6, hold=30)
    rank = I["rs_rank"].values[ei, ti]
    p = portfolio.run(dates, ti, ei + 1, xi, r, rank=rank, slots=SLOTS)

    curve = p["curve"]
    ye = curve.resample("YE").last()
    ye = pd.concat([pd.Series([1.0], index=[ye.index[0] - pd.offsets.YearEnd(1)]), ye])
    yret = ye.pct_change().dropna()

    out = pd.DataFrame({
        "year": yret.index.year,
        "return": yret.values,
        "equity_1": ye.iloc[1:].values,
        "equity_2000": (ye.iloc[1:].values * START_CAP).round(2),
    })
    os.makedirs("lab/results", exist_ok=True)
    out.to_csv("lab/results/india_atr36_yearly.csv", index=False)

    print("NSE ATR 3/6 leader-dip (slots=%d)" % SLOTS)
    print(f"trades={len(r)}  win={(r>0).mean():.3f}  avg={r.mean():.4f}")
    print(f"CAGR={p['cagr']:.3f}  max_dd={p['max_dd']:.3f}  win_months={p['win_months']:.3f}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
