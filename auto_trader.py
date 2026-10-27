"""
Auto-trader for India (Zerodha/Kite) portfolio.

TWO MODES:
  1. Position monitor  — runs every 5 min via GitHub Actions cron.
     Checks all open holdings. Auto-SELLS if:
       - P&L >= +3%  (profit target hit)
       - P&L <= -1%  (stop-loss hit)
     Sends Telegram alert after every action.

  2. Auto-buy mode  — triggered by tsx_monitor.yml / india_monitor.yml
     after Claude APPROVES a trade signal.
     Called with: python auto_trader.py buy SYMBOL QTY PRICE

Usage:
  Position monitor (GitHub Actions cron):
    python auto_trader.py monitor

  Auto-buy (after Claude approval):
    python auto_trader.py buy SYMBOL QTY PRICE

Env vars required:
  KITE_API_KEY, KITE_ACCESS_TOKEN
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  ANTHROPIC_API_KEY (for buy-mode verification)
"""

import os
import sys
import json
import logging
from datetime import datetime

from kiteconnect import KiteConnect
from notifier import send_telegram
from verifier import verify_trade, format_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

PROFIT_TARGET_PCT = 3.0   # auto-sell at +3%
STOP_LOSS_PCT     = -1.0  # auto-sell at -1%

# Legacy losing positions — sell immediately regardless of P&L
# (already far past stop-loss; holding costs more than cutting)
LEGACY_LOSSES = {"APCL", "WIPRO", "TRIDENT", "IBULLSLTD"}

# ── Kite setup ────────────────────────────────────────────────────────────────

def get_kite() -> KiteConnect:
    kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
    kite.set_access_token(os.environ["KITE_ACCESS_TOKEN"])
    return kite

# ── Trade execution ───────────────────────────────────────────────────────────

def place_market_sell(kite: KiteConnect, symbol: str, qty: int, exchange: str = "NSE") -> str:
    """Place a market sell order. Returns order_id."""
    order_id = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=exchange,
        tradingsymbol=symbol,
        transaction_type=kite.TRANSACTION_TYPE_SELL,
        quantity=qty,
        order_type=kite.ORDER_TYPE_MARKET,
        product=kite.PRODUCT_CNC,   # Delivery (CNC) for swing trades
    )
    log.info("SELL order placed: %s x%d | order_id=%s", symbol, qty, order_id)
    return order_id

def place_market_buy(kite: KiteConnect, symbol: str, qty: int, exchange: str = "NSE") -> str:
    """Place a market buy order. Returns order_id."""
    order_id = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=exchange,
        tradingsymbol=symbol,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        quantity=qty,
        order_type=kite.ORDER_TYPE_MARKET,
        product=kite.PRODUCT_CNC,
    )
    log.info("BUY order placed: %s x%d | order_id=%s", symbol, qty, order_id)
    return order_id

# ── Position monitor ──────────────────────────────────────────────────────────

def run_monitor():
    """
    Check all holdings. Auto-sell on target/stop or legacy loss.
    Designed to run once per GitHub Actions invocation (not a loop).
    """
    kite = get_kite()

    try:
        holdings = kite.holdings()
    except Exception as e:
        msg = f"⚠️ Auto-trader: failed to fetch holdings — {e}"
        log.error(msg)
        send_telegram(msg)
        sys.exit(1)

    if not holdings:
        log.info("No holdings found.")
        send_telegram("ℹ️ Auto-trader: no open holdings.")
        return

    actions_taken = []
    summary_lines = ["📊 *Position Scan — India*", ""]

    for h in holdings:
        symbol   = h["tradingsymbol"]
        qty      = h.get("quantity", 0)
        avg_cost = h.get("average_price", 0)
        ltp      = h.get("last_price", 0)
        exchange = h.get("exchange", "NSE")

        if qty <= 0 or avg_cost <= 0:
            continue

        pnl_pct = ((ltp - avg_cost) / avg_cost) * 100

        status_icon = "🟢" if pnl_pct >= 0 else "🔴"
        summary_lines.append(
            f"{status_icon} `{symbol}` {qty} shares | avg ₹{avg_cost:.2f} | LTP ₹{ltp:.2f} | {pnl_pct:+.2f}%"
        )

        # Decide whether to auto-sell
        reason = None
        if symbol in LEGACY_LOSSES:
            reason = f"Legacy loss position — auto-closing (P&L: {pnl_pct:+.2f}%)"
        elif pnl_pct >= PROFIT_TARGET_PCT:
            reason = f"Profit target +{PROFIT_TARGET_PCT}% hit ({pnl_pct:+.2f}%)"
        elif pnl_pct <= STOP_LOSS_PCT:
            reason = f"Stop-loss -{abs(STOP_LOSS_PCT)}% hit ({pnl_pct:+.2f}%)"

        if reason:
            try:
                order_id = place_market_sell(kite, symbol, qty, exchange)
                alert = (
                    f"🤖 *AUTO-SELL EXECUTED — India*\n"
                    f"Symbol: `{symbol}`\n"
                    f"Qty: {qty} shares\n"
                    f"Avg cost: ₹{avg_cost:.2f} | LTP: ₹{ltp:.2f}\n"
                    f"P&L: `{pnl_pct:+.2f}%`\n"
                    f"Reason: {reason}\n"
                    f"Order ID: `{order_id}`"
                )
                send_telegram(alert)
                actions_taken.append(f"SELL {symbol}")
                log.info("Auto-sold %s: %s", symbol, reason)
            except Exception as e:
                err = f"⚠️ Auto-sell FAILED for {symbol}: {e}"
                log.error(err)
                send_telegram(err)

    # Send position summary
    summary_lines.append("")
    if actions_taken:
        summary_lines.append(f"✅ Actions taken: {', '.join(actions_taken)}")
    else:
        summary_lines.append("⏸ No auto-sell triggered this scan.")
    summary_lines.append(f"_Scanned at {datetime.now().strftime('%Y-%m-%d %H:%M IST')}_")

    send_telegram("\n".join(summary_lines))

# ── Auto-buy ──────────────────────────────────────────────────────────────────

def run_buy(symbol: str, qty: int, price: float):
    """
    Verify the buy with Claude, then execute if APPROVED.
    Called after scanner signals agree on a stock.
    """
    kite = get_kite()

    trade = {
        "symbol":       symbol,
        "action":       "BUY",
        "qty":          qty,
        "price":        price,
        "order_id":     f"auto-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "triggered_by": "scanner",
        "timestamp":    datetime.now().isoformat(),
    }

    log.info("Verifying BUY: %s x%d @ %.2f", symbol, qty, price)
    result = verify_trade(trade, portfolio="india")
    alert  = format_alert(result)

    if result["verdict"] == "APPROVED":
        try:
            exchange = "BSE" if symbol.endswith("-BE") else "NSE"
            order_id = place_market_buy(kite, symbol, qty, exchange)
            final_alert = (
                f"🤖 *AUTO-BUY EXECUTED — India*\n"
                f"Symbol: `{symbol}`\n"
                f"Qty: {qty} @ ₹{price:.2f}\n"
                f"Order ID: `{order_id}`\n"
                f"Claude: {result.get('reason', '')}"
            )
            send_telegram(final_alert)
            log.info("Auto-bought %s", symbol)
        except Exception as e:
            err = f"⚠️ Auto-buy FAILED for {symbol}: {e}"
            log.error(err)
            send_telegram(err)
            sys.exit(1)
    else:
        # Claude flagged or errored — do NOT buy, send alert
        send_telegram(f"🚫 *AUTO-BUY BLOCKED — India*\n{alert}")
        log.warning("Buy blocked by Claude: %s", result.get("reason"))
        sys.exit(1)  # Fail the workflow so it's visible in GitHub Actions

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_trader.py monitor")
        print("       python auto_trader.py buy SYMBOL QTY PRICE")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "monitor":
        run_monitor()

    elif mode == "buy":
        if len(sys.argv) != 5:
            print("Usage: python auto_trader.py buy SYMBOL QTY PRICE")
            sys.exit(1)
        symbol = sys.argv[2].upper()
        qty    = int(sys.argv[3])
        price  = float(sys.argv[4])
        run_buy(symbol, qty, price)

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
