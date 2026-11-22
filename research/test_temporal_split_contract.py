"""Research-only chronological split contract; synthetic data, no broker access."""
import unittest
from unittest.mock import patch
import pandas as pd
from research import temporal_stability as ts

class TemporalSplitContract(unittest.TestCase):
    def test_three_blocks_have_no_overlapping_sessions_and_fixed_universe(self):
        days=pd.bdate_range("2026-08-03",periods=36,tz="America/Toronto")
        sessions=[str(x.date()) for x in days]
        boundaries=[0,len(sessions)//3,2*len(sessions)//3,len(sessions)]
        blocks=[set(sessions[boundaries[i]:boundaries[i+1]]) for i in range(3)]
        self.assertEqual(len(set.union(*blocks)),len(sessions))
        for i in range(3):
            for j in range(i+1,3):
                self.assertFalse(blocks[i]&blocks[j])
            self.assertLessEqual(min(blocks[i]),max(blocks[i]))
        self.assertLess(max(blocks[0]),min(blocks[1]))
        self.assertLess(max(blocks[1]),min(blocks[2]))

    def test_short_history_cannot_be_presented_as_verified_cagr(self):
        self.assertEqual(ts.COSTS,(0.001,0.0025,0.005))
        self.assertEqual(len(ts.METHODS),5)
        self.assertEqual(len(ts.COSTS)*len(ts.METHODS)*3,45)
        self.assertEqual(ts.core.START_CASH,5000)

if __name__=="__main__":
    unittest.main()
