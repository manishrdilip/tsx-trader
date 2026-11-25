# Batch 6: SPY options — expiries, calendar months, spreads (25 Nov 2026) — FAIL
Real SPY chains 2008-2025 (bid/ask), $10k, fractional contracts, cash 0%, SPY total return benchmark.
Dev 2008-2022 (CAGR / max DD): SPY 9.2 / -46.3.
- Covered call 30d: weekly 8.0/-19.8, monthly 9.0/-37.7, quarterly 7.1/-30.5, Nov-Apr only 8.2/-46.1, May-Oct only 9.0/-43.9
- Cash-secured put 30d: weekly 4.1/-18.0, monthly 2.7/-34.5, quarterly 1.3/-31.8, Nov-Apr 2.0, May-Oct 0.7
- Buy 30d calls 5%/trade: weekly -5.8/-80.2, monthly 0.5/-55.8, quarterly 2.2/-31.5, Nov-Apr 2.5, May-Oct -2.0
- LEAPS 80-delta: 5.2/-19.7
- Put credit spread 30/15d: 5.9/-39.7; only when VIX>=20: 7.3/-20.0
- Iron condor 20/10d: -4.4/-67.9; only when VIX>=20: 0.6/-36.7
Selected (best CAGR with DD <= SPY): covered call monthly 9.0 (below SPY 9.2 -> fails dev). Deflated Sharpe 0.65.
Eval 2023-25 (once): covered call monthly 15.3/-12.1 vs SPY 21.0/-8.3. FAIL.
Notes: weekly covered calls and VIX-filtered put spreads roughly halve the worst drop for 1-2 pts/yr less return;
none beats holding. Selling Nov-Apr vs May-Oct makes no useful difference. Iron condors lose in big trend moves.
