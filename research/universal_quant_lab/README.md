# Universal Quant Lab V0.1 (research only)
This branch is isolated from the live VMM bot. No brokerage integration, secrets, trade submission, or automatic promotion. This is an initial candidate generator and bar-level single-instrument screener, not a production portfolio backtester.

## Quick start
Node.js 20+ for the engine; Python 3.10+ with pandas, numpy, pyarrow for the optional importer.
From the repository root:
```sh
node research/universal_quant_lab/engine.cjs selftest
node research/universal_quant_lab/engine.cjs plan 3 0
python -m pip install pandas numpy pyarrow
python research/universal_quant_lab/import_bars.py path/to/bars_5m.parquet data/RY_5m.json --symbol RY.TO --timezone America/Toronto
node research/universal_quant_lab/engine.cjs run data/RY_5m.json 3 0 100 3 0.0005 1 > batch_0.json
node research/universal_quant_lab/engine.cjs run data/RY_5m.json 3 100 100 3 0.0005 1 > batch_100.json
```
The existing micro-test branch contains lab/micro/data/bars_5m.parquet and bars_1m.parquet; retrieve them via a separate checkout or git show. These are previously researched samples, not fresh holdouts. The source files are not copied into this branch. The CLI run positional arguments are input, max depth, offset, limit, holding bars, cost per side, direction. Candidate IDs depend on registry version, depth and family ordering; preserve commit SHA, input hash, exact parameters, interval, calendar, and costs for reproducibility. IDs use BigInt and are serialized as strings. No enumeration of earlier IDs is required; each batch is capped at 10,000. Plan output is a count, not executed tests.

## Current scope
Ten indicator families, one rule per family, AND logic. RSI lengths 5–100, thresholds 20–80 by 5, above/below/cross up/cross down. Other parameters are explicit in registry(). BOS is a causal confirmed-pivot break approximation, not a reproduction of HeatCharting. VWAP uses typical price and actual bar volume; no volume means unsupported VWAP/RVOL candidates. Forex tick volume is not exchange trade volume; label its provenance. 
Each input contains one symbol at one interval and one explicit session calendar. Use a common currency within an account. The long-only fixed-holding-period screen uses signal at close, entry and exit at subsequent opens, no overlapping positions or session crossing, whole units, $5,000 initial cash, fixed symmetric execution costs (default 0.05% each side). Short direction is exploratory arithmetic only: no borrow, margin, or liquidation model. Closed-trade drawdown excludes intratrade loss; not true portfolio max drawdown. No options, FX lot size, futures contract multiplier, funding, corporate actions, cross-asset FX conversion, spread/latency modeling, or portfolio capital allocation yet. Do not rank across assets using this screener as if those assumptions are interchangeable.

The 60/20/20 chronological bar split is for initial screening; final 20% is not evaluated. If those bars were previously used in other research they are not untouched. Separate splits must be fixed before screening, aligned by market dates across instruments, with embargo where required. Candidate selection is based on train/validation, never the final holdout. The original project 70/30 final comparison protocol remains a separate validation requirement. The selftest checks small synthetic inputs only and is not market evidence.

## Roadmap / acceptance gates
1. Inventory existing data and EODHD entitlements; ingest TSX/TSXV point-in-time equities and ETFs (including historical listings/delistings), US, FX, metals, crypto. Partition by source/market/symbol/interval/date, Parquet + DuckDB; audit sessions, missing bars, splits, duplicate timestamps, licenses, quotes and trade direction. Obtain actual historical option chains and NBBO with expiry/strike/contract multipliers; no underlying-only option proxies.
2. Expand registry to TA-Lib/pandas-ta-classic, causal SMC (CHoCH, FVG, order blocks, liquidity), tick CVD/OFI only with proper data, multi-timeframe features aligned to completed bars. Add OR/NOT, sequences, same-family multiple rules, exit parameters, long/short modes, and constraints to avoid equivalent/contradictory rules. Track tested vs unsupported, not merely total possible.
3. Replace screening hot loop with cached feature columns/bitsets, compiled NumPy/Numba or Rust and Parquet results. Benchmark wall time and memory before scaling; add durable shard leases, checkpoint/resume, run manifests, deterministic IDs with code/data hashes and deduplication. Use family-level coarse screening, random/sobol sampling, beam search, successive halving, and bounded exhaustive searches; report coverage and rejected trials. 
4. Build chart UI (Lightweight Charts or equivalent) showing actual candles, entry/exit and indicators with causal availability timestamps. Chart layer must use the exact same features as tests.
5. Validate surviving strategies with event-driven simulator (multi-position cash ledger, actual spreads, fees, slippage, session gaps, conservative stop ordering, liquidity/size limits, currency conversions, option exercise/assignment/greeks and futures funding/margin as appropriate). Test separate CAD/USD accounts and instrument availability on Wealthsimple; no live order submission. 
6. Multiple testing control, walk-forward development, block bootstrap, parameter stability, out-of-sample independent lockbox, identical VMM benchmark dates/capital/costs, report net profit/CAGR, drawdown, expectancy, profit factor, turnover, trade count and confidence intervals. Promotion requires the agreed 3x VMM gate and robust evidence, then paper trading. No target or profitability is guaranteed. Never extrapolate leveraged/crypto returns to the TSX or TFSA.
