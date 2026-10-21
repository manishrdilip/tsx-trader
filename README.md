# TSX Trader (runs on GitHub, no laptop needed)

Every weekday after the close, GitHub runs the scan and writes `results/report.md` (read it on your phone).

**Act on the top section only: ⭐ LEADER PULLBACK.** It is the one setup that survived an
18-year test on every liquid TSX/TSXV company (2009-2026, real companies only):
stage-2 uptrend + top-20% relative strength + RSI(2) < 10 + TSX above its 200-day.
Buy next open, stop 3×ATR, target 6×ATR, exit after 30 days. Max 5 positions, 1/5 of the account each.

- `results/live_log.csv` - every pick is logged before the outcome is known and scored automatically
  (the honest forward test). The scorecard is in the report.
- `lab/` - the research lab: ~50 setups (Connors, Crabel, Raschke, Minervini, Qullamaggie,
  Bulkowski candlesticks, turn-of-month...) × 15 exits, tested 2009-2018 and re-tested 2019-today.
  Results in `lab/results/`. Refreshed automatically on the 1st of each month.
- `stock_filter.py` - removes ETFs, BetaPro leveraged products, CDRs and split-share corps.

Research only - not financial advice.
