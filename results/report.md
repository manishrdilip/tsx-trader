# TSX Scanner - data up to 2026-10-20

## CONSENSUS BUY (all 3 scanners agree)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys
Scanned 1893 stocks with price history; 332 passed the safety filter (price >= $2, >= $1M traded/day). 2 got 3/3 votes.

Top 5 by 3-month strength, earnings in next 10 days excluded:

| Ticker | Exchange | Close | 3-mo | Stop-loss | Take-profit | Max hold |
|---|---|---|---|---|---|---|
| CJ.TO | TSX | 13.45 | 27.04% | 12.37 | 14.12 | 10d |
| AIF.TO | TSX | 48.54 | 4.41% | 44.66 | 50.97 | 10d |

_Generated 2026-10-20 16:06 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `pullback` {'stop': 0.08, 'target': 0.05, 'hold': 10}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 57.07% | >= 65.00% |
| Avg monthly (2% risk sizing) | 1.00% | >= 2.00% |
| Max drawdown | 33.48% | < 10.00% |
| Profit factor | 1.21 | > 1.3 |
| Trades | 615 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| pullback | {'stop': 0.08, 'target': 0.05, 'hold': 10} | 57.07% | 1.00% | 33.48% | 1.21 | 615 |
| pullback | {'stop': 0.05, 'target': 0.05, 'hold': 10} | 55.91% | 1.53% | 42.98% | 1.20 | 626 |
| breakout | {'stop': 0.03, 'target': 0.08, 'hold': 10} | 51.57% | 0.71% | 23.82% | 1.19 | 223 |
| breakout | {'stop': 0.03, 'target': 0.06, 'hold': 10} | 51.56% | 0.71% | 24.79% | 1.18 | 225 |
| pullback | {'stop': 0.03, 'target': 0.05, 'hold': 10} | 50.15% | 1.77% | 55.42% | 1.15 | 666 |

## Today's signals (TSX in uptrend)
Buy at next open only if you choose to; levels are from today's close.

| Ticker | Close | Stop-loss | Take-profit | Max hold |
|---|---|---|---|---|
| BNS.TO | 129.87 | 119.48 | 136.36 | 10d |
| CM.TO | 158.57 | 145.89 | 166.5 | 10d |
| CNR.TO | 170.07 | 156.46 | 178.57 | 10d |
| CP.TO | 122.98 | 113.14 | 129.13 | 10d |
| SLF.TO | 112.02 | 103.06 | 117.62 | 10d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 279.01 | 284.74 | 259.06 | above 200d |
| CP.TO | 122.98 | 125.08 | 117.9 | above 200d |
| L.TO | 69.54 | 62.58 | 63.02 | above 200d |
| BMO.TO | 235.04 | 241.28 | 218.15 | above 200d |
| CM.TO | 158.57 | 159.72 | 147.77 | above 200d |
| NA.TO | 203.89 | 211.39 | 198.98 | above 200d |
| TRP.TO | 86.61 | 85.31 | 86.41 | above 200d |
| CNR.TO | 170.07 | 170.85 | 157.43 | above 200d |
| ATD.TO | 85.14 | 82.37 | 81.48 | UPTREND |
| SHOP.TO | 245.18 | 209.65 | 180.09 | UPTREND |
| SLF.TO | 112.02 | 110.96 | 99.58 | UPTREND |
| MFC.TO | 62.44 | 60.75 | 54.37 | UPTREND |
| CVE.TO | 46.12 | 44.69 | 36.89 | UPTREND |
| TD.TO | 171.21 | 167.01 | 149.79 | UPTREND |
| SU.TO | 109.03 | 96.26 | 85.24 | UPTREND |
| CNQ.TO | 75.6 | 69.34 | 61.46 | UPTREND |
| BNS.TO | 129.87 | 127.11 | 111.24 | UPTREND |
| WCN.TO | 236.6 | 225.56 | 225.43 | UPTREND |
| BN.TO | 52.44 | 54.73 | 59.47 | DOWNTREND |
| ENB.TO | 67.17 | 68.22 | 71.06 | DOWNTREND |

## CONSENSUS BUY (all 3 scanners agree)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 57.58% | 0.43% | 30.84% | 1.21 | 818 |
| 2023-today (out-of-sample) | 56.19% | 0.49% | 14.91% | 1.20 | 331 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | Votes |
|---|---|---|---|---|
| BNS.TO | ✅ | ✅ | — | 2/3 |
| SHOP.TO | ✅ | ✅ | — | 2/3 |
| CVE.TO | ✅ | ✅ | — | 2/3 |
| CNQ.TO | ✅ | ✅ | — | 2/3 |
| MFC.TO | ✅ | ✅ | — | 2/3 |
| SLF.TO | ✅ | — | — | 1/3 |
| TD.TO | ✅ | — | — | 1/3 |
| ATD.TO | ✅ | — | — | 1/3 |
| SU.TO | ✅ | — | — | 1/3 |
| WCN.TO | ✅ | — | — | 1/3 |
| BMO.TO | — | — | — | 0/3 |
| RY.TO | — | — | — | 0/3 |
| CNR.TO | — | — | — | 0/3 |
| TRP.TO | — | — | — | 0/3 |
| NA.TO | — | — | — | 0/3 |
| ENB.TO | — | — | — | 0/3 |
| CM.TO | — | — | — | 0/3 |
| BN.TO | — | — | — | 0/3 |
| CP.TO | — | — | — | 0/3 |
| L.TO | — | — | — | 0/3 |