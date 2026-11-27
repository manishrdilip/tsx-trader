# Run sequence progress

Phase 1 was running at 2026-11-27T17:44:55.702245+00:00. The existing Canadian daily backfill had checked 9104 of 10308 symbols. The separate US, crypto, FX and indices daily worker had checked 200 of 122141 symbols.

The first 192 intraday windows completed and verified. The historical extension was running. The combined audit verified 743418 rows across 301 windows and 12 tickers, including 284597 bars missing volume. The coverage audit records affected symbol, interval and UTC ranges. Identical duplicate bars are collapsed. Conflicting duplicates and invalid bars are excluded and counted. Volume features must skip flagged windows.

Seven separately partitioned commodity reference series returned 57,467 observations through the development cutoff. The account returned HTTP 404 for the COMM contract directory and for sampled gold and crude contracts. The energy reference series lack contract OHLCV and are unsuitable for execution simulation.

status.json and data_coverage.json live in the local workspace. The existing untouched-data requirement still applies, and prior reports document exposure to the proposed 2025 validation period. Phase 1 has no completion marker. Phases 2 through 6 have not started, and no final survivors outcome exists.
