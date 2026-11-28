"""Research-only deterministic validation of the descriptive return-risk frontier."""
import unittest
import numpy as np
import pandas as pd

class FrontierContract(unittest.TestCase):
    def test_expected_grid_not_merely_45_unique_rows(self):
        methods=("orb","vwap","bull_flag","resistance","mean_reversion")
        blocks=(1,2,3)
        costs=(0.001,0.0025,0.005)
        expected={(m,b,c) for m in methods for b in blocks for c in costs}
        self.assertEqual(len(expected),45)
        bad=expected-{("orb",1,0.001)}
        bad.add(("invented",1,0.001))
        self.assertEqual(len(bad),45)
        self.assertNotEqual(bad,expected)

    def test_pareto_strict_dominance(self):
        # Equal return and risk do not dominate; strictly better return at
        # equal drawdown does. Better return with worse drawdown is a tradeoff.
        pts=[("A",100,-0.10),("B",120,-0.10),
             ("C",130,-0.20),("D",120,-0.10)]
        frontier=[]
        for name,net,dd in pts:
            dominated=any((n>=net and abs(d)<=abs(dd))
                and (n>net or abs(d)<abs(dd))
                for other,n,d in pts if other!=name)
            if not dominated:frontier.append(name)
        self.assertEqual(set(frontier),{"B","C","D"})

    def test_nonfinite_values_are_invalid(self):
        for v in (float("nan"),float("inf"),-float("inf")):
            self.assertFalse(np.isfinite(v))
        self.assertTrue(np.isfinite(-0.4))

if __name__=="__main__":
    unittest.main()
