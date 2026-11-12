"""Zerodha Kite Connect wrapper for the India VMM bot.

Reads KITE_API_KEY and KITE_ACCESS_TOKEN from the environment (same names as india_laptop/).
The access token is refreshed daily by the existing 8:15 IST login task.
Only this file talks to Kite. The rules and the runner never call Kite directly.
"""
import os

TERMINAL = {"COMPLETE", "CANCELLED", "REJECTED"}


def main_board(sym):
    """True for a regular NSE stock symbol. Series-suffixed symbols end in a 2-character code
    (-BE, -ST, -SM, -RE, -N1, -Z4, -GB ...); real names with a hyphen (BAJAJ-AUTO, MCDOWELL-N) don't."""
    sym = sym.upper()
    return "-" not in sym or len(sym.rsplit("-", 1)[1]) != 2


class KiteBroker:
    def __init__(self):
        from kiteconnect import KiteConnect

        self.k = KiteConnect(api_key=os.environ["KITE_API_KEY"], timeout=20)
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
        """Main-board NSE stocks from Kite's instrument dump, as .NS tickers.
        Kite tags bonds, NCDs, T-bills and BE/BZ/ST/SM/RE series as "EQ" too; those are dropped
        (Yahoo has no data for them, and they made each run download thousands of dead symbols)."""
        return sorted({i["tradingsymbol"].upper() + ".NS"
                       for i in self.k.instruments("NSE")
                       if i.get("instrument_type") == "EQ" and main_board(i["tradingsymbol"])})

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
