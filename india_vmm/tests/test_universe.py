import unittest
from india_vmm.broker import main_board


def test_main_board_keeps_stocks_drops_series_and_bonds():
    for s in ["RELIANCE", "BAJAJ-AUTO", "MCDOWELL-N", "M&M", "3MINDIA", "360ONE"]:
        assert main_board(s), s
    for s in ["ZEEMEDIA-BE", "VELS-SM", "UCL-ST", "URBAN-RE", "VIVIMEDLAB-BZ", "1003SCFL31-Z4",
              "1065NFL27-NC", "SGBMAR29-GB", "364D201126-TB"]:
        assert not main_board(s), s


class SameDayPositions(unittest.TestCase):
    def test_today_buys_and_sells_merge_into_holdings(self):
        from india_vmm.broker import merge_day_positions
        net = [{"product": "CNC", "exchange": "NSE", "tradingsymbol": "NINSYS", "quantity": 1},
               {"product": "CNC", "exchange": "NSE", "tradingsymbol": "WIPRO", "quantity": -8},
               {"product": "MIS", "exchange": "NSE", "tradingsymbol": "SBIN", "quantity": 5}]
        out = merge_day_positions({"WIPRO.NS": 8, "TRIDENT.NS": 13}, net)
        self.assertEqual(out, {"NINSYS.NS": 1, "TRIDENT.NS": 13})
