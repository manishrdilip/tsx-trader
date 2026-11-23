"""Research-only adversarial property checks for OHLC stop reference.
No market data or performance inference. Run with python -m unittest.
"""
import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).with_name("executable_stop_reference_audit.py")
spec = importlib.util.spec_from_file_location("stop_ref", path)
ref = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = ref
spec.loader.exec_module(ref)

class StopReferenceProperties(unittest.TestCase):
    def test_gap_stop_cannot_fill_at_unreachable_stop(self):
        for gap_open in (1, 30, 75, 89.99):
            price, reason = ref.held_position_exit(gap_open, max(101, gap_open), min(gap_open, 1), gap_open, 90)
            self.assertEqual((price, reason), (gap_open, "gap_stop"))

    def test_gap_target_fills_open_when_no_stop_hit(self):
        for gap_open in (111, 130, 200):
            self.assertEqual(ref.held_position_exit(gap_open, gap_open+1, gap_open, gap_open, 90, 110),
                             (gap_open, "gap_target"))

    def test_both_touch_conservative_stop_first(self):
        self.assertEqual(ref.held_position_exit(100, 120, 80, 115, 95, 110), (95, "stop"))

    def test_share_rounding_and_cash_conservation(self):
        for entry in (7.13, 33.33, 100, 4999):
            for cost in (0, 10, 50, 100):
                r = ref.simulate(entry, entry, entry, entry, .05, cash=5000, cost_bps=cost)
                fee = cost / 10000
                shares = int(5000/(entry*(1+fee)))
                expected = 5000 - shares*entry*(1+fee) + shares*entry*(1-fee)
                self.assertAlmostEqual(r.end_cash, expected, places=7)
                self.assertLessEqual(r.end_cash, 5000 + 1e-7)

    def test_no_stop_fill_before_entry(self):
        # Intraday new position entered at open; low touch is a stop, not a pre-entry gap.
        r = ref.simulate(100, 105, 80, 101, .05)
        self.assertEqual((r.exit, r.exit_reason), (95, "stop"))

    def test_monotone_costs_fixed_share_count(self):
        balances = [ref.simulate(100, 105, 100, 104, .05, cash=5000, cost_bps=b).end_cash
                    for b in (0, 5, 10, 20, 40)]
        self.assertEqual(balances, sorted(balances, reverse=True))

if __name__ == "__main__":
    unittest.main()
