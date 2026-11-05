"""RSI + EMA + session VWAP, 5-min bars. Rules fixed before running (5 Nov 2026).
Same data, names, costs, fills and pass rule as ema_vwap_5m.py. RSI = Wilder 14 on 5-min closes.
  R1 momentum: EMA9 crosses EMA20, close on same side of VWAP, RSI > 50 (long) / < 50 (short).
     Exit: opposite EMA cross, close back through VWAP, or end of day.
  R2 pullback: trend = EMA9 > EMA20 and close > VWAP (long; mirror short). Enter when RSI crosses
     back up through 40 (long) / down through 60 (short). Exit: RSI > 70 (<30), close through VWAP, or end of day.
  R3 R2 with stop at VWAP (min 0.2%) and 2R target, else end of day.
  RANDOM control.
"""
import numpy as np, pandas as pd
from reddit_test import TICKS, get, exit_walk, ret, rand_trade, summarize
from ema_vwap_5m import prep, late

def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def r1(day):
    c, vw, e9, e20 = prep(day); r = rsi(c); d = np.sign(e9 - e20)
    for i in range(15, len(day) - 1):
        if not late(day, i) or np.isnan(vw.iat[i]) or np.isnan(r.iat[i]): continue
        if d.iat[i] != 0 and d.iat[i] != d.iat[i-1]:
            s = int(d.iat[i])
            if s*(c.iat[i]-vw.iat[i]) <= 0 or s*(r.iat[i]-50) <= 0: continue
            p = day["Open"].iat[i+1]
            for j in range(i+1, len(day)):
                if d.iat[j] == -s or s*(c.iat[j]-vw.iat[j]) < 0:
                    ex = day["Open"].iat[j+1] if j+1 < len(day) else day["Close"].iat[-1]
                    return ret(s, p, ex), "exit"
            return ret(s, p, day["Close"].iat[-1]), "close"
    return None

def r2(day, stops=False):
    c, vw, e9, e20 = prep(day); r = rsi(c)
    for i in range(15, len(day) - 1):
        if not late(day, i) or np.isnan(vw.iat[i]) or np.isnan(r.iat[i-1]): continue
        s = 0
        if e9.iat[i] > e20.iat[i] and c.iat[i] > vw.iat[i] and r.iat[i-1] < 40 <= r.iat[i]: s = 1
        if e9.iat[i] < e20.iat[i] and c.iat[i] < vw.iat[i] and r.iat[i-1] > 60 >= r.iat[i]: s = -1
        if not s: continue
        p = day["Open"].iat[i+1]
        if stops:
            risk = max(abs(p - vw.iat[i]), 0.002*p)
            ex, why = exit_walk(day, i+1, s, p, p - s*risk, p + s*2*risk)
            return ret(s, p, ex), why
        for j in range(i+1, len(day)):
            if s*(r.iat[j]-50) > 20 or s*(c.iat[j]-vw.iat[j]) < 0:
                ex = day["Open"].iat[j+1] if j+1 < len(day) else day["Close"].iat[-1]
                return ret(s, p, ex), "exit"
        return ret(s, p, day["Close"].iat[-1]), "close"
    return None

SETUPS = {"R1 EMA cross+VWAP+RSI50": r1, "R2 RSI pullback in EMA/VWAP trend": r2,
          "R3 R2 + VWAP stop, 2R": lambda g: r2(g, True), "RANDOM": rand_trade}

if __name__ == "__main__":
    res = {k: [] for k in SETUPS}
    for t in TICKS:
        d = get(t, "5m", "60d")
        if d is None: continue
        mk = "TSX" if t.endswith(".TO") else "US"
        rngs = [np.random.default_rng(s) for s in range(5)]
        for _, g in d.groupby("day"):
            for n, fn in SETUPS.items():
                xs = [fn(g, rg) for rg in rngs] if n == "RANDOM" else [fn(g)]
                res[n] += [(x[0], x[1], mk) for x in xs if x]
    df = pd.DataFrame([summarize(k, v) for k, v in res.items()])
    print(df.to_string(index=False))
