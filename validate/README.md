# Validation protocol (frozen data, pre-registered)

- Data: one frozen snapshot of daily prices (release `data-latest`, recorded by sha256 at run time).
- Engine: `engine.py`. Signal on close of day t, fill at open of t+1 plus 0.05% slippage, 0.1% commission per side, whole shares, max 4 positions, 1.5% of equity at risk, all profits reinvested.
- Candidates: A = the 4/4 system; B = the same plus an index trend filter (XIU above its 200-day average).
- Selection rule (fixed in advance): pick the higher TRAIN CAGR (2016-10-31 to 2021-12-31).
- Test: 2022-01-01 to 2026-10-30, run once, fresh $5,000.
- Pass: beats XIU buy-and-hold, max drawdown no worse than -25%, at least 100 trades, at least 60% of calendar years positive.

Run: `python validate/run.py path/to/prices.parquet`. Output: `results/validate/validation.json`.
