"""India VMM runner.

Dry run is the default: it prints and saves the planned orders, places nothing.
Real orders need BOTH the flag --live AND the environment variable TRADING_ENABLED=true.

Examples
  Offline plan from the local price file (no broker, no network):
    python india_vmm/run.py --parquet /path/to/prices.parquet --cash 2000
  Plan against the real Zerodha account (dry run, nothing placed):
    python india_vmm/run.py
  Place the orders (only after review and approval):
    TRADING_ENABLED=true python india_vmm/run.py --live
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules  # noqa: E402
import data  # noqa: E402

STATE = os.path.join(HERE, "results", "state.json")
LAST_PLAN = os.path.join(HERE, "results", "last_plan.json")


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"ledger": {}, "pending": {}}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def reconcile(state, actual, open_syms):
    """Bot-owned ledger, reconciled to the real account.

    1. Credit buy fills from the previous run (pending entries).
       A pending buy stays pending while its order is still open.
    2. Never claim more shares than the account holds.
    3. Adopt manual holdings listed in INDIA_VMM_ADOPT.
    4. Never manage protected symbols.
    """
    ledger = {t: int(q) for t, q in state.get("ledger", {}).items()}
    pending = state.get("pending", {})
    still_pending = {}
    for t, p in pending.items():
        filled = max(0, actual.get(t, 0) - int(p["pre_units"]))
        ledger[t] = ledger.get(t, 0) + min(filled, int(p["units"]))
        if t in open_syms:
            still_pending[t] = p
    for t in [s.strip().upper() + ".NS" for s in os.environ.get("INDIA_VMM_ADOPT", "").split(",") if s.strip()]:
        if actual.get(t, 0) > 0:
            ledger[t] = actual[t]
    ledger = {t: min(q, actual.get(t, 0)) for t, q in ledger.items()}
    ledger = {t: q for t, q in ledger.items() if q > 0 and t not in rules.PROTECTED}
    return ledger, still_pending


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="place real orders (also needs TRADING_ENABLED=true)")
    ap.add_argument("--parquet", help="offline: NSE prices from a parquet file, no broker")
    ap.add_argument("--cash", type=float, default=None, help="offline: cash available in rupees")
    args = ap.parse_args()

    live = args.live and os.environ.get("TRADING_ENABLED", "").lower() == "true"
    if args.live and not live:
        print("--live given but TRADING_ENABLED is not 'true': staying in DRY RUN.")

    state = load_state()
    offline = args.parquet is not None

    if offline:
        broker = None
        actual = {}
        open_syms = set()
        cash = float(args.cash or 0)
        # offline: the ledger is only what the state file says (no real holdings to reconcile)
        actual = {t: int(q) for t, q in state.get("ledger", {}).items()}
        universe_hint = None
    else:
        from broker import KiteBroker

        broker = KiteBroker()
        actual = broker.holdings()
        cash = broker.cash()
        open_syms = broker.open_symbols()
        universe_hint = broker.universe()

    ledger, pending = reconcile(state, actual, open_syms)
    print(f"account holdings (all): {len(actual)} | bot ledger: {ledger}")

    if offline:
        closes, volumes = data.load_parquet(args.parquet)
    else:
        tick = sorted(set(universe_hint) | set(ledger) | {rules.MARKET, rules.MARKET_FALLBACK})
        closes, volumes = data.load_yfinance(tick)

    sig = rules.signals(closes, volumes)
    held_value = sum(q * float(sig["close"].get(t, 0.0) or 0.0) for t, q in ledger.items())
    total = held_value + cash
    budget = float(os.environ.get("INDIA_VMM_BUDGET_INR", "0") or 0)
    equity = min(total, budget) if budget > 0 else total

    orders, notes = rules.plan(sig, ledger, equity=equity, cash=cash, open_syms=open_syms,
                               protected=rules.PROTECTED)

    print(f"\nsession {sig['date'].date() if hasattr(sig['date'], 'date') else sig['date']} | "
          f"eligible {sig['n_eligible']} | ranked {len(sig['ranked'])} | "
          f"market {sig['market']} {'ON' if sig['market_ok'] else 'OFF'} | "
          f"equity Rs {equity:,.0f} | cash Rs {cash:,.0f}")
    for n in notes:
        print("  note:", n)
    if not orders:
        print("  no orders today")
    for o in orders:
        print(f"  {o['action']:4} {o['symbol']:<14} qty {o['qty']:>5}  limit Rs {o['limit']:>9.2f}  "
              f"value Rs {o['value']:>10,.2f}  {o['reason']}")

    plan_out = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "live": live,
                "session": str(sig["date"]), "equity": equity, "cash": cash, "orders": orders, "notes": notes}
    save_json(LAST_PLAN, plan_out)

    if not live:
        print("\nDRY RUN: nothing placed. Plan saved to results/last_plan.json")
        return

    if broker is None:
        print("\nlive mode needs the Kite broker, not --parquet. Nothing placed.")
        return

    pending_new = dict(pending)
    for o in orders:
        try:
            oid = broker.place(o)
            print(f"  placed {o['action']} {o['symbol']} x{o['qty']} -> order {oid}")
            if o["action"] == "BUY":
                pending_new[o["ticker"]] = {"units": o["qty"], "pre_units": actual.get(o["ticker"], 0),
                                            "order_id": str(oid)}
        except Exception as e:  # keep going; the failed order is reported
            print(f"  FAILED {o['action']} {o['symbol']}: {e}")
    state = {"ledger": ledger, "pending": pending_new,
             "last_run": dt.datetime.now().isoformat(timespec="seconds")}
    save_json(STATE, state)
    print("state saved to results/state.json")


if __name__ == "__main__":
    main()
