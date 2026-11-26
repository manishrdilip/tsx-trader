# Local-only billion-evaluation campaign — owner directive

Recorded 2026-11-26. This is the research specification, not evidence that the campaign has started.

## Execution boundary
- All bulk screening and backtests run on the owner's Windows laptop under D:\UniversalQuantLab, using local CPU/GPU workers. No AI inference, cloud backtests, GitHub Actions compute or paid compute is needed for individual evaluations.
- GitHub stores code, reproducible configuration, non-sensitive progress summaries and permitted derived research artifacts only. Keep credentials, licensed raw market data and bulk results local.
- AI may help develop/audit infrastructure before launch. Once the run is locked, no interactive AI selection or tuning during the campaign. At the milestone, GPT and Claude independently review the evidence; do not expose the final holdout until a shortlist and validation protocol are frozen.
- Research only: never execute real orders or change production VMM.

## Before launching
1. Acquire broad historical data from existing EODHD entitlement and legitimate free sources; audit calendars, gaps, OHLC, corporate actions, provenance, delistings and instrument semantics. Missing data or unsupported asset classes must remain explicit. Do not substitute CFDs for futures/options. Use only eligible data with market-specific execution assumptions.
2. Fix daily-bar execution: the current intraday screener prohibits crossing sessions and is NOT suitable for daily swing signals unchanged. Add appropriate holding and fill semantics and tests before screening daily data. Expand registry, wire Python features into actual evaluation, add constrained rule combinations and deduplication, and validate causality.
3. Pre-register market/timeframe/strategy-depth coverage, search budgets, cost assumptions, date-aligned development and holdout splits, strategy IDs and VMM comparator. Benchmark serial vs parallel on representative longer inputs; prove checkpoint/restart, resource guardrails and scheduled or standalone execution. No billion-run launch based on the 600-test pilot alone.
4. Define a counted evaluation as one successfully completed, unique canonical strategy configuration x immutable eligible dataset x execution/split specification. Count repeats, errors, unsupported jobs, duplicate configurations and synthetic engineering runs separately. One strategy across multiple datasets counts as multiple evaluations, not multiple distinct strategies. Start the new production-scale counter at zero.
5. Use bounded batches, deterministic sampling without replacement, persistent leases, checksums, reproducible manifests, local compressed columnar outputs and checkpoint recovery. Maintain >=150 GiB free space; benchmark storage growth. Keep sufficient per-evaluation evidence to reproduce results; retain detailed trades for shortlisted strategies and deterministic audit samples. Avoid a billion JSON files/rows with duplicated rule text.

## Local autonomous execution
- Target 1,000,000,000 completed eligible unique evaluations. Software runs independently of AI sessions. Pilot 10k, 100k, 1M on representative data, then lock campaign and scale. No automatic promotion or live trading.
- Keep one persistent campaign manifest and exact progress ledger, with atomic writes, restart-safe deduplication and no repeated counting on retry. Report completed/target, distinct strategy count, dataset count, skipped, failed, throughput, disk and elapsed time.
- Use local watchdog and safe pause/resume; respect sleep, power and Windows permission limitations. Verify scheduler by actual scheduled logs and restart test; do not bypass security or request passwords in chat. Stop safely on data/code/config drift, thermal or space problems.
- Freeze the campaign at the target; do not automatically unlock holdout or change rules. Export an evidence pack and publish a compact, permitted summary to the research branch.

## AI evaluation handoff
Create research/universal_quant_lab/BILLION_CAMPAIGN_PROGRESS.json (small summary, initially marked not_started) and update from reconciled local checkpoints periodically. At completion, publish an AI_REVIEW.md and compact leaderboard (subject to data licenses). Include campaign/version hashes, coverage by market/timeframe/family, rejection counts, search budget, costs, trade counts, net profit, CAGR where meaningful, drawdown, profit factor, expectancy, stability, selection bias/multiple testing and evidence for exact reruns. Keep raw results on D:. Do not publish API keys, personal paths beyond workspace, or licensed data.
GPT and Claude independently inspect the code, coverage, reproducibility and development leaderboard, then agree on frozen finalists and independent validation. Compare against VMM with identical dates, capital ($5,000), costs and eligible instruments, CAD/USD separately. A 3x VMM result is a goal, not an assumed outcome. No profitable strategy is guaranteed.

## Current blocker
As of the latest status, 600 pilot evaluations on a previously researched sample are verified by the local report, not counted toward this campaign. Daily data access works; intraday/options entitlement probes returned 403. Broader acquisition, daily execution semantics, feature integration, storage scaling, representative benchmarks and unattended execution verification are pending.
