# TSX Scanner - data up to 2026-10-23
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

**No leader pullbacks today - no trade.** Most days have none; that's normal.

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 6 · waiting for entry: 0 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MATR.TO | 2026-10-20 | 21.29 | 20.63 | -3.3% |
| MSA.TO | 2026-10-20 | 9.17 | 8.51 | -7.4% |
| ARE.TO | 2026-10-20 | 50.0 | 47.42 | -5.4% |
| MSA.TO | 2026-10-21 | 8.94 | 8.51 | -5.0% |
| ARE.TO | 2026-10-21 | 48.25 | 47.42 | -1.9% |
| ATH.TO | 2026-10-22 | 11.97 | 11.98 | -0.1% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 3154 listings with price history; 320 real companies passed the safety filter (price >= $2, >= $1M traded/day). 1 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| GFL.TO | TSX | Bullish Belt Hold, Tweezer Bottom | 63.75 | 65.03 | -7.9% | +15.7% | 58.74 | 73.78 | 0 | 20d |

_Generated 2026-10-23 23:54 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 55.18% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.36% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 415 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.18% | 4.36% | 34.67% | 1.52 | 415 |
| breakout | {'atr_stop': 2, 'atr_tgt': 6, 'hold': 20} | 50.74% | 2.71% | 28.91% | 1.51 | 203 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.96% | 26.42% | 1.49 | 199 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.25% | 27.36% | 1.30 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.79% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 174.47 | 177.96 | -5.2% | +10.3% | 165.45 | 192.51 | 0 | 20d |
| BNS.TO | 130.0 | 132.6 | -4.7% | +9.3% | 123.93 | 142.14 | 0 | 20d |
| CM.TO | 159.59 | 162.78 | -5.1% | +10.1% | 151.5 | 175.76 | 0 | 20d |
| CNQ.TO | 77.12 | 78.66 | -8.0% | +15.9% | 70.99 | 89.39 | 0 | 20d |
| SU.TO | 111.18 | 113.4 | -8.0% | +16.0% | 102.3 | 128.94 | 0 | 20d |
| CVE.TO | 45.98 | 46.9 | -10.2% | +20.3% | 41.31 | 55.33 | 0 | 20d |
| CNR.TO | 172.5 | 175.95 | -5.3% | +10.6% | 163.37 | 190.77 | 0 | 20d |
| CP.TO | 125.52 | 128.03 | -5.1% | +10.2% | 119.12 | 138.32 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 281.77 | 284.03 | 259.83 | above 200d |
| L.TO | 68.67 | 63.02 | 63.15 | above 200d |
| BMO.TO | 236.87 | 240.35 | 219.04 | above 200d |
| NA.TO | 204.96 | 210.26 | 199.51 | above 200d |
| SLF.TO | 110.78 | 110.97 | 99.99 | above 200d |
| TRP.TO | 87.32 | 85.29 | 86.63 | above 200d |
| CNR.TO | 172.5 | 170.78 | 158.02 | UPTREND |
| ATD.TO | 83.33 | 81.85 | 81.63 | UPTREND |
| SHOP.TO | 236.24 | 211.21 | 180.2 | UPTREND |
| MFC.TO | 61.99 | 60.89 | 54.57 | UPTREND |
| CP.TO | 125.52 | 124.94 | 118.29 | UPTREND |
| CVE.TO | 45.98 | 44.96 | 37.25 | UPTREND |
| TD.TO | 174.47 | 167.39 | 150.5 | UPTREND |
| SU.TO | 111.18 | 97.62 | 85.99 | UPTREND |
| CNQ.TO | 77.12 | 69.99 | 61.98 | UPTREND |
| CM.TO | 159.59 | 159.42 | 148.32 | UPTREND |
| BNS.TO | 130.0 | 127.56 | 111.74 | UPTREND |
| WCN.TO | 261.1 | 226.82 | 225.67 | UPTREND |
| BN.TO | 53.17 | 54.2 | 59.27 | DOWNTREND |
| ENB.TO | 67.37 | 68.01 | 71.16 | DOWNTREND |

## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.

### Does requiring agreement help? (consensus rule backtest)
| Period | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|
| 2016-today | 51.76% | 0.29% | 42.96% | 1.11 | 255 |
| 2023-today (out-of-sample) | 46.36% | -0.23% | 38.29% | 0.92 | 110 |

### Scanner votes
| Ticker | A Trend | B Momentum | C Volume/Risk | D Candle | Votes |
|---|---|---|---|---|---|
| WCN.TO | ✅ | — | ✅ | ✅ Gap Up | 3/4 |
| TD.TO | ✅ | ✅ | — | — | 2/4 |
| SU.TO | ✅ | — | ✅ | — | 2/4 |
| BNS.TO | ✅ | ✅ | — | — | 2/4 |
| L.TO | — | ✅ | — | ✅ Bullish Kicker | 2/4 |
| SHOP.TO | ✅ | — | — | — | 1/4 |
| ATD.TO | ✅ | — | — | — | 1/4 |
| CM.TO | ✅ | — | — | — | 1/4 |
| CNR.TO | ✅ | — | — | — | 1/4 |
| CVE.TO | ✅ | — | — | — | 1/4 |
| CNQ.TO | ✅ | — | — | — | 1/4 |
| NA.TO | — | — | ✅ | — | 1/4 |
| CP.TO | ✅ | — | — | — | 1/4 |
| MFC.TO | ✅ | — | — (gap risk) | — | 1/4 |
| BMO.TO | — | — | — | — | 0/4 |
| RY.TO | — | — | — | — | 0/4 |
| TRP.TO | — | — | — | — | 0/4 |
| ENB.TO | — | — | — | — | 0/4 |
| SLF.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |