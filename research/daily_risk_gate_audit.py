"""Research-only risk gate for daily cash-ledger diagnostics.
No candidate qualifies without a corrected matched VMM baseline, untouched OOS,
and forward paper trading. Stop thresholds are labels, not executed orders.
"""
import json
from pathlib import Path
import pandas as pd

ROOT=Path("research/cash_ledger_audit_results")

def evaluate(df):
    required={"lookback","slots","cost","stop_audit_threshold","split","cagr","max_dd","net_profit_cad","trades"}
    if not required.issubset(df.columns):
        raise ValueError("missing ledger metrics")
    # A stop threshold is a diagnostic label: it cannot create independent strategies.
    key=["lookback","slots","cost","split"]
    for _,group in df.groupby(key,dropna=False):
        for col in ("cagr","max_dd","net_profit_cad","trades"):
            if group[col].nunique(dropna=False)!=1:
                raise AssertionError("non-executed stop label changed executable results: "+col)
    distinct=df.drop_duplicates(key).copy()
    distinct["risk_gate_pass"]=(distinct.max_dd>=-0.30)&(distinct.trades>=100)&(distinct.cagr>0)
    distinct["validated_3x_winner"]=False
    return distinct

def test_synthetic():
    rows=[]
    for stop in (.05,.10,.20):
        rows.append(dict(lookback=120,slots=5,cost=.0025,stop_audit_threshold=stop,
            split="validation",cagr=.016548,max_dd=-.980271,
            net_profit_cad=3.342363,trades=122))
    d=evaluate(pd.DataFrame(rows))
    assert len(d)==1
    assert not bool(d.iloc[0].risk_gate_pass)
    assert not bool(d.iloc[0].validated_3x_winner)
    bad=pd.DataFrame(rows)
    bad.loc[1,"cagr"]=.99
    try:
        evaluate(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("failed to catch diagnostic-label pseudo-strategy")

def main():
    test_synthetic()
    path=ROOT/"ledger_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    distinct=evaluate(pd.read_csv(path))
    distinct.to_csv(ROOT/"distinct_risk_frontier.csv",index=False)
    summary={"raw_split_rows":int(len(pd.read_csv(path))),
       "distinct_executable_split_rows":int(len(distinct)),
       "validation_risk_gate_pass":int(distinct.loc[distinct.split=="validation","risk_gate_pass"].sum()),
       "validated_3x_winners":0,
       "risk_gate":"diagnostic only: max drawdown >= -30%, >=100 trades, positive CAGR",
       "limitations":["not matched against corrected VMM","not untouched out of sample",
         "no forward paper trading","survivor-only Yahoo symbols","adjusted OHLC non-executable",
         "no observed spreads/slippage","stop thresholds are not executed"]}
    (ROOT/"risk_gate.json").write_text(json.dumps(summary,indent=2))
    print("PASS: independent stop-label invariance and risk-gate audit",summary)

if __name__=="__main__":
    main()
