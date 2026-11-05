"""EMA + session VWAP combined, 5-minute bars. Rules fixed before running (5 Nov 2026).

Data: Yahoo 5-min bars, last ~60 days, regular session. Same 35 US/TSX names as reddit_test.py.
VWAP = session VWAP from typical price, reset each day. Entries after 9:45, flat by close,
one trade per stock per day, long and short. Signal on bar close, fill at next bar open.

  X9     EMA9 crosses session VWAP -> enter in cross direction. Exit on opposite cross or close.
  X20    EMA20 crosses session VWAP -> same.
  E_V    EMA9 crosses EMA20 AND close on the same side of VWAP (long: close > VWAP) -> enter.
         Exit on opposite EMA9/20 cross, or close crossing back through VWAP, or close.
  E_V_S  E_V with a stop at VWAP at entry (min 0.2%) and a 2R target, else close.
  RANDOM control (5 seeds), same as reddit_test.py.

Cost 0.03%/side (also 0.10%). Pass = mean > 0 at 0.03% with t > 2.8 and better than RANDOM.
"""
import numpy as np, pandas as pd
from reddit_test import TICKS, get, exit_walk, ret, rand_trade, summarize


def prep(day):
    tp = (day["High"] + day["Low"] + day["Close"]) / 3
    vw = (tp * day["Volume"]).cumsum() / day["Volume"].cumsum().replace(0, np.nan)
    c = day["Close"]
    return c, vw, c.ewm(span=9, adjust=False).mean(), c.ewm(span=20, adjust=False).mean()


def late(day, i):
    t = day.index[i]
    return (t.hour, t.minute) >= (9, 45)


def cross_trade(day, span):
    c, vw, e9, e20 = prep(day)
    e = e9 if span == 9 else e20
    d = np.sign(e - vw)
    for i in range(1, len(day) - 1):
        if not late(day, i) or np.isnan(d.iat[i]) or np.isnan(d.iat[i - 1]): continue
        if d.iat[i] != 0 and d.iat[i] != d.iat[i - 1]:
            side = int(d.iat[i]); p = day["Open"].iat[i + 1]
            for j in range(i + 1, len(day)):
                if d.iat[j] == -side:
                    ex = day["Open"].iat[j + 1] if j + 1 < len(day) else day["Close"].iat[-1]
                    return ret(side, p, ex), "cross"
            return ret(side, p, day["Close"].iat[-1]), "close"
    return None


def ema_vwap_trade(day, stops=False):
    c, vw, e9, e20 = prep(day)
    d = np.sign(e9 - e20)
    for i in range(1, len(day) - 1):
        if not late(day, i) or np.isnan(vw.iat[i]): continue
        if d.iat[i] != 0 and d.iat[i] != d.iat[i - 1]:
            side = int(d.iat[i])
            if side * (c.iat[i] - vw.iat[i]) <= 0: continue
            p = day["Open"].iat[i + 1]
            if stops:
                risk = max(abs(p - vw.iat[i]), 0.002 * p)
                ex, why = exit_walk(day, i + 1, side, p, p - side * risk, p + side * 2 * risk)
                return ret(side, p, ex), why
            for j in range(i + 1, len(day)):
                if d.iat[j] == -side or side * (c.iat[j] - vw.iat[j]) < 0:
                    ex = day["Open"].iat[j + 1] if j + 1 < len(day) else day["Close"].iat[-1]
                    return ret(side, p, ex), "exit"
            return ret(side, p, day["Close"].iat[-1]), "close"
    return None


SETUPS = {
    "X9 EMA9xVWAP": lambda g: cross_trade(g, 9),
    "X20 EMA20xVWAP": lambda g: cross_trade(g, 20),
    "E_V EMA9/20 + VWAP side": lambda g: ema_vwap_trade(g),
    "E_V_S same + VWAP stop, 2R": lambda g: ema_vwap_trade(g, True),
    "RANDOM": rand_trade,
}

if __name__ == "__main__":
    res = {k: [] for k in SETUPS}
    for t in TICKS:
        d = get(t, "5m", "60d")
        if d is None: print("no data", t); continue
        mk = "TSX" if t.endswith(".TO") else "US"
        rngs = [np.random.default_rng(s) for s in range(5)]
        for _, g in d.groupby("day"):
            for name, fn in SETUPS.items():
                xs = [fn(g, rg) for rg in rngs] if name == "RANDOM" else [fn(g)]
                res[name] += [(x[0], x[1], mk) for x in xs if x]
        print("done", t, len(d))
    df = pd.DataFrame([summarize(k, v) for k, v in res.items()])
    print(df.to_string(index=False))
    import os; os.makedirs("results/intraday", exist_ok=True)
    df.to_csv("results/intraday/ema_vwap_5m_summary.csv", index=False)
