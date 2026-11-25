# Quant Discovery V2, batch 2 results (25 Nov 2026)
Protocol 789a806 (before results) -> dev results + locked selections b3be091 -> evaluation run once (this file).
$5,000, whole shares, next-open fills, 0.50%/side. Batch 1 files unchanged.

| Exp | Candidate | Dev CAGR / DD | Eval 2023-26 CAGR / DD | vs exact VMM eval (26.1 / -15.3) |
|---|---|---|---|---|
| Benchmark | exact live VMM (permanent parking) | 8.3 / -30.3 | 26.1 / -15.3 | - |
| 1 | P2 no parking (cash) | 20.6 / -34.0 | 30.8 / -32.0 | +4.7 pts, but DD 16.7 pts worse: FAILS DD rule |
| 1 | P1 temporary parking | 16.8 / -35.4 | 25.0 / -34.4 | not selected |
| 1, deposits $3,500 + $350/mo (TWR) | P0 permanent parking | 8.5 / -30.4 | 22.3 / -15.1 | - |
| 1, deposits | P2 no parking | 20.2 / -32.2 | 27.9 / -33.7 | +5.6 pts TWR, deeper DD |
| 2 | GP best tree (4,038 trees), 20 slots | 19.7 / -33.3 | 30.1 / -35.2 | +4.0 pts, DD 20 pts worse: FAILS; Deflated Sharpe 0.575 |
| 3 | residual momentum | 20.4 / -34.1 | 25.1 / -28.4 | -1.0: FAIL |
| 4 | VMM_nopark + squeeze (did not meet selection rule) | 15.4 / -21.0 | 25.4 / -20.8 | -0.7: FAIL |
| 5 | Little Rizzy measured move | 8.9 / -49.4 (5 slots) | not run | FAIL in dev |
| 6 | vol contraction + acceleration + volume | 11.1 / -16.6 | 6.6 / -14.4 | -19.5: FAIL |

**Acceptance target 78.3%/yr: no candidate came close (best 30.8%).** By the pre-registered bar no new strategy passes.

## What is actually useful
1. **Permanent parking is the biggest drag found.** Over 2009-22 it cut VMM from 20.6% to 8.3%/yr with fixed capital and from
   20.2% to 8.5% TWR with Dilip's real deposit pattern. Over 2023-26 the gap is smaller (30.8 vs 26.1; 27.9 vs 22.3 with deposits)
   because VEQT/XIU itself did well. The price of removing it: the worst drop goes from about -15% to about -32% in 2023-26
   (in 2009-22 both were about -30 to -34%). Parking works as a slow de-risking: it lowers both return and drawdown.
   Temporary parking (sell the ETF to fund new picks) sat in between in dev and was worse than both in eval.
2. **GP rediscovered momentum.** The best of 4,038 evolved rules is "12-month return + small tilt to smaller, rising,
   high-volume stocks". After multiple-testing correction its edge is not significant (DSR 0.575), and its full-engine
   result is about the same as plain VMM without parking.
3. Little Rizzy, the asymmetry rules, residual/low-correlation/illiquidity rankings and the mixes did not beat VMM.

## Caveats
2009-11 survivor-biased (EODHD has no TSX delistings before 2012). $5,000 whole-share results move 1-3 points from path
effects. 2023-26 was looked at before (not untouched). Trials this batch: 8 allocation x 3 costs + 4,038 GP + 4 + 8 + 2 + 20 mixes.
Live VMM not modified.
