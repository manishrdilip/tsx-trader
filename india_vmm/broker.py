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


def merge_day_positions(holdings, net_positions):
    """Add today's NSE CNC net quantity (buys +, sells of holdings -) to holdings."""
    out = dict(holdings)
    for p in net_positions:
        if p.get("product") != "CNC" or p.get("exchange") != "NSE":
            continue
        t = p["tradingsymbol"].upper() + ".NS"
        q = out.get(t, 0) + int(p.get("quantity") or 0)
        if q > 0:
            out[t] = q
        else:
            out.pop(t, None)
    return out


class KiteBroker:
    def __init__(self):
        from kiteconnect import KiteConnect

        self.k = KiteConnect(api_key=os.environ["KITE_API_KEY"], timeout=20)
        self.k.set_access_token(os.environ["KITE_ACCESS_TOKEN"])

    def holdings(self):
        """{symbol.NS: qty} for every delivery holding in the account, including shares
        bought today (only in positions until T+1) and yesterday's buys (t1_quantity until settled).
        Without these the bot saw same-day fills as missing: equity fell to cash alone and the
        loss halt fired falsely (2026-11-13)."""
        out = {}
        for h in self.k.holdings():
            qty = int(h.get("quantity") or 0) + int(h.get("t1_quantity") or 0)
            if qty > 0:
                out[h["tradingsymbol"].upper() + ".NS"] = qty
        return merge_day_positions(out, self.k.positions().get("net", []))

    def open_buy_value(self):
        """Rupees blocked by today's still-open BUY orders (counted as money, not a loss)."""
        tot = 0.0
        for o in self.k.orders():
            if o.get("status") not in TERMINAL and o.get("transaction_type") == "BUY":
                left = int(o.get("pending_quantity") or 0)
                tot += left * float(o.get("price") or 0)
        return tot

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
