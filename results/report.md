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
| MATR.TO | 2026-10-20 | 21.29 | 20.61 | -3.4% |
| MSA.TO | 2026-10-20 | 9.17 | 8.89 | -3.3% |
| ARE.TO | 2026-10-20 | 50.0 | 53.52 | +6.8% |
| MSA.TO | 2026-10-21 | 8.94 | 8.89 | -0.8% |
| ARE.TO | 2026-10-21 | 48.25 | 53.52 | +10.7% |
| ATH.TO | 2026-10-22 | 11.97 | 11.94 | -0.5% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 3064 listings with price history; 305 real companies passed the safety filter (price >= $2, >= $1M traded/day). 0 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

**No market-wide consensus today - no trade.**

_Generated 2026-10-29 14:04 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.85% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.46% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.53 | > 1.3 |
| Trades | 419 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.85% | 4.46% | 34.67% | 1.53 | 419 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.32% | 3.66% | 42.64% | 1.50 | 470 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.70% | 1.94% | 26.41% | 1.48 | 201 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.85% | 1.25% | 27.36% | 1.30 | 209 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.68% | 1.13% | 25.78% | 1.28 | 214 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| RY.TO | 289.11 | 294.89 | -3.9% | +7.8% | 277.8 | 311.74 | 0 | 20d |
| TD.TO | 178.0 | 181.56 | -4.6% | +9.2% | 169.81 | 194.38 | 0 | 20d |
| BNS.TO | 133.83 | 136.51 | -4.2% | +8.4% | 128.2 | 145.09 | 0 | 20d |
| BMO.TO | 245.94 | 250.86 | -4.4% | +8.9% | 235.06 | 267.71 | 0 | 20d |
| CM.TO | 166.49 | 169.82 | -4.9% | +9.7% | 158.39 | 182.69 | 0 | 20d |
| SU.TO | 108.82 | 111.0 | -8.1% | +16.2% | 100.0 | 126.45 | 0 | 20d |
| CNR.TO | 171.61 | 175.04 | -5.5% | +11.0% | 162.16 | 190.51 | 0 | 20d |
| SLF.TO | 114.31 | 116.6 | -4.2% | +8.4% | 109.52 | 123.9 | 0 | 20d |
| SHOP.TO | 235.25 | 239.96 | -13.5% | +27.0% | 203.51 | 298.74 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| CVE.TO | 44.99 | 45.09 | 37.7 | above 200d |
| TRP.TO | 89.84 | 85.37 | 86.95 | above 200d |
| CP.TO | 121.71 | 124.57 | 118.82 | above 200d |
| L.TO | 68.27 | 63.57 | 63.29 | UPTREND |
| SHOP.TO | 235.25 | 213.09 | 180.26 | UPTREND |
| SLF.TO | 114.31 | 111.09 | 100.57 | UPTREND |
| MFC.TO | 63.31 | 61.06 | 54.83 | UPTREND |
| CNR.TO | 171.61 | 170.66 | 158.8 | UPTREND |
| TD.TO | 178.0 | 167.9 | 151.48 | UPTREND |
| RY.TO | 289.11 | 281.38 | 259.36 | UPTREND |
| SU.TO | 108.82 | 99.0 | 86.89 | UPTREND |
| CNQ.TO | 76.7 | 70.77 | 62.64 | UPTREND |
| NA.TO | 214.23 | 208.84 | 200.33 | UPTREND |
| CM.TO | 166.49 | 158.99 | 149.12 | UPTREND |
| BMO.TO | 245.94 | 239.25 | 220.28 | UPTREND |
| BNS.TO | 133.83 | 128.12 | 112.43 | UPTREND |
| WCN.TO | 251.23 | 228.82 | 226.19 | UPTREND |
| ENB.TO | 68.86 | 67.8 | 71.3 | DOWNTREND |
| BN.TO | 54.98 | 53.68 | 59.04 | DOWNTREND |
| ATD.TO | 80.4 | 81.06 | 81.77 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.56% | 0.28% | 42.96% | 1.11 | 256 |
| 2023-today (out-of-sample) | 46.36% | -0.23% | 38.29% | 0.92 | 110 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| SU.TO | ✅ | — | — | ✅ Bullish Harami | 2/4 |
| CNQ.TO | ✅ | ✅ | — (gap risk) | — | 2/4 |
| SHOP.TO | ✅ | — | — | ✅ Hammer | 2/4 |
| RY.TO | ✅ | — | — | — | 1/4 |
| BMO.TO | ✅ | — | — | — | 1/4 |
| NA.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| CVE.TO | — | — | — | ✅ Bullish Harami | 1/4 |
| BN.TO | — | — | — | ✅ Gap Up | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| L.TO | ✅ | — | — | — | 1/4 |
| ATD.TO | — | — | — | ✅ Bullish Harami | 1/4 |
| SLF.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| WCN.TO | ✅ | — | — | — | 1/4 |
| ENB.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| CP.TO | — | — | — | — | 0/4 |