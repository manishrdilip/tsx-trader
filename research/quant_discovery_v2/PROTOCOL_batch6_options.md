# Batch 6 — SPY options: expiries, calendar months, spreads (pre-registered before any result)

Data: waterscep/sks-options-dataset-hist (MIT) SPY daily chains 2008-2025 (bid/ask/delta), via media.githubusercontent.com.
SPY raw close (settlement) and adjusted close (total return incl. dividends) from EODHD SPY.US; VIX from EODHD VIX.INDX.
Rules for all: $10,000, no deposits, fractional contracts (per-share accounting; whole 100-share contracts are not possible
on $10k for most of the period), sell at bid, buy at ask, hold to expiry and settle at intrinsic on the SPY raw close
(LEAPS: sold at the bid when 90 days are left). Next trade opens on the first trading day after expiry/exit.
Cash earns 0% (understates collateral strategies by ~1-2%/yr). No commissions. Benchmark: SPY total return.

Family 1 — expiry length (20 settings total across families)
- Covered call 30-delta (hold SPY, sell call): weekly (4-10 DTE), monthly (21-45), quarterly (60-120)
- Cash-secured put 30-delta (collateral = strike): weekly, monthly, quarterly
- Buy 30-delta calls with 5% of the pot per trade: weekly, monthly, quarterly
- LEAPS stock replacement: buy ~80-delta call, 270-450 DTE, sized to pot/SPY shares, rest cash; roll at 90 DTE
  (Weeklies only exist in the data from when the chain lists them; weekly runs start at the first date with 4-10 DTE expiries.)
Family 2 — calendar months (monthly expiry, 30-delta): covered call, cash-secured put, 5% long calls, each traded only
  when the entry month is Nov-Apr, and separately only May-Oct (otherwise: hold SPY for covered call, cash for the others).
Family 3 — spreads (monthly): put credit spread short 30-delta / long 15-delta; iron condor short 20-delta both sides /
  long 10-delta; each sized so the maximum loss = 20% of the pot; each also with a filter "only when VIX >= 20 at entry".

Periods: dev 2008-01-01..2022-12-31; eval 2023-01-01..2025-12-31, run once after dev selection is committed.
Selection: the setting with the best dev CAGR whose dev max drawdown is no worse than SPY's dev drawdown.
Pass: selected setting beats SPY total return CAGR in dev AND eval, with drawdown no worse in both, and Deflated Sharpe
> 0.95 (N = 20 + 36 earlier options trials).
