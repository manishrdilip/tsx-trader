"""Run every setup x every exit, with and without the TSX market filter.
Train = 2009-2018, Test (out-of-sample) = 2019-today.  Writes lab/results/grid.csv"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import indicators, setups, sim  # noqa: E402

SPLIT = "2019-01-01"
START = "2009-01-01"


def main(path="lab/data/prices.parquet", out="lab/results/grid.csv", only=None):
    t0 = time.time()
    P = indicators.load_panel(path, exclude=indicators.non_stocks(path))
    I = indicators.build(P)
    for k, v in list(I.items()):
        if isinstance(v, (pd.DataFrame, pd.Series)):
            I[k] = v.loc[START:]
    dates = I["C"].index.values
    S, mkt = setups.all_setups(I)
    print(f"panel {I['C'].shape}, {len(S)} setups, built in {time.time()-t0:.0f}s", flush=True)
    rows = []
    for name, (sig, mode, src) in S.items():
        if only and not any(o in name for o in only):
            continue
        for regime in ("all", "TSX>200d"):
            sg = sig & mkt if regime == "TSX>200d" else sig
            for ex, kw in setups.EXITS.items():
                ti, ei, xi, r = sim.simulate(I, sg, mode=mode, **kw)
                if len(r) == 0:
                    continue
                ei1 = ei + 1                       # entry day index
                tr, te = sim.summarize(dates, ti, ei1, xi, r, SPLIT)
                row = dict(setup=name, regime=regime, exit=ex, entry="buy-stop" if mode else "next open", source=src)
                for tag, st in (("train", tr), ("test", te)):
                    for k2, v2 in (st or {}).items():
                        row[f"{tag}_{k2}"] = v2
                rows.append(row)
        print(f"  {name}  ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)
    print("done", len(df), "rows", f"{time.time()-t0:.0f}s")
    return df


if __name__ == "__main__":
    main()
