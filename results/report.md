# TSX Scanner - data up to 2026-10-28
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
| MSA.TO | 2026-10-20 | 9.17 | 9.21 | +0.2% |
| ARE.TO | 2026-10-20 | 50.0 | 53.27 | +6.3% |
| MSA.TO | 2026-10-21 | 8.94 | 9.21 | +2.8% |
| ARE.TO | 2026-10-21 | 48.25 | 53.27 | +10.2% |
| ATH.TO | 2026-10-22 | 11.97 | 11.93 | -0.5% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 3424 listings with price history; 350 real companies passed the safety filter (price >= $2, >= $1M traded/day). 2 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| CHR.TO | TSX | Bullish Belt Hold | 30.87 | 31.49 | -6.9% | +13.8% | 28.74 | 35.13 | 0 | 20d |
| POW.TO | TSX | Three White Soldiers | 96.8 | 98.74 | -5.8% | +11.5% | 91.21 | 107.98 | 0 | 20d |

_Generated 2026-10-29 01:08 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 56.09% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.43% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 419 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 56.09% | 4.43% | 34.67% | 1.53 | 419 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.98% | 2.64% | 30.36% | 1.50 | 204 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.50% | 1.92% | 26.41% | 1.47 | 200 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.65% | 1.24% | 27.36% | 1.29 | 208 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.50% | 1.12% | 25.78% | 1.27 | 213 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 286.41 | 292.14 | -4.0% | +8.0% | 275.02 | 309.19 | 0 | 20d |
| TD.TO | 176.89 | 180.43 | -4.7% | +9.4% | 168.58 | 193.5 | 0 | 20d |
| BNS.TO | 132.27 | 134.92 | -4.3% | +8.6% | 126.57 | 143.66 | 0 | 20d |
| BMO.TO | 243.45 | 248.32 | -4.5% | +9.1% | 232.38 | 265.59 | 0 | 20d |
| CM.TO | 164.61 | 167.9 | -4.9% | +9.7% | 156.59 | 180.65 | 0 | 20d |
| SU.TO | 108.52 | 110.69 | -8.7% | +17.5% | 99.03 | 127.5 | 0 | 20d |
| CVE.TO | 45.2 | 46.1 | -9.9% | +19.7% | 40.74 | 54.13 | 0 | 20d |
| CNR.TO | 174.05 | 177.53 | -5.1% | +10.2% | 165.18 | 191.79 | 0 | 20d |
| CP.TO | 125.7 | 128.21 | -5.1% | +10.2% | 119.3 | 138.5 | 0 | 20d |
| SLF.TO | 113.18 | 115.44 | -4.2% | +8.5% | 108.39 | 122.76 | 0 | 20d |
| SHOP.TO | 235.47 | 240.18 | -13.3% | +26.6% | 204.17 | 298.08 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| TRP.TO | 88.32 | 85.33 | 86.86 | above 200d |
| RY.TO | 286.41 | 281.49 | 259.05 | UPTREND |
| L.TO | 67.98 | 63.42 | 63.25 | UPTREND |
| SHOP.TO | 235.47 | 212.47 | 180.25 | UPTREND |
| SLF.TO | 113.18 | 111.02 | 100.41 | UPTREND |
| MFC.TO | 62.67 | 61.01 | 54.76 | UPTREND |
| CP.TO | 125.7 | 124.73 | 118.7 | UPTREND |
| CNR.TO | 174.05 | 170.72 | 158.6 | UPTREND |
| TD.TO | 176.89 | 167.71 | 151.23 | UPTREND |
| CVE.TO | 45.2 | 45.09 | 37.59 | UPTREND |
| SU.TO | 108.52 | 98.69 | 86.68 | UPTREND |
| CNQ.TO | 76.78 | 70.6 | 62.48 | UPTREND |
| NA.TO | 211.73 | 209.05 | 200.11 | UPTREND |
| CM.TO | 164.61 | 159.02 | 148.91 | UPTREND |
| BMO.TO | 243.45 | 239.41 | 219.95 | UPTREND |
| BNS.TO | 132.27 | 127.93 | 112.25 | UPTREND |
| WCN.TO | 251.38 | 228.39 | 226.06 | UPTREND |
| ENB.TO | 67.89 | 67.86 | 71.26 | DOWNTREND |
| BN.TO | 53.81 | 53.76 | 59.09 | DOWNTREND |
| ATD.TO | 80.24 | 81.25 | 81.73 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.97% | 0.32% | 41.72% | 1.13 | 254 |
| 2023-today (out-of-sample) | 46.79% | -0.18% | 36.95% | 0.93 | 109 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| L.TO | ✅ | ✅ | ✅ | — | 3/4 |
| RY.TO | ✅ | — | ✅ | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BMO.TO | ✅ | — | ✅ | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
| CVE.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| SU.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| SLF.TO | ✅ | — | ✅ | — | 2/4 |
| WCN.TO | ✅ | ✅ | — | — | 2/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| ATD.TO | — | — | ✅ | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| NA.TO | ✅ | — | — | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| ENB.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |