"""India NSE VMM rules: pure functions, no broker or network calls.

Rules (matches the tested India setup in lab/india_vmm_atr.py: 10 slots, equal weight):
  Universe: NSE .NS stocks (no indices, no ETFs), price Rs 60-6000,
            20-day median traded value >= Rs 50 lakh, >= 253 sessions of history.
  Market filter: NIFTYBEES.NS (or ^NSEI) close above its 200-day average.
            If it is not, the bot places no new buys. Sells still run.
  Buy:  12-month return in the top 10% of the universe AND close above the 200-day average.
        Strongest 12-month return first, into free slots.
  Sell: close below the 200-day average, OR 12-month return below the universe's top-40% cut.
  Sizing: slots = clamp(equity // MIN_SLOT_INR, MIN_SLOTS, MAX_SLOTS); equal size per slot.
          Every order is capped at MAX_ORDER_PCT (15%) of equity.
  Orders: LIMIT, CNC (delivery), DAY validity.
          Buy limit  = last close x 1.01, rounded UP to the tick.
          Sell limit = last close x 0.97, rounded DOWN to the tick.
  Ledger: the bot only sells shares it bought (or that were adopted). Other holdings are never touched.
"""
import math
import os

import numpy as np
import pandas as pd


def _env_float(name, default):
    v = os.environ.get(name, "")
    return float(v) if v.strip() else float(default)


MARKET = os.environ.get("INDIA_VMM_MARKET", "NIFTYBEES.NS")
MARKET_FALLBACK = "^NSEI"
MIN_PRICE = 60.0
MAX_PRICE = 6000.0
MIN_MEDIAN_TRADED = 5_000_000.0  # Rs, 20-day median of close x volume
MIN_HISTORY = 253  # sessions
TOP_FRAC = 0.10
KEEP_FRAC = 0.40
MIN_SLOTS = 10
MAX_SLOTS = 20
MIN_SLOT_INR = _env_float("INDIA_VMM_MIN_SLOT_INR", 400)  # below this per slot, use fewer slots (floor MIN_SLOTS)
MAX_ORDER_PCT = _env_float("INDIA_VMM_MAX_ORDER_PCT", 0.15)
MAX_ORDERS_PER_RUN = int(_env_float("INDIA_VMM_MAX_ORDERS", 25))
BUY_UP = 1.01
SELL_DN = 0.97
TICK = 0.05
PROTECTED = {MARKET, MARKET_FALLBACK} | {
    t.strip().upper() for t in os.environ.get("INDIA_VMM_PROTECTED", "").split(",") if t.strip()
}


def is_candidate(sym):
    """True for plain NSE stock tickers. Drops indices, ETFs and sovereign gold/liquid funds by name."""
    s = str(sym).upper()
    if not s.endswith(".NS") or s.startswith("^"):
        return False
    base = s[:-3]
    if base.endswith("BEES") or "ETF" in base or base.startswith("SGB") or "LIQUID" in base:
        return False
    return True


def tick_up(x):
    return round(math.ceil(round(x / TICK, 6)) * TICK, 2)


def tick_down(x):
    return round(math.floor(round(x / TICK, 6)) * TICK, 2)


def signals(closes, volumes):
    """Compute the day's signals.

    closes, volumes: DataFrames indexed by session date, one column per .NS symbol.
    Must contain completed sessions only (the caller trims today's partial session).
    """
    closes = closes.sort_index()
    volumes = volumes.reindex(index=closes.index, columns=closes.columns)
    close = closes.iloc[-1]
    sma200 = closes.rolling(200, min_periods=200).mean().iloc[-1]
    if len(closes) >= MIN_HISTORY:
        r12 = closes.iloc[-1] / closes.iloc[-253] - 1  # 252 sessions back, as in the Canada bot
    else:
        r12 = pd.Series(np.nan, index=closes.columns)
    dv20 = (closes * volumes).rolling(20, min_periods=20).median().iloc[-1]
    hist = closes.notna().sum()
    cand = pd.Series([is_candidate(s) for s in closes.columns], index=closes.columns, dtype=bool)
    elig = (cand & close.between(MIN_PRICE, MAX_PRICE) & (dv20 >= MIN_MEDIAN_TRADED)
            & (hist >= MIN_HISTORY) & r12.notna())

    mkt = next((m for m in (MARKET, MARKET_FALLBACK)
                if m in closes.columns and closes[m].notna().sum() >= 200), None)
    market_ok, mkt_close, mkt_sma = False, np.nan, np.nan
    if mkt is not None:
        mkt_close = float(closes[mkt].iloc[-1])
        mkt_sma = float(closes[mkt].rolling(200, min_periods=200).mean().iloc[-1])
        market_ok = bool(mkt_close > mkt_sma)

    r_el = r12[elig]
    if len(r_el):
        top_cut = float(r_el.quantile(1 - TOP_FRAC))
        keep_cut = float(r_el.quantile(1 - KEEP_FRAC))
        ok = r_el[(r_el >= top_cut) & (close[r_el.index] > sma200[r_el.index])]
        ranked = ok.sort_values(ascending=False).index.tolist()
    else:
        top_cut = keep_cut = np.nan
        ranked = []

    return {
        "date": closes.index[-1],
        "close": close,
        "sma200": sma200,
        "r12": r12,
        "eligible": elig,
        "n_eligible": int(elig.sum()),
        "ranked": ranked,
        "top_cut": top_cut,
        "keep_cut": keep_cut,
        "market": mkt,
        "market_close": mkt_close,
        "market_sma": mkt_sma,
        "market_ok": market_ok,
    }


def _order(action, sym, qty, limit, reason):
    return {
        "action": action,
        "ticker": sym,
        "symbol": sym[:-3] if sym.endswith(".NS") else sym,
        "qty": int(qty),
        "limit": float(limit),
        "value": round(int(qty) * float(limit), 2),
        "reason": reason,
    }


def plan(sig, ledger, equity, cash, open_syms=frozenset(), protected=frozenset(PROTECTED)):
    """Return (orders, notes).

    ledger:    {symbol: qty} shares the bot owns.
    equity:    money the bot manages (ledger value + cash, after any budget cap).
    cash:      cash available for new buys (sell proceeds are not counted: CNC sells settle T+1).
    open_syms: symbols that already have a live order today (duplicate guard).
    """
    orders, notes = [], []
    close, sma, r12 = sig["close"], sig["sma200"], sig["r12"]
    keep_cut = sig["keep_cut"]
    sells = set()

    for sym, qty in sorted(ledger.items()):
        if qty <= 0:
            continue
        if sym in protected:
            notes.append(f"{sym}: protected, never traded")
            continue
        c = close.get(sym, np.nan)
        if not np.isfinite(c):
            notes.append(f"{sym}: no price today, left alone")
            continue
        s = sma.get(sym, np.nan)
        r = r12.get(sym, np.nan)
        why = []
        if np.isfinite(s) and c < s:
            why.append(f"close {c:.2f} < 200d {s:.2f}")
        if np.isfinite(r) and np.isfinite(keep_cut) and r < keep_cut:
            why.append(f"12m {r * 100:.0f}% < top-40% cut {keep_cut * 100:.0f}%")
        if not why:
            continue
        if sym in open_syms:
            notes.append(f"{sym}: sell signal, but an order is already open today (no duplicate)")
            continue
        sells.add(sym)
        orders.append(_order("SELL", sym, qty, tick_down(c * SELL_DN), "; ".join(why)))

    if not sig["market_ok"]:
        notes.append(f"market filter OFF ({sig['market']} below 200d): no new buys")
        return orders[:MAX_ORDERS_PER_RUN], notes

    held_after = {s for s, q in ledger.items() if q > 0 and s not in sells}
    slots = int(min(MAX_SLOTS, max(MIN_SLOTS, equity // MIN_SLOT_INR)))
    open_slots = max(0, slots - len(held_after))
    slot_value = min(equity / slots, MAX_ORDER_PCT * equity) if slots and equity > 0 else 0.0
    cash_left = float(cash)

    for sym in sig["ranked"]:
        if open_slots <= 0 or len(orders) >= MAX_ORDERS_PER_RUN:
            break
        if sym in protected:
            continue
        if sym in held_after or sym in sells or sym in ledger:
            continue  # already held by the bot: no add-ons
        if sym in open_syms:
            notes.append(f"{sym}: buy skipped, an order is already open today (no duplicate)")
            continue
        px = float(close[sym])
        limit = tick_up(px * BUY_UP)
        qty = int(math.floor(min(slot_value, cash_left) / limit)) if limit > 0 else 0
        if qty < 1:
            notes.append(f"{sym}: Rs {limit:.2f} too expensive for slot Rs {slot_value:.0f} (or cash), skipped")
            continue
        orders.append(_order("BUY", sym, qty, limit,
                             f"12m {float(r12[sym]) * 100:.0f}% (top 10%), close above 200d"))
        cash_left -= qty * limit
        open_slots -= 1

    notes.insert(0, f"slots {slots}, slot value Rs {slot_value:.0f}, cap {MAX_ORDER_PCT * 100:.0f}% = "
                    f"Rs {MAX_ORDER_PCT * equity:.0f}")
    return orders[:MAX_ORDERS_PER_RUN], notes
