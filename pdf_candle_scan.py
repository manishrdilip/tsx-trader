"""
Candlestick + indicator scan (rules from "The Candlestick Trading Bible").

Indicators: EMA 9/21, SMA 50/200, RSI(14), MACD(12,26,9), Bollinger Bands(20,2),
            ADX(14) with +DI/-DI, ATR(14), volume vs 20-day average.
Candlesticks: bullish engulfing, hammer, pin bar, dragonfly doji, bullish harami,
              piercing line, tweezer bottom, morning star, three white soldiers.

A stock is a BUY candidate when ALL of these hold on the last closed bar:
  1. Uptrend: close > SMA50 > SMA200 and EMA9 > EMA21
  2. A bullish candlestick pattern appeared in the last 2 bars
  3. At least 3 of 5 confirmations:
       - RSI(14) between 40 and 70 and rising
       - MACD histogram positive and rising
       - Bounced off lower Bollinger Band in the last 3 bars (low touched band, close back above)
       - ADX > 20 and +DI > -DI (trend strength)
       - Volume on signal bar >= 1.0x the 20-day average (high volume confirms)
  4. Liquidity: close >= $2 and 50-day average dollar volume >= $500,000

Trade plan (per book: stop below the pattern, target at 2R):
  entry  = last close (buy at next open, skip if it opens above buy_max)
  stop   = min(signal low, close - 1.5 * ATR14)
  target = entry + 2 * (entry - stop)

Research only - not financial advice.
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

ACCOUNT = float(os.environ.get("ACCOUNT", "100"))   # CAD cap per trade
OUT_DIR = os.environ.get("OUT_DIR", "results/pdf_candle")
UNIVERSE_FILE = "universe_tickers.json"
SUFFIX_FILTER = (".TO",)           # TSX only (TSXV excluded)
BATCH = 80


# ---------- indicators ----------
def add_indicators(d):
    d = d.copy()
    c, h, l, o, v = d["Close"], d["High"], d["Low"], d["Open"], d["Volume"]
    d["ema9"] = c.ewm(span=9, adjust=False).mean()
    d["ema21"] = c.ewm(span=21, adjust=False).mean()
    d["sma50"] = c.rolling(50).mean()
    d["sma200"] = c.rolling(200).mean()

    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))

    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    d["macd_hist"] = macd - sig

    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    d["bb_low"] = mid - 2 * sd
    d["bb_mid"] = mid

    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d["atr"] = atr

    up_move, dn_move = h.diff(), -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    pdi = 100 * pd.Series(plus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=d.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    d["plus_di"], d["minus_di"] = pdi, mdi
    d["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

    d["vol20"] = v.rolling(20).mean()
    d["dollar_adv50"] = (c * v).rolling(50).mean()
    return d


# ---------- candlestick patterns (book definitions) ----------
def candle_patterns(d):
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    bull, bear = c > o, c < o
    avg_body = body.rolling(20).mean()
    big = body > avg_body
    small = body < 0.5 * avg_body
    doji = body <= 0.1 * rng
    S = lambda s, k=1: s.shift(k)
    # book: reversal patterns need a short dip before them
    dip = c.shift(1) < c.shift(5)

    p = {}
    p["Bullish Engulfing"] = dip & S(bear) & bull & (o <= S(c)) & (c >= S(o)) & (body > S(body))
    p["Hammer"] = dip & (lower >= 2 * body) & (upper <= 0.3 * body + 0.1 * rng) & ~doji
    p["Bullish Pin Bar"] = dip & (lower >= 0.6 * rng) & (body <= 0.3 * rng)
    p["Dragonfly Doji"] = dip & doji & (lower >= 0.7 * rng) & (upper <= 0.1 * rng)
    p["Bullish Harami"] = dip & S(bear) & S(big) & bull & (o >= S(c)) & (c <= S(o)) & small
    p["Piercing Line"] = dip & S(bear) & S(big) & bull & (o < S(c)) & (c > (S(o) + S(c)) / 2) & (c < S(o))
    p["Tweezer Bottom"] = dip & S(bear) & bull & ((l - S(l)).abs() <= 0.002 * c)
    p["Morning Star"] = (dip & S(bear, 2) & S(big, 2) & S(small) & bull & big
                         & (c > (S(o, 2) + S(c, 2)) / 2))
    p["Three White Soldiers"] = (bull & S(bull) & S(bull, 2) & (c > S(c)) & (S(c) > S(c, 2))
                                 & big & S(big) & S(big, 2) & (upper < 0.3 * body))
    return pd.DataFrame(p, index=d.index).fillna(False).astype(bool)


def score_last(d):
    """Return a dict for the last closed bar, or None if not a candidate."""
    if len(d) < 205 or d[["sma200", "adx", "rsi", "macd_hist", "dollar_adv50"]].iloc[-1].isna().any():
        return None
    last = d.iloc[-1]
    c = last["Close"]

    if not (c >= 2.0 and last["dollar_adv50"] >= 500_000):
        return None
    trend = c > last["sma50"] > last["sma200"] and last["ema9"] > last["ema21"]
    if not trend:
        return None

    pats = candle_patterns(d)
    recent = pats.iloc[-2:]
    names = sorted({col for col in recent.columns if recent[col].any()})
    if not names:
        return None

    conf = {}
    conf["RSI 40-70 rising"] = 40 <= last["rsi"] <= 70 and last["rsi"] > d["rsi"].iloc[-2]
    conf["MACD hist up"] = last["macd_hist"] > 0 and last["macd_hist"] > d["macd_hist"].iloc[-2]
    touched = (d["Low"].iloc[-3:] <= d["bb_low"].iloc[-3:]).any()
    conf["BB lower bounce"] = bool(touched and c > last["bb_low"])
    conf["ADX trend up"] = last["adx"] > 20 and last["plus_di"] > last["minus_di"]
    conf["Volume >=1x avg"] = last["Volume"] >= last["vol20"]
    n_conf = sum(bool(v) for v in conf.values())
    if n_conf < 3:
        return None

    atr = last["atr"]
    stop = min(last["Low"], c - 1.5 * atr)
    risk = c - stop
    if risk <= 0:
        return None
    target = c + 2 * risk
    shares = int(ACCOUNT // c)
    return {
        "ticker": None,
        "patterns": ", ".join(names),
        "confirmations": n_conf,
        "confirm_list": ", ".join(k for k, v in conf.items() if v),
        "close": round(c, 2),
        "entry_max": round(c * 1.01, 2),
        "stop": round(stop, 2),
        "stop_pct": round(100 * (c - stop) / c, 2),
        "target": round(target, 2),
        "target_pct": round(100 * (target - c) / c, 2),
        "rsi": round(last["rsi"], 1),
        "adx": round(last["adx"], 1),
        "shares_at_cap": shares,
        "cost_at_cap": round(shares * c, 2),
        "loss_at_stop_at_cap": round(shares * (c - stop), 2),
        "gain_at_target_at_cap": round(shares * (target - c), 2),
    }


def load_universe():
    tickers = json.load(open(UNIVERSE_FILE))
    return [t for t in tickers if t.endswith(SUFFIX_FILTER)]


def main():
    tickers = load_universe()
    print(f"Universe: {len(tickers)} TSX tickers")
    rows, errors = [], []
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i:i + BATCH]
        try:
            raw = yf.download(chunk, period="2y", interval="1d", group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            errors.append(f"batch {i}: {e}")
            continue
        for t in chunk:
            try:
                d = raw[t].dropna(how="all")
                if d.empty:
                    errors.append(f"{t}: no data")
                    continue
                d = add_indicators(d[["Open", "High", "Low", "Close", "Volume"]])
                res = score_last(d)
                if res:
                    res["ticker"] = t
                    res["last_bar"] = str(d.index[-1].date())
                    rows.append(res)
            except Exception as e:
                errors.append(f"{t}: {e}")
        time.sleep(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.DataFrame(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not df.empty:
        df = df.sort_values(["confirmations", "rsi"], ascending=[False, True])
    df.to_csv(f"{OUT_DIR}/candidates_{stamp}.csv", index=False)
    with open(f"{OUT_DIR}/errors_{stamp}.txt", "w") as f:
        f.write("\n".join(errors))

    print(f"Candidates: {len(df)}  errors: {len(errors)}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## Candle + indicator scan {stamp}\n\n")
            f.write(f"Universe {len(tickers)} TSX names, candidates {len(df)}, errors {len(errors)}\n\n")
            if not df.empty:
                f.write(df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string(index=False))
                f.write("\n")
    if not df.empty:
        print(df.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
