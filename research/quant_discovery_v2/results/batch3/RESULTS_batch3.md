# Batch 3: reverse-engineering big winners (25 Nov 2026)
Protocol committed before results; rule locked before the engine test; eval run once.

Dev 2009-22, 188,063 stock-days (every 5th day, eligible TSX stocks incl. delisted):
- Base rate: 4.9% of stock-days were followed by a +50% move within 60 days; 9.1% by a -30% fall.
- The strongest "predictors" of winners are high volatility, deep drops below the 52w high / 200d, low price, big 12m losses.
  Every one of them predicts blow-ups too: top-decile 60d volatility = 20.9% winners but 21.3% blow-ups; median 60d return +4%.
- Best decision-tree leaf (v60 > 3.7%/day and close >= 43% under its 200d): 34.2% winners, 28.9% blow-ups, median 60d +10%.

Rule test ($5,000, 10 slots, +50% target / 25% trail / 60 days, 0.5%/side):
| Period | CAGR | Max DD | Trades | Win rate |
|---|---|---|---|---|
| Dev 2009-22 | 6.1% | -57.2% | 624 | 38.9% |
| Eval 2023-26 | 9.7% | -26.1% | 110 | 41.8% |
Exact VMM: dev 8.3% / -30.3%, eval 26.1% / -15.3%. FAIL.

Conclusion: in hindsight big winners share one trait: they were wild, beaten-down, cheap stocks. But before the move those
stocks are just as likely to collapse. The rare clean predictor of big up-moves in price data is momentum (already VMM).
