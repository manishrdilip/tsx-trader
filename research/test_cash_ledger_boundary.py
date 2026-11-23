"""Regression for segment risk metrics: first validation-day crash cannot disappear.
Research only. Synthetic fixtures, not market performance evidence.
"""
import pathlib
import pandas as pd

def test_boundary():
    ix=pd.bdate_range("2021-12-29",periods=6)
    equity=pd.Series([5000.,5000.,3000.,3300.,3400.,3500.],index=ix)
    selected=equity.iloc[2:]
    boundary=equity.index.get_loc(selected.index[0])
    path_equity=pd.concat([equity.iloc[[boundary-1]],selected])
    dd=float((path_equity/path_equity.cummax()-1).min())
    assert abs(dd+0.4)<1e-12
    daily=path_equity.pct_change().dropna()
    assert abs(float(daily.iloc[0])+0.4)<1e-12
    assert len(daily)==len(selected)
    assert float((selected/selected.cummax()-1).min())==0.0

def test_production_contract():
    src=(pathlib.Path(__file__).parent/"daily_cash_ledger_audit.py").read_text()
    assert "path_equity/path_equity.cummax()" in src
    assert "daily=path_equity.pct_change().dropna()" in src
    assert "dd=float((c/c.cummax()-1).min())" not in src

if __name__=="__main__":
    test_boundary()
    test_production_contract()
    print("PASS: cash ledger boundary risk accounting")
