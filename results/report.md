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
| ARE.TO | 2026-10-20 | 50.0 | 49.08 | -2.0% |
| MSA.TO | 2026-10-21 | 8.94 | 8.61 | -3.9% |
| ARE.TO | 2026-10-21 | 48.25 | 49.08 | +1.5% |
| ATH.TO | 2026-10-22 | 11.97 | 12.0 | +0.1% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2839 listings with price history; 285 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-27 13:46 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.64% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.38% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 417 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.64% | 4.38% | 34.67% | 1.52 | 417 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.53% | 3.55% | 42.64% | 1.49 | 470 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.09% | 1.90% | 26.41% | 1.47 | 198 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.25% | 1.19% | 27.36% | 1.28 | 206 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.14% | 1.08% | 25.78% | 1.26 | 211 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 284.28 | 289.97 | -4.2% | +8.4% | 272.36 | 308.11 | 0 | 20d |
| TD.TO | 175.58 | 179.09 | -5.1% | +10.2% | 166.66 | 193.42 | 0 | 20d |
| BNS.TO | 131.18 | 133.8 | -4.6% | +9.3% | 125.09 | 143.36 | 0 | 20d |
| BMO.TO | 239.68 | 244.47 | -4.7% | +9.3% | 228.52 | 262.01 | 0 | 20d |
| CM.TO | 162.19 | 165.43 | -5.0% | +10.0% | 154.09 | 178.4 | 0 | 20d |
| SU.TO | 110.45 | 112.66 | -8.0% | +15.9% | 101.65 | 128.05 | 0 | 20d |
| CVE.TO | 46.04 | 46.96 | -9.4% | +18.7% | 41.73 | 54.65 | 0 | 20d |
| CNR.TO | 173.38 | 176.85 | -4.9% | +9.9% | 164.83 | 190.49 | 0 | 20d |
| CP.TO | 125.94 | 128.46 | -4.8% | +9.5% | 119.96 | 137.91 | 0 | 20d |
| SLF.TO | 111.84 | 114.08 | -4.3% | +8.5% | 107.08 | 121.36 | 0 | 20d |
| SHOP.TO | 232.31 | 236.96 | -13.3% | +26.7% | 201.31 | 294.31 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| ATD.TO | 82.59 | 81.47 | 81.71 | above 200d |
| NA.TO | 208.0 | 209.38 | 199.88 | above 200d |
| TRP.TO | 87.65 | 85.29 | 86.78 | above 200d |
| RY.TO | 284.28 | 281.7 | 258.76 | UPTREND |
| CNR.TO | 173.38 | 170.67 | 158.39 | UPTREND |
| L.TO | 68.35 | 63.28 | 63.23 | UPTREND |
| SHOP.TO | 232.31 | 211.87 | 180.23 | UPTREND |
| SLF.TO | 111.84 | 110.97 | 100.26 | UPTREND |
| MFC.TO | 62.64 | 60.96 | 54.7 | UPTREND |
| CP.TO | 125.94 | 124.78 | 118.56 | UPTREND |
| CVE.TO | 46.04 | 45.11 | 37.49 | UPTREND |
| TD.TO | 175.58 | 167.58 | 150.98 | UPTREND |
| SU.TO | 110.45 | 98.43 | 86.47 | UPTREND |
| CNQ.TO | 76.5 | 70.43 | 62.32 | UPTREND |
| CM.TO | 162.19 | 159.1 | 148.7 | UPTREND |
| BMO.TO | 239.68 | 239.63 | 219.63 | UPTREND |
| BNS.TO | 131.18 | 127.78 | 112.07 | UPTREND |
| WCN.TO | 259.33 | 228.01 | 225.97 | UPTREND |
| BN.TO | 53.47 | 53.87 | 59.15 | DOWNTREND |
| ENB.TO | 67.65 | 67.9 | 71.23 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 52.16% | 0.33% | 42.96% | 1.13 | 255 |
| 2023-today (out-of-sample) | 46.36% | -0.23% | 38.29% | 0.92 | 110 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| BMO.TO | ✅ | — | ✅ | — | 2/4 |
| CNQ.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
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