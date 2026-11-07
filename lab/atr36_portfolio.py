"""Full portfolio simulation for the leader-dip signal with ATR 3 stop / 6 target, 30d hold.
Same rules as the leader_pullback block in refresh_card.py (slots=2).
Writes lab/results/atr36_yearly.csv with equity on a $1 and $2000 start.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import candidates, sim, portfolio  # noqa: E402

SLOTS = int(os.environ.get("SLOTS", "2"))
START_CAP = 2000.0


def main():
    I = candidates.prep()
    dates = I["C"].index.values
    s2, rs, r2, liq, mk = I["stage2"], I["rs_rank"], I["rsi2"], I["liquid"], I["mktc"]
    lead = (s2 & (rs > 0.8) & (r2 < 10) & liq & mk).fillna(False)

    ti, ei, xi, r = sim.simulate(I, lead, mode=0, stop_atr=3, tgt_atr=6, hold=30)
    rank = I["rs_rank"].values[ei, ti]
    p = portfolio.run(dates, ti, ei + 1, xi, r, rank=rank, slots=SLOTS)

    curve = p["curve"]
    # year-end equity (last available value in each year)
    ye = curve.resample("YE").last()
    # prepend start
    ye = pd.concat([pd.Series([1.0], index=[ye.index[0] - pd.offsets.YearEnd(1)]), ye])
    yret = ye.pct_change().dropna()

    out = pd.DataFrame({
        "year": yret.index.year,
        "return": yret.values,
        "equity_1": ye.iloc[1:].values,
        "equity_2000": (ye.iloc[1:].values * START_CAP).round(2),
    })
    os.makedirs("lab/results", exist_ok=True)
    out.to_csv("lab/results/atr36_yearly.csv", index=False)

    print("ATR 3/6 leader-dip portfolio (slots=%d)" % SLOTS)
    print(f"trades={len(r)}  win={ (r>0).mean():.3f}  avg={r.mean():.4f}")
    print(f"CAGR={p['cagr']:.3f}  max_dd={p['max_dd']:.3f}  win_months={p['win_months']:.3f}")
    print(out.to_string(index=False))
    print(f"\n$2000 start -> ${out.iloc[-1].equity_2000:,.0f} at last year-end")


if __name__ == "__main__":
    main()
