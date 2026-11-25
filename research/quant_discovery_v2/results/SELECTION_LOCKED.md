# Selection locked after development run (2009-2022), before any evaluation-period run

Rule (PROTOCOL.md): per idea, best dev CAGR at 0.50%/side with dev max drawdown no worse than exact VMM + 5 pts (-35.3%).

Finding during benchmark build: the exact live rules park leftover cash >= $100 in VEQT and never sell it. In a $5,000 account
with no deposits this drains the momentum capital: exact VMM dev CAGR 8.3% vs 20.6% with parking switched off (everything else
identical). Because exact VMM is so weak here, every candidate is ALSO compared with "VMM_nopark" (stricter bar).

| Idea | Selected | Dev CAGR @0.5% | Dev max DD | Beats exact VMM (8.3%)? | Beats VMM_nopark (20.6%)? |
|---|---|---|---|---|---|
| A risk-adj momentum | A_riskadj_mom_20 | 13.3 | -28.6 | yes | no |
| B blended momentum | B_blend_mom_20 | 15.6 | -31.8 | yes | no |
| C RSI2 mean reversion | none (all lose money at 0.5%: -9.8 to -16.4%/yr, DD -86 to -93%) | | | FAIL | FAIL |
| D squeeze breakout | D_squeeze_10 | 9.3 | -27.8 | yes | no |
| E 52w high + volume | E_hivol_10 | 16.2 | -33.6 | yes | no |
| F gap-down reversal | F_gaprev_10 (F_5 breaks DD limit) | 3.8 | -28.3 | no | no |
| G sector ETF rotation | G_sector_2 | 8.0 | -30.0 | no | no |
| H LightGBM ranker | H_lgbm_20 | 6.0 | -24.8 | no | no |
XIU buy-and-hold dev: 8.5%/yr, DD -35.5%.

No idea beats VMM_nopark in development, so by pass-bar condition (3) none can be "promising" against the stronger
benchmark, whatever the evaluation shows. Evaluation (2023-latest) is run once for the selected settings, for the record.
Trials so far in V2: 38 settings x 3 cost levels.
