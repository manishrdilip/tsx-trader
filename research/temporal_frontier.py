"""Descriptive return-risk frontier for research-only 60-day chronological tests.
Not a corrected VMM comparison, untouched holdout, or forward validation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path("research/temporal_stability_results")

def main():
    d = pd.read_csv(ROOT / "block_comparison.csv")
    needed = {"strategy", "block", "cost_per_side", "net", "max_dd", "trades", "profit_factor", "expectancy_cad"}
    if missing := needed - set(d):
        raise ValueError(f"Missing columns: {sorted(missing)}")
    expected = {(m, b, c) for m in ("orb", "vwap", "bull_flag", "resistance", "mean_reversion")
                for b in (1, 2, 3) for c in (0.001, 0.0025, 0.005)}
    actual = set(zip(d["strategy"], d["block"], d["cost_per_side"]))
    if len(d) != 45 or actual != expected:
        raise ValueError("Expected complete 5-strategy x 3-block x 3-cost grid, without duplicates or substitutions")
    for field in ("net", "max_dd", "trades"):
        if not np.isfinite(pd.to_numeric(d[field], errors="coerce")).all():
            raise ValueError(f"Missing/nonfinite required metric: {field}")
    if (d.trades < 0).any() or (d.max_dd > 1e-9).any() or (d.max_dd < -1).any():
        raise ValueError("Invalid trade count or drawdown")
    # Same-cost, same-block comparisons only. Maximize net; minimize absolute drawdown.
    rows = []
    for (block, cost), g in d.groupby(["block", "cost_per_side"]):
        for _, r in g.iterrows():
            dd = abs(float(r.max_dd))
            dominated = any(
                (float(q.net) >= float(r.net) and abs(float(q.max_dd)) <= dd)
                and (float(q.net) > float(r.net) or abs(float(q.max_dd)) < dd)
                for _, q in g.iterrows()
            )
            rows.append(dict(strategy=r.strategy, block=int(block), cost_per_side=float(cost),
                             net_cad=float(r.net), max_drawdown_pct=round(dd*100, 3),
                             trades=int(r.trades), profit_factor=None if pd.isna(r.profit_factor) else float(r.profit_factor),
                             expectancy_cad=None if pd.isna(r.expectancy_cad) else float(r.expectancy_cad),
                             on_descriptive_frontier=not dominated))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "return_risk_frontier.csv", index=False)
    (ROOT / "frontier_audit.json").write_text(json.dumps({
        "validated_winner": False,
        "description": "Non-dominated net CAD profit vs absolute max drawdown within identical block and cost; descriptive only",
        "limitations": [
            "60-day Yahoo five-minute data previously explored: no untouched holdout",
            "Survivorship bias in currently listed tickers",
            "No observed bid/ask, market impact, queue position or forward paper trades",
            "No verified matched-period corrected VMM CAGR",
            "Max drawdown is sampled from daily equity, not intrabar adverse excursion",
            "Short-window profit must not be annualized into a credible CAGR"
        ]
    }, indent=2))
    print(out.to_string(index=False))

if __name__ == "__main__":
    main()
