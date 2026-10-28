"""
ENHANCED Universe Scan - Tightened Liquidity Filters (Phase 1 Improvement)

1. Pulls full TSX + TSX Venture company lists
2. Downloads 18 months of data (caching supported)
3. IMPROVED: Liquidity filters now:
   - Price >= $2.00 (increased from no filter)
   - 50-day ADV >= $500,000 CAD (upgraded from $1M daily volume)
4. Runs 4 scanners; lists top 5 consensus buys

This eliminates the penny stocks and illiquid microcaps that blow
spreads on entry and can't be exited reliably.
"""
import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

import cache_manager

# ======== IMPROVED LIQUIDITY FILTERS ========
MIN_PRICE = 2.0                  # Increased from no minimum
MIN_ADV_50 = 500_000             # 50-day ADV >= $500k (was $1M daily vol)
# ============================================

CACHE = "universe_tickers.json"
LAST_DATA = {}
URLS = {
    ".TO": "https://www.tsx.com/json/company-directory/search/tsx/%5E*",
    ".V": "https://www.tsx.com/json/company-directory/search/tsxv/%5E*",
}


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def get_tickers():
    """Fetch current TSX + TSXV lists."""
    tickers = []
    for suffix, url in URLS.items():
        try:
            for co in _fetch(url).get("results", []):
                for inst in co.get("instruments", []) or [{"symbol": co.get("symbol")}]:
                    sym = (inst.get("symbol") or "").strip()
                    if not sym:
                        continue
                    if any(sym.endswith(x) for x in (".DB", ".WT", ".RT", ".UN.U", ".U")) or ".PR." in sym:
                        continue
                    tickers.append(sym.replace(".", "-") + suffix)
            print(f"  {suffix}: list downloaded")
        except Exception as e:
            print(f"  ! could not fetch {suffix} list: {e}")

    tickers = sorted(set(tickers))
    if len(tickers) > 500:
        with open(CACHE, "w") as f:
            json.dump(tickers, f)
    elif os.path.exists(CACHE):
        print("  using saved ticker list")
        tickers = json.load(open(CACHE))
    print(f"  universe: {len(tickers)} tickers")
    return tickers


CHUNK = 150
MIN_BARS = 210
COLS = ["Open", "High", "Low", "Close", "Volume"]


def _fetch_chunk(chunk):
    """Download chunk of tickers with yfinance."""
    return yf.download(chunk, period="18mo", auto_adjust=True, group_by="ticker",
                       threads=True, progress=False)


def _extract(raw, chunk, out):
    """Extract individual tickers from multi-ticker download."""
    missing = []
    multi = isinstance(raw.columns, pd.MultiIndex)
    have = set(raw.columns.get_level_values(0)) if multi else set()
    for t in chunk:
        try:
            if multi and t in have:
                d = raw[t][COLS].dropna()
            elif not multi and len(chunk) == 1:
                d = raw[COLS].dropna()
            else:
                missing.append(t)
                continue
        except (KeyError, TypeError):
            missing.append(t)
            continue
        if len(d) >= MIN_BARS:
            out[t] = d
        elif d.empty:
            missing.append(t)
    return missing


def download(tickers, retries=3):
    """Download all tickers in chunks, with retry logic."""
    out, missing = {}, []
    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i+CHUNK]
        print(f"  chunk {i//CHUNK + 1}: {', '.join(chunk[:3])}... ({len(chunk)} tickers)")
        for attempt in range(retries):
            try:
                raw = _fetch_chunk(chunk)
                missing += _extract(raw, chunk, out)
                print(f"    ✓ got {len([x for x in chunk if x in out])} tickers")
                break
            except Exception as e:
                if attempt < retries - 1:
                    print(f"    ! retry {attempt+1}/{retries}: {e}")
                    time.sleep(1)
                else:
                    missing += chunk
                    print(f"    ! gave up on chunk, will retry next run")
    return out, missing


# ================================================================ filters & signals
def add_indicators(df):
    """Add technical indicators."""
    d = df.copy()
    c = d["Close"]
    for n in (20, 50, 200):
        d[f"sma{n}"] = c.rolling(n).mean()
    pc = c.shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    d["hi55"] = d["High"].rolling(55).max().shift(1)
    d["hi252"] = d["High"].rolling(252).max()
    d["lo252"] = d["Low"].rolling(252).min()
    d["vol20"] = d["Volume"].rolling(20).mean()
    d["adv_50"] = d["Volume"].rolling(50).mean() * d["Close"]  # IMPROVED: 50-day ADV for filtering
    return d


def trend_score(d):
    """Trend continuity: is the stock in a long-term uptrend?"""
    x = d.iloc[-1]
    if pd.isna(x["sma200"]) or pd.isna(x["sma50"]):
        return 0
    score = 0
    if x["Close"] > x["sma200"]:
        score += 1
    if x["sma50"] > x["sma200"]:
        score += 1
    if x["Close"] > x["sma50"]:
        score += 1
    return score / 3


def breakout_score(d):
    """Recent 55-day breakout."""
    x = d.iloc[-1]
    if pd.isna(x["hi55"]):
        return 0
    return 1 if x["Close"] > x["hi55"] else 0


def momentum_score(d):
    """12-month momentum + distance from 52-week high."""
    c = d["Close"]
    x = d.iloc[-1]
    if pd.isna(x["hi252"]):
        return 0
    mom = c.iloc[-1] / c.iloc[-252] - 1 if len(c) >= 252 else np.nan
    if pd.isna(mom):
        return 0
    if mom < 0.05:
        return 0  # Need positive momentum
    closeness = x["Close"] / x["hi252"]
    return 1 if closeness >= 0.85 else 0  # Within 15% of 52-week high


def volume_risk_score(d):
    """Volume and volatility confirm entry is reasonable."""
    x = d.iloc[-1]
    if pd.isna(x["vol20"]) or pd.isna(x["atr14"]):
        return 0
    vol_ok = x["Volume"] > 0.8 * x["vol20"]  # Volume at least 80% of 20d avg
    atr_reasonable = x["atr14"] / x["Close"] < 0.08  # ATR < 8% of price (not too volatile)
    return 1 if (vol_ok and atr_reasonable) else 0


def filter_liquid(data):
    """
    IMPROVED: Apply hard liquidity filters to eliminate slippage traps.

    Filters:
    - Price >= $2.00
    - 50-day ADV >= $500,000
    """
    filtered = {}
    for ticker, d in data.items():
        x = d.iloc[-1]

        # Price filter
        if x["Close"] < MIN_PRICE:
            continue

        # ADV filter (IMPROVED)
        adv = x.get("adv_50", np.nan)
        if pd.isna(adv) or adv < MIN_ADV_50:
            continue

        filtered[ticker] = d

    return filtered


def scan_all(mkt, champ_params, add_inds, consensus, pct_fmt, live=False):
    """Full universe scan: download, filter, score, report."""
    cache_manager.ensure_cache_dir()

    print("Getting ticker list...")
    tickers = get_tickers()

    print("Downloading universe (with caching)...")
    data, missing = download(tickers)
    print(f"  Downloaded: {len(data)}, retrying next run: {len(missing)}")

    print(f"Adding indicators to {len(data)} stocks...")
    for t in data:
        data[t] = add_indicators(data[t])

    print("Applying liquidity filters...")
    data = filter_liquid(data)
    print(f"  After filtering: {len(data)} tradable stocks")

    # Score all stocks
    print("Scoring all stocks...")
    scores = []
    for ticker, d in data.items():
        x = d.iloc[-1]
        score = {
            "ticker": ticker,
            "close": round(x["Close"], 2),
            "price": round(x["Close"], 2),
            "adv_50": round(x.get("adv_50", 0), 0),
            "trend": round(trend_score(d), 2),
            "breakout": round(breakout_score(d), 2),
            "momentum": round(momentum_score(d), 2),
            "volume_risk": round(volume_risk_score(d), 2),
        }
        score["total_score"] = sum([score[k] for k in ["trend", "breakout", "momentum", "volume_risk"]])
        scores.append(score)

    df = pd.DataFrame(scores).sort_values("total_score", ascending=False)

    # Top consensus (all 4 scanners agree)
    consensus_hits = df[df["total_score"] >= 3.5].head(5)

    report_lines = [
        f"## Universe Scan ({len(data)} tradable TSX/V stocks)",
        f"_Liquidity filter: price >= ${MIN_PRICE}, 50-day ADV >= ${MIN_ADV_50:,.0f}_\n",
        f"**Top {min(5, len(consensus_hits))} consensus buys** (4/4 scanners agree):",
        "| Ticker | Price | ADV | Trend | Breakout | Momentum | Vol/Risk | Score |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for _, r in consensus_hits.iterrows():
        report_lines.append(
            f"| {r['ticker']} | ${r['close']} | ${r['adv_50']:,.0f} | "
            f"{r['trend']:.1f} | {r['breakout']:.1f} | {r['momentum']:.1f} | {r['volume_risk']:.1f} | {r['total_score']:.1f} |"
        )

    if consensus_hits.empty:
        report_lines.append("| (none today) |")

    report_lines.append("")

    global LAST_DATA
    LAST_DATA = data

    return "\n".join(report_lines), consensus_hits, df
