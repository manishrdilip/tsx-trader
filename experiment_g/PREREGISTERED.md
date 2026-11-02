# Experiment G - structured three-leg entry vs single entry (pre-registered)

Source: a video claiming an 87% win rate for structured averaging across 100 trades, against 73% for a single-entry MACD method.
Research only. Not financial advice. Nothing here changes after the first run.

## Why this design
- The video's win rate is not the metric. Small targets raise win rate mechanically, so the primary metric is net expectancy per
  trade (a trade = one signal, all its filled legs), with profit factor, maximum drawdown and total return.
- The video reports no costs, no test period, no universe, no data source, and no out-of-sample split. This experiment supplies all of these.
- The video's 30-minute bars are not available from our pipeline. This test uses DAILY bars. It does not reproduce the video's test.

## Data and universe
- Universe: experiment_e/universe.json (frozen, 1,822 TSX equities). Survivorship and data limits as recorded in experiment_f_short/PREREGISTERED.md.
- Liquidity at signal close s: close >= $1 and 50-day average dollar volume >= $500,000 (no look-ahead).
- Starting capital CAD 5,000. No leverage.

## Signal (identical for all variants)
- MACD(12, 26, 9) bullish crossover on close s: MACD line crosses above its signal line (MACD[s-1] <= signal[s-1], MACD[s] > signal[s]).
- Trend filter: close[s] > EMA200[s].
- Liquidity as above.

## Stop (common to all legs of one signal; fixed at the signal, never moved)
- Stop = lowest low of the 10 sessions ending at s, minus 0.1 x ATR14(s).
- If stop >= the leg-1 fill price, the signal is skipped.

## Legs and variants (three predefined variants; no others are run)
- B0 single entry: 1 leg at next open (s+1). Target 2.0R. Baseline.
- S1 structured (the video's description): 3 legs. Leg 1 at the next open. Leg 2 limit at leg-1 price - 0.5 x ATR14(s).
  Leg 3 limit at leg-1 price - 1.0 x ATR14(s). Targets: leg 1 = 0.25R, leg 2 = 0.5R, leg 3 = 1.0R (R = leg's own fill minus stop).
  The video's exact levels are not stated; these are my predefined choices.
- S2 structured control: same legs as S1, but every leg targets 2.0R. This separates the effect of averaging from the effect of small targets.

## Leg fills and cancellation
- Leg 1 fills at the next session's open (s+1), skipped if the open is more than 1% above close[s].
- Limit legs are live for 3 sessions after s+1 (sessions s+1 to s+3 inclusive). A limit fills on the first session where low <= limit,
  at min(open, limit). Legs not filled in that window are cancelled. Filled legs are not cancelled.
- A leg with fill <= stop is cancelled.

## Sizing
- Total risk per signal: 0.5% of current equity, split equally across the variant's legs (one leg = 0.5%, three legs = 0.1667% each).
- Shares per leg = floor(leg risk / (fill - stop)), capped by: one third of equity at the fill price, cash, and 1% of 50-day average dollar volume.

## Exits (per leg; applied each session from the session after fill)
- Gap through stop: open <= stop fills at the open (stop_gap).
- Stop: low <= stop fills at the stop (stop).
- Target: high >= target fills at the target, or at the open if the open is already above target (target). A bar that touches both
  stop and target counts as a stop (conservative). No target is checked on the fill session, only the stop.
- Time: at the close of session s+20. Missing bar: the exit waits for the next traded bar (time_delayed), and after 10 sessions
  is written down to 50% of the last traded close (unresolved_writedown). No stale price is ever used as a fill.
- Costs per side: same provisional scenarios as F-short (optimistic, normal, stress). Normal is the gate.

## Portfolio
- At most 3 signals open at once. Competing signals on the same day are ranked by 63-day return, highest first.
- Costs and cost sensitivity: same grid and break-even procedure as F-short (flat round-trip grid 0 to 4%).

## Periods
- Train 2007-01-03 to 2015-12-31. Validation 2016-01-01 to 2021-12-31. Holdout 2022-01-01 to 2026-11-02 (contaminated; reported as such).

## Gates (for each variant, on normal costs unless stated)
- G1: net expectancy per trade > 0 on train, validation AND holdout.
- G2: profit factor >= 1.2 on validation and holdout.
- G3: maximum drawdown no worse than -20% on the holdout.
- G4: net expectancy > 0 at stress costs on the holdout.
- Win rate is reported with a 95% Wilson interval for every variant. It is NOT a gate.
- Total return, trade count, exposure, leg fill rates and break-even round-trip cost are reported.

## Break-even method (recorded before the first real run)
- Break-even round-trip cost = the flat round-trip cost at which net expectancy crosses zero, found by linear interpolation
  between the adjacent points of the 0 to 4% grid. If expectancy is non-positive at 0%, the report says "not profitable at zero cost".
  If it stays positive through 4%, the report says ">= 4.0%". Bisection is not used (runtime).

## Trials
- 3 variants, each run once. All three are reported, including failures. S2 is a control, not a candidate.

## Decision rule
- A variant passes only if it passes G1 to G4. If no variant passes, the result is that none passed.
- Gates and variants are not changed after results are seen.
