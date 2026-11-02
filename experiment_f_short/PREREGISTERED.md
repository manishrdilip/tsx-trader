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
- Costs: 0.10% per side (normal). Doubled 0.20%. Stress 0.30%. Normal is the gate; doubled and stress are reported.
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
- G4 Net expectancy > 0 at doubled costs on the holdout.
- G5 Win rate reported with a 95% Wilson confidence interval. Target 65% is a stretch goal, not a gate.
- Annual returns, trade count, exposure and turnover reported for every configuration.

## Decision rule
If no configuration passes all gates, the result is that none passed. Gates and grids are not changed after results are seen.
