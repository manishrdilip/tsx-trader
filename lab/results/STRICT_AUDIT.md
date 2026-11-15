# Strict Audit vs VMM Bot
**Branch:** lab/strict-audit-2026-11-14  
**Benchmark:** VMM ~30%/yr median, typical max drop -39%, worst year -27%.  
**Rules:** signal close t / fill t+1, 0.1% ETF + 1.5% FX on USD conversion, no borrowing, lev only inside real product (capped), starts 1999–2025 + Mar 2000 + Oct 2007, survivors-only (yfinance). Rules frozen before run.

## Results

| Strategy | median %/yr | worst start | med max drop | worst max drop | worst cal year | $5k final (med) | starts beating bot | @1% cost |
|----------|-------------|-------------|--------------|----------------|----------------|-----------------|--------------------|----------|
| QQQ vol0.4 (lev≤3) | 8.2 | -2.9 | -60.5 | -94.0 | -60.2 | 18313 | 0 of 29 | med -4.7 |
| XLK vol0.45 (lev≤3) | 11.3 | -0.2 | -57.7 | -97.2 | -68.3 | 31766 | 0 of 29 | — |
| QQQ SMA200 | 1.9 | -3.5 | -46.0 | -86.4 | -33.5 | 6619 | 0 of 29 | — |

**Status: FAIL** on all. None meet PASS A or B.

## Notes
- Prior vol-target medians of 36–48% used post-2011 windows and 0.1% cost with no FX. Adding 1.5% FX on every conversion and the 1999–2002 period drops median CAGR into single digits and produces large drawdowns.
- Survivors-only. EODHD delisted TSX data not used.
- No parameter tuning after results.

Scripts: `lab/strict_audit.py`
