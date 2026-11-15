# Independent Strategy Audit — Vol-Target Search & Combinations
**Date:** 2026-11-14  
**Branch:** lab/catalog-batch1  
**Method:** Fixed-capital cohorts (every start year 2011–2025), next-session execution, 0.1% cost per side, yfinance auto-adjusted data. No look-ahead.

## Benchmark progression
| Stage | Strategy | Median CAGR | Min cohort CAGR | Median Max DD |
|-------|----------|-------------|-----------------|---------------|
| Original ref | QQQ vol-target 40% / 20d | ~36–38% | >24% | ~-52% |
| Improved | QQQ vol 0.45 / 20d | 41.5% | 28.1% | -57% |
| Stronger | QQQ vol 0.50 / 20d | **44.6%** | **29.0%** | -62% |
| Stronger | QQQ vol 0.55 / 20d | **47.7%** | **30.5%** | -66% |
| Stronger | QQQ vol 0.60 / 20d | **50.2%** | **31.9%** | -70% |

Higher targets improve both median and worst-cohort CAGR. Drawdowns widen roughly 5 points per 0.05 increase in target.

## Other findings
- Lookbacks other than 20 days (10/15/25/30/60) underperformed the 20-day version on the combined median + min criteria.
- SMA filters on vol-target reduced returns more than they helped DD.
- Candlestick patterns (engulfing, hammer, morning star, 3 white soldiers) as standalone or hard filters destroyed edge.
- TQQQ 50d SMA ≈ 27–28% median (ties VMM, lower min).
- BTC vol-targets show high medians but negative worst cohorts and 75–90% DD.
- 50/50 blend of user VMM + QQQ vol40: ~33% CAGR, worst year ~-20% on overlapping 2009–2026 yearly data (3 negative years vs 5 for each alone).

## 100 CAD full-history paper trade (QQQ vol40, 1999–2026)
- Real (0.1% cost): 100 → 32,619 CAD, CAGR 23.3%, max DD -82.7% (2002).
- Zero-cost sim: 100 → 60,717 CAD, CAGR 26.1%.
- Full history CAGR lower than post-2011 cohorts because of 2000–2002 drawdown.
- 10 negative years vs VMM’s 5 (worst year -50% vs VMM -13%).

## Current strongest simple rule
**QQQ volatility targeting 0.50 with 20-day lookback** (max lev 5, next session, 0.1% cost):  
median CAGR 44.6%, worst cohort 29.0%, median DD -62%.

Higher targets (0.55–0.60) push median above 47–50% but DD exceeds -65%.

## Files
- Core cohort results and parameter sweeps run in /tmp (scripts: audit_core.py, beat_vol40.py, stronger.py, etc.).
- This report: lab/ideas/VOL_TARGET_AUDIT.md
- Trial log updated in lab/ideas/TRIALS.md

## Update 2026-11-14 — 50/50 QQQ + XLK blends (full cohorts)

| Blend | Median CAGR | Min cohort | Median DD | 2011-start |
|-------|-------------|------------|-----------|------------|
| 50/50 vol 0.40 | 41.3% | 28.8% | -46.7% | 41.3% |
| 50/50 vol 0.45 | 45.2% | 31.2% | -51.5% | 45.2% |
| **50/50 vol 0.50** | **48.5%** | **33.3%** | **-55.9%** | **48.5%** |
| 50/50 vol 0.55 | 51.2% | 34.9% | -60.1% | 51.2% |

The 50/50 QQQ+XLK vol 0.50 blend improves on single-asset QQQ or XLK vol 0.50:
- Higher median (48.5% vs ~44%)
- Higher worst cohort (33.3% vs ~29%)
- Similar or slightly better DD

Early-start (2011) matches the median, indicating consistency across the full window.
