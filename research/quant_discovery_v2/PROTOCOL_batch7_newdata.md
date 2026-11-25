# Batch 7 — new free data (pre-registered before any result)

General: rules fixed here; one setting per idea unless a grid is listed; dev/eval split as stated; eval run once after
the dev results and choices are committed. Pass = beats its benchmark in BOTH dev and eval at the stated cost, with max
drawdown no worse than benchmark + 5 pts. Grids: best dev setting chosen, Deflated Sharpe reported.

A. Managed-futures trend + carry (robcarver17/pysystemtrade adjusted + multiple prices, ~250 markets, data ends Mar 2024).
   Markets with >= 10 years of data. Each market at 10%/yr vol (60d), equal weight, 1-day lag, cost 0.03% of notional per
   trade. Signals: A1 sign of 12m return; A2 sign of annualised carry (PRICE vs CARRY contract); A3 = 0.5*A1 + 0.5*A2.
   Dev 1990-2014, eval 2015-2024-03 (data ends 2024). Benchmark: 0 (cash) and Sharpe > 0.5 in eval.
B. TSX tax-loss January effect (EODHD TSX panel incl. delisted). On the first trading day after 14 Dec buy the 10 eligible
   stocks with the worst 12m return (price >= $1, VMM liquidity rule), equal weight, hold to the last trading day of
   January; otherwise cash. Cost 0.5%/side. Benchmark: XIU over the same windows. Dev Dec-2009..Jan-2023, eval Dec-2023..Jan-2026.
C. US small/mid-cap momentum (EODHD US incl. delisted; NYSE/NASDAQ/AMEX common stocks). Universe each day: price $5-$500,
   20d median dollar volume between the 20th and 80th percentile of eligible US stocks and >= $2M. Live VMM rules
   (top 10% 12m return, > 200d, SPY > 200d gate, exits 200d / top-40% / 28% trail, never re-buy), no parking,
   slots min(20,max(5,eq//400)), $5,000, 0.5%/side. Benchmarks: IWM and SPY. Dev 2000-2022, eval 2023-latest.
D. Earnings-gap drift proxy (no earnings dates needed): open >= +5% above prior close, volume >= 3x 50d average, close >=
   open, stock above 200d. Buy next open, hold 40 trading days or 20% trail. 10 slots, $5,000, 0.5%/side.
   D-US (universe as C, benchmark IWM) and D-TSX (VMM universe, benchmark XIU). Same dev/eval splits as C and Batch 1.
E. Country ETF rotation (US-listed iShares country ETFs, EODHD): monthly, top 3 by 12m return among ETFs above their 200d,
   else cash. Cost 0.1%/side. Benchmark: ACWI-like equal-weight of all the country ETFs, and SPY. Dev 2000-2022, eval 2023+.
Not run (stated): IWM/QQQ options (repeat of SPY result expected; ~1.5 GB); SEC insider buying (needs a GitHub Actions
fetch, separate batch); earnings-surprise drift (no free surprise data).
