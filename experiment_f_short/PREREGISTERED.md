# Experiment F-short - four short-term families (pre-registered, frozen before any run)

Named F-short to keep it separate from the earlier Experiment F. Research only. Not financial advice.
Experiment E stays frozen as the baseline. Nothing here changes after the first run.

## Universe and data
- Frozen universe: experiment_e/universe.json (1,822 TSX equities, classification incomplete; 144 unclassified names excluded).
- Data: Yahoo daily OHLCV, auto-adjusted. Known limits: survivorship bias (today's listings), no point-in-time membership.
- Liquidity at signal close s (no look-ahead): close >= $1.00 and 50-day average dollar volume >= $500,000.

## Shared execution and portfolio (identical across all families)
- Signal: computed from data through the close of session s.
- Entry: next session's open (s+1). Skip the trade if that open is more than 1% above the signal close.
- Stop: entry minus 1.5 x ATR14 (ATR measured at s). Gaps are filled at the open; the stop itself is not a guaranteed fill.
- Time exit: at the close of the hold-th session after entry (entry session counts as session 1).
- Position size: risk 0.5% of current equity to the stop, capped at one third of equity, whole shares, cash-limited.
- Maximum 3 open positions. When more signals exist than free slots, take them in order of 63-day return, highest first.
- Costs (AMENDED before any real-data run, see Amendment 1). ALL COST VALUES ARE PROVISIONAL. They are not validated
  execution costs. No historical bid-ask or fill data is available, so the values below are assumptions. Any result
  is labelled "provisional cost" and cannot be presented as realistic net performance until validated.
  Cost components, charged on each side of every trade (entry and exit):
  1. Commission and applicable fees: 0.10% of notional (all scenarios).
  2. Half-spread: bucketed by the stock's 50-day average dollar volume at the decision session:
     >= $5M: 0.10%; >= $1M: 0.25%; otherwise 0.50%. Multiplied by the scenario spread factor.
  3. Slippage: fixed percentage of notional per side (scenario-specific).
  4. Liquidity cap: at most 1% of 50-day average dollar volume per order (a size limit, not a cost).
  Scenarios (provisional):
  - Optimistic: spread factor 0.5, slippage 0.02% per side.
  - Normal (gate): spread factor 1.0, slippage 0.05% per side.
  - Stress: spread factor 1.5, slippage 0.10% per side.
  Cost sensitivity: after the run, expectancy is reported across a grid of per-side cost levels from zero to stress,
  together with the break-even per-side cost (the cost at which net expectancy reaches zero). The scenarios above are
  not chosen by their effect on pass/fail; the grid is reported in full, whatever it shows.
- Stale or missing bars: a scheduled exit is never filled from a stale price. It waits for the next traded bar (exit_reason
  time_delayed). After 10 sessions without a bar, the position is written down to 50% of the last traded close and labelled
  unresolved_writedown. Delisted, suspended or acquired names are handled this way; the write-down is an assumption.
- Stops: checked on the entry session and every later session. Gaps through the stop fill at the open (stop_gap).
- Missing signal-close or open: no entry.
- Starting capital: CAD 5,000. No leverage.

## Families and their signals (exact)
Each family runs three predefined hold lengths: 2, 3 and 5 sessions. That is three variants per family, twelve in total.

- A. Trend pullback: close > SMA200 AND SMA50 > SMA200 AND close fell at least 3% over the last 5 sessions
  AND close >= 0.99 x SMA20 AND close > open (bullish close).
- B. Breakout continuation: close > highest high of the prior 20 sessions AND volume > 1.5 x 20-session average volume.
- C. Mean reversion: RSI(14) < 30 AND close > SMA200 (excludes severe downtrends).
- D. Relative strength: 63-day return in the top 10% of liquid names that day AND close > SMA50.

## Trials and count
- 12 configurations (4 families x hold {2, 3, 5}). All are reported, including failures.
- The earlier Experiment E grid and Experiment F (6 trials) are separate and are not reused here.

## Periods
- Training 2007-01-03 to 2015-12-31: choose the best hold length per family by net expectancy at normal costs. Only training is used for this choice.
- Validation 2016-01-01 to 2021-12-31: predefined check of each family's selected hold length only.
- Final holdout 2022-01-01 to 2026-11-02: run once, after everything above is frozen. Contaminated by earlier experiments; reported as such.

## Gates (must pass to be called a pass)
- G1 Net expectancy per trade > 0 at normal costs on training, validation AND holdout.
- G2 Profit factor >= 1.2 on validation and holdout.
- G3 Maximum drawdown no worse than -20% on the holdout.
- G4 Net expectancy > 0 at STRESS costs on the holdout (amended from doubled costs; see Amendment 1).
- G5 Win rate reported with a 95% Wilson confidence interval. Target 65% is a stretch goal, not a gate.
- Annual returns, trade count, exposure and turnover reported for every configuration.

## Amendment 1 (before any real-data F-short run)
- Reason: the first version used a fee-only cost model (0.10% normal, 0.20% doubled, 0.30% stress). The review required
  spread and slippage scenarios, so the cost model and gate G4 were replaced as written above.
- Stale-exit handling was changed from exiting at the last stale close to waiting for a traded bar.
- No real-data result has been produced under either version. Targets (65% win rate as a stretch goal) and gates G1-G3, G5 are unchanged.

## Cost grid (final, exact)
- Three provisional scenarios (optimistic, normal, stress) as defined above. Normal is the gate.
- Flat round-trip sensitivity grid, applied as equal per-side cost: 0.00, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 4.00 percent.
  Net expectancy at each point is reported for every configuration and period, whatever the result.
- Break-even round-trip cost: the largest flat round-trip cost at which net expectancy stays above zero, found by bisection
  (16 iterations on a one-way range of 0 to 5% per side). Reported per configuration and period. If expectancy is non-positive at zero
  cost, the report says "not profitable even at zero cost". No break-even figure is used for any gate.

## Data limitations (recorded before any real run)
- Survivorship bias: the universe is today's TSX listings (experiment_e/universe.json, 1,822 equities). Companies that were delisted, acquired
  or failed before today are absent. Results are biased upward for the historical period.
- No point-in-time index membership. The universe is not the TSX constituent list for each past date.
- 144 names are excluded because they could not be classified (120 rate-limited, 24 without quote type). Excluded names are not in the sample.
- Price data: Yahoo Finance daily OHLCV, auto-adjusted for splits and dividends. Not verified against exchange records.
- Delisting: no delisting or acquisition price data is available. Positions in names with no further bars are written down
  (unresolved_writedown, 50% of last traded close). That is an assumption.
- Liquidity: 50-day average dollar volume uses Yahoo volume, which is not exchange-verified.
- Costs: all cost values are provisional estimates. No historical bid-ask or fill data is used.
- Holdout 2022 to 2026-11-02 is contaminated by earlier experiments and is reported as such.
- The November 2 paper-trading opening prices are unverified and are not used as evidence of strategy performance.

## Decision rule
If no configuration passes all gates, the result is that none passed. Gates and grids are not changed after results are seen.
