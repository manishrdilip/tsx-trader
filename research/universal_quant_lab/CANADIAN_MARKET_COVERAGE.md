# Canadian market data coverage

## Warehouse evidence

Before this backfill the warehouse had 37 distinct Canadian daily series, with 30 TSX and seven TSXV. RY.TO was the only instrument with Canadian one-minute and five-minute coverage. CSE, Cboe Canada and Montréal Exchange had no admitted series.

At 2026-11-27T15:02:46.114712+00:00, the detached EODHD worker (PID 19304) had attempted 94 of 10308 queued provider symbols. It had ingested 74 additional daily series with 161371 verified Parquet rows across TSX, TSXV, CSE and Cboe Canada. The provider grouped 38 of these in its delisted directories. Series without history and failed validations are tracked separately. Query endpoints and Parquet checks passed on a 24-symbol bounded run and the detached worker resumed that checkpoint. The acquisition cutoff is 2024-11-26 to keep newer data out of this development backfill.

The frozen provider directories returned current/delisted rows of 3,114/1,714 for TSX, 1,525/2,064 for TSXV, 512/831 for CSE and 438/147 for Cboe Canada. These are provider directory counts. Screener eligibility still requires historical listing identity, corporate actions and delisting settlements, enough traded liquidity, and a defensible cost model. An ingested series can have very few observations and is not automatically eligible for research.

The Montréal Exchange sample for 2024-11-01 through 2024-11-26 returned 11,808 SHOP option contract-day records (951 distinct contract symbols) and 144 SXF futures contract-day records (eight distinct contract symbols). The validated files and source hashes are stored separately from equity bars. The downloader started expanding to SHOP, RY, TD, XIU and XEG options plus SXF, CGF, CGB and CRA futures for 2023-01-01 through 2024-11-26. The public summary does not supply a time-ordered book or simulated fills. [Montréal Exchange historical data](https://www.m-x.ca/en/trading/data/historical)

## Remaining coverage gaps

- Official current-listing reconciliation and point-in-time listing membership by venue, symbol changes, splits, distributions, historical volume gaps, and delisting proceeds. [TSX and TSXV issuer directory](https://www.tsx.com/en/listings/listing-with-us/listed-company-directory) · [CSE listed companies](https://thecse.com/listing/listed-companies/) · [Cboe Canada listing directory](https://www.cboe.com/markets/ca/equities/market-activity/listing-directory/)
- Market-wide Canadian minute bars and quotes. A targeted Canadian one-minute request under the current EODHD subscription returned HTTP 403. No free equivalent with verified full coverage was found. HeatCharting advertises free chart access, but a documented bulk Canadian history export could not be verified. [HeatCharting](https://heatcharting.com/) · [TMX market data documentation](https://docs.tmxanalytics.com/)
- Complete historical derivatives chains, intraday quotes and trades, and broker-specific instruments such as directly held bonds and GICs remain outside the verified warehouse scope. [Montréal Exchange market data services](https://www.m-x.ca/en/trading/data/market-data-services)

The local acquisition directories hold all raw data, symbol snapshots and checkpoints. This report contains only counts and methodology. No purchases, trading, research campaign counts or production VMM modifications were involved.
