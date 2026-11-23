"""Research-only executable stop-fill reference tests; no trading integration.

Conservative long-only OHLC convention: a stop resting before the session
fills at the open if gapped through; otherwise at stop on intrabar breach.
Never assume a stop guarantees its trigger price across an overnight gap.
When stop and target both touch in one bar, use stop-first pessimism.
"""
import unittest

def long_bracket_fill(open_, high, low, close, stop, target):
    assert 0 < low <= min(open_, close) <= max(open_, close) <= high
    assert 0 < stop < target
    if open_ <= stop:
        return ("stop_gap", open_)
    if open_ >= target:
        return ("target_gap", open_)
    if low <= stop:
        return ("stop", stop)
    if high >= target:
        return ("target", target)
    return ("hold", close)

def net_trade(entry, exit_, shares, fee_per_side, slip_bps):
    assert entry > 0 and exit_ > 0 and shares >= 0 and fee_per_side >= 0 and slip_bps >= 0
    buy = entry * (1 + slip_bps / 10000)
    sell = exit_ * (1 - slip_bps / 10000)
    return shares * (sell - buy) - 2 * fee_per_side

class StopExecutionReference(unittest.TestCase):
    def test_gap_through_stop(self):
        self.assertEqual(long_bracket_fill(80, 84, 75, 81, 95, 110), ("stop_gap", 80))
    def test_stop_and_target_same_bar_is_stop_first(self):
        self.assertEqual(long_bracket_fill(100, 115, 90, 108, 95, 110), ("stop", 95))
    def test_target_gap(self):
        self.assertEqual(long_bracket_fill(120, 123, 112, 117, 95, 110), ("target_gap", 120))
    def test_no_hit(self):
        self.assertEqual(long_bracket_fill(100, 105, 97, 103, 95, 110), ("hold", 103))
    def test_costs_reduce_profit(self):
        gross = net_trade(100, 105, 10, 0, 0)
        net = net_trade(100, 105, 10, 1, 10)
        self.assertGreater(gross, net)
    def test_gap_loss_can_exceed_stop_risk(self):
        entry, shares, stop = 100, 50, 95
        fill = long_bracket_fill(70, 75, 65, 72, stop, 120)[1]
        self.assertLess(net_trade(entry, fill, shares, 0, 0), -shares * (entry - stop))
    def test_5000_cash_sizing_includes_fees_and_slippage(self):
        cash, entry, fee, slip = 5000, 100, 1, 10
        shares = int((cash - fee) // (entry * (1 + slip / 10000)))
        self.assertLessEqual(shares * entry * (1 + slip / 10000) + fee, cash)
        self.assertGreater((shares + 1) * entry * (1 + slip / 10000) + fee, cash)

if __name__ == "__main__":
    unittest.main()
