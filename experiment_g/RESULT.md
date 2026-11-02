# Experiment G - result (run 41534946636, completed 2026-11-02 22:19 UTC, success)

Real data, daily bars, frozen universe (1,822 TSX equities), provisional costs, pre-registered gates. None of the three variants passed.
Holdout (2022 to 2026-11-02) is contaminated and reported as such. Survivorship bias applies (see PREREGISTERED.md).

Normal costs (gate scenario). Expectancy is net per signal (group). Win rate with 95% Wilson interval.

| Variant | Period | Groups | Win % (95% CI) | Expectancy % net | PF | Max DD % | Leg fill % | Break-even RT % |
|---|---|---|---|---|---|---|---|---|
| B0 single 2R | train | 448 | 42.86 (38.35, 47.48) | -1.1437 | 0.818 | -19.48 | 100 | not profitable at zero cost |
| B0 single 2R | validation | 306 | 41.18 (35.80, 46.77) | -0.4306 | 0.873 | -17.22 | 100 | 0.298 |
| B0 single 2R | holdout | 231 | 54.11 (47.67, 60.42) | 2.0818 | 1.551 | -4.38 | 100 | 2.237 |
| S1 structured 0.25/0.5/1R | train | 855 | 69.94 (66.78, 72.92) | 0.1958 | 0.556 | -34.64 | 65.86 | 0.972 |
| S1 structured 0.25/0.5/1R | validation | 586 | 70.82 (67.01, 74.35) | -0.0036 | 0.547 | -26.20 | 65.86 | 0.774 |
| S1 structured 0.25/0.5/1R | holdout | 461 | 68.55 (64.17, 72.62) | 0.0805 | 0.576 | -20.40 | 65.86 | 0.940 |
| S2 structured 2R control | train | 431 | 46.17 (41.52, 50.89) | -0.0064 | 0.697 | -23.00 | 66.73 | 0.754 |
| S2 structured 2R control | validation | 299 | 45.48 (39.93, 51.15) | 0.3246 | 0.679 | -17.16 | 66.73 | 1.706 |
| S2 structured 2R control | holdout | 233 | 55.36 (48.95, 61.61) | 2.9575 | 1.409 | -3.90 | 66.73 | 2.510 |

Gates: B0 FAIL, S1 FAIL, S2 FAIL. Decision rule: none passed.

Reading the result (no gate changed after seeing it):
- S1, the video's structure, reproduces the high win rate (about 70%) but not the profit: profit factor 0.55 to 0.58 in every period, expectancy about zero in validation.
  This is the video's trade-off taken to its end point: many small wins, few large losses.
- The only positive holdout figures (B0 +2.08%, S2 +2.96%) come from the contaminated 2022 to 2026 period. Train and validation are negative or near zero for every variant, so the holdout gain is not a stable effect.
- Break-even round-trip cost for S1 is 0.77 to 0.97%, which is about the normal-scenario cost of 0.5 to 1.3%. S1 has essentially no margin over costs.
- Max drawdown for S1 is -20% to -35%, worse than B0 in train.

Limitations: daily bars (not the video's 30-minute bars), survivorship bias from today's TSX listings, provisional cost values, unverified data source.
Run artifact (full CSVs and results.json) could not be downloaded from this sandbox; the report above is from the run log of run 41534946636.
