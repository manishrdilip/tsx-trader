"""Regression: split drawdown must retain lifetime high-water mark.
Synthetic fixtures only; no strategy-performance evidence.
"""
import pathlib
import pandas as pd

def lifetime_drawdown(equity, selected):
    peak=equity.loc[:selected.index[-1]].cummax().reindex(selected.index).clip(lower=5000.)
    return float((selected/peak-1).min())

def test_boundary():
    ix=pd.bdate_range("2021-12-29",periods=6)
    equity=pd.Series([5000.,5000.,3000.,3300.,3400.,3500.],index=ix)
    selected=equity.iloc[2:]
    boundary=equity.index.get_loc(selected.index[0])
    path_equity=pd.concat([equity.iloc[[boundary-1]],selected])
    assert abs(lifetime_drawdown(equity,selected)+0.4)<1e-12
    daily=path_equity.pct_change().dropna()
    assert abs(float(daily.iloc[0])+0.4)<1e-12
    assert len(daily)==len(selected)
    assert float((selected/selected.cummax()-1).min())==0.0

def test_old_peak():
    ix=pd.bdate_range("2021-12-20",periods=7)
    equity=pd.Series([5000.,9000.,8000.,7000.,6000.,6500.,6700.],index=ix)
    selected=equity.iloc[4:]
    assert abs(lifetime_drawdown(equity,selected)+1/3)<1e-12
    previous_only=pd.concat([equity.iloc[[3]],selected])
    assert abs(float((previous_only/previous_only.cummax()-1).min())) < 1/3

def test_production_contract():
    src=(pathlib.Path(__file__).parent/"daily_cash_ledger_audit.py").read_text()
    assert "curve.loc[:c.index[-1]].cummax().reindex(c.index)" in src
    assert "daily=path_equity.pct_change().dropna()" in src
    assert "dd=float((c/c.cummax()-1).min())" not in src

if __name__=="__main__":
    test_boundary()
    test_old_peak()
    test_production_contract()
    print("PASS: lifetime cash ledger high-water-mark boundary tests")
