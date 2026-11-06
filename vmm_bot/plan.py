"""VMM v1 order planner (locked plan: claude/vm-momentum-plan-v1.md in the Stock project).

Reads a broker snapshot of the dedicated VMM TFSA, computes signals from daily closes
up to the last completed session, and writes the orders to place at today's session.

Rules (VMM v1):
  Universe: TSX (.TO) common stocks, $1-100, 20d median dollar volume >= $300k, >= 1y history.
  Buy: 12m return in top 10% of universe, close > 200d SMA, XIU > its 200d SMA, free slot.
  Sell: close < 200d SMA, or 12m return drops out of top 40%.
  Slots: up to 20, equal size, whole shares, strongest 12m first.
  Monthly (first run of a new month): momentum share = vol(XIU)/vol(momentum), capped at 100%,
     rest in XIU. 50/50 until 60 days of momentum history exist.
  Small account: momentum budget < $2,000 -> no new momentum buys; slots 5..20 at ~$400 each.
Usage: python plan.py snapshot.json orders.json
"""
import json, math, os, re, sys, datetime as dt
import numpy as np, pandas as pd, yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import stock_filter as sf  # noqa: E402

STATE = os.path.join(ROOT, "results", "vmm_bot", "state.json")
XIU = "XIU.TO"
SUFFIX = os.environ.get("BROKER_SYMBOL_SUFFIX", ".TO")  # how the broker names TSX tickers
FUND = re.compile(r"Fund|Pool|Portfolio|Class\b|Alternative|Bond|Yield|Savings|Target 20|Split|"
                  r"Income Trust|Private|Mint|Trust Units|Corton|Arbitrage|Long Short|Market Neutral", re.I)
SLOT_DOLLARS, MIN_MOM, MAX_SLOTS, MIN_SLOTS = 400.0, 2000.0, 20, 5
BUY_LIMIT_UP, SELL_LIMIT_DN = 1.01, 0.97
ADOPT = {t.strip().upper() for t in os.environ.get("VMM_ADOPT", "LCFS.TO,MSA.TO,TWM.TO").split(",") if t.strip()}  # manual holdings handed to the bot
MAX_ORDER = float(os.environ.get("MAX_ORDER_CAD", "800"))
BUDGET = float(os.environ.get("VMM_BUDGET_CAD", "0") or 0)  # max dollars the bot may manage (0 = whole account)
EXCLUDE = {t.strip().upper() for t in os.environ.get("VMM_EXCLUDE", "LCFS.TO,TWM.TO").split(",") if t.strip()}  # e.g. takeover targets
PROTECTED = {t.strip().upper() for t in os.environ.get("VMM_PROTECTED", "VEQT.TO,AIQ.TO,SPCX.TO,SPCX").split(",") if t.strip()}


def to_broker(t):
    return t[:-3] + SUFFIX if t.endswith(".TO") else t


def from_broker(s):
    s = (s or "").upper()
    if s.endswith(".TO"):
        return s
    if s.endswith(SUFFIX.upper()) and SUFFIX:
        s = s[: -len(SUFFIX)]
    return s + ".TO"


def universe():
    tick = json.load(open(os.path.join(ROOT, "universe_tickers.json")))
    out = []
    for t in tick:
        if not t.endswith(".TO") or any(k in t for k in ("-DB", "-PF", "-WT")):
            continue
        if not sf.is_stock(t):
            continue
        name = sf.company(t) or ""
        if not name or FUND.search(name):
            continue
        out.append(t)
    return out


def prices(tickers):
    frames = []
    for i in range(0, len(tickers), 100):
        d = yf.download(tickers[i:i + 100], period="2y", interval="1d", auto_adjust=True,
                        progress=False, group_by="ticker", threads=True)
        frames.append(d)
    D = pd.concat(frames, axis=1)
    lv = D.columns.get_level_values(0).unique()
    C = pd.DataFrame({t: D[t]["Close"] for t in lv})
    V = pd.DataFrame({t: D[t]["Volume"] for t in lv})
    C = C.dropna(how="all")
    # use completed sessions only
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()
    C = C[C.index.date < today]
    return C, V.reindex(C.index)


def main(snap_path, out_path):
    snap = json.load(open(snap_path))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    actual = {}
    for p in snap["positions"]:
        if p.get("symbol") and (p.get("units") or 0) > 0:
            actual[from_broker(p["symbol"])] = int(math.floor(p["units"]))
    # Ledger: the bot only manages shares IT bought. Everything else in the account is ignored.
    ledger = {t: int(u) for t, u in state.get("ledger", {}).items()}
    for t, pend in state.get("pending", {}).items():  # credit fills from last run's buys
        filled = max(0, actual.get(t, 0) - int(pend["pre_units"]))
        ledger[t] = ledger.get(t, 0) + min(filled, int(pend["units"]))
    ledger = {t: min(u, actual.get(t, 0)) for t, u in ledger.items()}  # sells/fills reconcile
    for t in ADOPT:  # hand these manual holdings to the bot (sell rules apply)
        if actual.get(t, 0) > 0:
            ledger[t] = actual[t]
    ledger = {t: u for t, u in ledger.items() if u > 0 and t not in PROTECTED}
    print("account holdings:", actual, "| bot manages:", ledger)
    held = ledger
    tick = sorted(set(universe()) | set(held) | {XIU})
    C, V = prices(tick)
    last = C.index[-1]
    close = C.iloc[-1]
    sma = C.rolling(200).mean().iloc[-1]
    xiu_ok = bool(close[XIU] > sma[XIU])
    r12 = C.iloc[-1] / C.iloc[-253] - 1
    dv = (C * V).rolling(20).median().iloc[-1]
    hist = C.notna().sum()
    elig = close.between(1, 100) & (dv >= 300_000) & (hist >= 253)
    elig[XIU] = False
    r = r12[elig].dropna()
    top10, top40 = r.quantile(0.9), r.quantile(0.6)
    ranked = r[(r >= top10) & (close[r.index] > sma[r.index])].sort_values(ascending=False)

    mom_held = {t: u for t, u in held.items() if t != XIU}
    value = {t: u * float(close.get(t, np.nan)) for t, u in held.items()}
    held_val = sum(v for v in value.values() if v == v)
    cash_avail = float(snap["cash_cad"])
    if BUDGET > 0:
        cash_avail = max(0.0, min(cash_avail, BUDGET - held_val))
    equity = held_val + cash_avail

    orders, notes, sells = [], [], set()
    # 1) sell rules for momentum holdings
    for t, u in mom_held.items():
        c, s, rr = close.get(t), sma.get(t), r12.get(t)
        if c is None or not np.isfinite(c):
            notes.append(f"{t}: no price data, left alone"); continue
        why = []
        if np.isfinite(s) and c < s: why.append(f"close {c:.2f} < 200d {s:.2f}")
        if np.isfinite(rr) and rr < top40: why.append(f"12m {rr*100:.0f}% < top-40% cut {top40*100:.0f}%")
        if why:
            sells.add(t)
            orders.append({"action": "SELL", "ticker": t, "broker_symbol": to_broker(t), "units": u,
                           "limit": round(c * SELL_LIMIT_DN, 2), "reason": "; ".join(why)})

    # 2) monthly split
    month = last.strftime("%Y-%m")
    rebalance = state.get("last_rebalance_month") != month
    share = state.get("mom_share", 0.5)
    if rebalance:
        picks = list(ranked.index[:MAX_SLOTS])
        rets = C[picks].pct_change().iloc[-60:].mean(axis=1) if picks else pd.Series(dtype=float)
        xr = C[XIU].pct_change().iloc[-60:]
        if len(picks) and rets.std() > 0:
            share = float(min(1.0, xr.std() / rets.std()))
        notes.append(f"Monthly split {month}: momentum share {share*100:.0f}%")
    mom_budget = share * equity
    xiu_target = (1 - share) * equity

    # 3) XIU leg: full rebalance (buy or sell) at month start; on other days only top up
    #    with spare cash when XIU is $100+ under target (e.g. after a mid-month deposit)
    if rebalance or (xiu_target - value.get(XIU, 0.0) >= 100 and cash_avail >= 100):
        xiu_val = value.get(XIU, 0.0)
        diff = xiu_target - xiu_val
        px = float(close[XIU])
        if abs(diff) >= 100:
            u = int(abs(diff) // px)
            act = "BUY" if diff > 0 else "SELL"
            if act == "SELL" and not rebalance:
                u = 0
            if act == "BUY":
                lim0 = round(px * BUY_LIMIT_UP, 2)
                u = min(u, int(cash_avail // lim0), int(MAX_ORDER // lim0))  # cash and per-order cap
            if u > 0:
                orders.append({"action": act, "ticker": XIU, "broker_symbol": to_broker(XIU), "units": u,
                               "limit": round(px * (BUY_LIMIT_UP if act == "BUY" else SELL_LIMIT_DN), 2),
                               "reason": f"monthly split: XIU target ${xiu_target:,.0f}"})

    # 4) momentum buys
    keep = [t for t in mom_held if t not in sells]
    if not xiu_ok:
        notes.append("XIU below its 200-day: no new momentum buys")
    elif mom_budget < MIN_MOM:
        notes.append(f"Momentum budget ${mom_budget:,.0f} < ${MIN_MOM:,.0f}: no new momentum buys (small-account rule)")
    else:
        slots = int(min(MAX_SLOTS, max(MIN_SLOTS, mom_budget // SLOT_DOLLARS)))
        per = mom_budget / slots
        cash = cash_avail
        cash -= sum(o["units"] * o["limit"] for o in orders if o["action"] == "BUY")
        free = slots - len(keep)
        for t in ranked.index:
            if free <= 0: break
            if t in keep or t in sells or t in EXCLUDE: continue
            if actual.get(t, 0) > 0:  # already held manually in this account: don't double up
                notes.append(f"{t}: skipped, already held outside the bot"); continue
            px = float(close[t]); lim = round(px * BUY_LIMIT_UP, 2)
            u = int(min(per, cash, MAX_ORDER) // lim)
            if u < 1: notes.append(f"{t}: not enough cash for a slot"); break
            orders.append({"action": "BUY", "ticker": t, "broker_symbol": to_broker(t), "units": u, "limit": lim,
                           "reason": f"rank {list(ranked.index).index(t)+1}, 12m {r12[t]*100:.0f}%, sell line {sma[t]:.2f}"})
            cash -= u * lim; free -= 1

    watch = [{"ticker": t, "close": round(float(close[t]), 2), "sell_line": round(float(sma[t]), 2),
              "pct_above": round((float(close[t]) / float(sma[t]) - 1) * 100, 1), "r12_pct": round(float(r12[t]) * 100)}
             for t in mom_held if t in close and np.isfinite(close[t])]
    plan = {"signal_date": str(last.date()), "equity_cad": round(equity, 2), "cash_cad": snap["cash_cad"],
            "xiu_ok": xiu_ok, "mom_share": round(share, 3), "top40_cut_pct": round(float(top40) * 100, 1),
            "orders": orders, "holdings": watch, "notes": notes,
            "budget_cad": BUDGET, "bot_ledger": ledger,
            "new_state": {"last_rebalance_month": month if rebalance else state.get("last_rebalance_month"),
                          "mom_share": share, "ledger": ledger,
                          "pending": {o["ticker"]: {"units": o["units"], "pre_units": actual.get(o["ticker"], 0)}
                                      for o in orders if o["action"] == "BUY"}}}
    bad = [o for o in orders if o["ticker"] in PROTECTED or o["broker_symbol"].upper() in PROTECTED]
    if bad:
        raise SystemExit(f"refusing: protected ticker in orders {bad}")
    json.dump(plan, open(out_path, "w"), indent=2)
    print(json.dumps({k: plan[k] for k in ("signal_date", "equity_cad", "xiu_ok", "mom_share")}))
    for o in orders: print(o["action"], o["units"], o["ticker"], "@", o["limit"], "-", o["reason"])
    for n in notes: print("note:", n)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
