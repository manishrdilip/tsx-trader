"""Batch 7C + 7D-US: US small/mid momentum and gap drift on EODHD US incl. delisted (memory-light).
Usage: python exp14_us.py <us_dir with px/*.csv and list_US_*.json> <out> [eval]"""
import json, os, sys, types
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import run, stats

SRC, OUT = sys.argv[1:3]; EVAL = len(sys.argv) > 3; os.makedirs(OUT, exist_ok=True)
cache = os.path.join(OUT, "us_panel.npz")
if not os.path.exists(cache):
    spy = pd.read_csv(os.path.join(SRC, "px", "SPY.csv"), index_col=0, parse_dates=True)
    days = spy.index[spy.index >= "1999-01-01"]
    cols, C, O, V = [], [], [], []
    drop = {"short": 0, "never_liquid": 0, "spike": 0}
    for f in sorted(os.listdir(os.path.join(SRC, "px"))):
        t = f[:-4]
        if t in ("IWM", "QQQ", "MDY", "IJR"): continue
        d = pd.read_csv(os.path.join(SRC, "px", f), index_col=0, parse_dates=True)
        d = d[~d.index.duplicated()]
        d = d[(d.Close > 0) & d.Adjusted_close.notna()]
        d = d[d.index >= "1999-01-01"]
        if len(d) < 300: drop["short"] += 1; continue
        dv = (d.Close * d.Volume).rolling(20).median()
        if t != "SPY" and not ((dv >= 2e6) & (d.Close >= 5)).any(): drop["never_liquid"] += 1; continue
        a = d.Adjusted_close; r = a.pct_change()
        bad = any((a.iloc[i + 1:i + 6] < a.iloc[i - 1] * 1.5).any() for i in np.where(r.values > 1.5)[0])
        if bad and t != "SPY": drop["spike"] += 1; continue
        ratio = a / d.Close
        d = d.reindex(days)
        cols.append(t); C.append(d.Adjusted_close.values); V.append((d.Volume * d.Close / a.reindex(days)).values)
        O.append((d.Open * ratio.reindex(days)).values)
    C = np.array(C, dtype="float32").T; O = np.array(O, dtype="float32").T; V = np.array(V, dtype="float32").T
    np.savez_compressed(cache, days=days.values.astype("datetime64[D]"), tk=np.array(cols), C=C, O=O, V=V)
    json.dump({"tickers": len(cols), "dropped": drop, "first": str(days[0].date()), "last": str(days[-1].date())},
              open(os.path.join(OUT, "us_manifest.json"), "w"), indent=1)
z = np.load(cache, allow_pickle=True)
dates = pd.DatetimeIndex(z["days"]); tk = list(z["tk"])
Cdf = pd.DataFrame(z["C"], dates, tk); Odf = pd.DataFrame(z["O"], dates, tk)
print(json.load(open(os.path.join(OUT, "us_manifest.json"))), flush=True)
# signals, computed in column chunks to stay within memory (float32)
Cv = z["C"]; Ov = z["O"]; Vv = z["V"]; n, m = Cv.shape
s200v = np.full((n, m), np.nan, "float32"); r12v = np.full((n, m), np.nan, "float32"); dvv = np.full((n, m), np.nan, "float32")
histv = np.zeros((n, m), "int32"); v50 = np.full((n, m), np.nan, "float32")
for j0 in range(0, m, 1500):
    sl = slice(j0, min(m, j0 + 1500))
    c = pd.DataFrame(Cv[:, sl]); v = pd.DataFrame(Vv[:, sl])
    s200v[:, sl] = c.rolling(200).mean().values; r12v[:, sl] = (c / c.shift(252) - 1).values
    dvv[:, sl] = (c * v).rolling(20).median().values; histv[:, sl] = c.notna().cumsum().values
    v50[:, sl] = v.rolling(50).mean().shift(1).values
    del c, v
above = Cv > s200v
base = (Cv >= 5) & (Cv <= 500) & (histv >= 253) & (dvv >= 2e6)
dvq = np.where(base, dvv, np.nan)
lo = np.nanquantile(dvq, 0.2, axis=1); hi = np.nanquantile(dvq, 0.8, axis=1); del dvq
elig = base & (dvv >= lo[:, None]) & (dvv <= hi[:, None]); del base, histv
elig[:, tk.index("SPY")] = False
rq = np.where(elig, r12v, np.nan)
q90 = np.nanquantile(rq, 0.9, axis=1); q60 = np.nanquantile(rq, 0.6, axis=1); del rq
spy = Cdf["SPY"].astype(float); spy_ok = (spy > spy.rolling(200).mean()).values
lv = Cdf.apply(lambda s: s.last_valid_index())
last_i = np.array([dates.get_loc(d) if d is not None else -1 for d in lv])
class S200:
    values = s200v
s200 = S200
P = types.SimpleNamespace(dates=dates, tk=tk, C=Cdf, O=Odf, last_i=last_i, xiu=spy)
cv = Cv; tka = np.array(tk); col = {t: k for k, t in enumerate(tk)}
def rank(i, score, mask):
    s = np.where(mask & np.isfinite(score), score, np.nan); ok = np.isfinite(s)
    if not ok.any(): return None
    idx = np.where(ok)[0][np.argsort(-s[ok])]; return pd.Series(s[idx], tka[idx])
def vmm_us():
    def scores(i):
        if not spy_ok[i]: return None
        return rank(i, r12v[i], elig[i] & above[i] & (r12v[i] >= q90[i]))
    def exit_(i, t, p):
        k = col[t]
        if cv[i, k] < s200.values[i, k]: return "below 200d"
        if np.isfinite(r12v[i, k]) and r12v[i, k] < q60[i]: return "out of top 40%"
    return dict(scores=scores, exit=exit_, slots=lambda eq: int(min(20, max(5, eq // 400))), max_hold=20,
                buy_day=lambda i: True, trail=28, never_rebuy_trail=True)
prevc = np.vstack([np.full((1, m), np.nan, "float32"), Cv[:-1]])
gsig = (Ov >= prevc * 1.05) & (Vv >= 3 * v50) & (Cv >= Ov) & above
gap = Ov / prevc - 1
def gap_us():
    return dict(scores=lambda i: rank(i, gap[i], elig[i] & gsig[i]), exit=lambda i, t, p: "40 days" if i - p["ent"] >= 40 else None,
                slots=lambda eq: 10, max_hold=10, buy_day=lambda i: True, trail=20)
PER = {"dev": ("2000-01-03", "2022-12-30"), "eval": ("2023-01-03", str(dates[-1].date()))}
ph = "eval" if EVAL else "dev"; a, b = PER[ph]
iwm = pd.read_csv(os.path.join(SRC, "px", "IWM.csv"), index_col=0, parse_dates=True)["Adjusted_close"]
rows = []
for nm, mk in (("C_us_smallmid_vmm", vmm_us), ("D_us_gap_drift", gap_us)):
    eq, tr = run(P, mk(), a, b, cost=0.005); s = stats(eq, tr); s.update(name=nm, phase=ph); rows.append(s)
    print(nm, ph, "CAGR", s["cagr"], "DD", s["max_dd"], "trades", s["trades"], "win", s["win_rate"], flush=True)
for nm, ser in (("IWM", iwm), ("SPY", spy)):
    x = ser.loc[a:b].dropna(); s = stats(5000 * x / x.iloc[0], []); s.update(name=nm, phase=ph); rows.append(s)
    print(nm, ph, "CAGR", s["cagr"], "DD", s["max_dd"])
pd.DataFrame(rows).to_csv(os.path.join(OUT, f"us_{ph}.csv"), index=False)
