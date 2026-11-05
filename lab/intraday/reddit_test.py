"""Reddit r/Daytrading ideas, intraday test on Yahoo data. Rules fixed before running (4 Nov 2026).

Data: Yahoo 5-minute bars (last ~60 days, Yahoo's limit) and 1-hour bars (last ~730 days).
Universe: liquid US and TSX names (below). Regular session only.
Costs: 0.03% per side (liquid large caps); results also shown at 0.10% per side.
Every setup: one trade per stock per day max, flat by the close. Long and short.

Setups (5-minute data):
  ORB5      opening range = first 5-min bar. First close beyond the range -> enter next bar open.
            Stop = other side of range. Target = 2R. Else exit at close.
  ORB15     same, range = first 15 minutes.
  ORB5_RT   ORB5 with retest: after the breakout close, wait for a bar whose low (long) touches
            the range high and closes back above it; enter next bar open. Same stop/target.
  VWAP      at 10:00, if price above session VWAP go long, below go short; stop = VWAP at entry
            distance x1 (min 0.2%); target 2R; else close.
  EMA9_20   5-min EMA9 crosses EMA20 (after 9:45); enter next open in cross direction;
            exit on opposite cross or close.
  RANDOM    control: random time 9:40-15:00, random direction, stop 0.5%, target 1%, else close.
            5 seeds.
Setups (1-hour data, 2 years):
  ORB60     range = first hour. Same rules as ORB5.
  RANDOM60  control on 1-hour bars.

Pass (per setup): mean net % per trade > 0 at 0.03% cost with t > 2.8 (Bonferroni for ~8 tests),
and better than RANDOM. Short sample (60 days) for 5-min setups: treat any pass as a lead only.
"""
import sys, json
import numpy as np, pandas as pd, yfinance as yf

US = ["SPY","QQQ","IWM","AAPL","MSFT","NVDA","TSLA","AMD","AMZN","META","GOOGL","NFLX","JPM","XOM","BA","COIN","PLTR","SMCI","MU","AVGO"]
TSX = ["XIU.TO","RY.TO","TD.TO","SHOP.TO","ENB.TO","CNQ.TO","SU.TO","AEM.TO","BN.TO","CP.TO","BMO.TO","ABX.TO","CCO.TO","TRI.TO","WCN.TO"]
TICKS = US + TSX

def get(t, interval, period):
    d = yf.download(t, interval=interval, period=period, progress=False, auto_adjust=False, prepost=False)
    if d is None or d.empty: return None
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d[["Open","High","Low","Close","Volume"]].dropna()
    tz = "America/Toronto" if t.endswith(".TO") else "America/New_York"
    d.index = d.index.tz_convert(tz)
    d = d.between_time("09:30","15:59")
    d["day"] = d.index.date
    return d

def exit_walk(bars, i0, side, entry, stop, tgt):
    """Walk bars from i0 (entry bar). Stop checked first within a bar. Returns exit price, reason."""
    for j in range(i0, len(bars)):
        h, l = bars["High"].iat[j], bars["Low"].iat[j]
        if side > 0:
            if l <= stop: return min(stop, bars["Open"].iat[j]) if j>i0 else stop, "stop"
            if tgt is not None and h >= tgt: return max(tgt, bars["Open"].iat[j]) if j>i0 else tgt, "target"
        else:
            if h >= stop: return max(stop, bars["Open"].iat[j]) if j>i0 else stop, "stop"
            if tgt is not None and l <= tgt: return min(tgt, bars["Open"].iat[j]) if j>i0 else tgt, "target"
    return bars["Close"].iat[-1], "close"

def ret(side, entry, ex):
    return side * (ex / entry - 1) * 100

def orb(day, nbars, retest=False):
    if len(day) < nbars + 3: return None
    rh, rl = day["High"].iloc[:nbars].max(), day["Low"].iloc[:nbars].min()
    if rh <= rl: return None
    side = 0; k = None
    for i in range(nbars, len(day)-1):
        c = day["Close"].iat[i]
        if side == 0:
            if c > rh: side, b = 1, i
            elif c < rl: side, b = -1, i
            else: continue
            if not retest: k = i; break
        else:
            if side > 0 and day["Low"].iat[i] <= rh and c > rh: k = i; break
            if side < 0 and day["High"].iat[i] >= rl and c < rl: k = i; break
    if k is None or k + 1 >= len(day): return None
    e = day["Open"].iat[k+1]
    stop = rl if side > 0 else rh
    risk = abs(e - stop)
    if risk <= 0 or (side > 0 and e <= stop) or (side < 0 and e >= stop): return None
    tgt = e + 2*risk*side
    ex, why = exit_walk(day, k+1, side, e, stop, tgt)
    return ret(side, e, ex), why

def vwap_trade(day):
    tp = (day["High"]+day["Low"]+day["Close"])/3
    vw = (tp*day["Volume"]).cumsum() / day["Volume"].cumsum().replace(0, np.nan)
    idx = [i for i,t in enumerate(day.index) if t.hour==10 and t.minute==0]
    if not idx: return None
    i = idx[0]
    if i+1 >= len(day) or np.isnan(vw.iat[i]): return None
    side = 1 if day["Close"].iat[i] > vw.iat[i] else -1
    e = day["Open"].iat[i+1]
    risk = max(abs(e - vw.iat[i]), 0.002*e)
    ex, why = exit_walk(day, i+1, side, e, e - side*risk, e + side*2*risk)
    return ret(side, e, ex), why

def ema_trade(day):
    c = day["Close"]
    e9, e20 = c.ewm(span=9, adjust=False).mean(), c.ewm(span=20, adjust=False).mean()
    d = np.sign(e9 - e20)
    for i in range(1, len(day)-1):
        t = day.index[i]
        if (t.hour, t.minute) < (9,45): continue
        if d.iat[i] != 0 and d.iat[i] != d.iat[i-1]:
            side = int(d.iat[i]); e = day["Open"].iat[i+1]
            for j in range(i+1, len(day)):
                if d.iat[j] == -side:
                    ex = day["Open"].iat[j+1] if j+1 < len(day) else day["Close"].iat[-1]
                    return ret(side, e, ex), "cross"
            return ret(side, e, day["Close"].iat[-1]), "close"
    return None

def rand_trade(day, rng, stop_pct=0.5, tgt_pct=1.0):
    ok = [i for i,t in enumerate(day.index) if (9,40) <= (t.hour,t.minute) <= (15,0)]
    if len(ok) < 2: return None
    i = rng.choice(ok[:-1]); side = rng.choice([-1,1])
    e = day["Open"].iat[i+1]
    ex, why = exit_walk(day, i+1, side, e, e*(1-side*stop_pct/100), e*(1+side*tgt_pct/100))
    return ret(side, e, ex), why

def summarize(name, rows):
    if not rows: return {"setup": name, "trades": 0}
    r = np.array([x[0] for x in rows]); mkt = np.array([x[2] for x in rows])
    out = {"setup": name, "trades": len(r)}
    for cost in (0.03, 0.10):
        n = r - 2*cost
        out[f"mean_{cost}"] = round(n.mean(), 4)
        out[f"t_{cost}"] = round(n.mean()/(n.std(ddof=1)/np.sqrt(len(n))), 2) if len(n)>2 else None
    n = r - 0.06
    out["win%"] = round((n>0).mean()*100, 1)
    out["US_mean"] = round(n[mkt=="US"].mean(), 4) if (mkt=="US").any() else None
    out["TSX_mean"] = round(n[mkt=="TSX"].mean(), 4) if (mkt=="TSX").any() else None
    # $5,000, one trade per day at a time is not modeled; show compounding of the average daily basket
    return out

def run(interval, period, setups):
    res = {k: [] for k in setups}
    for t in TICKS:
        d = get(t, interval, period)
        if d is None: print("no data", t); continue
        mk = "TSX" if t.endswith(".TO") else "US"
        rngs = [np.random.default_rng(s) for s in range(5)]
        for day_, g in d.groupby("day"):
            for name, fn in setups.items():
                if name.startswith("RANDOM"):
                    for rg in rngs:
                        x = fn(g, rg)
                        if x: res[name].append((x[0], x[1], mk))
                else:
                    x = fn(g)
                    if x: res[name].append((x[0], x[1], mk))
        print("done", t, interval, len(d))
    return res

if __name__ == "__main__":
    out = []
    r5 = run("5m", "60d", {
        "ORB5": lambda g: orb(g, 1), "ORB15": lambda g: orb(g, 3),
        "ORB5_RT": lambda g: orb(g, 1, retest=True), "VWAP": vwap_trade,
        "EMA9_20": ema_trade, "RANDOM": rand_trade})
    out += [summarize(k + " (5m, 60d)", v) for k, v in r5.items()]
    r60 = run("60m", "730d", {"ORB60": lambda g: orb(g, 1), "RANDOM60": rand_trade})
    out += [summarize(k + " (1h, 2y)", v) for k, v in r60.items()]
    df = pd.DataFrame(out)
    print(df.to_string(index=False))
    import os; os.makedirs("results/intraday", exist_ok=True)
    df.to_csv("results/intraday/reddit_summary.csv", index=False)
