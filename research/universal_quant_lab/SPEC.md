# TSX and crypto pattern-search backtest engine

Build and run the engine locally in D:\UniversalQuantLab. Keep research code in this directory of the tsx-trader checkout. Target Python 3.12.10 and use requirements-windows-py312.txt for the Windows CPU environment. Reuse lab/indicators.py, lab/signals_day.py, lab/sim.py and existing Universal Quant Lab acquisition, warehouse, execution and portfolio tools where they meet the requirements. Use EODHD_API_KEY from the local environment. GitHub Actions may inject a repository secret when authorized. Keep keys out of code, command lines, URLs in logs, and reports.

## Data

Use verified entitlements on the existing EODHD account. The proposed All-In-One plan allows 100,000 calls per day. Read the account limits and endpoint weights as available. Checkpoint completed requests and resume bounded batches. Record fees, data scopes, response status, missing coverage, source timestamps and revisions. Save the data as ticker-partitioned Parquet.

- Acquire daily OHLCV for TSX, TSXV, US equities, crypto, forex, indices and commodities. Include available delisted histories and preserve the dates on which each instrument was eligible. Reuse existing Canadian and US warehouse records.
- Acquire and audit 1m, 5m, 15m and 1h history for US equities and crypto only, wherever the provider returns usable bars. Keep Canadian equities in the daily search. Derive coarser bars only from sufficiently complete finer bars, aligned to the exchange session. Label derived and provider intervals separately.
- Acquire fundamentals, earnings calendars and surprises, dividends and splits, macro/rates, and news sentiment where entitled. Retain actual release or filing availability and revision times so future information cannot leak into a signal. Keep indices and other reference series out of tradable universes unless mapped to an eligible traded instrument.

## Features

Compute features on closed bars across supported timeframes from one minute to weekly. Use GPU code where it improves measured end-to-end runtime, with a CPU reference and coverage for numerical parity and event timing.

- RSI, stochastic, StochRSI, Williams %R, CCI and MFI, with periods 5–50 and thresholds in the 20–80 range using each indicator's defined scale.
- SMA, EMA, HMA, MACD variants, ADX, Supertrend, Ichimoku, PSAR and Aroon.
- Bollinger Bands with 1.5, 2 and 2.5 standard deviations, Keltner Channels, Donchian Channels and ATR.
- OBV, VWAP, CMF, accumulation/distribution and Force Index.
- Explicit, causal rules for order blocks, fair value gaps, liquidity sweeps, change of character, break of structure and equal highs/lows. Record when any pivot becomes observable.
- P/E, P/B, EV/EBITDA, ROE, margins, debt/equity, growth and earnings surprises with point-in-time availability.

## Search and simulation

- Evaluate single rules and sampled AND combinations of two or three features. Use deterministic search seeds, canonical candidate identities, and a fixed exit template per candidate consisting of ATR-unit take-profit and stop-loss and maximum holding bars. Preserve replay information and remove duplicate configurations.
- Apply each candidate across all eligible tickers in its frozen scope. Record target-before-stop rate, mean net return, net compounded profit, drawdown, trade count and time in market after asset-class spreads, slippage and fees. Win rate is a diagnostic with zero ranking weight.
- Enter only on an executable price after the signal becomes known. Freeze corporate-action semantics, timezone and market calendars, gap-through-stop handling, and conservative treatment of bars that touch both barriers. Use matched capital, exposure rules, feasible liquidity and FX when aggregating results.

## Mandatory validation

1. Freeze chronological development and final holdout partitions before search. Target roughly the latest 30 percent of eligible history per ticker, with aligned calendar dates and embargo for trade or label horizons. Prove the final holdout is independent of prior lab research. If the proposed period was already used, keep development running and report final validation as INCONCLUSIVE until another holdout can be sealed.
2. Discover and tune only on development data. Freeze candidate IDs, costs, code, data revisions and benchmark before the fixed survivors receive their one holdout replay. Log every holdout access. The discovery path must reject access to holdout data and the validator must reject unsealed inputs or a second replay used for retuning.
3. Use deflated Sharpe or a preregistered Bonferroni test based on the actual number of unique tested candidates, including unsuccessful strategies that returned valid scores. Lock the count before final replay and reconcile it to the ledger. For a t-statistic comparison, report the observed statistic and corrected p-value. Account for correlated signals and overlapping positions when estimating uncertainty.
4. Require at least 100 independent trades and robustness across at least 10 eligible tickers. Define trade independence and the cross-ticker criterion before scoring. Simultaneous correlated trades alone cannot satisfy the sample-size gate.
5. Require each survivor to beat equal-weight buy-and-hold after costs over matched holdout dates, eligible securities, currency and capital. Add the matched VMM comparison when available under the existing promotion rules.
6. Publish a ranked table of passing candidates only, giving rule, timeframe, separate development and holdout statistics, independent trade and ticker counts, corrected significance and benchmark comparison. Report PASS, FAIL or INCONCLUSIVE with reproducible evidence for every stage. If zero pass, publish that result and aggregate rejection reasons.

## Deliverables and acceptance

- A resumable downloader, GPU feature builder with measured CPU comparison, deterministic search engine, mandatory validation pipeline, and results report.
- Preserve logs, actual completed counts, dataset and configuration hashes, random seeds, benchmark inputs, and evidence needed to reproduce the multiple-testing adjustment. Verify resume, leakage prevention, and planted and null controls before interpreting strategy results.
- Run locally under existing resource protections. No live trading, production VMM changes, paid data acquisition without authorization, or publication of credentials or raw restricted data.

## Local starting point

The active lab virtual environment is Python 3.12.10. The GPU is an NVIDIA RTX 4060 Laptop with 8,188 MiB of VRAM. The isolated CuPy environment is pinned in requirements-gpu-windows-py312.txt. A real GPU kernel passed CPU parity. The first feature block matched the existing CPU reference and showed causal prefix invariance on 16 TSX daily series of 1,000 bars each. For seven windows of SMA, ATR and ROC, the measured medians were 1.871 ms on CPU and 48.389 ms on GPU including transfers. Use CPU for that workload and benchmark larger batches separately. Local evidence is in reports/pattern-feature-parity.json.

The Windows user variable is configured. For a November 2024 sample, the EODHD key returned nonempty 5m and 1h data for SHOP.TO and RY.TO. Both Canadian 1m and 15m queries returned HTTP 200 with zero rows in that sample. AAPL.US and NVDA.US returned rows for all four requested intervals. These checks establish sample availability only. Historic Canadian intraday samples remain available for engineering checks.

The first US/crypto downloader is eodhd_intraday.py. Invoke it with the lab root and ticker list followed by --start YYYY-MM-DD, --end YYYY-MM-DD, --intervals and --max-requests. The end date is exclusive in UTC and cannot be after 2024-11-27. Resume with the same dates to preserve 28-day chunk boundaries. Downloader files remain in staging under database/eodhd-intraday/development-v1 until exchange-calendar and execution admission checks. Provider rows with invalid OHLC or invalid volume are excluded and counted. Missing volume is preserved and counted without imputation. A successful downloader check does not evaluate strategies.

Existing daily and portfolio research is development evidence. Consult RESEARCH_STATUS.md and BILLION_CAMPAIGN.md when sealing sources and aligning executable simulation semantics. Do not describe prior research windows as untouched merely because a new run uses a new split.
