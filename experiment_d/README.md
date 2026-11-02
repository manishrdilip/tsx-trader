# Experiment D - risk-controlled momentum bench

Independent of Experiments A, B and C. Does not change their code or results.

## What it tests
Experiment C's exact entry signal, data, cleaning and execution, with risk controls added:
0.5% equity risk per trade, max 2 positions, max 1% aggregate initial risk, whole shares, no leverage,
cash limit, and an optional XIU > 200-day SMA market filter. Costs are 0.10% per side (1x) and 0.20% (2x).

- **D1** C entry + 0.5% risk + 2 positions (trailing exit as in C)
- **D2** D1 + XIU market filter
- **D3** D1 + fixed stop at 2 x ATR and 2.5R target
- **D4** D3 + XIU market filter

D1-D4 run at $1,000 and $5,000, 1x and 2x costs (16 configs). The bench file adds 984 sampled grid
configs for 1,000 total.

## Files
- `experiment_d.py` - `fetch`, `grid`, `run`, `aggregate` subcommands
- `configs/bench_1000.json` - the 1,000 configs (first 16 are D1-D4; flagged `detail: true`)
- `../.github/workflows/experiment_d.yml` - fetch once, 10 parallel shards, aggregate

## Periods and selection
- Train: 2016-11-01 to 2020-12-31
- Validation: 2021-01-01 to 2023-12-31
- Test: 2024-01-01 to today

Winner selection uses train and validation only: score = min(train Calmar, validation Calmar) at 1x costs,
with at least 100 trades in each period. Test is reported for the selected config and is never used to choose it.
The final account value is not used to choose a winner.

## Outputs (artifact `exp-d-report`)
- `report/report.md` - summary and tables
- `report/all_configs.csv` - every config, all periods, regime splits
- `report/d_configs_table.csv` - D1-D4 results
- `report/selection.csv` - selected config per capital, with test results at 1x and 2x costs
- `report/top20_by_train_val.csv`
- `report/detail/<id>/` - for D1-D4: `trades.csv`, `daily_equity.csv`, `annual.csv`, `config.json`

## Run
Actions tab -> "Experiment D - risk-controlled momentum bench" -> Run workflow.
Locally (synthetic data test, no network needed):
```
python experiment_d/experiment_d.py fetch --out /tmp/panel.pkl.gz --synthetic
python experiment_d/experiment_d.py run --panel /tmp/panel.pkl.gz --configs experiment_d/configs/bench_1000.json --out /tmp/out
python experiment_d/experiment_d.py aggregate --inp /tmp/out --out /tmp/report
```

## Caveats
- Survivorship bias: the universe is today's listings, so failed companies are missing. Results are optimistic.
- Multiple testing: 1,000 configs means the best train+validation result can be luck. Check the test period
  and the D1-D4 table together.
- Walk-forward: the simulator fits no parameters. Year-by-year out-of-sample results are in each detail `annual.csv`.
- Research only, not financial advice.
