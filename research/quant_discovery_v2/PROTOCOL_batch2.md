# Quant Discovery V2 — Batch 2 protocol (pre-registered, committed before any Batch 2 result)

Batch 1 files are left unchanged. Same data (results/data_manifest.json), engine rules, $5,000, whole shares,
next-open fills; **0.50%/side is the deciding cost**. Dev 2009-01-02..2022-12-30; retrospective eval 2023-01-03..latest,
run once per experiment after its selection is committed.

Benchmark note: "26.1% CAGR / -15% DD" is exact VMM over **2023-26 only** (fresh $5,000 start). Over dev it is 8.3% / -30.3%.
Every candidate is compared with exact VMM *on the same period*. Acceptance target given by Dilip: 3x exact VMM CAGR on the
eval period (78.3%) with no worse drawdown. Our honest bar ("promising") stays as Batch 1: beat exact VMM by >= 3 pts in eval,
DD no worse than VMM + 5, beat VMM in dev, Deflated Sharpe > 0.95 counting all trials.

## Exp 1 — VMM capital allocation (all other live rules unchanged)
P0 permanent parking (live) | P1 temporary parking: park ETF is sold to fund new momentum buys | P2 cash only |
P3 dynamic: momentum share = vol(XIU)/vol(picks) monthly (live INDEX_LEG logic), rest in XIU |
P4 volatility-sized slots: per-slot $ x min(1.5, median stock vol / stock vol) | P5 drawdown brake: no new buys while
account is > 20% below its peak. Selection: best dev CAGR @0.5% with DD <= P0 dev DD + 5.
Contribution scenario reported separately (not used for selection): TFSA-like $3,500 start + $350 on the 1st business day
of each month; time-weighted return (TWR) so deposits are not counted as profit.

## Exp 2 — Genetic programming (rule discovery)
Expression trees (depth <= 3) over cross-sectional rank features: r5,r20,r60,r120,r250, v20,v60, d50,d200, h52, ldv,
relvol20, xiu_trend, breadth. Operators + - * max min neg. Fast screen: monthly rebalance, top-10 equal weight, 200d exit
not applied, cost 0.5% x turnover, dev period only. Fitness = dev Sharpe - 0.002*nodes - 0.1*annual turnover - 0.5*|maxDD|.
Population 250 x 20 generations = 5,000 evaluated (duplicates skipped). Best tree -> full engine (VMM-style exits,
20 slots) on dev, then eval once. Deflated Sharpe uses N = 5,000.

## Exp 3 — Statistical ranking (each a score in the VMM framework, 20 slots, VMM exits)
S1 residual momentum (12m return minus beta x XIU 12m, beta from 1y daily) | S2 return/vol (Sharpe-style 6m) |
S3 low correlation to XIU among top-half momentum | S4 Amihud illiquidity premium among top-half momentum.
Selection: best dev CAGR @0.5% within DD limit.

## Exp 4 — Multi-strategy portfolios
Daily return streams from dev runs: VMM_nopark, D squeeze, G sector, F gap, XIU. Pick the 2-3 stream equal-weight
(monthly rebalanced) mix with best dev Sharpe and dev CAGR >= VMM_nopark dev CAGR - 5. Selection uses dev only.

## Exp 5 — Little Rizzy measured move (daily)
Swing high/low = 5 bars each side, usable only 5 bars after the pivot. Down-trendline through last two confirmed lower
swing highs; entry when close crosses above the line and close > 20-day Bollinger mid; target = entry + (line value at
break - lowest low since first pivot); stop = last confirmed swing low; 30-day time stop. Next-open fills, target/stop
checked on close (conservative: stop first if both). Grid: slots 5/10.

## Exp 6 — Volatility/trend asymmetry
Buy when v20/v120 <= q (contraction), r60 - r120/2 > 0 (acceleration), relvol20 >= m, close within 5% of 52w high,
breadth (% of stocks > 200d) >= b. Score = r60. Exit: close < 50d or 20% trail. Grid q in {0.6,0.8}, m in {1,1.5},
b in {0,0.5}, slots 10 -> 8 settings.
