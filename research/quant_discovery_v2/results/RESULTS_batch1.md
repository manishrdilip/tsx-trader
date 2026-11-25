# Quant Discovery V2, batch 1 results (25 Nov 2026)

Protocol: PROTOCOL.md (committed b0c6339 before any result). Selection locked in SELECTION_LOCKED.md (e22b709)
before the evaluation run. Evaluation run once.

## Data
EODHD daily, TSX (`TO`), downloaded 25 Nov 2026: 3,980 price files -> 1,112 clean common stocks (615 listed,
497 delisted) + 15 ETFs, 2007-01-02 to 2026-11-24. Dropped: 221 fund-like names, 219 delisted with broken adjustments,
23 with reversed spike prints, 34 too short. No TSX delistings before 2012 in EODHD (2009-11 survivor-biased).
Subscription check: daily EOD yes; intraday 403; fundamentals 403. So 5-min, earnings and fundamental families
cannot be tested on this plan.

## Benchmark: exact live VMM ($5,000, no deposits, 0.50%/side)
| Period | Exact VMM | VMM without parking | XIU |
|---|---|---|---|
| Dev 2009-22 | 8.3%/yr, DD -30.3% | 20.6%/yr, DD -34.0% | 8.5%, -35.5% |
| Eval 2023-26 | 26.1%, -15.3% | 30.8%, -32.0% | 18.4%, -12.4% |
| Full 2009-26 | 10.4%, -30.3%, $5.38/day | 23.3%, -34.0%, $45.97/day | 10.6%, -35.5% |

**Important finding about the live bot:** the parking rule (leftover cash >= $100 goes into VEQT/VFV and is never sold) means
every sale whose cash isn't reused the same day, e.g. while XIU is below its 200-day, moves money out of momentum for good.
With no deposits that cut the bot's 2009-22 return from 20.6% to 8.3% a year. Live accounts get monthly deposits, which softens
this, but the same leak exists. Not changed here (research only); worth its own test with deposits before any decision.

## Candidates at 0.50%/side (selected setting per idea)
| Idea | Dev CAGR | Dev DD | Eval CAGR | Eval DD | Eval trades | vs exact VMM eval (26.1) |
|---|---|---|---|---|---|---|
| A risk-adjusted momentum, 20 | 13.3 | -28.6 | 26.9 | -26.5 | 179 | +0.8 (bar is +3) |
| B blended 3/6/12m momentum, 20 | 15.6 | -31.8 | 21.3 | -28.8 | 214 | -4.8 |
| C RSI(2) mean reversion | -9.8 to -16.4 | -86 to -93 | not run (failed dev) | | | FAIL |
| D squeeze breakout, 10 | 9.3 | -27.8 | 18.7 | -12.3 | 43 | -7.4 |
| E 52w high on 2x volume, 10 | 16.2 | -33.6 | 5.2 | -26.5 | 234 | -20.9 |
| F gap-down reversal, 10 | 3.8 | -28.3 | 6.0 | -18.6 | 305 | -20.1 |
| G sector ETF rotation, 2 | 8.0 | -30.0 | 4.9 | -28.1 | 27 | -21.2 |
| H LightGBM walk-forward ranker, 20 | 6.0 | -24.8 | 8.2 | -13.9 | 284 | -17.9 |

**Result: 0 of 8 ideas pass.** None beats VMM-without-parking in development; none beats exact VMM by 3+ points in evaluation.
The Deflated Sharpe test was not needed (no candidate reached it). Dilip's targets ($100/day on $5,000; 3x VMM CAGR) were not
approached by anything: the best full-period figure was VMM without parking at about $46/day average, mostly from compounding late.

Notes:
- RSI(2) mean reversion makes money at 0.10% costs (21-23%/yr) but is wiped out at 0.25-0.50%: ~3,400-7,000 trades.
- E (52w-high on volume) looked good in dev (16.2%) and collapsed in eval (5.2%): classic overfit/regime decay.
- The ML ranker trailed simple momentum in both periods, consistent with ML Discovery V1.
- Results are path-sensitive with $5,000 and whole shares (e.g. VMM_nopark dev 19.6% at 0.10% vs 20.6% at 0.50%), so
  differences of 1-3 points between settings are noise.
- Trials in V2: 38 settings x 3 costs (dev) + 9 x 3 (eval). Project-wide trial count now ~6,100+.
