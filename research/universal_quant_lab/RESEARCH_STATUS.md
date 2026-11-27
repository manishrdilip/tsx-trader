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

## Profit-first work and launch readiness

The official campaign remains at zero. The action-aware evaluator, cross-job recovery, transactional rolling top 100, new Coinbase and EODHD data, and outstanding launch gates are tracked in [profit-first readiness](PROFIT_FIRST_READINESS.md) and [machine-readable acceptance](BILLION_CAMPAIGN_ACCEPTANCE.json).

## Official launch check on November 26

Windows Task Scheduler returned success at 17:39 local time and produced a matching local runner log. Its three previously completed intraday pilot jobs resumed with zero new rows. This verifies scheduled invocation of the pilot entry point. The official results directory inventory contains zero official manifests, and the official worker process inventory is empty. The frozen official configuration, sealed launch evidence index and CPU telemetry sample are absent.

The completed-pilot Windows task was disabled after verifying its action path. The revision-specific development universe and alternative benchmark are now frozen in DEVELOPMENT_UNIVERSE.json. A second invocation reproduced the freeze. Development calendar checks and corporate-action loading passed for the three instruments. Production liquidity/cost evidence and a sealed independent dataset remain outstanding. The prospective holdout protocol excludes existing observations. Neither the LibreHardwareMonitor nor OpenHardwareMonitor WMI query supplied a CPU temperature sample during this check.

## Cloud review of the rolling top-100 reducer (2026-11-26)

- `bounded_topk.select` was checked against an exact full-sort reference on 400 synthetic trials (1 to 5,000 rows, k 1 to 119) with heavy ties in every ordering field. Result: 0 mismatches. The check is `test_bounded_topk_reference.py` and runs with `python research/universal_quant_lab/test_bounded_topk_reference.py`.
- This covers ordering only. It does not cover the transactional merge in `profit_retention.py`, forced termination during cleanup, or merged jobs against a full-output reference on real pilot data. Those remain open.
- Campaign wall-time arithmetic from measured rates already in this file (not new benchmarks): 1,000,000,000 evaluations take about 1.8 h at the 153,197.5/s batch rate, about 2.5 h at the 111,124/s wall rate, and about 29 h at the 9,548/s memory-capped turnover rate. A 104-day duration is not reproduced by these rates. The binding constraints are data eligibility, the global coordinator, the VMM comparator and the sealed holdout, not compute time.

LibreHardwareMonitor v0.9.6 was downloaded from the official GitHub release and extracted in the dedicated workspace. The archive matched the published SHA-256 (086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001). The runtime blocked the combined install/launch command. Separate download and extraction succeeded. The WMI probe returned no package/core readings. The added WMI reader writes the existing watchdog sample format only after both sensor types are present; hardware integration remains unverified.

## Continuous provisional campaign

The detached CPU supervisor targets one billion new provisional evaluations in rotating immutable three-million scopes. Each worker uses two CPU threads, 4,000-row leases and a 192 MB single-thread DuckDB configuration. Scope manifests pin the data and a nonoverlapping candidate index range. Full Parquet, batch distributions and category top-100 tables remain on D:. The supervisor publishes state and candidate summaries every 15 minutes while GitHub is reachable.

Ten additional Canadian symbols cleared the development calendar and corporate-action checks and were queued in separately pinned scopes. The Coinbase minute data and intraday/position experiments use separate manifests and evaluation counters. Those experiments cover next-open entries, time exits, candlestick and trailing range conditions. There are no official evaluations in these runs.

The LibreHardwareMonitor CSV bridge received an actual 61 C package reading with 14 valid individual core readings. It preserves the source timestamp and never writes a substitute reading. The discovery runner consults the fresh CPU reading at batch boundaries when available, while retaining the existing disk, GPU and RAM checks.
