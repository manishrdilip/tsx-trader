"""Independent reference audit: executable cash and risk under multi-position fills.

Synthetic fixtures only. Not a profitability backtest or production simulator patch.
"""
import unittest

def trade(cash, shares, entry, exit_price, fee_rate=0.001, spread=0.002):
    """Buy at ask, sell at bid, charge commission on each executed notional."""
    ask = entry * (1 + spread / 2)
    bid = exit_price * (1 - spread / 2)
    buy = shares * ask
    fee_in = buy * fee_rate
    if buy + fee_in > cash + 1e-9:
        raise ValueError("insufficient cash")
    remaining = cash - buy - fee_in
    proceeds = shares * bid
    fee_out = proceeds * fee_rate
    return remaining + proceeds - fee_out

def shares_for_cash(cash, price, fee_rate=0.001, spread=0.002):
    return int(cash // (price * (1 + spread / 2) * (1 + fee_rate)))

def stop_fill(open_price, stop, low, high):
    """Long position: opening gap is executable before intrabar stop."""
    if open_price <= stop:
        return open_price
    if low <= stop:
        return stop
    return None

class CashAndGapTests(unittest.TestCase):
    def test_full_cash_buy_never_overdraws(self):
        for capital in (5000, 2500, 1000):
            for price in (1.01, 7.19, 112.43, 499.99):
                n = shares_for_cash(capital, price)
                result = trade(capital, n, price, price)
                self.assertGreaterEqual(result, 0)

    def test_round_trip_flat_market_loses_costs(self):
        for spread in (0.0, 0.002, 0.01):
            result = trade(5000, 30, 100, 100, spread=spread)
            self.assertLess(result, 5000)

    def test_gap_below_stop_not_filled_at_stop(self):
        self.assertEqual(stop_fill(70, 95, 68, 76), 70)
        self.assertEqual(stop_fill(100, 95, 92, 104), 95)
        self.assertIsNone(stop_fill(100, 95, 96, 104))

    def test_stop_gap_can_exceed_intended_risk(self):
        capital, entry, stop = 5000, 100, 95
        n = shares_for_cash(capital, entry)
        planned_loss = n * (entry - stop)
        gap_loss = capital - trade(capital, n, entry, 70)
        self.assertGreater(gap_loss, planned_loss)

    def test_worse_spread_or_fees_never_improve_flat_trade(self):
        baseline = trade(5000, 30, 100, 100, 0, 0)
        for fee in (0.001, 0.005):
            for spread in (0.002, 0.01):
                self.assertLess(trade(5000, 30, 100, 100, fee, spread), baseline)

    def test_split_allocations_do_not_create_money(self):
        capital = 5000
        a = trade(2500, shares_for_cash(2500, 100), 100, 100)
        b = trade(2500, shares_for_cash(2500, 50), 50, 50)
        self.assertLess(a+b, capital)

if __name__ == "__main__":
    unittest.main()
