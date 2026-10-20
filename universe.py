"""
Market-wide scan: every TSX + TSX Venture stock.
1. Pulls the full company lists from tsx.com (falls back to a saved list).
2. Downloads ~1.5 years of daily prices for all of them (yfinance, bulk).
3. Safety filter: price >= $2 and average daily trading >= $1M
   (removes penny stocks you can't reliably get in/out of).
4. Runs the same 3 scanners (trend, momentum, volume/risk);
   lists the top 5 where all three agree.
Research only - not financial advice.
"""
import json
import os
import urllib.request

import numpy as np
import pandas as pd

MIN_PRICE = 2.0
MIN_DOLLAR_VOL = 1_000_000
CACHE = "universe_tickers.json"
URLS = {
    ".TO": "https://www.tsx.com/json/company-directory/search/tsx/%5E*",
    ".V": "https://www.tsx.com/json/company-directory/search/tsxv/%5E*",
}


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def get_tickers():
    tickers = []
    for suffix, url in URLS.items():
        try:
            for co in _fetch(url).get("results", []):
                for inst in co.get("instruments", []) or [{"symbol": co.get("symbol")}]:
                    sym = (inst.get("symbol") or "").strip()
                    if not sym:
                        continue
                    # skip debentures, warrants, rights, preferreds, units
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


def download(tickers):
    import yfinance as yf
    out = {}
    for k in range(0, len(tickers), 400):
        chunk = tickers[k:k + 400]
        raw = yf.download(chunk, period="18mo", auto_adjust=True, group_by="ticker",
                          threads=True, progress=False)
        for t in chunk:
            try:
                d = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
                if len(d) >= 210:
                    out[t] = d
            except Exception:
                pass
        print(f"  prices: {min(k + 400, len(tickers))}/{len(tickers)}")
    return out


def scan_all(mkt, params, add_indicators, consensus, pct):
    data = download(get_tickers())
    rows = []
    for t, d in data.items():
        last = d.iloc[-20:]
        if d["Close"].iloc[-1] < MIN_PRICE or (last["Close"] * last["Volume"]).mean() < MIN_DOLLAR_VOL:
            continue
        x = consensus.add_extra(add_indicators(d))
        a, b, c, dd = consensus.scanners(x, mkt)
        votes = sum(int(s.iloc[-1]) for s in (a, b, c, dd))
        import candles
        rows.append({"ticker": t, "close": round(x["Close"].iloc[-1], 2), "votes": votes,
                     "ret_3m": x["ret63"].iloc[-1],
                     "pattern": candles.latest_names(x) if dd.iloc[-1] else "",
                     "exchange": "TSX Venture" if t.endswith(".V") else "TSX"})
    df = pd.DataFrame(rows, columns=["ticker", "close", "votes", "ret_3m", "pattern", "exchange"])
    full = df[df["votes"] == 4].sort_values("ret_3m", ascending=False)
    picks = []
    for _, r in full.iterrows():          # top 5 that don't report earnings soon
        if consensus.earnings_soon(r.ticker):
            continue
        picks.append(r)
        if len(picks) == 5:
            break
    picks = pd.DataFrame(picks, columns=df.columns)
    if not picks.empty:
        picks["stop_loss"] = (picks["close"] * (1 - params["stop"])).round(2)
        picks["take_profit"] = (picks["close"] * (1 + params["target"])).round(2)

    L = ["\n## ALL CANADA (TSX + TSX Venture) - consensus buys (4/4)"]
    L.append(f"Scanned {len(data)} stocks with price history; {len(df)} passed the safety filter "
             f"(price >= ${MIN_PRICE:.0f}, >= ${MIN_DOLLAR_VOL/1e6:.0f}M traded/day). "
             f"{len(full)} got 4/4 votes (trend + momentum + volume/risk + bullish candle).\n")
    if picks.empty:
        L.append("**No market-wide consensus today - no trade.**")
    else:
        L.append("Top 5 by 3-month strength, earnings in next 10 days excluded:\n")
        L.append("| Ticker | Exchange | Pattern | Close | 3-mo | Stop-loss | Take-profit | Max hold |\n|---|---|---|---|---|---|---|---|")
        for _, r in picks.iterrows():
            L.append(f"| {r.ticker} | {r.exchange} | {r.pattern} | {r.close} | {pct(r.ret_3m)} | {r.stop_loss} "
                     f"| {r.take_profit} | {params['hold']}d |")
    return "\n".join(L), picks, df
