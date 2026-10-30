# TSX Scanner - data up to 2026-10-29
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

_v2 upgrades active: ATH clearance · sector momentum · MACD+OBV confirmation · candlestick patterns · Stochastic · 20-day earnings blackout_

**No leader pullbacks today - no trade.** Most days have none; that's normal.

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 6 · waiting for entry: 0 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MATR.TO | 2026-10-20 | 21.29 | 20.67 | -3.1% |
| MSA.TO | 2026-10-20 | 9.17 | 8.94 | -2.7% |
| ARE.TO | 2026-10-20 | 50.0 | 53.46 | +6.7% |
| MSA.TO | 2026-10-21 | 8.94 | 8.94 | -0.2% |
| ARE.TO | 2026-10-21 | 48.25 | 53.46 | +10.6% |
| ATH.TO | 2026-10-22 | 11.97 | 11.94 | -0.5% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 3440 listings with price history; 349 real companies passed the safety filter (price >= $2, >= $1M traded/day). 3 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| DSG.TO | TSX | Bullish Pin Bar, Dragonfly Doji | 128.77 | 131.35 | -8.9% | +17.8% | 117.32 | 151.67 | 0 | 20d |
| KXS.TO | TSX | Bullish Pin Bar, Hammer | 192.64 | 196.49 | -8.9% | +17.9% | 175.41 | 227.1 | 0 | 20d |
| CGY.TO | TSX | Bullish Belt Hold, Bullish Engulfing, Bullish Pin Bar, Hammer, Morning Star | 85.14 | 86.84 | -8.2% | +16.3% | 78.2 | 99.03 | 0 | 20d |

_Generated 2026-10-30 01:13 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 56.09% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.48% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 419 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 56.09% | 4.48% | 34.67% | 1.53 | 419 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 51.22% | 2.68% | 30.36% | 1.51 | 205 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.70% | 1.95% | 26.41% | 1.48 | 201 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.85% | 1.25% | 27.36% | 1.30 | 209 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.68% | 1.13% | 25.78% | 1.28 | 214 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 288.21 | 293.97 | -4.0% | +8.0% | 276.62 | 311.38 | 0 | 20d |
| TD.TO | 178.13 | 181.69 | -4.6% | +9.2% | 169.9 | 194.59 | 0 | 20d |
| BNS.TO | 133.44 | 136.11 | -4.3% | +8.5% | 127.75 | 144.83 | 0 | 20d |
| BMO.TO | 246.28 | 251.21 | -4.6% | +9.1% | 235.03 | 268.78 | 0 | 20d |
| CM.TO | 166.22 | 169.54 | -4.9% | +9.8% | 158.07 | 182.52 | 0 | 20d |
| SU.TO | 108.65 | 110.82 | -8.3% | +16.7% | 99.6 | 126.76 | 0 | 20d |
| CNR.TO | 173.68 | 177.15 | -5.5% | +11.0% | 164.09 | 192.85 | 0 | 20d |
| SLF.TO | 114.49 | 116.78 | -4.2% | +8.4% | 109.7 | 124.08 | 0 | 20d |
| SHOP.TO | 233.7 | 238.37 | -13.6% | +27.2% | 201.86 | 297.38 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| CVE.TO | 45.02 | 45.09 | 37.7 | above 200d |
| TRP.TO | 90.06 | 85.37 | 86.95 | above 200d |
| CP.TO | 123.7 | 124.61 | 118.83 | above 200d |
| L.TO | 68.5 | 63.58 | 63.29 | UPTREND |
| SHOP.TO | 233.7 | 213.06 | 180.25 | UPTREND |
| SLF.TO | 114.49 | 111.09 | 100.57 | UPTREND |
| MFC.TO | 63.33 | 61.06 | 54.83 | UPTREND |
| CNR.TO | 173.68 | 170.7 | 158.81 | UPTREND |
| TD.TO | 178.13 | 167.91 | 151.48 | UPTREND |
| RY.TO | 288.21 | 281.36 | 259.35 | UPTREND |
| SU.TO | 108.65 | 98.99 | 86.89 | UPTREND |
| CNQ.TO | 77.05 | 70.77 | 62.64 | UPTREND |
| NA.TO | 213.33 | 208.82 | 200.33 | UPTREND |
| CM.TO | 166.22 | 158.98 | 149.12 | UPTREND |
| BMO.TO | 246.28 | 239.26 | 220.28 | UPTREND |
| BNS.TO | 133.44 | 128.11 | 112.42 | UPTREND |
| WCN.TO | 254.46 | 228.88 | 226.21 | UPTREND |
| ENB.TO | 68.9 | 67.81 | 71.3 | DOWNTREND |
| BN.TO | 55.21 | 53.69 | 59.04 | DOWNTREND |
| ATD.TO | 80.47 | 81.06 | 81.77 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.78% | 0.30% | 42.30% | 1.11 | 253 |
| 2023-today (out-of-sample) | 46.30% | -0.20% | 37.57% | 0.92 | 108 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| BMO.TO | ✅ | — | ✅ | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
| CM.TO | ✅ | — | ✅ | — | 2/4 |
| WCN.TO | ✅ | ✅ | — | — | 2/4 |
| ATD.TO | — | — | ✅ | ✅ Bullish Harami, Bullish Pin Bar | 2/4 |
| SU.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| L.TO | ✅ | ✅ | — | — | 2/4 |
| SHOP.TO | ✅ | — | — | ✅ Bullish Pin Bar | 2/4 |
| BN.TO | — | — | ✅ | ✅ Gap Up | 2/4 |
| SLF.TO | ✅ | — | ✅ | — | 2/4 |
| TD.TO | ✅ | — | — | — | 1/4 |
| RY.TO | ✅ | — | — | — | 1/4 |
| NA.TO | ✅ | — | — | — | 1/4 |
| CVE.TO | — | — | — | ✅ Bullish Harami, Bullish Pin Bar | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| CP.TO | — | — | ✅ | — | 1/4 |
| TRP.TO | — | — | — | — | 0/4 |
| ENB.TO | — | — | — | — | 0/4 |