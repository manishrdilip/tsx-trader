from india_vmm.broker import main_board


def test_main_board_keeps_stocks_drops_series_and_bonds():
    for s in ["RELIANCE", "BAJAJ-AUTO", "MCDOWELL-N", "M&M", "3MINDIA", "360ONE"]:
        assert main_board(s), s
    for s in ["ZEEMEDIA-BE", "VELS-SM", "UCL-ST", "URBAN-RE", "VIVIMEDLAB-BZ", "1003SCFL31-Z4",
              "1065NFL27-NC", "SGBMAR29-GB", "364D201126-TB"]:
        assert not main_board(s), s
