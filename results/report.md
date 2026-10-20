# TSX Scanner - data up to 2026-10-20

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 1699 stocks with price history; 289 passed the safety filter (price >= $2, >= $1M traded/day). 2 got 4/4 votes (trend + momentum + volume/risk + bullish candle).

Top 5 by 3-month strength, earnings in next 10 days excluded:

| Ticker | Exchange | Pattern | Close | 3-mo | Stop-loss | Take-profit | Max hold |
|---|---|---|---|---|---|---|---|
| CJ.TO | TSX | Rising Three / Mat Hold | 13.45 | 27.04% | 12.37 | 14.12 | 10d |
| AIF.TO | TSX | Bullish Belt Hold | 48.4 | 4.11% | 44.53 | 50.82 | 10d |

_Generated 2026-10-20 16:19 UTC. Research only, not financial advice._

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
| pullback | {'stop': 0.05, 'target': 0.05, 'hold': 10} | 55.91% | 1.52% | 42.98% | 1.20 | 626 |
| breakout | {'stop': 0.03, 'target': 0.08, 'hold': 10} | 50.90% | 0.68% | 23.82% | 1.18 | 222 |
| breakout | {'stop': 0.03, 'target': 0.06, 'hold': 10} | 50.89% | 0.67% | 24.79% | 1.18 | 224 |
| pullback | {'stop': 0.03, 'target': 0.05, 'hold': 10} | 50.15% | 1.75% | 55.42% | 1.15 | 666 |

## Today's signals (TSX in uptrend)
Buy at next open only if you choose to; levels are from today's close.

| Ticker | Close | Stop-loss | Take-profit | Max hold |
|---|---|---|---|---|
| BNS.TO | 129.77 | 119.39 | 136.26 | 10d |
| CM.TO | 158.42 | 145.75 | 166.34 | 10d |
| CNR.TO | 169.84 | 156.25 | 178.33 | 10d |
| CP.TO | 122.75 | 112.93 | 128.89 | 10d |
| SLF.TO | 111.93 | 102.98 | 117.53 | 10d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 278.83 | 284.74 | 259.06 | above 200d |
| CP.TO | 122.75 | 125.07 | 117.9 | above 200d |
| L.TO | 69.54 | 62.58 | 63.02 | above 200d |
| BMO.TO | 234.7 | 241.27 | 218.15 | above 200d |
| CM.TO | 158.42 | 159.71 | 147.77 | above 200d |
| NA.TO | 203.66 | 211.39 | 198.98 | above 200d |
| TRP.TO | 86.67 | 85.31 | 86.41 | above 200d |
| CNR.TO | 169.84 | 170.85 | 157.43 | above 200d |
| ATD.TO | 85.06 | 82.37 | 81.48 | UPTREND |
| SHOP.TO | 245.37 | 209.65 | 180.09 | UPTREND |
| SLF.TO | 111.93 | 110.96 | 99.58 | UPTREND |
| MFC.TO | 62.3 | 60.75 | 54.37 | UPTREND |
| CVE.TO | 46.16 | 44.69 | 36.89 | UPTREND |
| TD.TO | 171.1 | 167.01 | 149.79 | UPTREND |
| SU.TO | 109.13 | 96.26 | 85.24 | UPTREND |
| CNQ.TO | 75.6 | 69.34 | 61.46 | UPTREND |
| BNS.TO | 129.77 | 127.11 | 111.24 | UPTREND |
| WCN.TO | 236.53 | 225.56 | 225.43 | UPTREND |
| BN.TO | 52.31 | 54.73 | 59.47 | DOWNTREND |
| ENB.TO | 67.2 | 68.22 | 71.06 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 59.43% | 0.13% | 20.65% | 1.16 | 281 |
| 2023-today (out-of-sample) | 53.72% | -0.12% | 13.53% | 0.91 | 121 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| SHOP.TO | ✅ | ✅ | — | ✅ Bullish Belt Hold, Bullish Engulfing, Tweezer Bottom | 3/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — | — | 2/4 |
| MFC.TO | ✅ | ✅ | — | — | 2/4 |
| CVE.TO | ✅ | ✅ | — | — | 2/4 |
| ATD.TO | ✅ | — | — | — | 1/4 |
| TD.TO | ✅ | — | — | — | 1/4 |
| SLF.TO | ✅ | — | — | — | 1/4 |
| BN.TO | — | — | — | ✅ Bullish Belt Hold, Bullish Engulfing, Tweezer Bottom | 1/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| RY.TO | — | — | — | — | 0/4 |
| BMO.TO | — | — | — | — | 0/4 |
| CNR.TO | — | — | — | — | 0/4 |
| NA.TO | — | — | — | — | 0/4 |
| ENB.TO | — | — | — | — | 0/4 |
| CM.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| CP.TO | — | — | — | — | 0/4 |
| L.TO | — | — | — | — | 0/4 |