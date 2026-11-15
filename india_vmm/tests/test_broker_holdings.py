import os, sys, types, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("kiteconnect", types.SimpleNamespace(KiteConnect=object))
import broker


class FakeKite:
    def holdings(self):
        return [{"tradingsymbol": "AAA", "quantity": 2, "t1_quantity": 3},
                {"tradingsymbol": "BBB", "quantity": 0, "t1_quantity": 4}]

    def positions(self):
        return {"day": [{"tradingsymbol": "CCC", "product": "CNC", "exchange": "NSE", "quantity": 5},
                        {"tradingsymbol": "AAA", "product": "CNC", "exchange": "NSE", "quantity": -1},
                        {"tradingsymbol": "DDD", "product": "MIS", "exchange": "NSE", "quantity": 7}]}


class HoldingsTest(unittest.TestCase):
    def test_counts_t1_and_todays_buys(self):
        b = broker.KiteBroker.__new__(broker.KiteBroker)
        b.k = FakeKite()
        self.assertEqual(b.holdings(), {"AAA.NS": 4, "BBB.NS": 4, "CCC.NS": 5})


if __name__ == "__main__":
    unittest.main()
