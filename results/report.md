# TSX Scanner - data up to 2026-10-20
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 5 positions:_ **18.5%/yr** (≈1.4%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 30.3% · 5 losing years of 18.

**How to trade:** buy at tomorrow's open with a limit no higher than *Buy max*. After it fills, set the stop and target as % of YOUR fill price. Sell at the close after 30 trading days if neither is hit. Use 1/5 of the account per position ($100 on $500); never more than 5 open at once - take the highest RS first.

| Ticker | Company | RS | RSI2 | Close | Buy max | Stop % | Target % | Stop | Target | $ at risk |
|---|---|---|---|---|---|---|---|---|---|---|
| MATR.TO | Mattr Corp. | 99 | 4.9 | 21.27 | 21.7 | -8.6% | +17.3% | 19.43 | 24.95 | $8.65 |
| MSA.TO | Mineros S.A. | 95 | 1.5 | 9.12 | 9.3 | -11.6% | +23.3% | 8.06 | 11.24 | $11.64 |
| ARE.TO | Aecon Group Inc. | 83 | 7.9 | 49.7 | 50.69 | -14.4% | +28.8% | 42.55 | 64.0 | $14.39 |

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 0 · waiting for entry: 3 · skipped (opened above buy max): 0
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2962 listings with price history; 303 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-21 00:44 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.69% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.36% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 413 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.69% | 4.36% | 34.67% | 1.52 | 413 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 54.84% | 3.46% | 42.64% | 1.48 | 465 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.90% | 26.42% | 1.46 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.20% | 27.36% | 1.28 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.09% | 25.79% | 1.26 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($500 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 171.71 | 175.14 | -5.0% | +10.0% | 163.17 | 188.8 | 1 | 20d |
| BNS.TO | 129.78 | 132.38 | -4.6% | +9.2% | 123.79 | 141.77 | 1 | 20d |
| SU.TO | 110.11 | 112.31 | -7.5% | +14.9% | 101.9 | 126.52 | 1 | 20d |
| CVE.TO | 46.65 | 47.58 | -9.8% | +19.6% | 42.08 | 55.79 | 2 | 20d |
| SLF.TO | 111.95 | 114.19 | -4.3% | +8.5% | 107.18 | 121.49 | 2 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 280.17 | 284.76 | 259.07 | above 200d |
| CP.TO | 122.72 | 125.07 | 117.9 | above 200d |
| L.TO | 69.09 | 62.57 | 63.02 | above 200d |
| BMO.TO | 235.4 | 241.29 | 218.16 | above 200d |
| CM.TO | 159.12 | 159.73 | 147.78 | above 200d |
| NA.TO | 203.6 | 211.38 | 198.97 | above 200d |
| TRP.TO | 86.85 | 85.31 | 86.41 | above 200d |
| CNR.TO | 170.59 | 170.86 | 157.43 | above 200d |
| ATD.TO | 85.36 | 82.38 | 81.48 | UPTREND |
| SHOP.TO | 244.01 | 209.63 | 180.08 | UPTREND |
| SLF.TO | 111.95 | 110.96 | 99.58 | UPTREND |
| MFC.TO | 62.53 | 60.75 | 54.37 | UPTREND |
| CVE.TO | 46.65 | 44.7 | 36.89 | UPTREND |
| TD.TO | 171.71 | 167.02 | 149.79 | UPTREND |
| SU.TO | 110.11 | 96.28 | 85.25 | UPTREND |
| CNQ.TO | 76.23 | 69.35 | 61.47 | UPTREND |
| BNS.TO | 129.78 | 127.11 | 111.24 | UPTREND |
| WCN.TO | 238.15 | 225.59 | 225.43 | UPTREND |
| BN.TO | 52.49 | 54.74 | 59.47 | DOWNTREND |
| ENB.TO | 67.35 | 68.22 | 71.06 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.57% | 0.29% | 43.52% | 1.11 | 254 |
| 2023-today (out-of-sample) | 45.87% | -0.25% | 38.90% | 0.91 | 109 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| SHOP.TO | ✅ | ✅ | — | ✅ Bullish Engulfing, Tweezer Bottom | 3/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| CVE.TO | ✅ | ✅ | — | — | 2/4 |
| MFC.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
| ATD.TO | ✅ | — | ✅ | — | 2/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| RY.TO | — | — | ✅ | — | 1/4 |
| TD.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | — | — | ✅ | — | 1/4 |
| CNQ.TO | ✅ | — | — (gap risk) | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| ENB.TO | — | — | ✅ | — | 1/4 |
| BN.TO | — | — | — | ✅ Bullish Belt Hold, Bullish Engulfing, Tweezer Bottom | 1/4 |
| SLF.TO | ✅ | — | — | — | 1/4 |
| BMO.TO | — | — | — | — | 0/4 |
| NA.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| CM.TO | — | — | — | — | 0/4 |
| CP.TO | — | — | — | — | 0/4 |
| L.TO | — | — | — | — | 0/4 |