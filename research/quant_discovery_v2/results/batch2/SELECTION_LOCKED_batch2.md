# Batch 2 selections, locked on dev (2009-2022) before any batch 2 evaluation run
DD limit = exact VMM dev DD (-30.3) + 5 = -35.3. Cost 0.50%/side.

| Exp | Selected | Dev CAGR | Dev DD | Note |
|---|---|---|---|---|
| 1 allocation | P2_cash (no parking) | 20.6 | -34.0 | P0 live permanent parking 8.3; P1 temporary 16.8; P3 dynamic XIU 13.7; P4 vol-size(cash) 16.5/-24.7; P5 20% DD brake(cash) 3.9 |
| 1 with deposits ($3,500 + $350/mo, TWR) | P2_cash | 20.2 TWR | -32.2 | permanent parking 8.5 TWR even with deposits |
| 2 GP (4,038 unique trees scored; 5,022 incl. rejects) | ('+', ('min', ('-','r60','ldv'), ('+','d200','relvol20')), 'r250') in VMM frame, 20 slots | 19.7 | -33.3 | fast-screen 42.8%/yr, Deflated Sharpe prob 0.575 (< 0.95: not significant) |
| 3 statistical ranking | E3_S1_residual_mom | 20.4 | -34.1 | S2 14.9, S3 5.4, S4 13.5 |
| 4 multi-strategy | none met rule (needs dev CAGR >= 15.6) | | | nearest VMM_nopark+D squeeze 15.4/-21.0, Sharpe 1.04 (evaluated for information only) |
| 5 Little Rizzy | none (both settings break DD limit: -49.4, -61.7) | 8.9 / -1.8 | | FAIL |
| 6 vol/trend asymmetry | E6_q0.8_m1.5_b0.5 | 11.1 | -16.6 | 8 settings, range 4.6-11.1 |
No batch 2 candidate beats VMM_nopark/P2 dev (20.6) except none; residual momentum 20.4 is a tie.
