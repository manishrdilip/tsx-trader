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
| MATR.TO | 2026-10-20 | 21.29 | 20.71 | -2.9% |
| MSA.TO | 2026-10-20 | 9.17 | 8.61 | -6.3% |
| ARE.TO | 2026-10-20 | 50.0 | 49.1 | -2.0% |
| MSA.TO | 2026-10-21 | 8.94 | 8.61 | -3.9% |
| ARE.TO | 2026-10-21 | 48.25 | 49.1 | +1.6% |
| ATH.TO | 2026-10-22 | 11.97 | 11.99 | -0.0% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 1780 listings with price history; 177 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-27 14:11 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.64% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.37% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 417 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.64% | 4.37% | 34.67% | 1.52 | 417 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.68% | 29.04% | 1.51 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.95% | 26.41% | 1.48 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.24% | 27.36% | 1.29 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.78% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 283.0 | 288.66 | -4.3% | +8.7% | 270.75 | 307.5 | 0 | 20d |
| TD.TO | 174.83 | 178.33 | -5.3% | +10.5% | 165.64 | 193.21 | 0 | 20d |
| BNS.TO | 130.82 | 133.44 | -4.7% | +9.4% | 124.67 | 143.12 | 0 | 20d |
| CM.TO | 161.79 | 165.03 | -5.1% | +10.2% | 153.53 | 178.3 | 0 | 20d |
| CNQ.TO | 76.39 | 77.92 | -7.7% | +15.4% | 70.51 | 88.15 | 0 | 20d |
| SU.TO | 109.79 | 111.99 | -8.1% | +16.3% | 100.85 | 127.68 | 0 | 20d |
| CVE.TO | 45.96 | 46.88 | -9.4% | +18.9% | 41.63 | 54.63 | 0 | 20d |
| CNR.TO | 173.73 | 177.2 | -4.9% | +9.9% | 165.13 | 190.92 | 0 | 20d |
| CP.TO | 125.89 | 128.41 | -4.8% | +9.5% | 119.89 | 137.89 | 0 | 20d |
| SLF.TO | 111.74 | 113.97 | -4.3% | +8.5% | 106.97 | 121.28 | 0 | 20d |
| SHOP.TO | 231.94 | 236.58 | -13.6% | +27.2% | 200.4 | 295.02 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| BMO.TO | 238.96 | 239.62 | 219.62 | above 200d |
| ATD.TO | 82.2 | 81.46 | 81.71 | above 200d |
| NA.TO | 207.0 | 209.36 | 199.88 | above 200d |
| TRP.TO | 87.66 | 85.29 | 86.78 | above 200d |
| RY.TO | 283.0 | 281.67 | 258.76 | UPTREND |
| CNR.TO | 173.73 | 170.68 | 158.39 | UPTREND |
| L.TO | 68.48 | 63.28 | 63.23 | UPTREND |
| SHOP.TO | 231.94 | 211.87 | 180.23 | UPTREND |
| SLF.TO | 111.74 | 110.96 | 100.26 | UPTREND |
| MFC.TO | 62.73 | 60.96 | 54.7 | UPTREND |
| CP.TO | 125.89 | 124.78 | 118.56 | UPTREND |
| CVE.TO | 45.96 | 45.11 | 37.49 | UPTREND |
| TD.TO | 174.83 | 167.57 | 150.98 | UPTREND |
| SU.TO | 109.79 | 98.42 | 86.46 | UPTREND |
| CNQ.TO | 76.39 | 70.43 | 62.32 | UPTREND |
| CM.TO | 161.79 | 159.1 | 148.7 | UPTREND |
| BNS.TO | 130.82 | 127.77 | 112.07 | UPTREND |
| WCN.TO | 258.1 | 227.99 | 225.96 | UPTREND |
| BN.TO | 53.3 | 53.86 | 59.15 | DOWNTREND |
| ENB.TO | 67.55 | 67.89 | 71.23 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.78% | 0.31% | 42.30% | 1.12 | 253 |
| 2023-today (out-of-sample) | 46.30% | -0.20% | 37.57% | 0.92 | 108 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| SU.TO | ✅ | ✅ | — | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — | — | 2/4 |
| L.TO | ✅ | ✅ | — | — | 2/4 |
| SLF.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| CVE.TO | ✅ | — | — | ✅ Bullish Belt Hold | 2/4 |
| RY.TO | ✅ | — | — | — | 1/4 |
| BMO.TO | — | — | ✅ | — | 1/4 |
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