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
| ARE.TO | 2026-10-20 | 50.0 | 48.67 | -2.9% |
| MSA.TO | 2026-10-21 | 8.94 | 8.51 | -5.0% |
| ARE.TO | 2026-10-21 | 48.25 | 48.67 | +0.7% |
| ATH.TO | 2026-10-22 | 11.97 | 12.035 | +0.3% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2105 listings with price history; 216 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-26 16:03 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.66% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.39% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 415 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.66% | 4.39% | 34.67% | 1.53 | 415 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.70% | 28.91% | 1.51 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.95% | 26.42% | 1.49 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.24% | 27.36% | 1.29 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.79% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 175.18 | 178.68 | -5.2% | +10.3% | 166.14 | 193.27 | 0 | 20d |
| BNS.TO | 130.85 | 133.47 | -4.7% | +9.4% | 124.67 | 143.21 | 0 | 20d |
| CM.TO | 161.6 | 164.83 | -5.1% | +10.2% | 153.34 | 178.12 | 0 | 20d |
| CNQ.TO | 76.85 | 78.39 | -7.8% | +15.5% | 70.88 | 88.79 | 0 | 20d |
| SU.TO | 111.54 | 113.77 | -8.0% | +15.9% | 102.65 | 129.33 | 0 | 20d |
| CVE.TO | 46.49 | 47.42 | -9.4% | +18.9% | 42.11 | 55.26 | 0 | 20d |
| CNR.TO | 173.01 | 176.47 | -5.2% | +10.4% | 164.03 | 190.97 | 0 | 20d |
| CP.TO | 125.63 | 128.14 | -4.9% | +9.8% | 119.49 | 137.91 | 0 | 20d |
| SLF.TO | 111.13 | 113.35 | -4.6% | +9.3% | 105.97 | 121.45 | 0 | 20d |
| SHOP.TO | 236.38 | 241.11 | -13.3% | +26.5% | 205.01 | 299.12 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 282.75 | 283.7 | 260.1 | above 200d |
| L.TO | 68.42 | 63.14 | 63.19 | above 200d |
| BMO.TO | 238.92 | 240.0 | 219.33 | above 200d |
| ATD.TO | 82.47 | 81.65 | 81.67 | above 200d |
| NA.TO | 207.15 | 209.82 | 199.7 | above 200d |
| TRP.TO | 87.61 | 85.3 | 86.71 | above 200d |
| CNR.TO | 173.01 | 170.7 | 158.2 | UPTREND |
| SHOP.TO | 236.38 | 211.52 | 180.22 | UPTREND |
| SLF.TO | 111.13 | 110.96 | 100.13 | UPTREND |
| MFC.TO | 62.33 | 60.93 | 54.63 | UPTREND |
| CP.TO | 125.63 | 124.84 | 118.42 | UPTREND |
| CVE.TO | 46.49 | 45.05 | 37.37 | UPTREND |
| TD.TO | 175.18 | 167.49 | 150.74 | UPTREND |
| SU.TO | 111.54 | 98.04 | 86.23 | UPTREND |
| CNQ.TO | 76.85 | 70.21 | 62.15 | UPTREND |
| CM.TO | 161.6 | 159.27 | 148.51 | UPTREND |
| BNS.TO | 130.85 | 127.68 | 111.9 | UPTREND |
| WCN.TO | 260.29 | 227.41 | 225.81 | UPTREND |
| BN.TO | 53.43 | 54.01 | 59.21 | DOWNTREND |
| ENB.TO | 67.56 | 67.95 | 71.19 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 52.16% | 0.32% | 42.96% | 1.13 | 255 |
| 2023-today (out-of-sample) | 46.36% | -0.23% | 38.29% | 0.92 | 110 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| CVE.TO | ✅ | ✅ | — | ✅ Bullish Belt Hold | 3/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| MFC.TO | ✅ | — | — (gap risk) | ✅ Bullish Harami | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| L.TO | — | ✅ | — | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| SLF.TO | ✅ | — | — | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| CNQ.TO | ✅ | — | — | — | 1/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| RY.TO | — | — | — | — | 0/4 |
| BMO.TO | — | — | — | — | 0/4 |
| NA.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| ENB.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |
| ATD.TO | — | — | — | — | 0/4 |