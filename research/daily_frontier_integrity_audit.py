"""Research-only independent frontier integrity checks; never declares a 3x winner.
Only distinct executable parameter combinations count; stop labels are diagnostics.
A frontier cannot compare differing cost scenarios or split periods as if matched.
"""
import pandas as pd
from daily_risk_gate_audit import evaluate

METRICS = ("cagr", "max_dd", "net_profit_cad", "trades")

def frontier(df, split="validation", cost=0.0025):
    distinct = evaluate(df)
    x = distinct.loc[(distinct["split"] == split) &
                     ((distinct["cost"] - cost).abs() < 1e-10)].copy()
    if x.empty:
        raise ValueError("no matched cost/split observations")
    if x[list(METRICS)].isna().any().any():
        raise ValueError("missing performance or sample-size metrics")
    # Risk is better when max_dd is closer to zero (less negative).
    x["pareto_efficient"] = [
        not any(
            (other.cagr >= row.cagr and other.max_dd >= row.max_dd) and
            (other.cagr > row.cagr or other.max_dd > row.max_dd)
            for j, other in x.iterrows() if j != i
        )
        for i, row in x.iterrows()
    ]
    # Diagnostic only: this is not independent OOS or forward evidence.
    x["validated_3x_winner"] = False
    return x

def test_synthetic():
    rows = []
    for lookback, cagr, dd in [(20,.12,-.20),(60,.08,-.10),(120,.05,-.30)]:
        for stop in (.05,.10,.20):
            rows.append(dict(lookback=lookback,slots=3,cost=.0025,
                stop_audit_threshold=stop,split="validation",cagr=cagr,
                max_dd=dd,net_profit_cad=5000*cagr,trades=200))
    result=frontier(pd.DataFrame(rows))
    assert len(result)==3
    assert set(result.loc[result.pareto_efficient,"lookback"])=={20,60}
    assert not result.validated_3x_winner.any()
    bad=pd.DataFrame(rows)
    bad.loc[1,"net_profit_cad"]+=1
    try: frontier(bad)
    except AssertionError: pass
    else: raise AssertionError("non-executed stop label was counted as independent")
    bad=pd.DataFrame(rows)
    bad.loc[0,"max_dd"]=float("nan")
    try: frontier(bad)
    except AssertionError: pass
    else: raise AssertionError("missing stop-label metric was not detected")

if __name__=="__main__":
    test_synthetic()
    source=pd.read_csv("research/cash_ledger_audit_results/ledger_metrics.csv")
    result=frontier(source)
    result.to_csv("research/cash_ledger_audit_results/matched_cost_pareto_frontier.csv",index=False)
    print("PASS: matched-cost frontier; distinct strategies:",len(result),
          "Pareto:",int(result.pareto_efficient.sum()),"validated winners: 0")
