"""
Improved risk management helpers.
Use these in scanners and auto-trader for better drawdown control.

- Base risk scales down in weak market regimes
- Portfolio-level open-risk cap
- Volatility-aware sizing
"""
from __future__ import annotations

RISK_PER_TRADE = 0.015          # 1.5% base (down from 2%)
MAX_PORTFOLIO_RISK = 0.06       # total open risk ceiling
WEAK_REGIME_MULTIPLIER = 0.5    # half size when market is weak


def effective_risk(regime_weak: bool, open_risk_pct: float = 0.0) -> float:
    """Return the risk fraction to use for the next trade."""
    base = RISK_PER_TRADE * (WEAK_REGIME_MULTIPLIER if regime_weak else 1.0)
    remaining = max(0.0, MAX_PORTFOLIO_RISK - open_risk_pct)
    return min(base, remaining)


def shares_for_risk(entry: float, stop_pct: float, account: float,
                    regime_weak: bool = False, open_risk_pct: float = 0.0) -> int:
    """Calculate share quantity that respects risk rules."""
    if entry <= 0 or stop_pct <= 0:
        return 0
    risk_frac = effective_risk(regime_weak, open_risk_pct)
    risk_dollars = account * risk_frac
    shares = int(risk_dollars / (entry * stop_pct))
    # never put more than 20% of account in one name
    max_by_capital = int(account * 0.20 / entry)
    return max(0, min(shares, max_by_capital))


def regime_is_weak(price: float, sma200: float) -> bool:
    return price < sma200
