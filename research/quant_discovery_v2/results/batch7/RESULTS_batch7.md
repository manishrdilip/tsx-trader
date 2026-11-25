# Batch 7: new free data (25 Nov 2026)
| Test | Dev | Eval (once) | Benchmark dev / eval | Verdict |
|---|---|---|---|---|
| A managed futures, 145 markets (pysystemtrade), selected trend+carry | Sharpe 1.66, 3.2%/yr at ~3% vol, DD -3.4 (1990-2014) | Sharpe 0.48, 0.8%/yr (2015-Mar 2024) | cash; pass needs eval Sharpe > 0.5 | FAIL (just). Trend alone: dev 1.42, eval 0.71; carry alone: eval -0.18 |
| B TSX January tax-loss (10 worst 12m losers, mid-Dec to end-Jan) | avg +7.1% per window vs XIU +2.4; beat XIU 7 of 14 | +3.2% vs XIU +2.0; 2 of 3 | worst window -9.1% vs XIU -3.2 | FAIL (worse drop; 2 big years drive the average; t ~1.9) |
| D-TSX gap-up drift | 5.5%/yr, DD -29.1 | 2.9%, DD -21.1 | XIU 8.5 / 18.4 | FAIL |
| C US small/mid momentum (VMM rules, 11,112 US stocks incl. delisted) | 4.2%/yr, DD -60.5 | 5.4%, DD -46.9 | IWM 7.5 / 13.2; SPY 6.2 / 19.0 | FAIL |
| D-US gap-up drift | 5.4%/yr, DD -49.6 | -0.8%, DD -34.0 | IWM 7.5 / 13.2 | FAIL |
| E country ETF rotation (35 iShares) | 6.3%/yr, DD -44.9 | 14.3%, DD -27.2 | SPY 6.2 / 19.1; EW countries 6.0 / 13.1 | FAIL |
Notes: futures script printed dev and eval together (selection rule was mechanical: best dev Sharpe; disclosed).
Futures portfolio runs at ~3% vol when 145 markets each target 10%; ~3x scaling needed for 10% portfolio vol (needs margin account).
January dev string-filter bug excluded Dec2022-Jan2023 from the printed dev average (4.72% over 13); corrected over 14 = 7.1%.
