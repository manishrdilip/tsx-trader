"""
Zerodha/Kite order monitor for India portfolio.
Polls for new completed orders and verifies each one via Claude.

Setup:
  1. pip install kiteconnect requests
  2. Set env vars: KITE_API_KEY, KITE_ACCESS_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  3. Run: python india_monitor.py
     Or via GitHub Actions cron (every 5 min during market hours)

Zerodha market hours: 9:15 AM – 3:30 PM IST (Mon–Fri)
"""

import os
import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
from kiteconnect import KiteConnect
from verifier import verify_trade, format_alert
from notifier import send_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

KITE_API_KEY     = os.environ["KITE_API_KEY"]
KITE_ACCESS_TOKEN = os.environ["KITE_ACCESS_TOKEN"]
POLL_INTERVAL_SEC = 30          # check every 30 seconds
STATE_FILE        = "india_seen_orders.json"   # persists across runs

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if Path(STATE_FILE).exists():
        return set(json.loads(Path(STATE_FILE).read_text()))
    return set()

def save_seen(seen: set):
    Path(STATE_FILE).write_text(json.dumps(list(seen)))

def get_avg_cost(kite: KiteConnect, symbol: str) -> float | None:
    """Look up avg cost from current holdings."""
    try:
        holdings = kite.holdings()
        for h in holdings:
            if h["tradingsymbol"] == symbol:
                return h["average_price"]
    except Exception:
        pass
    return None

def order_to_trade(order: dict, kite: KiteConnect) -> dict:
    """Convert Kite order dict to verifier trade dict."""
    symbol = order.get("tradingsymbol", "")
    action = order.get("transaction_type", "").upper()   # BUY or SELL
    trade = {
        "symbol":       symbol,
        "action":       action,
        "qty":          order.get("filled_quantity", 0),
        "price":        order.get("average_price", 0),
        "order_id":     order.get("order_id", ""),
        "triggered_by": "manual",   # Zerodha has no way to tag scanner vs manual
        "timestamp":    str(order.get("order_timestamp", datetime.now().isoformat())),
    }
    if action == "SELL":
        trade["avg_cost"] = get_avg_cost(kite, symbol)
    return trade

# ── Main loop ────────────────────────────────────────────────────────────────

def run():
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(KITE_ACCESS_TOKEN)
    log.info("India monitor started. Polling every %ds.", POLL_INTERVAL_SEC)

    seen = load_seen()

    while True:
        try:
            orders = kite.orders()
            for order in orders:
                oid    = order.get("order_id", "")
                status = order.get("status", "")

                # Only process newly COMPLETE orders
                if status != "COMPLETE" or oid in seen:
                    continue

                seen.add(oid)
                save_seen(seen)

                log.info("New completed order: %s %s x%d @ %.2f",
                         order.get("transaction_type"),
                         order.get("tradingsymbol"),
                         order.get("filled_quantity", 0),
                         order.get("average_price", 0))

                trade  = order_to_trade(order, kite)
                result = verify_trade(trade, portfolio="india")
                alert  = format_alert(result)

                log.info("Verdict: %s", result["verdict"])
                send_telegram(alert)

        except Exception as e:
            log.error("Poll error: %s", e)
            send_telegram(f"⚠️ India monitor error: {e}")

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    run()
