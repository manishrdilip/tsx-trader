# TSX Scanner - data up to 2026-10-26
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

_v2 upgrades active: ATH clearance · sector momentum · MACD+OBV confirmation · candlestick patterns · Stochastic · 20-day earnings blackout_

**No leader pullbacks today - no trade.** Most days have none; that's normal.

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 6 · waiting for entry: 0 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MATR.TO | 2026-10-20 | 21.29 | 20.63 | -3.3% |
| MSA.TO | 2026-10-20 | 9.17 | 8.51 | -7.4% |
| ARE.TO | 2026-10-20 | 50.0 | 49.02 | -2.2% |
| MSA.TO | 2026-10-21 | 8.94 | 8.51 | -5.0% |
| ARE.TO | 2026-10-21 | 48.25 | 49.02 | +1.4% |
| ATH.TO | 2026-10-22 | 11.97 | 12.035 | +0.3% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2020 listings with price history; 202 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-26 17:34 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.90% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.42% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 415 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.90% | 4.42% | 34.67% | 1.53 | 415 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.53% | 3.55% | 42.64% | 1.49 | 470 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.09% | 1.91% | 26.42% | 1.48 | 198 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.25% | 1.19% | 27.36% | 1.28 | 206 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.14% | 1.08% | 25.79% | 1.26 | 211 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 283.9 | 289.58 | -4.2% | +8.4% | 272.01 | 307.68 | 0 | 20d |
| TD.TO | 175.99 | 179.51 | -5.1% | +10.3% | 166.95 | 194.08 | 0 | 20d |
| BNS.TO | 131.38 | 134.01 | -4.7% | +9.4% | 125.2 | 143.74 | 0 | 20d |
| CM.TO | 162.24 | 165.48 | -5.1% | +10.2% | 153.95 | 178.81 | 0 | 20d |
| CNQ.TO | 77.31 | 78.86 | -7.7% | +15.4% | 71.34 | 89.25 | 0 | 20d |
| SU.TO | 111.79 | 114.03 | -8.0% | +16.0% | 102.84 | 129.7 | 0 | 20d |
| CVE.TO | 46.58 | 47.51 | -9.4% | +18.9% | 42.18 | 55.38 | 0 | 20d |
| CNR.TO | 173.08 | 176.54 | -5.2% | +10.4% | 164.1 | 191.04 | 0 | 20d |
| CP.TO | 125.91 | 128.43 | -4.9% | +9.8% | 119.77 | 138.19 | 0 | 20d |
| SLF.TO | 111.75 | 113.98 | -4.6% | +9.2% | 106.59 | 122.07 | 0 | 20d |
| SHOP.TO | 237.02 | 241.76 | -13.2% | +26.5% | 205.65 | 299.76 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| L.TO | 68.43 | 63.14 | 63.19 | above 200d |
| BMO.TO | 239.73 | 240.01 | 219.33 | above 200d |
| ATD.TO | 82.59 | 81.65 | 81.67 | above 200d |
| NA.TO | 207.65 | 209.83 | 199.7 | above 200d |
| TRP.TO | 87.66 | 85.3 | 86.71 | above 200d |
| RY.TO | 283.9 | 283.72 | 260.1 | UPTREND |
| CNR.TO | 173.08 | 170.7 | 158.2 | UPTREND |
| SHOP.TO | 237.02 | 211.54 | 180.22 | UPTREND |
| SLF.TO | 111.75 | 110.97 | 100.13 | UPTREND |
| MFC.TO | 62.61 | 60.93 | 54.64 | UPTREND |
| CP.TO | 125.91 | 124.85 | 118.42 | UPTREND |
| CVE.TO | 46.58 | 45.05 | 37.37 | UPTREND |
| TD.TO | 175.99 | 167.5 | 150.75 | UPTREND |
| SU.TO | 111.79 | 98.05 | 86.23 | UPTREND |
| CNQ.TO | 77.31 | 70.22 | 62.15 | UPTREND |
| CM.TO | 162.24 | 159.28 | 148.51 | UPTREND |
| BNS.TO | 131.38 | 127.69 | 111.91 | UPTREND |
| WCN.TO | 261.73 | 227.44 | 225.82 | UPTREND |
| BN.TO | 53.27 | 54.01 | 59.21 | DOWNTREND |
| ENB.TO | 67.6 | 67.95 | 71.19 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.75% | 0.30% | 42.96% | 1.12 | 257 |
| 2023-today (out-of-sample) | 46.36% | -0.23% | 38.29% | 0.92 | 110 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| CVE.TO | ✅ | ✅ | — | ✅ Bullish Belt Hold | 3/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| SLF.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| RY.TO | ✅ | — | — | — | 1/4 |
| CNQ.TO | ✅ | — | — | — | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| ENB.TO | — | — | — | ✅ Bullish Belt Hold | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| L.TO | — | ✅ | — | — | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| BMO.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| NA.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |
| ATD.TO | — | — | — | — | 0/4 |