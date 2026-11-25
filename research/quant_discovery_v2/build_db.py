"""Build the clean TSX panel from EODHD per-ticker CSVs (rules in PROTOCOL.md).
Usage: python build_db.py <eodhd_dir> <out_dir>
  eodhd_dir has list_TO_0.json, list_TO_1.json and px/TO_<CODE>.csv
Writes panel.npz (dates, tickers, adj close/open, raw close, volume) and manifest.json."""
import json, os, re, sys
import numpy as np, pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
FUND = re.compile(r"Fund|Pool|Portfolio|Class\b|Alternative|Bond|Yield|Savings|Target 20|Split|Income Trust|"
                  r"Private|Mint|Trust Units|Corton|Arbitrage|Long Short|Market Neutral|\bETF\b|BetaPro|\bCDR\b|"
                  r"Bullion|Physical|Banc Corp|Money Market|Cash Management|Covered Call|Index", re.I)
ETFS = {"XIU", "XIC", "VEQT", "VFV", "XEG", "XFN", "XIT", "XMA", "ZUT", "XRE", "XST", "XHC", "XGD", "XUT", "ZIN"}

meta = {}
for dl in (0, 1):
    for x in json.load(open(os.path.join(SRC, f"list_TO_{dl}.json"))):
        meta[x["Code"]] = {"type": x["Type"], "name": x.get("Name") or "", "delisted": dl}

C, O, R, V = {}, {}, {}, {}
log = {"kept": 0, "fund_name": 0, "bad_adj": 0, "spike": 0, "short": 0, "etf": 0}
for f in sorted(os.listdir(os.path.join(SRC, "px"))):
    if not f.startswith("TO_"):
        continue
    code = f[3:-4]
    m = meta.get(code, {"type": "?", "name": "", "delisted": 0})
    is_etf = code in ETFS
    if not is_etf:
        if m["type"] != "Common Stock" or any(k in code for k in ("-DB", "-PR", "-WT", "-UN", "-P")):
            continue
        if FUND.search(m["name"]):
            log["fund_name"] += 1; continue
    d = pd.read_csv(os.path.join(SRC, "px", f))
    d = d[d["Close"] > 0].dropna(subset=["Adjusted_close"])
    if len(d) < 60:
        log["short"] += 1; continue
    d["Date"] = pd.to_datetime(d["Date"]); d = d.drop_duplicates("Date").set_index("Date").sort_index()
    d = d[d.index >= "2006-01-01"]
    if len(d) < 60:
        log["short"] += 1; continue
    ratio = d["Adjusted_close"] / d["Close"]
    # amendment (before any results): adjustment check only on delisted names and only from 2006, because
    # 30 years of dividends/splits legitimately move the ratio >3x for healthy listed stocks (604 were dropped)
    if not is_etf and m["delisted"] == 1 and ratio.max() / max(ratio.min(), 1e-12) > 3:
        log["bad_adj"] += 1; continue
    a = d["Adjusted_close"]
    r = a.pct_change()
    # +150% day reversed (back below 1.5x the pre-spike level) within 5 days -> bad print
    spike = False
    for i in np.where(r.values > 1.5)[0]:
        pre = a.iloc[i - 1]
        if (a.iloc[i + 1:i + 6] < pre * 1.5).any():
            spike = True; break
    if spike and not is_etf:
        log["spike"] += 1; continue
    key = code + ".TO"
    C[key] = a; R[key] = d["Close"]; V[key] = d["Volume"]
    O[key] = d["Open"].where(d["Open"] > 0, d["Close"]) * ratio
    log["etf" if is_etf else "kept"] += 1

C = pd.DataFrame(C)
xiu_days = C["XIU.TO"].dropna().index
C = C.reindex(xiu_days)  # real TSX trading days only (drops EODHD weekend/holiday rows)
C = C[C.index >= "2007-01-01"]
idx = C.index
O = pd.DataFrame(O).reindex(idx); R = pd.DataFrame(R).reindex(idx); V = pd.DataFrame(V).reindex(idx)
np.savez_compressed(os.path.join(OUT, "panel.npz"), dates=idx.values.astype("datetime64[D]"),
                    tickers=np.array(C.columns), close=C.values.astype("float32"), open=O.values.astype("float32"),
                    raw=R.values.astype("float32"), vol=V.values.astype("float32"))
delisted = [t for t in C.columns if meta.get(t[:-3], {}).get("delisted") == 1]
last = C.apply(lambda s: s.last_valid_index())
man = {"built_from": "EODHD eod TO, downloaded 25 Nov 2026", "days": len(idx), "first": str(idx[0].date()),
       "last": str(idx[-1].date()), "tickers": C.shape[1], "delisted_kept": len(delisted), "filter_log": log,
       "delisted_by_last_year": pd.Series([last[t].year for t in delisted]).value_counts().sort_index().to_dict()}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1, default=str)
print(json.dumps(man, indent=1, default=str))
