# Profit-first implementation and launch audit

The official campaign remains at zero of one billion. The local global coordinator currently admits engineering evaluations only.

## Objective, risk and acquisition

- The evaluator compounds an initial CAD or USD 5,000 cash account with half-spread, slippage and per-order fees. Drawdown uses opening and closing marks plus observed lows while positions are open. Tail loss is worst daily close-to-close equity decline and stability is the weaker half-period return. Daily OHLC cannot establish full intraday equity-path ordering.
- Separate currency, market, timeframe and style boards rank net profit in drawdown bands of 10%, 20%, 30%, 40% and unrestricted. Family boards and a profit/drawdown/tail/stability Pareto report preserve alternatives. Win rate has zero ranking weight. A 30% win-rate synthetic candidate beat a 95% candidate on net profit within the same band.
- Added 18 EODHD histories. The warehouse holds 404,275 daily bars across 58 series. Added 4,320 Coinbase Exchange hourly BTC-USD and ETH-USD spot bars with no missing hours in the requested 90-day window. Bond and metals ETFs are classified as ETFs. CSE and additional US venue coverage, direct bonds, options and futures remain open. Spot and FX series do not supply derivative execution evidence. [Coinbase candle specification](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
- Ten feature families now feed actual evaluation. The additions are RSI with EWM smoothing, Bollinger z-score and efficiency ratio. Added pinned corporate actions, integer forward-split share adjustments, causal split normalization, and dividend receivables with conservative payment timing. The action audit and 60,000-evaluation pilot covered SHOP.TO, AAPL.US and XEG.TO. Reverse splits, cash-in-lieu, M&A, uncertain distributions and cross-currency dividends remain outside the model. [Provider adjustment methodology](https://eodhd.com/help/methodology)
- Cash and passive comparators were calculated on the same dates and costs. A matched VMM series has yet to be verified, so no 3x VMM claim was made. No holdout metrics were calculated.

## Global accounting and measurements

- One DuckDB engineering ledger reserves disjoint ranges across jobs, validates exact Parquet IDs and checksums, accepts repeated identical commits idempotently, and stops at the configured quota. An uneven 13-evaluation test covered exact stop, invalid IDs and repeated commits. A 1.2M run recovered through the watchdog after forced termination at 50,000 across two jobs. All 48 Parquet batches matched the uninterrupted run, and 1.2M distinct job/strategy pairs reconciled.
- The detached 10M profit-first run on the earlier seven-family engine took 147.29 s end to end (67,892/s) with 58.95 s evaluator time (169,630/s) and wrote 829,161,337 bytes. These rates do not apply to the expanded action-aware model. The older 111,124/s and 153,197.5/s figures were from separate uninterrupted and restarted one-million pilots and both used batch timings.
- Standalone process execution and recovery are verified. The interactive scheduled task remains queued. The tested runtime did not expose a CPU thermal reading or CUDA acceleration.

## Open launch gates

Production admission and exact-billion freeze still need wiring beyond the engineering coordinator. Freeze and validate an eligible scope with actual costs, liquidity limits, calendar and corporate-action reconciliation. Seal the independent holdout and freeze the VMM or alternative comparator protocol. Verify unattended Windows recovery and production resource guardrails, and complete the final validation and evidence workflow. The approved specification permits an eligible subset with unsupported markets in separate manifests.
