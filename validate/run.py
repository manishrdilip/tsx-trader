"""Pre-registered validation of two candidates on frozen data.
Selection rule (fixed before running): pick the candidate with the higher TRAIN CAGR.
Then report its TEST result (2022-01-01 to end) once. Pass criteria are in PASS.
Usage: python validate/run.py path/to/prices.parquet
"""
import json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine

TRAIN = ("2016-10-31", "2021-12-31")
TEST = ("2022-01-01", "2026-10-30")
CANDIDATES = {"A_4of4": False, "B_4of4_index_filter": True}
PASS = dict(beats_bench=True, max_dd_pct=-25.0, min_trades=100, min_years_positive_pct=60.0)


def run(path):
    bars, bench = engine.load_tsx(path)
    print(f"tickers {len(bars)}, bench rows {len(bench)}", flush=True)
    out = {}
    for name, idx in CANDIDATES.items():
        sig = engine.signals(bars, bench, idx)
        res = {}
        for label, (s, e) in [("train", TRAIN), ("test", TEST)]:
            eq, tr = engine.simulate(bars, sig, pd.Timestamp(s), pd.Timestamp(e))
            res[label] = engine.metrics(eq, tr, bench, pd.Timestamp(s), pd.Timestamp(e))
            print(name, label, {k: res[label][k] for k in ("return_pct", "cagr_pct", "max_dd_pct", "bench_return_pct", "trades")}, flush=True)
        out[name] = res
    chosen = max(CANDIDATES, key=lambda n: out[n]["train"]["cagr_pct"])
    t = out[chosen]["test"]
    verdict = {
        "beats_bench": bool(float(t["return_pct"]) > float(t["bench_return_pct"])),
        "max_dd_ok": bool(float(t["max_dd_pct"]) >= PASS["max_dd_pct"]),
        "trades_ok": bool(t["trades"] >= PASS["min_trades"]),
        "years_ok": bool(float(t["years_positive_pct"]) >= PASS["min_years_positive_pct"]),
    }
    verdict["PASS"] = all(verdict.values())
    result = {"chosen_on_train": chosen, "candidates": out, "test_verdict": verdict,
              "criteria": PASS, "data": os.path.basename(path)}
    os.makedirs("results/validate", exist_ok=True)
    json.dump(result, open("results/validate/validation.json", "w"), indent=2, default=str)
    print("CHOSEN (train CAGR):", chosen, flush=True)
    print("TEST:", json.dumps(t, default=str), flush=True)
    print("VERDICT:", json.dumps(verdict), flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
