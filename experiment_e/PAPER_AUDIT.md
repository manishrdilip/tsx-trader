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

## Close-mark audit: 2026-11-02 (run 41530641087)
- Run: dispatched 21:41 UTC, succeeded 21:51 UTC. Run-log entry 21:50:39 UTC: executions 0, trades 0, waiting none, errors none.
- Marks: last_marked 2026-11-02, using the Nov 2 close (after the 30-minute close gate). No execution on this run, so no duplicates.
- Reconciliation (cash + marked holdings = reported equity):
  - CAD 1,000 account: cash 327.57 + holdings 647.96 = 975.53 (equity.csv 975.53). 16 positions.
  - CAD 5,000 account: cash 730.70 + holdings 4,104.83 = 4,835.54 (equity.csv 4,835.54). 18 positions.
- Change over the Nov 2 session against the Oct 30 marks: 1,003.55 to 975.53 (-2.79%); 5,028.03 to 4,835.54 (-3.83%).
- Fill check on the Nov 2 open buys: cash_flow = shares x price x 1.001 for every row (0.10% per side). Sum of cash flows
  -672.43 (1k) and -4,269.31 (5k) equals starting cash minus current cash.
- Timestamps: signal 2026-10-30 close; execution 2026-11-02 at the open (run 41464660277 at 14:52 UTC, 5 minutes after the 14:30 UTC open);
  close mark 2026-11-02 (21:50 UTC, after the 21:00 UTC close plus 30 minutes). Consistent with the session calendar (XTSE).

### Gaps found in the records (not fixed here; the engine is frozen)
1. equity.csv has only the Nov 2 close row. The Oct 30 and Nov 2 open-execution equity values are only in run_log.csv.
2. watchlist.csv has 40 rows for as_of 2026-10-30: the same top-20 list was appended by two runs. It is not used for trades.
3. Open prices come from Yahoo daily bars fetched during the session. They have not been checked against an exchange print.
4. A matching close mark checks record consistency only. It does not check whether the simulated fills are realistic.

Action needed before relying on these records: approve a records-only fix (dedupe watchlist, backfill equity rows from run_log)
and an independent check of the Nov 2 open prices.
