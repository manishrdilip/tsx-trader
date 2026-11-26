# Universal Quant Lab — Research Status

Last updated: 2026-11-26 (cloud session, no laptop attached)

## Infrastructure status
- Laptop (D:\UniversalQuantLab\ layout, GPU, EODHD config): **NOT CONNECTED.** No Windows machine is attached to the cloud session, so nothing has been created on D: and no hardware benchmark has been run.
- Directory layout: **not created** (blocked on laptop access).
- Repository: cloned (shallow, depth 1 on `main`; research branch fetched at depth 50) into the cloud container only. The laptop checkout does not exist yet.
- Live VMM bot: not touched.

## Installed software
- Cloud container: Python 3.13.18, Node v22.23.5. `pandas`, `numpy`, `pyarrow` are **not installed** in the container.
- Laptop software stack (Python/Node versions, NumPy, Pandas, Polars, DuckDB, PyArrow, TA-Lib, pandas-ta-classic, Numba, VectorBT, Optuna, SciPy, scikit-learn, XGBoost, LightGBM, NautilusTrader, CUDA/CuPy, Lightweight Charts): **not installed.**

## Available datasets
- None on the laptop (D: drive not reachable).
- The research branch does not contain market data. GPT's README refers to `lab/micro/data/bars_5m.parquet` and `bars_1m.parquet` on another branch (`research/quant-discovery-v2`). These are previously researched Yahoo Finance samples, not fresh holdouts. They were not fetched in this session.
- EODHD subscription: **not investigated** (credentials and entitlements are on the laptop).

## Data coverage and limitations
- Not assessed yet. Required before any result is trusted: session calendars, missing bars, duplicate timestamps, splits and corporate actions, listings/delistings, options quotes (no underlying-only proxies).

## Indicator count
- Engine V0.1 (`research/universal_quant_lab/engine.cjs`): **10 indicator families, 19,822 rule variants** (RSI 4,992; EMA 784; SMA 784; MACD 11,000; VWAP 4; RVOL 120; BOS 38; ROC 1,180; ATR 460; BB 460). Target of 1,000 distinct indicators/patterns/features is far from met.

## Actual completed backtests
- None on real market data in this session.

## Measured testing speed
- `selftest`: PASS, 0.13 s wall (synthetic inputs only; not market evidence).
- Combinatorial space (engine `plan`, computed counts only, not executed tests):
  - depth 1–3: 307,690,228,702 candidates
  - depth 1–10: ~2.0 × 10^26 candidates
- Execution throughput on real data: **not measured** (needs a benchmark on the laptop).

## Research results
- None. No strategy has been evaluated. No result is comparable to the VMM benchmark yet.

## Bugs and unresolved issues
- Engine V0.1 uses one rule per family with AND logic only. OR/NOT, sequences, multi-timeframe confirmation, exit variants, short mode and position sizing are not implemented.
- Screener is single-instrument, fixed-holding-period, closed-trade drawdown only (not true portfolio drawdown). No options, futures multipliers, funding, FX conversion, or capital allocation.
- BOS is an approximation of the HeatCharting definition, not a reproduction.
- The 60/20/20 split in the README is for screening; the final 20% is only "untouched" if it was never used in earlier research.
- Importer (`import_bars.py`) requires pandas/pyarrow; not yet run.

## Questions requiring GPT's independent review
1. Is the causal BOS approximation acceptable, or should it be replaced before any BOS-based result is reported?
2. Should the 10,000-candidate batch cap and the 60/20/20 split be fixed per instrument, or aligned across instruments by market date with embargo?
3. Is the closed-trade drawdown metric acceptable for screening, given that the portfolio simulator is not built yet?

## Next development priorities
1. Attach the Windows laptop (or confirm the D: path and access method) so the directory layout, EODHD inventory and software install can be done.
2. Inventory EODHD entitlements and rate limits; record results here (no credentials in the repo).
3. Install the pinned software stack in isolated virtual environments and record exact versions.
4. Ingest and audit TSX/TSXV data, then benchmark the screening loop on real bars before any multi-day campaign.
