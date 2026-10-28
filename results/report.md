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
| MATR.TO | 2026-10-20 | 21.29 | 20.46 | -4.1% |
| MSA.TO | 2026-10-20 | 9.17 | 8.88 | -3.4% |
| ARE.TO | 2026-10-20 | 50.0 | 50.27 | +0.3% |
| MSA.TO | 2026-10-21 | 8.94 | 8.88 | -0.9% |
| ARE.TO | 2026-10-21 | 48.25 | 50.27 | +4.0% |
| ATH.TO | 2026-10-22 | 11.97 | 11.91 | -0.7% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 1920 listings with price history; 192 real companies passed the safety filter (price >= $2, >= $1M traded/day). 1 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| CHR.TO | TSX | Bullish Belt Hold | 30.5 | 31.11 | -7.1% | +14.3% | 28.32 | 34.85 | 0 | 20d |

_Generated 2026-10-28 00:38 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.88% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.41% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 417 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.88% | 4.41% | 34.67% | 1.52 | 417 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.66% | 29.04% | 1.50 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.94% | 26.41% | 1.48 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.24% | 27.36% | 1.29 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.78% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 285.46 | 291.17 | -4.3% | +8.6% | 273.21 | 309.96 | 0 | 20d |
| TD.TO | 176.57 | 180.1 | -5.2% | +10.5% | 167.31 | 195.09 | 0 | 20d |
| BNS.TO | 131.82 | 134.46 | -4.7% | +9.5% | 125.57 | 144.33 | 0 | 20d |
| BMO.TO | 241.98 | 246.82 | -4.9% | +9.7% | 230.21 | 265.53 | 0 | 20d |
| CM.TO | 163.65 | 166.92 | -5.2% | +10.4% | 155.13 | 180.69 | 0 | 20d |
| NA.TO | 209.95 | 214.15 | -5.7% | +11.4% | 198.03 | 233.79 | 0 | 20d |
| CNQ.TO | 75.95 | 77.47 | -7.9% | +15.8% | 69.94 | 87.97 | 0 | 20d |
| SU.TO | 106.99 | 109.13 | -8.9% | +17.8% | 97.47 | 126.03 | 0 | 20d |
| CNR.TO | 176.47 | 180.0 | -5.2% | +10.4% | 167.31 | 194.78 | 0 | 20d |
| CP.TO | 127.99 | 130.55 | -4.9% | +9.9% | 121.66 | 140.65 | 0 | 20d |
| SLF.TO | 112.43 | 114.68 | -4.4% | +8.8% | 107.51 | 122.28 | 0 | 20d |
| SHOP.TO | 232.93 | 237.59 | -13.5% | +27.1% | 201.39 | 296.01 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| CVE.TO | 44.48 | 45.08 | 37.48 | above 200d |
| TRP.TO | 88.27 | 85.31 | 86.79 | above 200d |
| L.TO | 68.15 | 63.27 | 63.23 | UPTREND |
| SHOP.TO | 232.93 | 211.89 | 180.24 | UPTREND |
| SLF.TO | 112.43 | 110.98 | 100.27 | UPTREND |
| MFC.TO | 63.2 | 60.97 | 54.7 | UPTREND |
| CP.TO | 127.99 | 124.82 | 118.57 | UPTREND |
| CNR.TO | 176.47 | 170.73 | 158.41 | UPTREND |
| TD.TO | 176.57 | 167.6 | 150.99 | UPTREND |
| RY.TO | 285.46 | 281.72 | 258.77 | UPTREND |
| SU.TO | 106.99 | 98.36 | 86.45 | UPTREND |
| CNQ.TO | 75.95 | 70.42 | 62.31 | UPTREND |
| NA.TO | 209.95 | 209.42 | 199.89 | UPTREND |
| CM.TO | 163.65 | 159.13 | 148.71 | UPTREND |
| BMO.TO | 241.98 | 239.68 | 219.64 | UPTREND |
| BNS.TO | 131.82 | 127.79 | 112.07 | UPTREND |
| WCN.TO | 255.88 | 227.94 | 225.95 | UPTREND |
| ENB.TO | 68.01 | 67.9 | 71.23 | DOWNTREND |
| BN.TO | 53.43 | 53.86 | 59.15 | DOWNTREND |
| ATD.TO | 81.39 | 81.45 | 81.7 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.75% | 0.30% | 41.72% | 1.12 | 257 |
| 2023-today (out-of-sample) | 46.79% | -0.18% | 36.95% | 0.93 | 109 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| SLF.TO | ✅ | — | ✅ | ✅ Bullish Harami | 3/4 |
| RY.TO | ✅ | — | ✅ | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BMO.TO | ✅ | — | ✅ | — | 2/4 |
| CM.TO | ✅ | — | ✅ | — | 2/4 |
| ENB.TO | — | — | ✅ | ✅ Bullish Belt Hold | 2/4 |
| NA.TO | ✅ | — | ✅ | — | 2/4 |
| SU.TO | ✅ | ✅ | — | — | 2/4 |
| CNR.TO | ✅ | — | ✅ | — | 2/4 |
| WCN.TO | ✅ | — | ✅ | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — | — | 2/4 |
| L.TO | ✅ | ✅ | — | — | 2/4 |
| CVE.TO | — | — | — | ✅ Bullish Belt Hold | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| TRP.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |
| ATD.TO | — | — | — | — | 0/4 |