# Batch 5: forex (25 Nov 2026) — FAIL
EODHD daily FOREX, 14 pairs, 1990-2026, each pair at 10%/yr volatility, long/short, 1-day lag, 0.02%/side.
Spot only: interest/carry not included (no free rate data reachable), so carry strategies untested.

Dev 1990-2022 (CAGR at 10% vol / Sharpe / max DD; Sharpe 1990-2006 vs 2007-2022):
best: 12m time-series momentum 1.9% / 0.38 / -15.7 (0.56 vs 0.22); MA 50/200 1.8% / 0.37 / -15.0 (0.39 vs 0.36);
Donchian 100/50 1.4% / 0.25; others <= 0.26; mean reversion -4 to -4.6%/yr (DD -77 to -81%);
cross-sectional momentum, month-end USD seasonal: negative.
Selected 12m momentum: fails the dev bar (Sharpe > 0.5 in both halves), Deflated Sharpe 0.147.
Eval 2023-26 (run once): -1.4%/yr, Sharpe -0.31, DD -8.8%.
Conclusion: no usable daily forex edge in spot prices. The classic FX trend edge of the 1990s has mostly faded;
to earn even 10%/yr from ~2%/yr at 10% vol needs ~5x leverage, with drawdowns scaling the same way.
