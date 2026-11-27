# Run sequence progress

Phase 1 was running at 2026-11-27T17:44:55.702245+00:00. The existing Canadian daily backfill had checked 9104 of 10308 symbols. The separate US, crypto, FX and indices daily worker had checked 200 of 122141 symbols.

The first 192 intraday windows completed and verified. The historical extension was running. The combined audit verified 743418 rows across 301 windows and 12 tickers, including 284597 bars missing volume. The coverage audit records affected symbol, interval and UTC ranges. Identical duplicate bars are collapsed. Conflicting duplicates and invalid bars are excluded and counted. Volume features must skip flagged windows.

Seven separately partitioned commodity reference series returned 57,467 observations through the development cutoff. The account returned HTTP 404 for the COMM contract directory and for sampled gold and crude contracts. The energy reference series lack contract OHLCV and are unsuitable for execution simulation.

status.json and data_coverage.json live in the local workspace. The existing untouched-data requirement still applies, and prior reports document exposure to the proposed 2025 validation period. Phase 1 has no completion marker. Phases 2 through 6 have not started, and no final survivors outcome exists.

## Capped sequence

The global non-Canadian worker was paused at 330 checked symbols with its checkpoint intact. The new frozen, local config/universe.json enumerates 4,828 TSX listings, 3,589 TSXV listings, 722 historical US index constituents, 50 crypto pairs, 14 FX pairs and four reference indices. The US membership lookback starts in 2016. S&P 500 membership comes from EODHD and Nasdaq-100 membership comes from a pinned community reconstruction. Six historical US labels had no match in the provider directory and remain explicitly flagged. Crypto is selected using median USD turnover on seven daily observations ending 2024-11-26. This selection must be disclosed in earlier-period crypto results.

The strict coordinator started Phase 1 on Windows under PID 42572. It validates the frozen specification hashes and predecessor marker before it advances. A synthetic acceptance check verified ordered phases, interruption at a failed phase, resume from the first missing marker and final formatting for a completed zero-survivor run. These checks did not evaluate market strategies.

Phase 2 through Phase 5 do not yet have verified implementations for this capped sequence. The Phase 6 renderer checks the hashed validation artifact, reconciles actual counts to the search marker and requires a passed independent holdout. The previously seen 2025 period is ineligible as a new independent holdout. No production survivor report or Phase 1 done-marker has been written.
