"""Research-only robust screening of 45 chronological/cost experiments.
A screening score is NOT a VMM comparison or independent validation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path("research/temporal_stability_results")
def main():
    p=ROOT/"block_comparison.csv"
    if not p.exists(): raise FileNotFoundError("Run temporal_stability.py first")
    d=pd.read_csv(p)
    required={"block","cost_per_side","return_pct","net","method"}
    if missing:=required-set(d.columns): raise ValueError(f"Missing columns: {sorted(missing)}")
    if d.duplicated(["method","block","cost_per_side"]).any(): raise ValueError("Duplicate test cells")
    if d.isna().any().any(): raise ValueError("Incomplete experiment cells")
    out=[]
    for method,g in d.groupby("method"):
        if len(g)!=9 or set(g.block)!=set((1,2,3)) or len(g.cost_per_side.unique())!=3:
            raise ValueError(f"Incomplete 3 x 3 cost/block grid: {method}")
        high=g[g.cost_per_side==max(g.cost_per_side)]
        low=g[g.cost_per_side==min(g.cost_per_side)]
        # Consistency across time and adverse costs is mandatory even for preliminary screening.
        out.append(dict(method=method,positive_blocks_high_cost=int((high.net>0).sum()),
            worst_block_return_pct=float(high.return_pct.min()),
            median_high_cost_return_pct=float(high.return_pct.median()),
            mean_high_cost_return_pct=float(high.return_pct.mean()),
            mean_low_cost_return_pct=float(low.return_pct.mean()),
            cost_sensitivity_pct_points=float(low.return_pct.mean()-high.return_pct.mean()),
            all_blocks_profitable_at_high_cost=bool((high.net>0).all()),
            eligible_for_independent_validation=bool((high.net>0).all()),
            validated_3x_vmm=False))
    out=sorted(out,key=lambda z:(z["positive_blocks_high_cost"],z["median_high_cost_return_pct"]),reverse=True)
    ROOT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(out).to_csv(ROOT/"robustness_screen.csv",index=False)
    (ROOT/"robustness_audit.json").write_text(json.dumps({
      "screening_only":True,"winner_verified":False,
      "warning":"Historical 60-day windows previously explored; not untouched holdout or forward paper trading",
      "baseline":"Corrected matched-period VMM CAGR not available",
      "interpretation":"Profitable in all 3 blocks at highest tested costs is necessary for further research, not proof of an edge",
      "results":out},indent=2))
    print(pd.DataFrame(out).to_string(index=False))
if __name__=="__main__":main()
