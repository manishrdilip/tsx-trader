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
| ARE.TO | 2026-10-20 | 50.0 | 48.16 | -3.9% |
| MSA.TO | 2026-10-21 | 8.94 | 8.51 | -5.0% |
| ARE.TO | 2026-10-21 | 48.25 | 48.16 | -0.4% |
| ATH.TO | 2026-10-22 | 11.97 | 12.01 | +0.1% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2098 listings with price history; 202 real companies passed the safety filter (price >= $2, >= $1M traded/day). 1 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| GFL.TO | TSX | Bullish Belt Hold | 64.0 | 65.28 | -7.8% | +15.6% | 59.01 | 73.98 | 0 | 20d |

_Generated 2026-10-27 00:40 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.90% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.41% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 415 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.90% | 4.41% | 34.67% | 1.53 | 415 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.53% | 3.54% | 42.64% | 1.49 | 470 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.97% | 26.41% | 1.49 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.25% | 27.36% | 1.30 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.78% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 284.26 | 289.95 | -4.2% | +8.4% | 272.3 | 308.19 | 0 | 20d |
| TD.TO | 175.76 | 179.28 | -5.1% | +10.3% | 166.72 | 193.85 | 0 | 20d |
| BNS.TO | 130.73 | 133.34 | -4.7% | +9.5% | 124.55 | 143.09 | 0 | 20d |
| CM.TO | 161.92 | 165.16 | -5.1% | +10.3% | 153.6 | 178.56 | 0 | 20d |
| CNQ.TO | 77.21 | 78.75 | -7.7% | +15.5% | 71.23 | 89.17 | 0 | 20d |
| SU.TO | 111.42 | 113.65 | -8.0% | +16.1% | 102.47 | 129.33 | 0 | 20d |
| CVE.TO | 46.54 | 47.47 | -9.5% | +19.0% | 42.12 | 55.37 | 0 | 20d |
| CNR.TO | 173.0 | 176.46 | -5.2% | +10.4% | 164.02 | 190.96 | 0 | 20d |
| CP.TO | 125.91 | 128.43 | -4.9% | +9.8% | 119.75 | 138.23 | 0 | 20d |
| SLF.TO | 111.51 | 113.74 | -4.6% | +9.3% | 106.35 | 121.83 | 0 | 20d |
| SHOP.TO | 235.93 | 240.65 | -13.3% | +26.6% | 204.56 | 298.67 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| L.TO | 68.92 | 63.15 | 63.19 | above 200d |
| BMO.TO | 239.05 | 240.0 | 219.33 | above 200d |
| ATD.TO | 82.71 | 81.65 | 81.67 | above 200d |
| NA.TO | 207.3 | 209.82 | 199.7 | above 200d |
| TRP.TO | 87.58 | 85.3 | 86.71 | above 200d |
| RY.TO | 284.26 | 283.73 | 260.1 | UPTREND |
| CNR.TO | 173.0 | 170.7 | 158.2 | UPTREND |
| SHOP.TO | 235.93 | 211.51 | 180.22 | UPTREND |
| SLF.TO | 111.51 | 110.97 | 100.13 | UPTREND |
| MFC.TO | 62.59 | 60.93 | 54.64 | UPTREND |
| CP.TO | 125.91 | 124.85 | 118.42 | UPTREND |
| CVE.TO | 46.54 | 45.05 | 37.37 | UPTREND |
| TD.TO | 175.76 | 167.5 | 150.75 | UPTREND |
| SU.TO | 111.42 | 98.04 | 86.23 | UPTREND |
| CNQ.TO | 77.21 | 70.22 | 62.15 | UPTREND |
| CM.TO | 161.92 | 159.27 | 148.51 | UPTREND |
| BNS.TO | 130.73 | 127.68 | 111.9 | UPTREND |
| WCN.TO | 261.69 | 227.44 | 225.82 | UPTREND |
| BN.TO | 53.27 | 54.01 | 59.21 | DOWNTREND |
| ENB.TO | 67.65 | 67.95 | 71.19 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.97% | 0.31% | 42.30% | 1.12 | 254 |
| 2023-today (out-of-sample) | 46.30% | -0.20% | 37.57% | 0.92 | 108 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| SLF.TO | ✅ | — | ✅ | ✅ Bullish Harami | 3/4 |
| CVE.TO | ✅ | ✅ | — | ✅ Bullish Belt Hold | 3/4 |
| RY.TO | ✅ | — | ✅ | — | 2/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| ENB.TO | — | — | ✅ | ✅ Bullish Belt Hold | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| CM.TO | ✅ | — | ✅ | — | 2/4 |
| BMO.TO | — | — | ✅ | — | 1/4 |
| CNQ.TO | ✅ | — | — | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| NA.TO | — | — | ✅ | — | 1/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| L.TO | — | ✅ | — | — | 1/4 |
| TRP.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |
| ATD.TO | — | — | — | — | 0/4 |