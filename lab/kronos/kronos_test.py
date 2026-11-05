"""Kronos-small out-of-sample trading test. Rules fixed before run, 4 Nov 2026.

Model: NeoQuasar/Kronos-small + Kronos-Tokenizer-base (public repo shiyu-coder/Kronos). CPU.
Period: forecasts made every 5 trading days from 2025-10-01 to 2026-10-23 (after the paper's Aug 2025 release,
so after its training data). Daily bars from Yahoo, lookback 400 days, forecast 5 days ahead, 3 samples averaged.
Universe: same 35 liquid US + TSX names as the intraday tests.

Tests:
  A Direction: share of forecasts whose 5-day direction is right (coin flip = ~50%, up-days bias ~53%).
  B Long-top-5: each week buy the 5 stocks with the highest forecast 5-day return, hold 5 days, 0.1%/side.
  C Long-short: long top 5, short bottom 5 (market-neutral), 0.1%/side each side.
  D Volatility: correlation of forecast 5-day range with actual 5-day range (this is where Kronos claims skill).
Controls: equal-weight all 35 held each week (same costs), and random 5 stocks each week (200 seeds).
Pass (B): beats equal-weight AND beats >= 95% of random portfolios. Pass (C): mean weekly return > 0 with t > 2.
"""
import sys, os, json, numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, "Kronos")
from model import Kronos, KronosTokenizer, KronosPredictor

US = ["SPY","QQQ","IWM","AAPL","MSFT","NVDA","TSLA","AMD","AMZN","META","GOOGL","NFLX","JPM","XOM","BA","COIN","PLTR","SMCI","MU","AVGO"]
TSX = ["XIU.TO","RY.TO","TD.TO","SHOP.TO","ENB.TO","CNQ.TO","SU.TO","AEM.TO","BN.TO","CP.TO","BMO.TO","ABX.TO","CCO.TO","TRI.TO","WCN.TO"]
TICKS = US + TSX; LOOK, H, COST = 400, 5, 0.001

tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
pred = KronosPredictor(mdl, tok, device="cpu", max_context=512)

data = {}
for t in TICKS:
    d = yf.download(t, start="2023-06-01", interval="1d", progress=False, auto_adjust=True)
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d.dropna().rename(columns=str.lower)[["open","high","low","close","volume"]]
    d["amount"] = d["close"] * d["volume"]; data[t] = d
cal = data["SPY"].index
dates = [x for x in cal[(cal >= "2025-10-01") & (cal <= "2026-10-23")]][::H]
rows = []
for k, dt in enumerate(dates):
    for t, d in data.items():
        i = d.index.searchsorted(dt)
        if i < LOOK or i + H >= len(d) or d.index[i] != dt: continue
        x = d.iloc[i - LOOK + 1:i + 1]; fut = d.iloc[i + 1:i + 1 + H]
        try:
            p = pred.predict(df=x.reset_index(drop=True), x_timestamp=pd.Series(x.index),
                             y_timestamp=pd.Series(fut.index), pred_len=H, T=1.0, top_p=0.9, sample_count=3, verbose=False)
        except TypeError:
            p = pred.predict(df=x.reset_index(drop=True), x_timestamp=pd.Series(x.index),
                             y_timestamp=pd.Series(fut.index), pred_len=H, T=1.0, top_p=0.9, sample_count=3)
        c0 = x["close"].iat[-1]
        rows.append(dict(date=dt, t=t, f_ret=p["close"].iat[-1] / c0 - 1, a_ret=fut["close"].iat[-1] / c0 - 1,
                         f_rng=(p["high"].max() - p["low"].min()) / c0, a_rng=(fut["high"].max() - fut["low"].min()) / c0))
    print("week", k + 1, "/", len(dates), dt.date(), flush=True)

R = pd.DataFrame(rows); out = {"forecasts": len(R), "weeks": R.date.nunique()}
out["A_direction_hit_pct"] = round((np.sign(R.f_ret) == np.sign(R.a_ret)).mean() * 100, 1)
out["A_up_share_pct"] = round((R.a_ret > 0).mean() * 100, 1)
out["A_corr_forecast_vs_actual_ret"] = round(R[["f_ret","a_ret"]].corr().iat[0,1], 3)
out["D_vol_corr"] = round(R[["f_rng","a_rng"]].corr().iat[0,1], 3)
wk_b, wk_ew, wk_ls = [], [], []
for dt, g in R.groupby("date"):
    g = g.sort_values("f_ret"); top, bot = g.tail(5), g.head(5)
    wk_b.append(top.a_ret.mean() - 2 * COST); wk_ew.append(g.a_ret.mean() - 2 * COST)
    wk_ls.append(top.a_ret.mean() - bot.a_ret.mean() - 4 * COST)
wk_b, wk_ew, wk_ls = map(np.array, (wk_b, wk_ew, wk_ls))
rng = np.random.default_rng(0); rand_tot = []
for s in range(200):
    rw = [g.sample(5, random_state=int(rng.integers(1e9))).a_ret.mean() - 2 * COST for _, g in R.groupby("date")]
    rand_tot.append(np.prod(1 + np.array(rw)) - 1)
tot = lambda w: round((np.prod(1 + w) - 1) * 100, 1)
out["B_kronos_top5_total_pct"] = tot(wk_b); out["equal_weight_total_pct"] = tot(wk_ew)
out["random5_median_pct"] = round(np.median(rand_tot) * 100, 1); out["random5_p95_pct"] = round(np.percentile(rand_tot, 95) * 100, 1)
out["B_beats_random_pct"] = round(np.mean(np.array(rand_tot) < np.prod(1 + wk_b) - 1) * 100, 1)
out["B_pass"] = bool(tot(wk_b) > tot(wk_ew) and out["B_beats_random_pct"] >= 95)
out["C_longshort_mean_weekly_pct"] = round(wk_ls.mean() * 100, 3)
out["C_t"] = round(wk_ls.mean() / (wk_ls.std(ddof=1) / np.sqrt(len(wk_ls))), 2)
out["C_total_pct"] = tot(wk_ls); out["C_pass"] = bool(out["C_t"] > 2)
print(json.dumps(out, indent=1))
os.makedirs("results/kronos", exist_ok=True)
R.to_csv("results/kronos/forecasts.csv", index=False); json.dump(out, open("results/kronos/summary.json", "w"), indent=1)
