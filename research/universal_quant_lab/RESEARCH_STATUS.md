# Universal Quant Lab Research Status

Last updated 2026-11-26 (Windows laptop).

## Infrastructure and pilot

- Dedicated workspace at `D:\UniversalQuantLab`. The checkout is on `research/universal-quant-lab`. The setup script ran with `--pilot` at `42c5359a8b06cd887e2d046e4f650efe23fe391d`.
- Hardware verified on Windows: Core i7-13700H (20 logical processors visible), RTX 4060 Laptop GPU (8,188 MiB, driver 566.24), and 1,275.42 GiB free on D: at setup. The pilot used the CPU.
- Git 2.55.0, Node v26.12.1, Python 3.12.10, and an isolated venv. Installed DuckDB 2.0.1, NumPy 2.5.5, pandas 3.1.1, Polars 2.2.0, and PyArrow 26.0.1. The full version list is in the local `reports/requirements-installed.txt`.
- Engine and campaign self-tests passed. The RY.TO 5-minute pilot screened 600 candidates across depths 1–3 in 0.52 seconds of campaign wall time. Zero were unsupported in this sample. Evidence is in local `reports/setup.json` and `results/pilot-20261126-163711`. The sample was previously researched and is unsuitable as an independent holdout.
- The configured Windows user credential authenticated against EODHD. The User API reported a monthly subscription and a 100,000-call daily limit. The tested EOD, listing and corporate-action routes are accessible. Intraday and historical options route probes returned HTTP 403. See the coverage details below.
- No purchases or live trades. The live VMM checkout was used only for read-only configuration discovery and local dataset inventory.

## Warehouse and features

- Partitioned Parquet and a DuckDB dataset catalog are initialized under `database/warehouse`. Verified count and timestamp uniqueness after reading from Parquet.
- Yahoo Finance samples from `origin/micro-test`: RY.TO 5-minute, 3,141 bars across 41 session dates (2026-09-24 to 2026-11-20); RY.TO 1-minute, 7,588 bars across 20 session dates (2026-10-26 to 2026-11-20). The catalog retains importer audits and SHA-256 provenance.
- The existing checkout contains six additional TSX CSV files. Their provider, timestamp semantics, and adjustment policy need verification before ingestion.
- The screener retains 10 rule families and 19,822 parameterized rules. The new research feature module computes seven columns and passed a prefix-invariance check on both warehouse samples. These Python features are currently separate from the screener's Node registry.
- Remaining data work includes exchange-calendar and missing-bar audits, corporate actions, point-in-time listings/delistings, broader market coverage, and licensed historical options chain and quote data.

## Parallel screening and Windows scheduling

- The parallel launcher runs independent jobs in separate Node processes with per-job manifests and batch checkpoints. Two-worker runs reproduced the 600 serial results exactly apart from measured timing. A rerun skipped completed batches. Within-job parallel sharding, stale lock recovery, feature caching, Parquet results, and benchmarks on larger inputs are still pending.
- The Windows entry point ran manually and produced a logged 600-candidate run matching the pilot. Its local config uses the pilot jobs with two workers and up to 15 minutes per job. Task Scheduler now has an enabled daily 19:00 local task under the current user in interactive-only mode. Its requested run remains queued and no new scheduled runner log has been observed. A passwordless noninteractive registration attempt returned Access is denied.
- No independent strategy validation or VMM comparison has been completed. The portfolio simulator, constrained search expansion, and independent holdout remain open. Use the README acceptance gates before interpreting or promoting results.

## EODHD history acquired on 2026-11-26

- Added 23 EOD series with 165,911 rows through the 2026-11-25 cutoff, across TSX, TSXV, US, FX, crypto and spot metals. Five series were selected from the vendor's delisted TSX/TSXV snapshots. Coverage spans 1971-01-04 (USDCAD.FOREX) to 2026-11-25. The earliest sample start is a vendor label and has not been independently verified. XBC.V was rejected for inconsistent OHLC.
- Archived listing snapshots locally. TSX returned 3,116 active and 1,712 delisted records; TSXV returned 1,524 active and 2,064 delisted records. These current provider snapshots do not establish historical eligibility or handle ticker reuse. Downloaded split and dividend responses for RY.TO, CNC.V and AAPL.US. Empty event responses still require reconciliation.
- Recent and November 2020 intraday probes returned 403 for the tested symbols and intervals. The AAPL historical options EOD probe also returned 403. Historical options NBBO, additional intraday coverage, and commodities beyond the spot-metal samples remain open. No subscription changes or purchases.
- Verified Parquet counts and timestamp uniqueness at ingestion. A first-pass calendar audit across the 17 downloaded equity and ETF series flags extra dates for RY.TO, XIU.TO and other TSX series, and substantial gaps in CNC.V and HIVE.V. The TSXV calendar is a TSX proxy. Use these findings to investigate coverage before using the series in point-in-time research. Full audit is in local `reports/eodhd-daily-audit.json`.
- The isolated venv now includes exchange-calendars 4.13.3. The downloader and audit are reusable, and all provider data and acquisition reports remain on D:.

## Billion campaign readiness

The local daily engineering engine passed 10k, 100k and 1M milestones. The million-run restart test produced identical Parquet outputs after process termination. The official campaign remains at zero pending data eligibility, global coordinator, VMM comparator and unattended-run gates. See [launch readiness](BILLION_CAMPAIGN_READINESS.md) and [reconciled progress](BILLION_CAMPAIGN_PROGRESS.json).
