"""Every setup from the research, as boolean wide frames (True = signal at today's close).
Each entry: name -> (signal, entry_mode, source).  entry_mode 0 = next open, 1 = buy-stop above signal high.
All require the stock to be liquid at the time (>= $1M/day traded, price >= $2)."""
import numpy as np
import pandas as pd


def candle_patterns(I):
    O, H, L, C = I["O"], I["H"], I["L"], I["C"]
    body = (C - O).abs()
    rng = (H - L).replace(0, np.nan)
    top, bot = np.maximum(O, C), np.minimum(O, C)
    upper, lower = H - top, bot - L
    bull, bear = C > O, C < O
    ab = body.rolling(20).mean()
    big, small = body > ab, body < 0.5 * ab
    doji = body <= 0.1 * rng
    S = lambda x, k=1: x.shift(k)
    dip = S(C) < S(C, 6)                       # short pullback before the candle
    p = {}
    p["Hammer"] = dip & (lower >= 2 * body) & (upper <= 0.3 * body + 0.1 * rng) & ~doji
    p["Bullish Pin Bar"] = dip & (lower >= 0.6 * rng) & (body <= 0.3 * rng)
    p["Dragonfly Doji"] = dip & doji & (lower >= 0.7 * rng) & (upper <= 0.1 * rng)
    p["Bullish Engulfing"] = dip & S(bear) & bull & (O <= S(C)) & (C >= S(O)) & (body > S(body))
    p["Bullish Harami"] = dip & S(bear) & S(big) & bull & (O >= S(C)) & (C <= S(O)) & small
    p["Piercing Line"] = dip & S(bear) & S(big) & bull & (O < S(C)) & (C > (S(O) + S(C)) / 2) & (C < S(O))
    p["Tweezer Bottom"] = dip & S(bear) & bull & ((L - S(L)).abs() <= 0.002 * C)
    p["Bullish Belt Hold"] = dip & bull & big & (lower <= 0.05 * rng)
    p["Bullish Kicker"] = S(bear) & S(big) & bull & (O > S(O)) & (L > S(O))
    p["Morning Star"] = dip & S(bear, 2) & S(big, 2) & S(small) & bull & big & (C > (S(O, 2) + S(C, 2)) / 2)
    p["Three Outside Up"] = S(bear, 2) & S(bull) & (S(O) <= S(C, 2)) & (S(C) >= S(O, 2)) & bull & (C > S(C))
    p["Three White Soldiers"] = (bull & S(bull) & S(bull, 2) & (C > S(C)) & (S(C) > S(C, 2))
                                 & big & S(big) & S(big, 2) & (upper < 0.3 * body))
    p["Rising Three"] = (S(bull, 4) & S(big, 4) & S(small, 3) & S(small, 2) & S(small)
                         & (np.minimum(np.minimum(S(L, 3), S(L, 2)), S(L)) > S(L, 4)) & bull & big & (C > S(C, 4)))
    p["Gap Up"] = (O > S(H)) & bull & (O / S(C) - 1 > 0.01)
    # Bulkowski top-ranked bullish patterns
    p["Three Line Strike (bull)"] = (S(bull, 3) & S(bull, 2) & S(bull) & (S(C, 2) > S(C, 3)) & (S(C) > S(C, 2))
                                     & bear & (O >= S(C)) & (C <= S(O, 3)))
    p["Abandoned Baby (bull)"] = S(bear, 2) & S(doji) & (S(H) < S(L, 2)) & bull & (L > S(H)) & dip
    return {k: v.fillna(False) for k, v in p.items()}


def all_setups(I):
    O, H, L, C, V = I["O"], I["H"], I["L"], I["C"], I["V"]
    liq = I["liquid"]
    mkt = I["mkt_up"].reindex(C.index).fillna(False).values[:, None]
    up200 = C > I["sma200"]
    stage2 = ((C > I["sma50"]) & (I["sma50"] > I["sma150"]) & (I["sma150"] > I["sma200"])
              & (I["sma200"] > I["sma200"].shift(21)) & (C >= 1.3 * I["lo252"]) & (C >= 0.75 * I["hi252"]))
    S = {}

    def add(name, sig, mode, src):
        S[name] = ((sig & liq).fillna(False), mode, src)

    # ---------- baselines (to measure real edge)
    add("BASE any day, stock>200d", up200, 0, "baseline")
    add("BASE any day, stage-2 trend", stage2, 0, "baseline")

    # ---------- mean reversion (Connors / Alvarez / Pagonidis IBS)
    add("RSI2<10 & >200d", up200 & (I["rsi2"] < 10), 0, "Connors & Alvarez, Short Term Trading Strategies That Work (2008)")
    add("RSI2<5 & >200d", up200 & (I["rsi2"] < 5), 0, "Connors & Alvarez (2008)")
    cum = I["rsi2"] + I["rsi2"].shift(1)
    add("Cumulative RSI2<35 & >200d", up200 & (cum < 35), 0, "Connors & Alvarez (2008)")
    add("IBS<0.2 & >200d", up200 & (I["ibs"] < 0.2), 0, "Pagonidis, IBS (NAAIM 2014)")
    add("IBS<0.2 & RSI2<10 & >200d", up200 & (I["ibs"] < 0.2) & (I["rsi2"] < 10), 0, "combined")
    add("Double 7s (7-day low close) & >200d", up200 & (C <= C.rolling(7).min()), 0, "Connors & Alvarez (2008)")
    d3 = (C < C.shift(1)) & (C.shift(1) < C.shift(2)) & (C.shift(2) < C.shift(3))
    add("3 down closes & >200d", up200 & d3, 0, "Connors, 3-day pullback")
    add("Pullback to 20EMA in stage-2", stage2 & (L <= I["ema20"]) & (C > I["ema20"]), 0, "classic pullback")
    add("RSI2<10 in stage-2 & strong RS", stage2 & (I["rsi2"] < 10) & (I["rs_rank"] > 0.7), 0, "Connors + Minervini filter")

    # ---------- trend / breakout (Raschke, Crabel, Minervini, Qullamaggie, O'Neil)
    grail = (I["adx14"] > 30) & (I["ema20"] > I["ema50"]) & (L <= I["ema20"]) & (C > I["ema50"])
    add("Holy Grail (ADX>30, touch 20EMA) buy-stop", grail, 1, "Raschke & Connors, Street Smarts (1995)")
    nr7 = (H - L) <= (H - L).rolling(7).min()
    inside = (H < H.shift(1)) & (L > L.shift(1))
    add("NR7 + inside day in stage-2, buy-stop", stage2 & nr7 & inside, 1, "Crabel, Day Trading with Short Term Price Patterns (1990)")
    add("NR7 in stage-2, buy-stop", stage2 & nr7, 1, "Crabel (1990)")
    tight = (I["atr10"] / I["atr50"] < 0.75) & (I["V"].rolling(5).mean() < 0.75 * I["vol50"])
    near = C >= 0.95 * I["hi20"]
    add("VCP: stage-2 + volatility & volume dry-up, buy-stop", stage2 & tight & near & (I["rs_rank"] > 0.7), 1,
        "Minervini, Trade Like a Stock Market Wizard (2013)")
    h10, l10 = H.rolling(10).max(), L.rolling(10).min()
    flag = (I["ret63_rank"] > 0.9) & (h10 / l10 < 1.15) & (C > I["sma10"]) & (I["sma10"] > I["sma20"])
    add("Qullamaggie flag (top 10% 3m, tight 10d), buy-stop", flag, 1, "Kullamagi breakout setup")
    ep = (O / C.shift(1) - 1 >= 0.08) & (V >= 3 * I["vol50"]) & (I["ibs"] >= 0.5)
    add("Episodic pivot (gap>=8% on 3x volume), buy-stop", ep, 1, "Kullamagi / Pradeep Bonde episodic pivot")
    add("52-week-high breakout on 1.5x volume", (C >= I["hi252"]) & (V > 1.5 * I["vol50"]) & stage2, 0,
        "George & Hwang (2004) 52-week-high momentum")
    add("20-day breakout on 1.5x volume (stage-2)", stage2 & (C >= I["hi20"]) & (V > 1.5 * I["vol50"]), 0, "Donchian / Turtle")

    # ---------- calendar
    dom = pd.Series(C.index.day, index=C.index)
    nxt = pd.Series(C.index.month, index=C.index).shift(-5)
    tom = (pd.Series(C.index.month, index=C.index) != nxt).fillna(False)   # last ~5 trading days of month
    tom = pd.DataFrame(np.repeat(tom.values[:, None], C.shape[1], axis=1), index=C.index, columns=C.columns)
    add("Turn-of-month window & stage-2", stage2 & tom & (I["rsi2"] < 30), 0, "Lakonishok & Smidt (1988); Ariel (1987)")

    # ---------- candlesticks (wrtrading list + Bulkowski top ranks), with trend filter
    for nm, pat in candle_patterns(I).items():
        add(f"Candle: {nm} & >200d", pat & up200, 0, "wrtrading guide / Bulkowski, Encyclopedia of Candlestick Charts")
        add(f"Candle: {nm} & >200d, confirm buy-stop", pat & up200, 1, "Bulkowski: wait for close/break above the pattern")

    # market regime variants added by the runner
    return S, mkt


EXITS = {
    "YOUR TARGET +3% / -1%, 10d": dict(tgt_pct=0.03, stop_pct=0.01, hold=10),
    "+3% / -1%, 5d": dict(tgt_pct=0.03, stop_pct=0.01, hold=5),
    "+3% / -1.5%, 10d": dict(tgt_pct=0.03, stop_pct=0.015, hold=10),
    "+3% / -2%, 10d": dict(tgt_pct=0.03, stop_pct=0.02, hold=10),
    "+3% / -3%, 10d": dict(tgt_pct=0.03, stop_pct=0.03, hold=10),
    "+2% / -2%, 5d": dict(tgt_pct=0.02, stop_pct=0.02, hold=5),
    "+5% / -2.5%, 15d": dict(tgt_pct=0.05, stop_pct=0.025, hold=15),
    "+6% / -3%, 20d": dict(tgt_pct=0.06, stop_pct=0.03, hold=20),
    "ATR 1 stop / 3 target, 15d": dict(stop_atr=1, tgt_atr=3, hold=15),
    "ATR 1.5 stop / 3 target, 15d": dict(stop_atr=1.5, tgt_atr=3, hold=15),
    "ATR 2 stop / 4 target, 20d": dict(stop_atr=2, tgt_atr=4, hold=20),
    "ATR 2 stop / 2 target, 10d": dict(stop_atr=2, tgt_atr=2, hold=10),
    "MR: close>SMA5, stop -5%, 10d": dict(mr=1, stop_pct=0.05, hold=10),
    "MR: close>SMA5 or +3%, stop -5%, 10d": dict(mr=1, stop_pct=0.05, tgt_pct=0.03, hold=10),
    "MR: first close>prior high, stop -5%, 10d": dict(mr=2, stop_pct=0.05, hold=10),
}
