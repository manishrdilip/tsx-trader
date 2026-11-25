# Batch 5 — Forex (pre-registered before any result)

Data: EODHD daily FOREX (on Dilip's plan), 14 pairs: EURUSD GBPUSD AUDUSD NZDUSD USDJPY USDCAD USDCHF USDNOK USDSEK
EURJPY EURGBP EURCHF AUDJPY GBPJPY, from first available date (>= 1990 used). Interest rates not available
(EODHD GBOND = not on plan; FRED/ECB/Stooq blocked) -> carry/interest is NOT included in any return and carry strategies are
not testable. Returns are spot-only.

Execution: signal at close t, position from close t+1 (one full day lag). Each pair scaled to 10%/yr volatility using
60-day realised vol known at t; basket = equal weight of all pairs (or of the long/short legs). Cost 0.02%/side of traded
notional for majors (0.05% also reported). Long and short allowed (forex account, not a TFSA).

Strategies (13 settings):
1 Time-series momentum: sign of 63/126/252-day return (3)
2 Moving-average cross 50/200, 20/100 (2)
3 Close-based Donchian breakout 20/10, 55/20, 100/50 (enter on N-day high/low close, exit on opposite M-day) (3)
4 Mean reversion: fade 5-day z-score beyond 1.5, exit at 0; RSI(2) fade < 10 / > 90, exit after 3 days (2)
5 Cross-sectional momentum on 9 currencies vs USD: long top 3 / short bottom 3 by 63- or 252-day return, monthly (2)
6 Month-end USD seasonal: long USD vs the 9 currencies on the last 3 trading days of each month (1)

Periods: dev 1990-01-01..2022-12-31; eval 2023-01-01..latest, run once after the dev selection is committed.
Selection: best dev Sharpe at 0.02%. Pass: dev Sharpe > 0.5 in BOTH dev halves (1990-2006, 2007-2022), eval Sharpe > 0.3,
and Deflated Sharpe > 0.95 with N = 13 + 5 earlier FX/asset trials.
Reported at 10% target volatility; returns scale with leverage (and so do drawdowns).
