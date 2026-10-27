"""
TSX / Wealthsimple monitor.
Wealthsimple has no official API, so this uses TWO methods:

  Method A (Recommended): Manual trigger
    After you place a trade on Wealthsimple, run:
      python tsx_monitor.py --trade BUY --symbol MSA.TO --qty 5 --price 9.50 --signal yes

  Method B: Unofficial Wealthsimple API (wealthsimple-trade library)
    pip install git+https://github.com/MarkGalloway/wealthsimple-trade
    Set env vars: WS_EMAIL, WS_PASSWORD, WS_OTP (one-time, then session saved)
    Run in background: python tsx_monitor.py --auto

Both methods call verifier.py → Claude → Telegram.

Setup:
  pip install requests
  Set env vars: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path
from verifier import verify_trade, format_alert
from notifier import send_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

STATE_FILE = "tsx_seen_orders.json"

# ── Manual trade trigger (Method A) ─────────────────────────────────────────

def manual_verify(args):
    """Called with CLI args after you place a trade manually."""
    trade = {
        "symbol":       args.symbol,
        "action":       args.trade.upper(),
        "qty":          args.qty,
        "price":        args.price,
        "order_id":     f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "triggered_by": "scanner" if args.signal == "yes" else "manual",
        "timestamp":    datetime.now().isoformat(),
    }
    if args.trade.upper() == "SELL" and args.avg_cost:
        trade["avg_cost"] = args.avg_cost

    log.info("Verifying manual trade: %s", trade)
    result = verify_trade(trade, portfolio="tsx")
    alert  = format_alert(result)

    print("\n" + alert.replace("*", "").replace("`", ""))
    send_telegram(alert)
    return result


# ── Auto poll via unofficial Wealthsimple API (Method B) ────────────────────

def load_seen() -> set:
    if Path(STATE_FILE).exists():
        return set(json.loads(Path(STATE_FILE).read_text()))
    return set()

def save_seen(seen: set):
    Path(STATE_FILE).write_text(json.dumps(list(seen)))

def auto_poll():
    """Poll Wealthsimple for new orders using unofficial library."""
    try:
        from wealthsimple import WSTrade
    except ImportError:
        log.error("wealthsimple-trade not installed. Run: pip install git+https://github.com/MarkGalloway/wealthsimple-trade")
        sys.exit(1)

    email    = os.environ["WS_EMAIL"]
    password = os.environ["WS_PASSWORD"]
    ws       = WSTrade(email, password)

    log.info("TSX monitor started (auto mode). Polling every 60s.")
    seen = load_seen()

    while True:
        try:
            activities = ws.get_activities()
            for act in activities.get("results", []):
                oid    = act.get("id", "")
                status = act.get("status", "")

                if status not in ("posted", "executed") or oid in seen:
                    continue

                seen.add(oid)
                save_seen(seen)

                symbol = act.get("symbol", act.get("security_id", ""))
                action = act.get("type", "").upper()
                if action not in ("BUY", "SELL"):
                    continue

                trade = {
                    "symbol":       symbol,
                    "action":       action,
                    "qty":          act.get("quantity", 0),
                    "price":        act.get("price", {}).get("amount", 0),
                    "order_id":     oid,
                    "triggered_by": "unknown",
                    "timestamp":    act.get("created_at", datetime.now().isoformat()),
                }
                if action == "SELL":
                    trade["avg_cost"] = act.get("market_value", {}).get("amount")

                log.info("New TSX order: %s %s", action, symbol)
                result = verify_trade(trade, portfolio="tsx")
                alert  = format_alert(result)
                log.info("Verdict: %s", result["verdict"])
                send_telegram(alert)

        except Exception as e:
            log.error("TSX poll error: %s", e)
            send_telegram(f"⚠️ TSX monitor error: {e}")

        time.sleep(60)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TSX trade verifier")
    sub = parser.add_subparsers(dest="mode")

    # Manual mode
    m = sub.add_parser("manual", help="Verify a trade you just placed manually")
    m.add_argument("--trade",    required=True, choices=["BUY", "SELL", "buy", "sell"])
    m.add_argument("--symbol",   required=True, help="e.g. MSA.TO")
    m.add_argument("--qty",      required=True, type=int)
    m.add_argument("--price",    required=True, type=float)
    m.add_argument("--avg_cost", type=float,    help="Original buy price (SELL only)")
    m.add_argument("--signal",   default="yes", choices=["yes", "no"],
                   help="Was this triggered by the scanner? (yes/no)")

    # Auto mode
    sub.add_parser("auto", help="Auto-poll Wealthsimple for new orders")

    args = parser.parse_args()

    if args.mode == "manual":
        manual_verify(args)
    elif args.mode == "auto":
        auto_poll()
    else:
        parser.print_help()
