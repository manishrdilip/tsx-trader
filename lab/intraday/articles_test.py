"""Strategies from 5 articles (Sarwa, Reddit 'list', Radex 12, ACY top-5). Rules fixed before run, 4 Nov 2026.
Same universe, costs, pass rule and random control as reddit_test.py. Intraday = 5-min (60 days).
Daily = Yahoo daily, 2016-01 to today, hold up to 20 days, stop/target as stated, 0.03%/side.

Intraday:
  HTF_EMA      bias = close vs 100-EMA on 1-hour bars (built from 5-min); 5-min EMA9/20 cross only in bias direction.
  HOUR_LOCK    at 10:30, direction = close vs 9:30 open; enter next bar, hold to close.
  REV_945      at 9:45, trade opposite of 9:30-9:45 move; hold to close.
  PARABOLIC    5+ straight green 5-min bars, then a red bar that engulfs the last green: short next open,
               stop = run high, target 2R (mirror for 5 red then green engulfing: long).
  RSI_EXH      5-min RSI14 > 90 (or < 10), then first bar closing against it: fade, stop = extreme, target 2R.
  STOP_HUNT    price trades above prior-day high then a bar closes back below it: short, stop = session high, 2R
               (mirror at prior-day low).
  GAP_FADE     open gaps >= 1% vs prior close: fade at open, target = prior close, stop = 1x gap, else close.
  GAP_GO       same gaps, trade with the gap, stop = prior close, target 2R, else close.
  BAG_BOUNCE   gap down >= 3%: after 9:45, first 5-min bar closing above prior bar high: long, stop = session low, 2R.
Daily (swing, the articles' trend/range/momentum/pullback/Fibonacci ideas):
  D_MACD       MACD(12,26,9) crosses up while close > SMA50: long, stop 2 ATR, target 4 ATR.
  D_RANGE      ADX14 < 20 and RSI14 < 30 then RSI turns up: long, stop 1.5 ATR, target = 20-day high.
  D_FIB        uptrend (close > SMA50 > SMA200); price pulls back to 61.8% of last 20-day swing and closes up:
               long, stop below 20-day low, target = 20-day high.
  D_ADX_TREND  ADX > 25, +DI > -DI, close crosses above EMA20: long, stop 2 ATR, target 4 ATR.
  D_RANDOM     control: random days at same rate, stop 2 ATR, target 4 ATR.
"""
import numpy as np, pandas as pd
from reddit_test import TICKS, get, exit_walk, ret, rand_trade, summarize

def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn.replace(0, np.nan))

def bar_hm(t): return (t.hour, t.minute)

def two_r(day, k, side, stop):
    if k+1 >= len(day): return None
    e = day["Open"].iat[k+1]; risk = abs(e-stop)
    if risk <= 0 or (side>0 and e<=stop) or (side<0 and e>=stop): return None
    ex, why = exit_walk(day, k+1, side, e, stop, e+2*risk*side)
    return ret(side, e, ex), why

def hour_lock(day):
    idx = [i for i,t in enumerate(day.index) if bar_hm(t)==(10,25)]
    if not idx or idx[0]+1 >= len(day): return None
    i = idx[0]; side = 1 if day["Close"].iat[i] > day["Open"].iat[0] else -1
    e = day["Open"].iat[i+1]; return ret(side, e, day["Close"].iat[-1]), "close"

def rev_945(day):
    idx = [i for i,t in enumerate(day.index) if bar_hm(t)==(9,40)]
    if not idx or idx[0]+1 >= len(day): return None
    i = idx[0]; side = -1 if day["Close"].iat[i] > day["Open"].iat[0] else 1
    e = day["Open"].iat[i+1]; return ret(side, e, day["Close"].iat[-1]), "close"

def parabolic(day):
    o, c, h, l = day["Open"].values, day["Close"].values, day["High"].values, day["Low"].values
    g = np.sign(c - o)
    for i in range(6, len(day)-1):
        for s in (1, -1):
            if all(g[i-6+1:i] == s) and len(g[i-5:i])==5 and all(g[i-5:i]==s) and g[i] == -s:
                prev_o, prev_c = o[i-1], c[i-1]
                if s>0 and o[i] >= prev_c and c[i] <= prev_o:
                    return two_r(day, i, -1, h[i-5:i+1].max())
                if s<0 and o[i] <= prev_c and c[i] >= prev_o:
                    return two_r(day, i, 1, l[i-5:i+1].min())
    return None

def rsi_exh(day):
    r = rsi(day["Close"]).values; c, o = day["Close"].values, day["Open"].values
    armed = 0
    for i in range(15, len(day)-1):
        if r[i] > 90: armed = 1
        elif r[i] < 10: armed = -1
        if armed == 1 and c[i] < o[i]: return two_r(day, i, -1, day["High"].iloc[:i+1].max())
        if armed == -1 and c[i] > o[i]: return two_r(day, i, 1, day["Low"].iloc[:i+1].min())
    return None

def stop_hunt(day, pdh, pdl):
    h, l, c = day["High"].values, day["Low"].values, day["Close"].values
    up = dn = False
    for i in range(len(day)-1):
        if h[i] > pdh: up = True
        if l[i] < pdl: dn = True
        if up and c[i] < pdh: return two_r(day, i, -1, h[:i+1].max())
        if dn and c[i] > pdl: return two_r(day, i, 1, l[:i+1].min())
    return None

def gap(day, pc, mode):
    o = day["Open"].iat[0]; gp = o/pc - 1
    if mode == "bag":
        if gp > -0.03: return None
        for i in range(3, len(day)-1):
            if day["Close"].iat[i] > day["High"].iat[i-1]:
                return two_r(day, i, 1, day["Low"].iloc[:i+1].min())
        return None
    if abs(gp) < 0.01: return None
    s = np.sign(gp)
    if mode == "fade":
        side = -s; stop = o + s*abs(o-pc); tgt = pc
    else:
        side = s; stop = pc; tgt = o + s*2*abs(o-pc)
    ex, why = exit_walk(day, 0, int(side), o, stop, tgt)
    return ret(int(side), o, ex), why

def htf_ema(day, bias):
    c = day["Close"]; e9, e20 = c.ewm(span=9, adjust=False).mean(), c.ewm(span=20, adjust=False).mean()
    d = np.sign(e9-e20)
    for i in range(1, len(day)-1):
        if bar_hm(day.index[i]) < (9,45): continue
        if d.iat[i] == bias and d.iat[i-1] != bias:
            e = day["Open"].iat[i+1]
            for j in range(i+1, len(day)):
                if d.iat[j] == -bias:
                    ex = day["Open"].iat[j+1] if j+1 < len(day) else day["Close"].iat[-1]
                    return ret(bias, e, ex), "cross"
            return ret(bias, e, day["Close"].iat[-1]), "close"
    return None

def intraday():
    names = ["HTF_EMA","HOUR_LOCK","REV_945","PARABOLIC","RSI_EXH","STOP_HUNT","GAP_FADE","GAP_GO","BAG_BOUNCE","RANDOM"]
    res = {k: [] for k in names}
    for t in TICKS:
        d = get(t, "5m", "60d")
        if d is None: continue
        mk = "TSX" if t.endswith(".TO") else "US"
        hc = d["Close"].resample("60min").last().dropna()
        e100 = hc.ewm(span=100, adjust=False).mean()
        rngs = [np.random.default_rng(s) for s in range(5)]
        days = list(d.groupby("day")); prev = None
        for dt, g in days:
            def add(k, x):
                if x: res[k].append((x[0], x[1], mk))
            add("HOUR_LOCK", hour_lock(g)); add("REV_945", rev_945(g))
            add("PARABOLIC", parabolic(g)); add("RSI_EXH", rsi_exh(g))
            for rg in rngs: add("RANDOM", rand_trade(g, rg))
            if prev is not None:
                pc = prev["Close"].iat[-1]
                add("STOP_HUNT", stop_hunt(g, prev["High"].max(), prev["Low"].min()))
                add("GAP_FADE", gap(g, pc, "fade")); add("GAP_GO", gap(g, pc, "go")); add("BAG_BOUNCE", gap(g, pc, "bag"))
                hb = hc[hc.index < g.index[0]]
                if len(hb) > 100:
                    add("HTF_EMA", htf_ema(g, 1 if hb.iat[-1] > e100[hb.index[-1]] else -1))
            prev = g
        print("done", t)
    return [summarize(k + " (5m)", v) for k, v in res.items()]

def atr(df, n=14):
    pc = df["Close"].shift()
    tr = pd.concat([df["High"]-df["Low"], (df["High"]-pc).abs(), (df["Low"]-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = up.where((up>dn)&(up>0), 0.0); mdm = dn.where((dn>up)&(dn>0), 0.0)
    a = atr(df, n)
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi

def daily_walk(df, i, stop, tgt, hold=20):
    if i+1 >= len(df): return None
    e = df["Open"].iat[i+1]
    if not (stop < e): return None
    end = min(i+1+hold, len(df))
    for j in range(i+1, end):
        o, h, l = df["Open"].iat[j], df["High"].iat[j], df["Low"].iat[j]
        if l <= stop: return ret(1, e, min(o, stop) if j>i+1 else stop), "stop"
        if tgt is not None and h >= tgt: return ret(1, e, max(o, tgt) if j>i+1 else tgt), "target"
    return ret(1, e, df["Close"].iat[end-1]), "time"

def daily():
    names = ["D_MACD","D_RANGE","D_FIB","D_ADX_TREND","D_RANDOM"]
    res = {k: [] for k in names}
    import yfinance as yf
    for t in TICKS:
        df = yf.download(t, start="2015-01-01", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty: continue
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna(); mk = "TSX" if t.endswith(".TO") else "US"
        c = df["Close"]; A = atr(df); r = rsi(c); ax, pdi, mdi = adx(df)
        s50, s200, e20 = c.rolling(50).mean(), c.rolling(200).mean(), c.ewm(span=20, adjust=False).mean()
        m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean(); sig = m.ewm(span=9, adjust=False).mean()
        hi20, lo20 = df["High"].rolling(20).max(), df["Low"].rolling(20).min()
        rng = np.random.default_rng(1); busy = {k: -1 for k in names}
        for i in range(260, len(df)-1):
            if df.index[i] < pd.Timestamp("2016-01-01"): continue
            def take(k, cond, stop, tgt):
                if cond and i > busy[k]:
                    x = daily_walk(df, i, stop, tgt)
                    if x: res[k].append((x[0], x[1], mk)); busy[k] = i + 20
            ci, ai = c.iat[i], A.iat[i]
            take("D_MACD", m.iat[i] > sig.iat[i] and m.iat[i-1] <= sig.iat[i-1] and ci > s50.iat[i], ci-2*ai, ci+4*ai)
            take("D_RANGE", ax.iat[i] < 20 and r.iat[i-1] < 30 and r.iat[i] > r.iat[i-1], ci-1.5*ai, hi20.iat[i])
            sw = hi20.iat[i] - lo20.iat[i]; fib = hi20.iat[i] - 0.618*sw
            take("D_FIB", ci > s50.iat[i] > s200.iat[i] and df["Low"].iat[i] <= fib and ci > df["Open"].iat[i] and sw > 0,
                 lo20.iat[i]*0.995, hi20.iat[i])
            take("D_ADX_TREND", ax.iat[i] > 25 and pdi.iat[i] > mdi.iat[i] and ci > e20.iat[i] and c.iat[i-1] <= e20.iat[i-1], ci-2*ai, ci+4*ai)
            take("D_RANDOM", rng.random() < 0.02, ci-2*ai, ci+4*ai)
        print("daily done", t)
    return [summarize(k + " (daily 2016+)", v) for k, v in res.items()]

if __name__ == "__main__":
    out = intraday() + daily()
    df = pd.DataFrame(out); print(df.to_string(index=False))
    import os; os.makedirs("../../results/intraday", exist_ok=True)
    df.to_csv("../../results/intraday/articles_summary.csv", index=False)
