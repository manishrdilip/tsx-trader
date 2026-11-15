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

## TSX proxies (no FX, 0.1% cost)

| Strategy | median %/yr | worst start | med max drop | worst max drop | worst cal year | $5k final (med) | starts beating bot | Status |
|----------|-------------|-------------|--------------|----------------|----------------|-----------------|--------------------|--------|
| XIU.TO vol0.25 | 17.3 | 12.5 | -38.5 | -63.0 | -29.8 | 47903 | 3 of 29 | FAIL |
| XIU.TO SMA200 | 5.7 | 3.9 | -24.4 | -34.2 | -14.7 | 11194 | 0 of 29 | FAIL |
| XIC.TO vol0.25 | 16.7 | 12.4 | -40.9 | -52.3 | -30.5 | 46678 | 3 of 29 | FAIL |
| XIT.TO vol0.3 | 17.6 | 6.9 | -56.0 | -68.2 | -48.4 | 83712 | 0 of 29 | FAIL |
| ZQQ.TO SMA200 | 10.1 | 6.2 | -25.7 | -25.7 | -16.9 | 25103 | 0 of 29 | FAIL |

Closest on return is XIU vol0.25 at 17.3% median — still well below the VMM ~30% benchmark, and worst year/DD do not satisfy PASS A or B.
