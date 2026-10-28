"""
Auto-trader for India (Zerodha/Kite) portfolio.

TWO MODES:
  1. Position monitor  — runs every 5 min via GitHub Actions cron.
     Checks all open holdings. Makes sure each one has an exchange-side GTT OCO
     exit (stop = 3x ATR14 capped at -8%, target = 6x ATR14, from risk_levels.py,
     the same rule as the lab backtest). Legacy losers are closed with a limit sell.
     Sends Telegram alert after every action.

  2. Auto-buy mode  — triggered by tsx_monitor.yml / india_monitor.yml
     after Claude APPROVES a trade signal. Limit buy (LTP + 0.2%), then a GTT exit.
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
from datetime import datetime, timedelta

import pandas as pd
from kiteconnect import KiteConnect
from notifier import send_telegram
from verifier import verify_trade, format_alert
from risk_levels import levels, round_to_tick, wilder_atr
from auto_trader_orders import place_limit_buy, place_exit_gtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SELL_BUFFER = 0.002       # legacy exits: accept at most 0.2% below LTP

# Legacy losing positions — sell immediately regardless of P&L
# (already far past stop-loss; holding costs more than cutting)
LEGACY_LOSSES = {"APCL", "WIPRO", "TRIDENT", "IBULLSLTD"}

# ── Kite setup ────────────────────────────────────────────────────────────────

def get_kite() -> KiteConnect:
    kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
    kite.set_access_token(os.environ["KITE_ACCESS_TOKEN"])
    return kite

_INSTRUMENTS = {}

def instrument(kite: KiteConnect, symbol: str, exchange: str = "NSE") -> dict:
    """Instrument row (instrument_token, tick_size, ...). The list is fetched once per run."""
    if exchange not in _INSTRUMENTS:
        _INSTRUMENTS[exchange] = {i["tradingsymbol"]: i for i in kite.instruments(exchange)}
    return _INSTRUMENTS[exchange][symbol]

def daily_bars(kite: KiteConnect, symbol: str, exchange: str = "NSE", days: int = 90) -> pd.DataFrame:
    """Daily OHLC (oldest first) with the High/Low/Close columns risk_levels expects."""
    token = instrument(kite, symbol, exchange)["instrument_token"]
    rows = kite.historical_data(token, datetime.now() - timedelta(days=days), datetime.now(), "day")
    return pd.DataFrame(rows).rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})

def active_gtt_symbols(kite: KiteConnect) -> set:
    return {g["condition"]["tradingsymbol"] for g in kite.get_gtts() if g.get("status") == "active"}

# ── Trade execution ───────────────────────────────────────────────────────────

def place_limit_sell(kite: KiteConnect, symbol: str, qty: int, ltp: float, tick: float,
                     exchange: str = "NSE") -> str:
    """Limit sell at LTP - 0.2%, rounded down to tick. Returns order_id."""
    price = round_to_tick(ltp * (1 - SELL_BUFFER), tick, "down")
    order_id = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=exchange,
        tradingsymbol=symbol,
        transaction_type=kite.TRANSACTION_TYPE_SELL,
        quantity=qty,
        order_type=kite.ORDER_TYPE_LIMIT,
        price=price,
        product=kite.PRODUCT_CNC,   # Delivery (CNC) for swing trades
    )
    log.info("SELL order placed: %s x%d @ %.2f | order_id=%s", symbol, qty, price, order_id)
    return order_id

# ── Position monitor ──────────────────────────────────────────────────────────

def run_monitor():
    """
    Check all holdings. Close legacy losers; make sure every other holding
    has an active GTT stop/target at the exchange.
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

    try:
        protected = active_gtt_symbols(kite)
    except Exception as e:
        send_telegram(f"⚠️ Auto-trader: failed to fetch GTTs — {e}")
        protected = None    # unknown: don't risk placing duplicate GTTs this run

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

        if symbol in LEGACY_LOSSES:
            reason = f"Legacy loss position — auto-closing (P&L: {pnl_pct:+.2f}%)"
            try:
                tick = float(instrument(kite, symbol, exchange)["tick_size"])
                order_id = place_limit_sell(kite, symbol, qty, ltp, tick, exchange)
                alert = (
                    f"🤖 *AUTO-SELL PLACED — India*\n"
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
            continue

        # Every other holding must have an exchange-side stop/target (GTT OCO)
        if protected is None or symbol in protected:
            continue
        try:
            tick = float(instrument(kite, symbol, exchange)["tick_size"])
            lv = place_exit_gtt(kite, symbol, qty, avg_cost, daily_bars(kite, symbol, exchange), tick, exchange)
            capped = " capped" if lv["capped"] else ""
            send_telegram(
                f"🛡 *GTT EXIT PLACED — India*\n"
                f"`{symbol}` x{qty} | entry ₹{avg_cost:.2f}\n"
                f"Stop ₹{lv['stop']:.2f} ({lv['stop_pct']:+.2f}%{capped}) | "
                f"Target ₹{lv['target']:.2f} ({lv['target_pct']:+.2f}%)\n"
                f"GTT ID: `{lv['gtt_id']}`"
            )
            actions_taken.append(f"GTT {symbol}")
        except Exception as e:
            err = f"⚠️ GTT exit FAILED for {symbol}: {e}"
            log.error(err)
            send_telegram(err)

    # Send position summary
    summary_lines.append("")
    if actions_taken:
        summary_lines.append(f"✅ Actions taken: {', '.join(actions_taken)}")
    else:
        summary_lines.append("⏸ No action needed (exits are held as GTTs at the exchange).")
    summary_lines.append(f"_Scanned at {datetime.now().strftime('%Y-%m-%d %H:%M IST')}_")

    send_telegram("\n".join(summary_lines))

# ── Auto-buy ──────────────────────────────────────────────────────────────────

def run_buy(symbol: str, qty: int, price: float):
    """
    Compute ATR stop/target, verify the buy with Claude, then execute if APPROVED:
    limit buy, and on fill an exchange-side GTT OCO exit.
    Called after scanner signals agree on a stock.
    """
    kite = get_kite()
    exchange = "BSE" if symbol.endswith("-BE") else "NSE"

    try:
        ins = instrument(kite, symbol, exchange)
        tick = float(ins["tick_size"])
        bars = daily_bars(kite, symbol, exchange)
        lv = levels(price, wilder_atr(bars), tick)
    except Exception as e:
        send_telegram(f"🚫 *AUTO-BUY BLOCKED — India*\n`{symbol}`: could not compute ATR levels — {e}")
        log.error("ATR levels failed for %s: %s", symbol, e)
        sys.exit(1)

    trade = {
        "symbol":       symbol,
        "company":      ins.get("name") or symbol,   # Kite name, used for the headline search
        "action":       "BUY",
        "order_type":   "LIMIT",
        "qty":          qty,
        "price":        price,
        "atr14":        lv["atr"],
        "stop":         lv["stop"],
        "target":       lv["target"],
        "stop_capped_at_8pct": lv["capped"],
        "tick_size":    tick,
        "order_id":     f"auto-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "triggered_by": "scanner",
        "timestamp":    datetime.now().isoformat(),
    }

    log.info("Verifying BUY: %s x%d @ %.2f (stop %.2f / target %.2f)",
             symbol, qty, price, lv["stop"], lv["target"])
    result = verify_trade(trade, portfolio="india")
    alert  = format_alert(result)

    if result["verdict"] != "APPROVED":
        # Claude flagged or errored — do NOT buy, send alert
        send_telegram(f"🚫 *AUTO-BUY BLOCKED — India*\n{alert}")
        log.warning("Buy blocked by Claude: %s", result.get("reason"))
        sys.exit(1)  # Fail the workflow so it's visible in GitHub Actions

    try:
        ltp = kite.ltp(f"{exchange}:{symbol}")[f"{exchange}:{symbol}"]["last_price"]
        order_id = place_limit_buy(kite, symbol, qty, ltp, tick, exchange)
        if order_id is None:
            send_telegram(f"⏹ *AUTO-BUY NOT FILLED — India*\n`{symbol}` limit order cancelled or "
                          f"rejected. Check positions for a partial fill.")
            log.warning("Buy not filled: %s", symbol)
            return
        fill = float(kite.order_history(order_id)[-1].get("average_price") or ltp)
        lv = place_exit_gtt(kite, symbol, qty, fill, bars, tick, exchange)
        final_alert = (
            f"🤖 *AUTO-BUY EXECUTED — India*\n"
            f"Symbol: `{symbol}`\n"
            f"Qty: {qty} @ ₹{fill:.2f}\n"
            f"Stop ₹{lv['stop']:.2f} ({lv['stop_pct']:+.2f}%) | "
            f"Target ₹{lv['target']:.2f} ({lv['target_pct']:+.2f}%)\n"
            f"Order ID: `{order_id}` | GTT ID: `{lv['gtt_id']}`\n"
            f"Claude: {result.get('reason', '')}"
        )
        send_telegram(final_alert)
        log.info("Auto-bought %s", symbol)
    except Exception as e:
        err = f"⚠️ Auto-buy FAILED for {symbol}: {e}"
        log.error(err)
        send_telegram(err)
        sys.exit(1)

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
