"""Mix-and-match: daily (interday) filter x intraday day-trade setup. Rules fixed before run, 4 Nov 2026.

Intraday setups (5-min, last 60 days, flat by close; from reddit_test / articles_test):
  ORB5, ORB15, ORB5_RT, VWAP, EMA9_20, HOUR_LOCK, REV_945, STOP_HUNT, GAP_GO, GAP_FADE
Daily filters, computed on the PRIOR day's daily bar (no lookahead):
  NONE      take every trade
  TREND     long only if close > SMA50 > SMA200; short only if close < SMA50 < SMA200
  MACD      long only if MACD > signal; short only if MACD < signal
  ADX       only when ADX14 > 25; long if +DI > -DI, short if -DI > +DI
  LONG_UP   long-only, and only if close > SMA50 (the articles' "trade with the trend", no shorts)
  MKT       long only if SPY (US) / XIU (TSX) close > its SMA50, short only if below
Combos: 10 x 6 = 60. Cost 0.03%/side (also 0.10%). Pass = mean > 0 with t > 3.2 (Bonferroni 0.05/60),
and beats RANDOM filtered the same way. 60 days of 5-min data: any pass is a lead only.
"""
import numpy as np, pandas as pd, yfinance as yf
import reddit_test as R, articles_test as A

SIDE = {"s": 0}
def ret_capture(side, e, ex):
    SIDE["s"] = side
    return side * (ex / e - 1) * 100
R.ret = ret_capture; A.ret = ret_capture

def daily_feats(t):
    df = yf.download(t, period="2y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna(); c = df["Close"]
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    ax, pdi, mdi = A.adx(df)
    f = pd.DataFrame({"c": c, "s50": c.rolling(50).mean(), "s200": c.rolling(200).mean(),
                      "macd": m, "sig": m.ewm(span=9, adjust=False).mean(), "adx": ax, "pdi": pdi, "mdi": mdi})
    f.index = pd.to_datetime(f.index).date
    return f.shift(1)  # prior day's values on each date

def allowed(fname, f, mk):
    """return set of allowed sides for this day"""
    if fname == "NONE": return {1, -1}
    if f is None or f.isna().any(): return set()
    if fname == "TREND":
        return {1} if f.c > f.s50 > f.s200 else ({-1} if f.c < f.s50 < f.s200 else set())
    if fname == "MACD": return {1} if f.macd > f.sig else {-1}
    if fname == "ADX":
        if f.adx <= 25: return set()
        return {1} if f.pdi > f.mdi else {-1}
    if fname == "LONG_UP": return {1} if f.c > f.s50 else set()
    if fname == "MKT": return {1} if mk.c > mk.s50 else {-1}
    return set()

SETUPS = {
    "ORB5": lambda g, p: R.orb(g, 1), "ORB15": lambda g, p: R.orb(g, 3),
    "ORB5_RT": lambda g, p: R.orb(g, 1, retest=True), "VWAP": lambda g, p: R.vwap_trade(g),
    "EMA9_20": lambda g, p: R.ema_trade(g), "HOUR_LOCK": lambda g, p: A.hour_lock(g),
    "REV_945": lambda g, p: A.rev_945(g),
    "STOP_HUNT": lambda g, p: A.stop_hunt(g, p["High"].max(), p["Low"].min()) if p is not None else None,
    "GAP_GO": lambda g, p: A.gap(g, p["Close"].iat[-1], "go") if p is not None else None,
    "GAP_FADE": lambda g, p: A.gap(g, p["Close"].iat[-1], "fade") if p is not None else None,
}
FILTERS = ["NONE", "TREND", "MACD", "ADX", "LONG_UP", "MKT"]

if __name__ == "__main__":
    res = {(s, f): [] for s in list(SETUPS) + ["RANDOM"] for f in FILTERS}
    mkt = {"US": daily_feats("SPY"), "TSX": daily_feats("XIU.TO")}
    for t in R.TICKS:
        d = R.get(t, "5m", "60d")
        if d is None: continue
        mk = "TSX" if t.endswith(".TO") else "US"; feats = daily_feats(t)
        rngs = [np.random.default_rng(s) for s in range(5)]; prev = None
        for day, g in d.groupby("day"):
            f = feats.loc[day] if day in feats.index else None
            m = mkt[mk].loc[day] if day in mkt[mk].index else None
            allow = {fn: allowed(fn, f, m) if fn != "MKT" else (allowed("MKT", f, m) if m is not None and not m.isna().any() else set()) for fn in FILTERS}
            trades = []
            for s, fn in SETUPS.items():
                x = fn(g, prev)
                if x: trades.append((s, x[0], SIDE["s"]))
            for rg in rngs:
                x = R.rand_trade(g, rg)
                if x: trades.append(("RANDOM", x[0], SIDE["s"]))
            for s, r, side in trades:
                for fn in FILTERS:
                    if side in allow[fn]: res[(s, fn)].append((r, "", mk))
            prev = g
        print("done", t)
    rows = []
    for (s, fn), v in res.items():
        row = R.summarize(f"{s} | {fn}", v); row["setup_only"] = s; row["filter"] = fn; rows.append(row)
    df = pd.DataFrame(rows)
    rnd = df[df.setup_only == "RANDOM"].set_index("filter")["mean_0.03"]
    df["vs_random"] = (df["mean_0.03"] - df["filter"].map(rnd)).round(4)
    df["PASS"] = (df["t_0.03"] > 3.2) & (df["vs_random"] > 0) & (df.setup_only != "RANDOM")
    df = df.sort_values("mean_0.03", ascending=False)
    pd.set_option("display.width", 250)
    print(df[["setup", "trades", "mean_0.03", "t_0.03", "mean_0.1", "win%", "vs_random", "PASS"]].to_string(index=False))
    import os; os.makedirs("../../results/intraday", exist_ok=True)
    df.to_csv("../../results/intraday/combo_summary.csv", index=False)
