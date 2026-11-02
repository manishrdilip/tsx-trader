# Research engine audit (Experiments B, C, D, E)

Scope: the shared data, signal, simulation and reporting code used by B, C, D and E. Reviewed as of 2026-11-02.

## Known issues, ranked by impact

1. **Survivorship bias (high).** The universe is `universe_tickers.json`, which lists today's TSX and TSXV names.
   Companies that failed, were taken over, or were delisted before today are absent, so every backtest here is
   optimistic. Fixing this needs point-in-time index membership and delisting data, which yfinance does not provide.
2. **No point-in-time eligibility (high).** Liquidity and price filters use each day's data, which is correct,
   but the candidate pool is still today's listings.
3. **Flat cost model (medium).** Every trade pays 0.10% per side (commission, spread and slippage combined).
   Small TSX Venture names have wider spreads, so their costs are understated. The 2x runs partly cover this.
4. **Intrabar ordering assumed (medium).** When a stop and a target are both inside one bar, the stop is assumed
   to fill first (conservative). Trailing exits use the bar's high to move the stop. Real fill order is unknown.
5. **Data cleaning is minimal (medium).** Only `dropna` and a 260-bar minimum are applied. Bad ticks, splits that
   yfinance mis-adjusts, and suspended-trading days are not detected. Extreme single-bar moves should be checked.
6. **Benchmark not cross-checked (medium).** XIU total return comes from yfinance adjusted prices, which include
   dividends. It has not been compared with a second source.
7. **Inconsistent time stops across experiments (low).** B uses 20 bars, C and D use 60 bars. Comparisons across
   experiments mix exit-horizon effects with signal effects.
8. **Multiple testing (high for D and E).** D tested 1,000 configs and E tests 192. The best train and validation
   config can still be luck. Selection uses the worse of train and validation Calmar, but this does not remove the effect.
9. **Shared code edits (low).** `backtest_candle.py` gained env-controlled options (`START_TEST`, `EXIT_MODE`,
   `STOP_PCT`, `TARGET_PCT`, a portfolio function). Defaults reproduce the original behaviour. Experiment C was
   run before these edits, so rerunning C on the current code should give the same results; this has not been verified.
10. **Account simulations are order-dependent (medium).** The one-position-at-a-time account takes signals in
    date order, not ranked by strength. Results depend heavily on which trades are taken.

## Checked and correct (as far as reviewed)

- Entry signals use only data up to the signal day's close; execution is at the next open.
- XIU market filters in D and E use the signal-day close and the 200-day SMA; no future data.
- Liquidity (50-day average dollar volume) uses data up to the signal day.
- Whole shares, cash limits, and the aggregate risk cap are enforced in D and E.
- Equity is valued at each day's close, with forward-filled prices for missing days.

## Not implemented (blocked by data)

- Point-in-time TSX membership and delisting history.
- Sector classifications, so sector rotation cannot be tested.
