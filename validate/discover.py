"""Pattern discovery on TSX, pre-specified features only.
Discovery: 2016-10-31 .. 2021-12-31. Confirmation: 2022-01-01 .. 2026-10-30.
Outcome: enter next open, hold 10 trading days, return after 0.2% round-trip cost.
Compare each feature's average outcome with the average for all days in the same period.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import engine, candles

H, COST = 10, 0.002
TR = (pd.Timestamp("2016-10-31"), pd.Timestamp("2021-12-31"))
CF = (pd.Timestamp("2022-01-01"), pd.Timestamp("2026-10-30"))

def features(d):
    c = d.Close
    f = pd.DataFrame(index=d.index)
    f["rsi2_lt10"] = (d.rsi14 < 0) | False  # placeholder replaced below
    r2 = 100 - 100 / (1 + (c.diff().clip(lower=0).rolling(2).mean() / (-c.diff().clip(upper=0)).rolling(2).mean().replace(0, np.nan)))
    f["rsi2_lt10"] = r2 < 10
    f["rsi14_lt30"] = d.rsi14 < 30
    f["above_sma200"] = c > d.sma200
    f["sma50_gt_sma200"] = d.sma50 > d.sma200
    f["dist_sma200_lt_m5pct"] = (c / d.sma200 - 1) < -0.05
    f["new_52w_high"] = c >= c.rolling(252).max()
    f["vol_spike_2x"] = d.Volume > 2 * d.vol20
    f["down_3d"] = c < c.shift(3)
    f["gap_up_2pct"] = d.Open > c.shift(1) * 1.02
    f["candle_bull"] = candles.signal(d).reindex(d.index).fillna(False)
    f["macd_cross_up"] = (d.macd > d.macd_sig) & (d.macd.shift(1) <= d.macd_sig.shift(1))
    return f.fillna(False).astype(bool)

def main(path):
    bars, bench = engine.load_tsx(path)
    rows = []
    for t, d in bars.items():
        f = features(d)
        fwd = d.Open.shift(-(H + 1)) / d.Open.shift(-1) - 1 - COST   # enter next open, exit H days later open
        for name in f.columns:
            for label, (a, b) in [("train", TR), ("test", CF)]:
                m = (d.index >= a) & (d.index <= b)
                sel = m & f[name].values & fwd.notna().values
                allm = m & fwd.notna().values
                rows.append((name, label, t, int(sel.sum()), fwd[sel].sum(), fwd[allm].sum(), allm.sum()))
    df = pd.DataFrame(rows, columns=["feature", "period", "ticker", "n", "sum_sel", "sum_all", "n_all"])
    g = df.groupby(["feature", "period"])[["n", "sum_sel", "sum_all", "n_all"]].sum().reset_index()
    g["avg_sel_pct"] = 100 * g.sum_sel / g.n
    g["avg_all_pct"] = 100 * g.sum_all / g.n_all
    g["edge_pct"] = g.avg_sel_pct - g.avg_all_pct
    out = g.pivot(index="feature", columns="period", values=["n", "avg_sel_pct", "edge_pct"])
    out.columns = [f"{a}_{b}" for a, b in out.columns]
    out = out.sort_values("edge_pct_train", ascending=False).round(3)
    os.makedirs("results/validate", exist_ok=True)
    out.to_csv("results/validate/discovery_features.csv")
    print(out.to_string())

if __name__ == "__main__":
    main(sys.argv[1])
