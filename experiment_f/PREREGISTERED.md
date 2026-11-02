# Experiment F - pre-registered tests (frozen 2026-11-02, before any result)

Research only. Not financial advice. Frozen rules: do not change after the first run.

## Baseline
Experiment E frozen v1: monthly, top 20 by 252-day return, inverse-volatility weights, no regime filter,
0.10% per side. Reported unchanged as the baseline for every F test.

## Periods (non-overlapping)
- Training: 2006-01-01 to 2015-12-31. Used to develop and select.
- Validation: 2016-01-01 to 2021-12-31. Compare survivors. Limited changes only.
- Final holdout: 2022-01-01 to 2026-11-02. One evaluation, after all decisions are frozen.
  This period has been seen in earlier experiments, so it is contaminated and labelled as such.

## The five tests (each run once on training, survivors on validation, holdout once)
1. T1 Trend filter: hold the E picks only when XIU closes above its 200-day average; otherwise hold cash.
2. T2 Volatility-scaled sizing: each position targets the same dollar risk (ATR-based), not inverse-volatility weights.
3. T3 Drawdown cut: halve exposure after the portfolio falls 10% from its peak; restore full exposure when it recovers to the prior peak.
4. T4 Per-stock stop: exit any position that closes 15% below its entry price; re-entry only at the next monthly rebalance.
5. T5 Fewer names: top 10 instead of top 20, otherwise identical to baseline.

Trials counted: 5 variants + baseline = 6. Results are corrected for this count and for earlier experiments.

## Pass/fail gates (all must pass to be called a pass)
- G1 Net CAGR at least 15% over 2006-2026 (stretch target 20%).
- G2 Maximum drawdown no worse than -25% over 2006-2026 (stretch target -20%).
- G3 Still profitable (CAGR above 0%) at doubled transaction costs.
- G4 Calendar-year rule: returns measured from the last trading day's close to the next year's last trading day's close,
  net of dividends, costs and cash. A year is negative if below 0%. At most one negative year in ten; worst year no worse than -10%.
  Each period reports its number of annual observations and percent of time invested, so holding cash cannot pass.
- G5 Concentration: performance excluding the five largest contributing stocks stays above 0% CAGR.
- G6 Holdout: the same rules pass on 2022-2026 (one evaluation only, no changes after it).

## Reporting (mandatory)
Annual return per year; worst rolling 12-month return; max drawdown and recovery time; trades, turnover, average holding
period; results excluding top-5 contributors; results by regime (XIU above/below 200-day) and by sector if available;
results at normal and doubled costs; equal-weight benchmark and XIU total return (with dividends); every configuration
tried, including failures; every parameter change.

## Known limits (stated before results)
- Survivorship bias: universe is today's TSX listings. All results are provisional until this is measured.
- Universe excludes 144 names that could not be classified (rate limits, no quote type).
- Costs are flat 0.10% per side. Real spreads on small TSX Venture names are likely wider.
- The 2022-2026 holdout has been examined earlier, so it is not clean.

## Decision rule
If no variant passes all gates, the result is: none of the tested variants passed. Gates are not loosened after results.
