# TSX Quant Discovery V2 — pre-registered protocol (lean V2)

Written and committed **before** any strategy result was looked at. Dilip chose "lean V2": a handful of
distinct ideas, not 30,000 configurations. Nothing here touches live code (`vmm_bot/`, `india_vmm/`),
main, or any broker.

## Data
- Source: EODHD daily EOD (Historian plan), exchange `TO`, listed + delisted, Common Stock + ETF.
  Checked 25 Nov 2026: intraday = 403, fundamentals = 403, so no intraday/earnings/fundamental families
  (S13 5-min, S14) can be run on this subscription.
- Signals use `adjusted_close`. Fills use the adjusted open (`open * adjusted_close / close`).
- Cleaning (fixed now, same for every strategy): drop a ticker if any single-day adjusted move is > +150%
  that is reversed within 5 days, or if `adjusted_close/close` ranges more than 3x (broken adjustment).
  Crashes are kept. A stock whose data ends is sold at its last close minus 0.5% extra.
- EODHD has no TSX delistings before 2012, so 2009–2011 is still survivor-biased. Stated in every result.
- Universe (same as live VMM): `.TO` common stocks, names not matching the fund/ETF/split/trust filter,
  price $1–100, 20-day median dollar volume >= $300k, >= 253 days history. Wealthsimple trades all of these.

## Execution (every strategy, including the benchmark)
$5,000 CAD start, no deposits, long-only, whole shares, no leverage, signals at close t, fills at open t+1.
Buy limit = close × 1.01 (no fill if the open is above it); sells at the open. Costs 0.10 / 0.25 / **0.50%** per
side; 0.50% is the deciding scenario. Cash earns 0.

## Benchmarks
1. **Exact VMM** = live `vmm_bot/plan.py` in RRSP "daily" mode with current workflow settings: rank 12m return,
   buy top 10% above own 200d while XIU > 200d, sell on close < 200d, 12m below top-40% cut, or close 28% under
   the highest close since entry (never re-buy a 28%-sold stock); slots = min(20, max(5, equity//400)),
   per slot = equity/slots, per-order cap max($800, 10% equity), max 20 holdings; guard = no buys when XIU
   fell >= 2% that day, VIX >= 30 or VIX +20% that day, or equity 15% below its 7-day high; leftover cash
   >= $100 parked in VEQT (XIC before VEQT existed), never sold. Index leg off (live setting).
   Not modelled: AI drop judge, manual exclusions, intraday guard timing.
2. **XIU** buy and hold (adjusted).

## Periods
- Development: 2009-01-01 to 2022-12-31. All choices made here only.
- Retrospective evaluation: 2023-01-01 to latest. Run **once**, after the choices below are locked in git.
  Not truly untouched (VMM was designed with it in view); treated as weaker evidence.

## Strategy ideas (each a distinct hypothesis; grid <= 6 settings each; trials counted)
| ID | Idea | Grid |
|---|---|---|
| A | Risk-adjusted momentum: 12-1 month return / 1y vol, VMM exits | 10 or 20 slots |
| B | Blended momentum 3/6/12m z-score, VMM exits | 10 or 20 slots |
| C | Short-term mean reversion: RSI(2) < 10 and close > 200d; exit close > 5d SMA or 10 days | RSI 5/10, slots 5/10 |
| D | Volatility squeeze breakout: 20d range in lowest 10% of its year, close at 55d high; 20% trail | slots 5/10 |
| E | 52-week high on volume >= 2x 50d avg; exit close < 50d SMA | slots 5/10 |
| F | Gap-down reversal: open <= -5% vs prior close in a >200d stock, close up on the day; hold 5 days | slots 5/10 |
| G | TSX sector ETF rotation: top 2 of sector ETFs by 6m return, monthly, cash if below 200d | 2 or 3 ETFs |
| H | LightGBM ranker: features = 5/20/60/120/250d returns, 20/60d vol, dist to 200d/50d, 52w-high gap, dollar volume; label = next-20d return rank; trained walk-forward yearly on prior years only with 20-day embargo; monthly, top N, VMM-style 200d exit | N 10/20 |

## Selection rule (locked)
Per idea pick the setting with the best dev-period CAGR at 0.50% costs whose dev max drawdown is no worse
than exact VMM's dev drawdown + 5 points. That single setting per idea goes to evaluation.

## Pass bar (locked)
A candidate is "promising" only if, at 0.50% costs: (1) evaluation-period CAGR beats exact VMM by >= 3 points,
(2) max drawdown no worse than VMM + 5 points, (3) it also beats VMM in the development period, and
(4) the Deflated Sharpe Ratio (number of trials = all settings tried) of its full-period daily returns is > 0.95.
Dilip's stated bars ($100/day ≈ 500%/yr; 3× VMM CAGR) are reported against but are not expected to be met.
Even a "promising" result goes to paper trading only, not live money.
