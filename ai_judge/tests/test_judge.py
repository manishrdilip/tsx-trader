import os, sys, unittest, tempfile, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from ai_judge import judge


def fake(answers):
    """answers: {ai: (verdict, cause)} or {ai: [(v,c) per verdict call]} -> ask dict."""
    calls = {"claude": 0, "gemini": 0}
    def mk(ai):
        def f(system, prompt):
            if "honest decision" in prompt:
                a = answers[ai]
                v = a[min(calls[ai], len(a) - 1)] if isinstance(a, list) else a
                calls[ai] += 1
                return f'thinking... {{"verdict": "{v[0]}", "cause": "{v[1]}", "confidence": 80, "reason": "x"}}'
            return f"{ai} argument"
        return f
    return {"claude": mk("claude"), "gemini": mk("gemini")}


class T(unittest.TestCase):
    def test_drop_score_market_fall_does_not_trigger(self):
        s = [100 * (1.001 ** i) * (1 + (0.01 if i % 2 else -0.01)) for i in range(80)]
        m = [100 * (1.001 ** i) * (1 + (0.008 if i % 2 else -0.008)) for i in range(80)]
        z, ex, sd = judge.drop_score(s, m, s[-1] * 0.95, m[-1] * 0.95)   # both fall 5%
        self.assertGreater(z, -1)

    def test_drop_score_stock_only_triggers(self):
        s = [100 * (1 + (0.01 if i % 2 else -0.01)) for i in range(80)]
        m = [100 * (1 + (0.008 if i % 2 else -0.008)) for i in range(80)]
        z, ex, sd = judge.drop_score(s, m, s[-1] * 0.90, m[-1])
        self.assertLess(z, -3)

    def test_agree_sell_company(self):
        r = judge.debate({}, fake({"claude": ("SELL", "company"), "gemini": ("SELL", "company")}))
        self.assertEqual(r["decision"], "SELL"); self.assertTrue(r["consensus"]); self.assertEqual(len(r["rounds"]), 1)

    def test_sell_without_company_cause_is_keep(self):
        r = judge.debate({}, fake({"claude": ("SELL", "market"), "gemini": ("SELL", "market")}))
        self.assertEqual(r["decision"], "KEEP")

    def test_disagree_swaps_then_agrees(self):
        r = judge.debate({}, fake({"claude": [("SELL", "company"), ("SELL", "company")],
                                   "gemini": [("KEEP", "none"), ("SELL", "company")]}))
        self.assertEqual(len(r["rounds"]), 2); self.assertEqual(r["decision"], "SELL")
        self.assertEqual(r["rounds"][1]["sell_side"], "gemini")

    def test_never_agree_defaults_keep(self):
        r = judge.debate({}, fake({"claude": ("SELL", "company"), "gemini": ("KEEP", "none")}))
        self.assertEqual(r["decision"], "KEEP"); self.assertFalse(r["consensus"]); self.assertIn("final_verdicts", r)

    def test_ai_error_is_keep(self):
        def boom(s, p): raise RuntimeError("api down")
        r = judge.debate({}, {"claude": boom, "gemini": boom})
        self.assertEqual(r["decision"], "KEEP"); self.assertIn("api down", r["summary"])

    def test_garbage_reply_is_keep(self):
        r = judge.debate({}, {"claude": lambda s, p: "no json", "gemini": lambda s, p: "no json"})
        self.assertEqual(r["decision"], "KEEP")

    def test_check_holding_once_per_day_and_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            seen, today = {}, dt.date(2026, 11, 16)
            det = lambda *a: {"trigger": True, "z": -5}
            ask = fake({"claude": ("SELL", "company"), "gemini": ("SELL", "company")})
            r = judge.check_holding("ABC.NS", 90, "^NSEI", today, seen, d, ask=ask, detector=det)
            self.assertEqual(r["decision"], "SELL")
            self.assertIsNone(judge.check_holding("ABC.NS", 90, "^NSEI", today, seen, d, ask=ask, detector=det))
            bp = os.path.join(d, "blocks.json")
            judge.add_block(bp, "ABC.NS", today)
            self.assertIn("ABC.NS", judge.blocked(bp, "2026-12-01"))
            self.assertNotIn("ABC.NS", judge.blocked(bp, "2027-01-30"))

    def test_no_trigger_no_ai(self):
        r = judge.check_holding("X", 1, "M", dt.date(2026, 11, 16), {}, "/tmp", ask={}, detector=lambda *a: {"trigger": False})
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
