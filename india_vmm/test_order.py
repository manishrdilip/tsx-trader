"""One manual test order through the bot's Zerodha connection (India server).

  .venv/bin/python india_vmm/test_order.py SELL SUZLON 1
  .venv/bin/python india_vmm/test_order.py BUY SUZLON 1

LIMIT / CNC / DAY order near the live price (sell 0.5% below, buy 0.5% above), so it fills
like a market order but can never fill far away. Asks you to type YES first, then shows the
order status for up to 60 seconds. Only works during NSE hours (9:15-15:30 IST).
Tagged "indiavmm" so the 5-minute watcher reports it on Telegram.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import local_env  # noqa: E402,F401
from broker import KiteBroker  # noqa: E402


def main():
    if len(sys.argv) != 4 or sys.argv[1].upper() not in ("BUY", "SELL"):
        print(__doc__)
        return
    side, sym, qty = sys.argv[1].upper(), sys.argv[2].upper(), int(sys.argv[3])
    b = KiteBroker()
    k = b.k
    ltp = float(k.ltp([f"NSE:{sym}"])[f"NSE:{sym}"]["last_price"])
    tick = 0.05
    if side == "SELL":
        held = int(next((h.get("quantity") or 0 for h in k.holdings() if h["tradingsymbol"].upper() == sym), 0))
        if held < qty:
            print(f"You hold {held} {sym}; cannot sell {qty}.")
            return
        limit = math.floor(ltp * 0.995 / tick) * tick
    else:
        limit = math.ceil(ltp * 1.005 / tick) * tick
        cash = b.cash()
        if qty * limit > cash:
            print(f"Not enough cash: need Rs {qty * limit:,.2f}, have Rs {cash:,.2f}.")
            return
    limit = round(limit, 2)
    print(f"{side} {qty} {sym} at limit Rs {limit} (live price Rs {ltp}), value Rs {qty * limit:,.2f}")
    if input("Type YES to place this REAL order: ").strip() != "YES":
        print("Cancelled, nothing placed.")
        return
    oid = b.place({"action": side, "symbol": sym, "qty": qty, "limit": limit})
    print("placed, order id", oid)
    for _ in range(12):
        time.sleep(5)
        o = [x for x in k.order_history(oid)][-1]
        print(" status:", o.get("status"), o.get("status_message") or "", "filled", o.get("filled_quantity"),
              "@", o.get("average_price"))
        if o.get("status") in ("COMPLETE", "REJECTED", "CANCELLED"):
            break


if __name__ == "__main__":
    main()
