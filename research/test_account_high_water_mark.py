"""Research-only audit: segment drawdown must respect the account's prior high-water mark.

A one-day boundary carry fixes first-day return omission but does NOT preserve
drawdown from peaks earlier than the immediately preceding session.
This module is standalone and does not alter live trading or the existing ledger.
"""
import unittest
import numpy as np
import pandas as pd


def account_drawdown_in_window(equity: pd.Series, start, end):
    """Drawdown of the actual continuous account over [start,end], with full prior peak."""
    s = equity.astype(float).sort_index()
    if s.empty or not s.index.is_unique or not np.isfinite(s.to_numpy()).all() or (s <= 0).any():
        raise ValueError("equity must be positive, finite, nonempty and unique-indexed")
    window = s.loc[start:end]
    if window.empty:
        raise ValueError("empty segment")
    running_peak = s.cummax().reindex(window.index)
    return float((window / running_peak - 1).min())


def segment_local_drawdown(equity: pd.Series, start, end):
    """Diagnostic only: previous-day boundary but NOT lifetime account drawdown."""
    s = equity.sort_index()
    window = s.loc[start:end]
    if window.empty:
        raise ValueError("empty segment")
    i = s.index.get_loc(window.index[0])
    if i:
        window = pd.concat([s.iloc[[i - 1]], window])
    return float((window / window.cummax() - 1).min())


class HighWaterMarkRegression(unittest.TestCase):
    def setUp(self):
        self.days = pd.bdate_range("2022-01-03", periods=8)
        self.eq = pd.Series([5000., 9000., 8000., 7000., 6500., 6000., 6200., 6400.], index=self.days)

    def test_prior_peak_not_reset_at_validation_boundary(self):
        start = self.days[5]
        self.assertAlmostEqual(segment_local_drawdown(self.eq, start, self.days[-1]), -500 / 6500)
        self.assertAlmostEqual(account_drawdown_in_window(self.eq, start, self.days[-1]), -1 / 3)

    def test_drawdown_cannot_improve_by_resegmenting_same_account(self):
        whole = account_drawdown_in_window(self.eq, self.days[0], self.days[-1])
        later = account_drawdown_in_window(self.eq, self.days[3], self.days[-1])
        self.assertAlmostEqual(whole, later)

    def test_future_values_do_not_change_historical_drawdown(self):
        altered = self.eq.copy()
        altered.iloc[-1] = 100000.
        self.assertEqual(
            account_drawdown_in_window(self.eq, self.days[3], self.days[6]),
            account_drawdown_in_window(altered, self.days[3], self.days[6]),
        )

    def test_invalid_or_empty_equity_rejected(self):
        with self.assertRaises(ValueError):
            account_drawdown_in_window(self.eq, "2030-01-01", "2031-01-01")
        bad = self.eq.copy()
        bad.iloc[2] = np.nan
        with self.assertRaises(ValueError):
            account_drawdown_in_window(bad, self.days[4], self.days[-1])


if __name__ == "__main__":
    unittest.main()
