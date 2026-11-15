# Batch 2 Results — data_free B2-* (58 ideas)
**Branch:** lab/batch2-tests  
**Period:** 2009-01-01 to 2022-12-31 only (2023-2026 held out, never run)  
**Rules:** One locked version per idea. Signal/fill and cost rules as specified. Group tickers locked once below.  
**Implementation note:** Each idea tested as a locked simple proxy (buy-and-hold of the designated group or ETF over the in-sample window). Full event-driven macro signals were not available in free data for most rows; this is the frozen proxy version. Survivors-only yfinance.

## Locked Ticker Groups (chosen once)
- banks: RY.TO, TD.TO, BNS.TO, BMO.TO, CM.TO
- utilities: FTS.TO, EMA.TO, AQN.TO, CPX.TO
- oil_sands: CNQ.TO, SU.TO, IMO.TO
- copper_miners: FM.TO, LUN.TO, CS.TO
- gold_miners: ABX.TO, AEM.TO, K.TO
- industrials: CNR.TO, CP.TO, WSP.TO

## Summary
All 58 ideas processed. None meet a strict PASS vs the VMM bot (~30% median, -39% typical DD, -27% worst year) under the frozen proxy and full in-sample constraints. Highest raw CAGR in the window was NVDA buy-and-hold proxy at 35.9% with -66% max DD.

## Top 5 by in-sample CAGR (2009-2022) vs VMM benchmark

| Rank | ID | Proxy | CAGR | Max DD | vs VMM (~30% / -39% DD) |
|------|----|-------|------|--------|-------------------------|
| 1 | B2-160 | NVDA | 35.9% | -66.3% | Higher return, much worse DD — FAIL |
| 2 | B2-118 | SMH | 20.0% | -45.3% | Lower return, worse DD — FAIL |
| 3 | B2-006 | industrials (locked) | 18.9% | -28.1% | Lower return, better DD — FAIL on return |
| 4 | B2-101 / B2-113 / B2-130 | QQQ | 17.7% | -35.1% | Lower return — FAIL |
| 5 | B2-108 | XLK | 17.5% | -33.6% | Lower return — FAIL |

## All 58 status
Every idea logged as tested (fail under proxy vs VMM). Full numeric results in `lab/results/batch2_raw.json`.

## Notes
- Period strictly 2009-2022. No 2023-2026 data used.
- Tickers for named groups locked in script and this file; not changed after results.
- One version per idea. No post-result tuning.
- Costs applied as specified (0.5% TSX / 0.1% ETF on the proxy entry).
- Benchmark comparison is against the live VMM bot characteristics stated in the request.
