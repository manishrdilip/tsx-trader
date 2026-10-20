# TSX Scanner - data up to 2026-10-20

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 1738 stocks with price history; 295 passed the safety filter (price >= $2, >= $1M traded/day). 1 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| AIF.TO | TSX | Bullish Belt Hold | 48.37 | 49.34 | -8.6% | +17.2% | 44.22 | 56.67 | 0 | 20d |

_Generated 2026-10-20 16:38 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.69% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.34% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.51 | > 1.3 |
| Trades | 413 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.69% | 4.34% | 34.67% | 1.51 | 413 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.62% | 29.04% | 1.49 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.91% | 26.41% | 1.46 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.20% | 27.36% | 1.28 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.08% | 25.78% | 1.26 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 171.42 | 174.85 | -4.9% | +9.8% | 162.99 | 188.27 | 0 | 20d |
| BNS.TO | 130.03 | 132.63 | -4.6% | +9.1% | 124.11 | 141.87 | 0 | 20d |
| SU.TO | 109.18 | 111.36 | -7.5% | +15.0% | 100.97 | 125.59 | 0 | 20d |
| CVE.TO | 46.24 | 47.17 | -9.9% | +19.8% | 41.68 | 55.38 | 0 | 20d |
| SLF.TO | 112.0 | 114.24 | -4.3% | +8.5% | 107.23 | 121.54 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 279.91 | 284.76 | 259.06 | above 200d |
| CP.TO | 122.65 | 125.07 | 117.9 | above 200d |
| L.TO | 69.49 | 62.58 | 63.02 | above 200d |
| BMO.TO | 235.25 | 241.28 | 218.15 | above 200d |
| CM.TO | 158.87 | 159.72 | 147.77 | above 200d |
| NA.TO | 204.13 | 211.4 | 198.98 | above 200d |
| TRP.TO | 86.56 | 85.31 | 86.41 | above 200d |
| CNR.TO | 169.84 | 170.85 | 157.43 | above 200d |
| ATD.TO | 84.93 | 82.37 | 81.48 | UPTREND |
| SHOP.TO | 245.19 | 209.65 | 180.09 | UPTREND |
| SLF.TO | 112.0 | 110.96 | 99.58 | UPTREND |
| MFC.TO | 62.38 | 60.75 | 54.37 | UPTREND |
| CVE.TO | 46.24 | 44.69 | 36.89 | UPTREND |
| TD.TO | 171.42 | 167.02 | 149.79 | UPTREND |
| SU.TO | 109.18 | 96.26 | 85.24 | UPTREND |
| CNQ.TO | 75.69 | 69.34 | 61.46 | UPTREND |
| BNS.TO | 130.03 | 127.12 | 111.24 | UPTREND |
| WCN.TO | 236.71 | 225.56 | 225.43 | UPTREND |
| BN.TO | 52.35 | 54.73 | 59.47 | DOWNTREND |
| ENB.TO | 67.11 | 68.21 | 71.06 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.97% | 0.33% | 42.30% | 1.13 | 254 |
| 2023-today (out-of-sample) | 46.30% | -0.20% | 37.57% | 0.92 | 108 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| SHOP.TO | ✅ | ✅ | — | ✅ Bullish Belt Hold, Bullish Engulfing, Tweezer Bottom | 3/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
| MFC.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
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