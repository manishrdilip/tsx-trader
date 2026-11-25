# Batch 4 — regime switching (pre-registered before any result)

Idea (Dilip): read the market first, then choose the strategy, instead of one strategy always.
First-hour reading cannot be tested (EODHD plan: intraday 403). Daily/monthly readings only.

Menu (daily return streams already produced by Batch 1 full-engine runs at 0.5%/side, $5,000):
VMM_nopark, D_squeeze_10, G_sector_2, F_gaprev_10, XIU buy-and-hold, cash (0%).
A switch between menu items is charged 1.0% (sell + buy at 0.5% each).

Regime known at the close of the last day of month m-1, applied to month m:
- Scheme A (trend/fear): bull = XIU > 200d and XIU 3-month return > 0; pullback = XIU > 200d, 3m <= 0;
  weak = XIU < 200d and VIX < 25; fear = XIU < 200d and VIX >= 25.
- Scheme B (first day + trend): previous month's first-trading-day XIU return up/down x XIU above/below 200d.
  (Uses the previous month's first day, so it is known before the month starts.)
Selection (dev 2009-2022 only): in each regime, pick the menu item with the highest mean monthly return; if a regime has
< 6 dev months, use VMM_nopark. Then pick the scheme (A or B) with the higher dev Sharpe. Evaluate 2023-latest once.
Pass bar: eval CAGR >= VMM_nopark eval + 3 pts, drawdown no worse + 5, and better than VMM_nopark in dev.
(VMM_nopark is used because it is the strongest single strategy found; exact VMM shown too.)
