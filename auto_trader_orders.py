"""
Order placement for auto_trader.py (Zerodha Kite, NSE, CNC). Replaces the
reviewer's patch, which removed market orders but then hardcoded +10% / -5%,
contradicting its own advice to use ATR levels.

auto_trader.py imports these; PROFIT_TARGET_PCT / STOP_LOSS_PCT (+3% / -1%) are gone.

What changed vs the reviewer's version:
- Stop/target come from risk_levels.levels() (3x / 6x ATR, 8% cap), same as the backtest.
- Limit price is rounded UP to the instrument's real tick size (from kite.instruments),
  not to 0.1, so Kite does not reject it.
- Unfilled limit orders are cancelled after a timeout instead of sitting open.
- The protective stop is placed as an exchange-side GTT OCO (stop + target together),
  so exits still happen if the GitHub Action or your PC is down.
"""
from __future__ import annotations

import time

from risk_levels import levels, round_to_tick, wilder_atr

BUY_BUFFER = 0.002      # pay at most 0.2% above LTP
FILL_TIMEOUT_S = 60


_TICK_CACHE: dict[str, dict[str, float]] = {}


def _ticks(kite, exchange: str) -> dict[str, float]:
    """Download the instrument list once per run (it's several MB) and keep symbol -> tick."""
    if exchange not in _TICK_CACHE:
        _TICK_CACHE[exchange] = {
            ins["tradingsymbol"]: float(ins["tick_size"]) for ins in kite.instruments(exchange)
        }
    return _TICK_CACHE[exchange]


def tick_size(kite, symbol: str, exchange: str = "NSE") -> float:
    # No silent 0.05 fallback: NSE tick sizes vary by price band, and a wrong tick
    # gets the order rejected. An unknown symbol is a bug upstream, so fail loudly.
    try:
        return _ticks(kite, exchange)[symbol]
    except KeyError:
        raise KeyError(f"{exchange}:{symbol} not in Kite instrument list") from None


def place_limit_buy(kite, symbol: str, qty: int, ltp: float, tick: float,
                    exchange: str = "NSE") -> str | None:
    """Limit buy at LTP + 0.2%, rounded up to tick. Returns order_id if filled, else None."""
    price = round_to_tick(ltp * (1 + BUY_BUFFER), tick, "up")
    order_id = kite.place_order(
        variety=kite.VARIETY_REGULAR, exchange=exchange, tradingsymbol=symbol,
        transaction_type=kite.TRANSACTION_TYPE_BUY, quantity=qty,
        order_type=kite.ORDER_TYPE_LIMIT, price=price, product=kite.PRODUCT_CNC,
    )
    deadline = time.time() + FILL_TIMEOUT_S
    while time.time() < deadline:
        status = kite.order_history(order_id)[-1]["status"]
        if status == "COMPLETE":
            return order_id
        if status in ("REJECTED", "CANCELLED"):
            return None
        time.sleep(3)
    kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=order_id)
    return None   # a partial fill stays in positions; reconcile from kite.positions()


def place_exit_gtt(kite, symbol: str, qty: int, entry: float, daily_df, tick: float,
                   exchange: str = "NSE") -> dict:
    """Exchange-side OCO: one leg sells at the stop, the other at the target."""
    lv = levels(entry, wilder_atr(daily_df), tick)
    ltp = kite.ltp(f"{exchange}:{symbol}")[f"{exchange}:{symbol}"]["last_price"]
    sell = dict(exchange=exchange, tradingsymbol=symbol, quantity=qty,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                order_type=kite.ORDER_TYPE_LIMIT, product=kite.PRODUCT_CNC)
    gtt_id = kite.place_gtt(
        trigger_type=kite.GTT_TYPE_OCO, tradingsymbol=symbol, exchange=exchange,
        trigger_values=[lv["stop"], lv["target"]], last_price=ltp,
        orders=[
            # stop leg: limit a little below trigger so it still fills on a fast drop
            {**sell, "price": round_to_tick(lv["stop"] * 0.995, tick, "down")},
            {**sell, "price": lv["target"]},
        ],
    )
    lv["gtt_id"] = gtt_id
    return lv
