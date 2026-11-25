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
Cdf = pd.DataFrame(z["C"], dates, tk); Odf = pd.DataFrame(z["O"], dates, tk); Vdf = pd.DataFrame(z["V"], dates, tk)
print(json.load(open(os.path.join(OUT, "us_manifest.json"))), flush=True)
# signals (float32 where possible)
s200 = Cdf.rolling(200).mean(); above = (Cdf > s200).values
r12 = (Cdf / Cdf.shift(252) - 1)
dv = (Cdf * Vdf).rolling(20).median()
hist = Cdf.notna().cumsum()
base = (Cdf >= 5) & (Cdf <= 500) & (hist >= 253) & (dv >= 2e6)
dvq = dv.where(base)
lo, hi = dvq.quantile(0.2, axis=1), dvq.quantile(0.8, axis=1)
elig = (base & dv.ge(lo, axis=0) & dv.le(hi, axis=0)).values
elig[:, tk.index("SPY")] = False
r12v = r12.values
q90 = np.nanquantile(np.where(elig, r12v, np.nan), 0.9, axis=1); q60 = np.nanquantile(np.where(elig, r12v, np.nan), 0.6, axis=1)
spy = Cdf["SPY"]; spy_ok = (spy > spy.rolling(200).mean()).values
lv = Cdf.apply(lambda s: s.last_valid_index())
last_i = np.array([dates.get_loc(d) if d is not None else -1 for d in lv])
P = types.SimpleNamespace(dates=dates, tk=tk, C=Cdf, O=Odf, last_i=last_i, xiu=spy)
cv = Cdf.values; tka = np.array(tk); col = {t: k for k, t in enumerate(tk)}
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
gsig = ((Odf >= Cdf.shift(1) * 1.05) & (Vdf >= 3 * Vdf.rolling(50).mean().shift(1)) & (Cdf >= Odf)).values & above
gap = (Odf / Cdf.shift(1) - 1).values
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
