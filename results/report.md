# TSX Scanner - data up to 2026-10-27
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

_v2 upgrades active: ATH clearance · sector momentum · MACD+OBV confirmation · candlestick patterns · Stochastic · 20-day earnings blackout_

**No leader pullbacks today - no trade.** Most days have none; that's normal.

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 6 · waiting for entry: 0 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MATR.TO | 2026-10-20 | 21.29 | 20.62 | -3.3% |
| MSA.TO | 2026-10-20 | 9.17 | 8.88 | -3.4% |
| ARE.TO | 2026-10-20 | 50.0 | 50.01 | -0.2% |
| MSA.TO | 2026-10-21 | 8.94 | 8.88 | -0.9% |
| ARE.TO | 2026-10-21 | 48.25 | 50.01 | +3.4% |
| ATH.TO | 2026-10-22 | 11.97 | 11.96 | -0.3% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2588 listings with price history; 252 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-27 16:06 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.88% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.42% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 417 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.88% | 4.42% | 34.67% | 1.52 | 417 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.50% | 2.60% | 28.91% | 1.49 | 202 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.09% | 1.89% | 26.42% | 1.47 | 198 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.25% | 1.19% | 27.36% | 1.28 | 206 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.14% | 1.08% | 25.79% | 1.26 | 211 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 284.67 | 290.36 | -4.3% | +8.6% | 272.42 | 309.17 | 0 | 20d |
| TD.TO | 176.22 | 179.74 | -5.2% | +10.4% | 167.03 | 194.6 | 0 | 20d |
| BNS.TO | 131.74 | 134.37 | -4.7% | +9.4% | 125.52 | 144.18 | 0 | 20d |
| BMO.TO | 240.86 | 245.68 | -4.8% | +9.6% | 229.31 | 263.97 | 0 | 20d |
| CM.TO | 163.23 | 166.49 | -5.2% | +10.4% | 154.76 | 180.17 | 0 | 20d |
| CNQ.TO | 76.23 | 77.75 | -7.8% | +15.7% | 70.26 | 88.17 | 0 | 20d |
| SU.TO | 108.71 | 110.88 | -8.5% | +16.9% | 99.51 | 127.11 | 0 | 20d |
| CVE.TO | 45.33 | 46.24 | -9.9% | +19.7% | 40.86 | 54.27 | 0 | 20d |
| CNR.TO | 175.65 | 179.16 | -5.1% | +10.3% | 166.63 | 193.69 | 0 | 20d |
| CP.TO | 127.48 | 130.03 | -4.9% | +9.7% | 121.29 | 139.87 | 0 | 20d |
| SLF.TO | 112.22 | 114.46 | -4.4% | +8.7% | 107.31 | 122.04 | 0 | 20d |
| SHOP.TO | 233.6 | 238.27 | -13.5% | +27.0% | 202.06 | 296.68 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| NA.TO | 208.57 | 209.39 | 199.89 | above 200d |
| TRP.TO | 87.53 | 85.29 | 86.78 | above 200d |
| RY.TO | 284.67 | 281.71 | 258.76 | UPTREND |
| TD.TO | 176.22 | 167.59 | 150.99 | UPTREND |
| L.TO | 68.33 | 63.28 | 63.23 | UPTREND |
| SHOP.TO | 233.6 | 211.9 | 180.24 | UPTREND |
| SLF.TO | 112.22 | 110.97 | 100.27 | UPTREND |
| MFC.TO | 63.17 | 60.97 | 54.7 | UPTREND |
| CP.TO | 127.48 | 124.81 | 118.56 | UPTREND |
| CNR.TO | 175.65 | 170.72 | 158.4 | UPTREND |
| CVE.TO | 45.33 | 45.09 | 37.49 | UPTREND |
| SU.TO | 108.71 | 98.4 | 86.46 | UPTREND |
| CNQ.TO | 76.23 | 70.43 | 62.32 | UPTREND |
| CM.TO | 163.23 | 159.12 | 148.71 | UPTREND |
| BMO.TO | 240.86 | 239.66 | 219.63 | UPTREND |
| BNS.TO | 131.74 | 127.79 | 112.07 | UPTREND |
| WCN.TO | 257.12 | 227.97 | 225.96 | UPTREND |
| BN.TO | 53.25 | 53.86 | 59.15 | DOWNTREND |
| ENB.TO | 67.54 | 67.89 | 71.23 | DOWNTREND |
| ATD.TO | 81.69 | 81.45 | 81.71 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 52.17% | 0.32% | 41.72% | 1.13 | 253 |
| 2023-today (out-of-sample) | 46.79% | -0.18% | 36.95% | 0.93 | 109 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| BMO.TO | ✅ | — | ✅ | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — | — | 2/4 |
| L.TO | ✅ | ✅ | — | — | 2/4 |
| SU.TO | ✅ | ✅ | — | — | 2/4 |
| CVE.TO | ✅ | — | — | ✅ Bullish Belt Hold | 2/4 |
| SLF.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| RY.TO | ✅ | — | — | — | 1/4 |
| ENB.TO | — | — | — | ✅ Bullish Belt Hold | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| TRP.TO | — | — | — | — | 0/4 |
| NA.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |
| ATD.TO | — | — | — | — | 0/4 |