# TSX Scanner - data up to 2026-10-21
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

**Plan for a $100 account: up to 2 positions of $50.** Buy at tomorrow's open with a limit order at *Buy max* (skip if it opens higher). Right after it fills, enter the take-profit and stop-loss below (prices are from today's close; if you fill a few cents different, use the % columns on your fill price). If neither hits in 30 trading days, sell at the close.

| Ticker | Company | Shares | Invest | Take profit at | Profit if hit | Stop-loss at | Loss if hit | Buy max | Target % | Stop % |
|---|---|---|---|---|---|---|---|---|---|---|
| MSA.TO | Mineros S.A. | 5 | $45.35 | $11.16 | **+$10.45** | $8.03 | **-$5.20** | $9.25 | +23.0% | -11.5% |
| ARE.TO | Aecon Group Inc. | 1 | $48.86 | $62.89 | **+$14.03** | $41.84 | **-$7.02** | $49.84 | +28.7% | -14.4% |

_Fees: Wealthsimple charges no commission on TSX trades. Profit and loss above are before the bid-ask spread (a few cents a share)._

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 2 · waiting for entry: 3 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MSA.TO | 2026-10-20 | 9.17 | 9.07 | -1.3% |
| ARE.TO | 2026-10-20 | 50.0 | 48.86 | -2.5% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2057 listings with price history; 196 real companies passed the safety filter (price >= $2, >= $1M traded/day). 1 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| AIF.TO | TSX | Bullish Belt Hold | 49.06 | 50.04 | -8.8% | +17.5% | 44.76 | 57.66 | 0 | 20d |

_Generated 2026-10-22 00:06 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.69% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.43% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 413 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.69% | 4.43% | 34.67% | 1.53 | 413 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.60% | 28.91% | 1.48 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.89% | 26.42% | 1.46 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.19% | 27.36% | 1.27 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.08% | 25.79% | 1.26 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 175.11 | 178.61 | -5.1% | +10.1% | 166.26 | 192.82 | 0 | 20d |
| BNS.TO | 131.9 | 134.54 | -4.6% | +9.3% | 125.79 | 144.11 | 0 | 20d |
| CM.TO | 161.34 | 164.57 | -5.0% | +10.0% | 153.27 | 177.48 | 0 | 20d |
| SU.TO | 110.87 | 113.09 | -7.5% | +14.9% | 102.59 | 127.43 | 0 | 20d |
| CVE.TO | 46.54 | 47.47 | -9.8% | +19.7% | 41.96 | 55.7 | 0 | 20d |
| CNR.TO | 171.53 | 174.96 | -5.2% | +10.3% | 162.69 | 189.21 | 0 | 20d |
| SLF.TO | 113.3 | 115.57 | -4.3% | +8.6% | 108.42 | 123.07 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 283.62 | 284.55 | 259.32 | above 200d |
| L.TO | 68.46 | 62.7 | 63.06 | above 200d |
| BMO.TO | 239.31 | 241.0 | 218.45 | above 200d |
| NA.TO | 207.47 | 211.04 | 199.15 | above 200d |
| TRP.TO | 87.44 | 85.31 | 86.48 | above 200d |
| CP.TO | 123.65 | 125.02 | 118.02 | above 200d |
| CNR.TO | 171.53 | 170.82 | 157.62 | UPTREND |
| ATD.TO | 83.36 | 82.19 | 81.52 | UPTREND |
| SHOP.TO | 244.93 | 210.2 | 180.16 | UPTREND |
| SLF.TO | 113.3 | 110.94 | 99.72 | UPTREND |
| MFC.TO | 63.51 | 60.8 | 54.44 | UPTREND |
| CVE.TO | 46.54 | 44.81 | 37.01 | UPTREND |
| TD.TO | 175.11 | 167.17 | 150.02 | UPTREND |
| SU.TO | 110.87 | 96.76 | 85.5 | UPTREND |
| CNQ.TO | 76.2 | 69.57 | 61.63 | UPTREND |
| CM.TO | 161.34 | 159.65 | 147.96 | UPTREND |
| BNS.TO | 131.9 | 127.3 | 111.41 | UPTREND |
| WCN.TO | 236.45 | 225.68 | 225.43 | UPTREND |
| BN.TO | 52.65 | 54.56 | 59.4 | DOWNTREND |
| ENB.TO | 67.43 | 68.15 | 71.09 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.76% | 0.31% | 43.52% | 1.12 | 255 |
| 2023-today (out-of-sample) | 45.87% | -0.25% | 38.90% | 0.91 | 109 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| BNS.TO | ✅ | ✅ | — | ✅ Three Outside Up | 3/4 |
| SHOP.TO | ✅ | ✅ | — | ✅ Bullish Engulfing, Three Outside Up, Tweezer Bottom | 3/4 |
| MFC.TO | ✅ | ✅ | — (gap risk) | ✅ Three Outside Up | 3/4 |
| CM.TO | ✅ | — | ✅ | ✅ Three Outside Up | 3/4 |
| BMO.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| TD.TO | ✅ | — | — | ✅ Three Outside Up | 2/4 |
| RY.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| NA.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| SLF.TO | ✅ | — | — | ✅ Three Outside Up | 2/4 |
| ATD.TO | ✅ | — | ✅ | — | 2/4 |
| CVE.TO | ✅ | ✅ | — | — | 2/4 |
| ENB.TO | — | — | ✅ | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| TRP.TO | — | — | ✅ | — | 1/4 |
| SU.TO | ✅ | — | — | — | 1/4 |
| CNQ.TO | ✅ | — | — (gap risk) | — | 1/4 |
| L.TO | — | ✅ | — | — | 1/4 |
| BN.TO | — | — | — | ✅ Bullish Belt Hold, Bullish Engulfing, Tweezer Bottom | 1/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| CP.TO | — | — | — | — | 0/4 |