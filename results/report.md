# TSX Scanner - data up to 2026-10-22
## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)
_Backtest 2009-01-02 to 2026-10-20, 249 real TSX/TSXV companies, max 2 positions:_ **26.2%/yr** (≈2.0%/month) vs XIC buy-and-hold 11.0%/yr · win rate 53.1% · avg win +13.0% / avg loss -8.7% · worst drawdown 34.4% · 4 losing years of 18.

**Plan for a $100 account: up to 2 positions of $50.** Buy at tomorrow's open with a limit order at *Buy max* (skip if it opens higher). Right after it fills, enter the take-profit and stop-loss below (prices are from today's close; if you fill a few cents different, use the % columns on your fill price). If neither hits in 30 trading days, sell at the close.

| Ticker | Company | Shares | Invest | Take profit at | Profit if hit | Stop-loss at | Loss if hit | Buy max | Target % | Stop % |
|---|---|---|---|---|---|---|---|---|---|---|
| ATH.TO | Athabasca Oil Corporation | 4 | $47.64 | $13.64 | **+$6.92** | $11.04 | **-$3.48** | $12.15 | +14.6% | -7.3% |

_Fees: Wealthsimple charges no commission on TSX trades. Profit and loss above are before the bid-ask spread (a few cents a share)._

## Live paper-trade scorecard (picks logged before the outcome was known)
No closed trades yet.
Open: 4 · waiting for entry: 2 · skipped (opened above buy max): 0
| Ticker | Signal | Entry | Last | Unrealized |
|---|---|---|---|---|
| MSA.TO | 2026-10-20 | 9.17 | 8.46 | -7.9% |
| ARE.TO | 2026-10-20 | 50.0 | 47.93 | -4.3% |
| MSA.TO | 2026-10-21 | 8.94 | 8.46 | -5.6% |
| ARE.TO | 2026-10-21 | 48.25 | 47.93 | -0.9% |
_Fewer than 30 closed trades: too few to judge yet. The backtest says ~53% winners; expect long losing streaks along the way._


## WATCHLIST CONSENSUS BUY (all 4 scanners agree: trend, momentum, volume/risk, bullish candle)
**No consensus today - no trade.** This is the safety rule working.



## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)
Scanned 2201 listings with price history; 228 real companies passed the safety filter (price >= $2, >= $1M traded/day). 2 got 4/4 votes. Stocks whose worst overnight gap-down in the past year was bigger than their stop are excluded.

Top 5 by 3-month strength, earnings in next 10 days excluded.

**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Exchange | Pattern | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|---|---|
| GFL.TO | TSX | Tweezer Bottom | 61.74 | 62.97 | -7.9% | +15.7% | 56.89 | 71.45 | 0 | 20d |
| GEI.TO | TSX | Rising Three / Mat Hold | 33.01 | 33.67 | -6.3% | +12.7% | 30.91 | 37.2 | 0 | 20d |

_Generated 2026-10-23 00:04 UTC. Research only, not financial advice._

## Goal check (out-of-sample 2023-today)
**Best strategy:** `trend_template` {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20}

| Metric | Result | Goal |
|---|---|---|
| Win rate | 56.04% | >= 65.00% |
| Avg monthly (2% risk sizing) | 4.41% | >= 2.00% |
| Max drawdown | 34.67% | < 10.00% |
| Profit factor | 1.52 | > 1.3 |
| Trades | 414 | 50+ |

**Verdict:** Does NOT meet the goal - keep paper trading / prefer an ETF like XEQT

## Top 5 from training, re-tested out-of-sample
| Strategy | Params | Win | Monthly | Max DD | PF | Trades |
|---|---|---|---|---|---|---|
| trend_template | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 56.04% | 4.41% | 34.67% | 1.52 | 414 |
| breakout | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 59.30% | 1.99% | 26.41% | 1.49 | 199 |
| pullback | {'atr_stop': 3, 'atr_tgt': 6, 'hold': 20} | 55.56% | 3.57% | 42.64% | 1.49 | 468 |
| breakout | {'atr_stop': 3, 'atr_tgt': 4, 'hold': 20} | 58.45% | 1.27% | 27.36% | 1.30 | 207 |
| breakout | {'atr_stop': 3, 'atr_tgt': 3, 'hold': 20} | 61.32% | 1.12% | 25.78% | 1.27 | 212 |

## Today's signals (TSX in uptrend)
**How to enter:** buy at the next open with a limit order no higher than *Buy max* (skip if it opens above). After your order fills, set the stop and target as **percentages of YOUR fill price** (Stop % / Target % columns). Shares = what keeps your loss at 2% of the account if the stop is hit.

| Ticker | Close | Buy max | Stop % | Target % | Stop (from close) | Target (from close) | Shares ($100 acct) | Max hold |
|---|---|---|---|---|---|---|---|---|
| TD.TO | 175.14 | 178.64 | -5.0% | +9.9% | 166.45 | 192.52 | 0 | 20d |
| BNS.TO | 130.72 | 133.33 | -4.6% | +9.2% | 124.71 | 142.74 | 0 | 20d |
| CM.TO | 161.0 | 164.22 | -4.9% | +9.8% | 153.15 | 176.7 | 0 | 20d |
| CNQ.TO | 75.5 | 77.01 | -8.0% | +16.1% | 69.42 | 87.65 | 0 | 20d |
| SU.TO | 108.39 | 110.56 | -8.1% | +16.2% | 99.63 | 125.91 | 0 | 20d |
| CNR.TO | 175.01 | 178.51 | -5.2% | +10.4% | 165.95 | 193.13 | 0 | 20d |
| CP.TO | 126.93 | 129.47 | -5.0% | +10.0% | 120.62 | 139.56 | 0 | 20d |
| SLF.TO | 113.08 | 115.34 | -4.2% | +8.4% | 108.31 | 122.62 | 0 | 20d |

## Trend status of watchlist
| Ticker | Close | 50d | 200d | Trend |
|---|---|---|---|---|
| RY.TO | 282.78 | 284.35 | 259.58 | above 200d |
| NA.TO | 207.31 | 210.71 | 199.33 | above 200d |
| L.TO | 70.66 | 62.88 | 63.11 | above 200d |
| TRP.TO | 86.86 | 85.3 | 86.55 | above 200d |
| CVE.TO | 44.88 | 44.88 | 37.13 | above 200d |
| BMO.TO | 238.7 | 240.73 | 218.75 | above 200d |
| CM.TO | 161.0 | 159.58 | 148.15 | UPTREND |
| CNQ.TO | 75.5 | 69.76 | 61.8 | UPTREND |
| SU.TO | 108.39 | 97.17 | 85.74 | UPTREND |
| TD.TO | 175.14 | 167.32 | 150.26 | UPTREND |
| CNR.TO | 175.01 | 170.83 | 157.81 | UPTREND |
| CP.TO | 126.93 | 125.01 | 118.15 | UPTREND |
| MFC.TO | 63.81 | 60.87 | 54.51 | UPTREND |
| SLF.TO | 113.08 | 110.98 | 99.86 | UPTREND |
| SHOP.TO | 236.41 | 210.69 | 180.18 | UPTREND |
| ATD.TO | 84.58 | 82.02 | 81.58 | UPTREND |
| BNS.TO | 130.72 | 127.46 | 111.57 | UPTREND |
| WCN.TO | 258.95 | 226.21 | 225.53 | UPTREND |
| ENB.TO | 67.19 | 68.08 | 71.12 | DOWNTREND |
| BN.TO | 53.56 | 54.38 | 59.33 | DOWNTREND |

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
| TD.TO | ✅ | ✅ | — | ✅ Three Outside Up | 3/4 |
| BNS.TO | ✅ | ✅ | — | ✅ Three Outside Up | 3/4 |
| SU.TO | ✅ | ✅ | ✅ | — | 3/4 |
| CM.TO | ✅ | — | ✅ | ✅ Three Outside Up | 3/4 |
| WCN.TO | ✅ | — | ✅ | ✅ Gap Up | 3/4 |
| MFC.TO | ✅ | ✅ | — (gap risk) | ✅ Three Outside Up | 3/4 |
| BMO.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| RY.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| CNR.TO | ✅ | — | ✅ | — | 2/4 |
| SLF.TO | ✅ | — | — | ✅ Three Outside Up | 2/4 |
| CNQ.TO | ✅ | ✅ | — | — | 2/4 |
| NA.TO | — | — | ✅ | ✅ Three Outside Up | 2/4 |
| ATD.TO | ✅ | — | ✅ | — | 2/4 |
| SHOP.TO | ✅ | — | — | ✅ Three Outside Up | 2/4 |
| CP.TO | ✅ | — | ✅ | — | 2/4 |
| TRP.TO | — | — | ✅ | — | 1/4 |
| L.TO | — | — | — | ✅ Bullish Kicker | 1/4 |
| ENB.TO | — | — | — | — | 0/4 |
| CVE.TO | — | — | — | — | 0/4 |
| BN.TO | — | — | — | — | 0/4 |