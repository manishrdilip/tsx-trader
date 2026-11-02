# Paper trading audit - frozen v1 (Experiment E)

Research only. No real orders. Not financial advice.

## Status (2026-11-02)
- Signal: 2026-10-30 close (last TSX session of October), from the frozen rule.
- Execution: 2026-11-02 open, recorded by run 41464660277 (dispatched 14:43 UTC, after the open at 14:30 UTC).
- Close mark for 2026-11-02: pending. Needs a run after 21:35 UTC (close + 30 min).

## Trades executed at the open
- $1,000 account: 16 buys, about $672 invested, $328 cash, fees about $0.67.
- $5,000 account: 18 buys, about $4,269 invested, $731 cash, fees about $4.27.
- Whole shares only. Costs 0.10% per side, applied on buys and sells.

## Why cash is left (not a bug; matches experiment_e.simulate)
- Four names in the $1,000 account (TNZ, DRX, HMM-A, BDT) have target allocations of $41-$64,
  below their opening prices, so zero whole shares could be bought. About $217 of target stayed in cash.
- Two names in the $5,000 account (DRX, HMM-A) have the same issue, about $555 of target.
- Rounding down on each name leaves the rest of the cash.
- Changing this would change the strategy's sizing rule, so it stays as-is in v1.

## Valuation caveat
- The run log values were marked at the October 30 closes, because the November 2 close was not yet published.
- They are not the November 2 result. The close mark will be recorded by a later run.

## Universe (frozen in experiment_e/universe.json)
- 1,822 equities kept. 1,190 ETFs excluded, 20 mutual funds excluded.
- 144 excluded because classification was incomplete: 120 hit Yahoo rate limits, 24 returned no quote type.
- The frozen v1 universe is NOT changed. Reclassifying would change the frozen test; that would be a new version (v2).
- The exclusion is a known bias in the frozen universe, and it is not measured yet.

## Known limits (unchanged from the research audit)
- Survivorship bias: the universe is today's listings, so the history is optimistic.
- No point-in-time index membership or delisting data.
- XIU total return has not been cross-checked against a second source.
- The 2024-2026 test period has been examined many times, so it is no longer a clean holdout.
