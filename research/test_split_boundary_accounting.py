"""Research-only audit: correct split-boundary risk and return accounting.

A split must include the equity immediately preceding its first observation.
A local drawdown reset can hide a loss on the first day of validation.
No strategy or live trading code is imported or modified.
"""
import numpy as np
import pandas as pd


def segment_metrics(curve: pd.Series, start: str, end: str) -> dict:
    curve = curve.sort_index().astype(float)
    if curve.empty or curve.index.has_duplicates or not np.isfinite(curve).all() or (curve <= 0).any():
        raise ValueError("equity must be finite, positive, unique and chronological")
    selected = curve.loc[(curve.index >= pd.Timestamp(start)) & (curve.index < pd.Timestamp(end))]
    if selected.empty:
        raise ValueError("empty segment")
    first_index = curve.index.get_loc(selected.index[0])
    if first_index == 0:
        raise ValueError("missing preceding equity observation")
    initial = float(curve.iloc[first_index - 1])
    path = pd.concat([pd.Series([initial], index=[curve.index[first_index-1]]), selected])
    rets = path.pct_change().dropna()
    peak = path.cummax()
    dd = path / peak - 1
    years = len(rets) / 252
    return {
        "starting_equity": initial,
        "ending_equity": float(selected.iloc[-1]),
        "net_profit_cad": float(selected.iloc[-1] - initial),
        "cagr": float((selected.iloc[-1] / initial) ** (1 / years) - 1),
        "max_drawdown": float(dd.min()),
        "observations": len(rets),
        "sharpe": float(np.sqrt(252) * rets.mean() / rets.std(ddof=1)) if len(rets)>1 and rets.std(ddof=1)>0 else None,
    }


def test_first_day_crash():
    ix = pd.bdate_range("2021-12-29", periods=6)
    equity = pd.Series([5000, 5000, 3000, 3300, 3400, 3500], index=ix)
    m = segment_metrics(equity, str(ix[2].date()), "2022-02-01")
    assert m["starting_equity"] == 5000
    assert abs(m["max_drawdown"] + .4) < 1e-12
    assert m["observations"] == 4
    assert abs(m["net_profit_cad"] + 1500) < 1e-9
    # Incorrect reset would produce 0% max drawdown for the rising post-crash path.
    assert float((equity.iloc[2:] / equity.iloc[2:].cummax() - 1).min()) == 0


def test_boundary_gain_and_cash():
    ix = pd.bdate_range("2022-01-03", periods=5)
    equity = pd.Series([5000, 5500, 5500, 5500, 5500], index=ix)
    m = segment_metrics(equity, str(ix[1].date()), "2022-02-01")
    assert m["observations"] == 4
    assert abs(m["cagr"] - (1.1 ** 63 - 1)) < 1e-5
    assert m["max_drawdown"] == 0


def test_invalid_series():
    ix = pd.bdate_range("2022-01-03", periods=3)
    for values in ([5000, 0, 5000], [5000, np.nan, 5000]):
        try:
            segment_metrics(pd.Series(values, index=ix), "2022-01-04", "2022-02-01")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid equity was accepted")


if __name__ == "__main__":
    test_first_day_crash()
    test_boundary_gain_and_cash()
    test_invalid_series()
    print("PASS: split-boundary return and drawdown accounting audit")
