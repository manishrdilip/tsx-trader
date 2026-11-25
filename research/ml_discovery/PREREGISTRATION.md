# ML opportunity discovery v1 — pre-registration (written before any results)

Standalone research. Imports nothing from the live bot; nothing in `vmm_bot/` changes.

## Data
- Daily OHLCV (Yahoo, auto-adjusted), 2015-01-01 to the latest close.
- Universe: 50 TSX stocks, picked from the fixed candidate list in `engine.py` by median
  dollar volume over 2016-2018 only (no later information used to choose names).
  Known bias: all candidates still trade today (survivorship). It affects VMM and ML alike.

## Periods
- Development (choose the ML setup): 2019-01-01 to 2022-12-31.
- Locked retrospective evaluation: 2023-01-01 to latest close. **Not untouched**: earlier
  research looked at parts of this period. Run once, with the setup chosen on development data.
  Forward paper trading is still required after this.

## ML strategy
- Features (all known at close of day t): returns 1/5/10/20/60/120/250d, distance from
  20/50/200d SMA, 20d and 60d volatility, ATR14 %, volume vs 20d average, log dollar volume,
  20d high/low position, gap, XIU 60d return and XIU above its 200d SMA.
- Label: forward return from open t+1 to close t+H exceeds k.
- Grid (48 setups): k in {1,2,3,5}% x model {logistic regression, gradient-boosted trees}
  x entry probability {0.55, 0.60, 0.65} x hold H in {5, 10} days.
- Walk-forward: retrain at the start of each calendar year on all earlier data, dropping the last
  H+1 days before the cutoff so no label overlaps the test year. No shuffling.
- Trading: signal at close t, buy at open t+1, up to 5 positions, each sized at equity/5 capped by cash,
  whole shares; sell at open after H days. Highest probability first.
- Setup selection: highest Sharpe on 2019-2022 with at least 30 trades. Ties -> fewer trades.

## VMM (same 50 stocks, same engine)
- Buy: 12m return in top 10% of the universe, close > 200d SMA, XIU > its 200d SMA, free slot (5 slots).
- Sell: close < 200d SMA, 12m return below top-40% cut, or close 28% below peak since entry.
- Simplified: momentum-only (no XIU leg, no parking ETF, no rebuy block).

## Both
- $5,000 start, 0.5% cost per side, whole shares, cash can't go negative, next-open execution.
- Metrics on 2023+ : net profit, CAGR, max drawdown, Sharpe (daily, rf=0), profit factor, trades.
