"""Simple combination of a basic VMM-style momentum equity curve and the ATR 3/6 leader-dip curve.
VMM-style: monthly rebalance to top 10% 12-month return names that are above their 200-day SMA,
market filter on, equal weight, up to 10 slots, on the full panel (TSX-centric filter).
Combination: 50/50 of the two monthly return series (rebalanced monthly).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import candidates, sim, portfolio, indicators  # noqa: E402

SLOTS_ATR = 2
SLOTS_VMM = 10
START_CAP = 2000.0


def vmm_curve(I):
    """Very simple monthly VMM: top 10% 12m return, above 200d, market up, equal weight."""
    C = I["C"]
    dates = C.index
    r12 = C.pct_change(252)
    above = C > I["sma200"]
    mkt = I["mkt_up"].reindex(dates).fillna(False)
    liquid = I["liquid"]

    # month-end dates
    month_ends = C.resample("ME").last().index
    equity = 1.0
    curve = {}
    holdings = []
    for i, me in enumerate(month_ends):
        if me not in C.index:
            # find last trading day <= me
            loc = dates[dates <= me]
            if len(loc) == 0:
                continue
            me = loc[-1]
        if not bool(mkt.loc[me]):
            # stay in cash
            curve[me] = equity
            holdings = []
            continue
        # rank
        rr = r12.loc[me]
        ok = above.loc[me] & liquid.loc[me] & rr.notna()
        if BENCH := "XIU.TO":
            ok = ok & (rr.index != BENCH)
        ranked = rr[ok].nlargest(max(1, int(0.1 * ok.sum())))
        picks = list(ranked.index[:SLOTS_VMM])
        if not picks:
            curve[me] = equity
            holdings = []
            continue
        # hold to next month-end (or last)
        if i + 1 < len(month_ends):
            nxt = month_ends[i + 1]
            loc = dates[dates <= nxt]
            nxt = loc[-1] if len(loc) else me
        else:
            nxt = dates[-1]
        rets = []
        for t in picks:
            if me in C.index and nxt in C.index and pd.notna(C.at[me, t]) and pd.notna(C.at[nxt, t]):
                rets.append(C.at[nxt, t] / C.at[me, t] - 1)
        if rets:
            equity *= (1 + np.mean(rets))
        curve[me] = equity
        holdings = picks
    s = pd.Series(curve).sort_index()
    return s


def main():
    I = candidates.prep()
    dates = I["C"].index.values

    # ATR 3/6 curve (already computed style)
    s2, rs, r2, liq, mk = I["stage2"], I["rs_rank"], I["rsi2"], I["liquid"], I["mktc"]
    lead = (s2 & (rs > 0.8) & (r2 < 10) & liq & mk).fillna(False)
    ti, ei, xi, r = sim.simulate(I, lead, mode=0, stop_atr=3, tgt_atr=6, hold=30)
    rank = I["rs_rank"].values[ei, ti]
    p_atr = portfolio.run(dates, ti, ei + 1, xi, r, rank=rank, slots=SLOTS_ATR)
    atr_curve = p_atr["curve"]

    # VMM-style curve
    vmm = vmm_curve(I)

    # align to monthly
    atr_m = atr_curve.resample("ME").last().ffill()
    vmm_m = vmm.resample("ME").last().ffill()
    common = atr_m.index.intersection(vmm_m.index)
    atr_m = atr_m.loc[common]
    vmm_m = vmm_m.loc[common]
    # normalize both to 1 at start of common period
    atr_n = atr_m / atr_m.iloc[0]
    vmm_n = vmm_m / vmm_m.iloc[0]
    # 50/50 combination (monthly rebalance)
    combo = (atr_n + vmm_n) / 2

    def yearly(s, label):
        ye = s.resample("YE").last()
        ye = pd.concat([pd.Series([1.0], index=[ye.index[0] - pd.offsets.YearEnd(1)]), ye])
        yret = ye.pct_change().dropna()
        return pd.DataFrame({
            "year": yret.index.year,
            f"{label}_ret": yret.values,
            f"{label}_eq2000": (ye.iloc[1:].values * START_CAP).round(2),
        })

    out = yearly(atr_n, "atr")
    out = out.merge(yearly(vmm_n, "vmm"), on="year", how="outer")
    out = out.merge(yearly(combo, "combo"), on="year", how="outer")
    os.makedirs("lab/results", exist_ok=True)
    out.to_csv("lab/results/vmm_atr_combo.csv", index=False)

    print("50/50 VMM-style + ATR 3/6 (normalized to common period)")
    print(out.to_string(index=False))
    print(f"\nATR final (from 1): {atr_n.iloc[-1]:.2f}")
    print(f"VMM final (from 1): {vmm_n.iloc[-1]:.2f}")
    print(f"Combo final (from 1): {combo.iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
