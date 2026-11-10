"""Zerodha Kite Connect wrapper for the India VMM bot.

Reads KITE_API_KEY and KITE_ACCESS_TOKEN from the environment (same names as india_laptop/).
The access token is refreshed daily by the existing 8:15 IST login task.
Only this file talks to Kite. The rules and the runner never call Kite directly.
"""
import os

TERMINAL = {"COMPLETE", "CANCELLED", "REJECTED"}


class KiteBroker:
    def __init__(self):
        from kiteconnect import KiteConnect

        self.k = KiteConnect(api_key=os.environ["KITE_API_KEY"])
        self.k.set_access_token(os.environ["KITE_ACCESS_TOKEN"])

    def holdings(self):
        """{symbol.NS: qty} for every delivery holding in the account."""
        out = {}
        for h in self.k.holdings():
            qty = int(h.get("quantity") or 0)
            if qty > 0:
                out[h["tradingsymbol"].upper() + ".NS"] = qty
        return out

    def cash(self):
        return float(self.k.margins("equity")["available"]["live_balance"])

    def open_symbols(self):
        syms = set()
        for o in self.k.orders():
            if o.get("status") not in TERMINAL and o.get("tradingsymbol"):
                syms.add(o["tradingsymbol"].upper() + ".NS")
        return syms

    def universe(self):
        """NSE equity (EQ) symbols from Kite's instrument dump, as .NS tickers."""
        return sorted({i["tradingsymbol"].upper() + ".NS"
                       for i in self.k.instruments("NSE") if i.get("instrument_type") == "EQ"})

    def ltp(self, tickers):
        """{ticker.NS: last traded price} from Kite (used by the pre-order price check)."""
        if not tickers:
            return {}
        keys = ["NSE:" + t[:-3] for t in tickers]
        q = self.k.ltp(keys)
        return {t: float(q[k]["last_price"]) for t, k in zip(tickers, keys) if k in q}

    def place(self, order):
        """Place one LIMIT / CNC / DAY order. Returns the Kite order id."""
        k = self.k
        return k.place_order(
            variety=k.VARIETY_REGULAR,
            exchange=k.EXCHANGE_NSE,
            tradingsymbol=order["symbol"],
            transaction_type=k.TRANSACTION_TYPE_BUY if order["action"] == "BUY" else k.TRANSACTION_TYPE_SELL,
            quantity=int(order["qty"]),
            product=k.PRODUCT_CNC,
            order_type=k.ORDER_TYPE_LIMIT,
            price=float(order["limit"]),
            validity=k.VALIDITY_DAY,
            tag="indiavmm",
        )
