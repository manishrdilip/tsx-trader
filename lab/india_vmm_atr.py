"""India (NSE) ATR 3/6 leader-dip + VMM-style combo from earliest available (aim 1998).
Market filter prefers NIFTYBEES.NS, falls back to ^NSEI if present and longer.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators, sim, portfolio  # noqa: E402

SLOTS_ATR = 2
SLOTS_VMM = 10
START_CAP = 2000.0
START = "1998-01-01"


def choose_bench(tickers):
    for b in ("NIFTYBEES.NS", "^NSEI"):
        if b in tickers:
            return b
    return None


def vmm_curve(I, bench):
    C = I["C"]
    dates = C.index
    r12 = C.pct_change(252)
    above = C > I["sma200"]
    mkt = I["mkt_up"].reindex(dates).fillna(False)
    liquid = I["liquid"]
    month_ends = C.resample("ME").last().index
    equity = 1.0
    curve = {}
    for i, me in enumerate(month_ends):
        if me not in C.index:
            loc = dates[dates <= me]
            if len(loc) == 0:
                continue
            me = loc[-1]
        if not bool(mkt.loc[me]):
            curve[me] = equity
            continue
        rr = r12.loc[me]
        ok = above.loc[me] & liquid.loc[me] & rr.notna()
        if bench in rr.index:
            ok = ok & (rr.index != bench)
        ranked = rr[ok].nlargest(max(1, int(0.1 * ok.sum())))
        picks = list(ranked.index[:SLOTS_VMM])
        if not picks:
            curve[me] = equity
            continue
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
    return pd.Series(curve).sort_index()


def main(path="lab/data/prices.parquet"):
    raw = pd.read_parquet(path)
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    raw["ticker"] = raw["ticker"].astype(str)
    raw = raw[raw.ticker.str.endswith(".NS") | raw.ticker.isin(["NIFTYBEES.NS", "^NSEI"])]
    bench = choose_bench(raw.ticker.unique())
    if bench is None:
        print("No NSE benchmark found; aborting")
        return
    print(f"Using market filter: {bench}", flush=True)
    tmp = "/tmp/nse_prices.parquet"
    raw.to_parquet(tmp, index=False)

    P = indicators.load_panel(tmp)
    I = indicators.build(P, market=bench)
    for k, v in list(I.items()):
        if isinstance(v, (pd.DataFrame, pd.Series)):
            I[k] = v.loc[START:]

    C = I["C"]
    print(f"Panel date range: {C.index.min().date()} to {C.index.max().date()}", flush=True)
    stage2 = ((C > I["sma50"]) & (I["sma50"] > I["sma150"]) & (I["sma150"] > I["sma200"])
              & (I["sma200"] > I["sma200"].shift(21))
              & (C >= 1.3 * I["lo252"]) & (C >= 0.75 * I["hi252"]))
    mkt = I["mkt_up"].reindex(C.index).fillna(False)
    mktc = pd.DataFrame(np.repeat(mkt.values[:, None], C.shape[1], 1),
                        index=C.index, columns=C.columns)
    lead = (stage2 & (I["rs_rank"] > 0.8) & (I["rsi2"] < 10) & I["liquid"] & mktc).fillna(False)
    if bench in lead.columns:
        lead[bench] = False

    dates = C.index.values
    ti, ei, xi, r = sim.simulate(I, lead, mode=0, stop_atr=3, tgt_atr=6, hold=30)
    rank = I["rs_rank"].values[ei, ti]
    p = portfolio.run(dates, ti, ei + 1, xi, r, rank=rank, slots=SLOTS_ATR)
    atr_curve = p["curve"]

    vmm = vmm_curve(I, bench)

    atr_m = atr_curve.resample("ME").last().ffill()
    vmm_m = vmm.resample("ME").last().ffill()
    common = atr_m.index.intersection(vmm_m.index)
    atr_n = (atr_m.loc[common] / atr_m.loc[common].iloc[0])
    vmm_n = (vmm_m.loc[common] / vmm_m.loc[common].iloc[0])
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
    out.to_csv("lab/results/india_vmm_atr_long.csv", index=False)

    print("NSE ATR 3/6 + VMM (earliest available, target from 1998)")
    print(f"ATR trades={len(r)}  win={(r>0).mean():.3f}  CAGR={p['cagr']:.3f}  max_dd={p['max_dd']:.3f}")
    print(f"ATR final: {atr_n.iloc[-1]:.2f}x  |  VMM final: {vmm_n.iloc[-1]:.2f}x  |  Combo final: {combo.iloc[-1]:.2f}x")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
