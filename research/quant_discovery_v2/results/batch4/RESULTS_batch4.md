# Batch 4: regime switching (25 Nov 2026) — FAIL
Monthly regime read at the prior month-end; menu = Batch 1 streams (VMM_nopark, D squeeze, G sector, F gap, XIU, cash);
1% charged per switch. First-hour reading not testable (no intraday on EODHD plan).
Dev (picks chosen on dev, so dev is in-sample): Scheme A 23.6%/yr DD -25.4 Sharpe 1.08; Scheme B 22.9% DD -19.3 Sharpe 1.10
(selected); VMM_nopark alone 20.6% DD -27.5 Sharpe 0.97.
Picks (B): market above 200d -> VMM; below 200d -> XIU (first day down) or gap reversal (first day up).
Eval 2023-26 (run once): Scheme B 23.7%/yr DD -31.1 Sharpe 0.87 vs VMM_nopark 30.6% DD -31.1 Sharpe 1.04. FAIL.
Why: in bad markets VMM already stops buying (XIU < 200d gate), so switching mostly re-labels what VMM does; the extra
choices for down months were fitted to the few dev down months (21-24 each) and did not repeat.
Caveat: stream switching assumes instant moves between whole portfolios (approximation).
