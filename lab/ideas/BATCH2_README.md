# Batch 2: Trading Mechanisms Catalog

## Ideas by Family
- Yield: 11
- Cross-Asset: 20
- Sentiment: 20
- Macro: 20
- Seasonality: 20
- Corporate Action: 20
- Flow: 20
- Fundamentals: 20
- Options: 15
- Alternative: 14
- Microstructure: 20
Total: 200

## 20 Most Promising Rows

1. **Yield Steepener Banks**: Banks borrow short and lend long; steep curves expand net interest margin.
2. **Rate Cut Utilities**: Lower rates make dividend yields of utilities more attractive relative to bonds.
3. **Oil Spike Energy**: Energy producers' revenue jumps directly with crude prices.
4. **Copper Deficit Miners**: LME inventory drops signal supply squeeze, benefiting base metal miners.
5. **Gold CPI Hedge**: Unexpected inflation spikes drive immediate haven flows into gold equities.
6. **CAD Weakness Exporters**: A weaker CAD immediately boosts foreign revenue margins for Canadian exporters.
7. **Lumber Housing Boom**: Lumber futures leading indicator for homebuilder margins.
8. **Employment Surprise**: NFP massive beats signal economic acceleration for consumer discretionary.
9. **Sovereign Downgrade Safe Haven**: US debt downgrade causes panic buying into mega-cap tech as a cash proxy.
10. **Money Supply Expansion**: M2 growth in India directly correlates with mid-cap speculation.
11. **Credit Spread Tightening**: High yield spreads compressing signals risk-on for highly levered small caps.
12. **Consumer Sentiment Spike**: UoM sentiment bounce precedes retail sales jumps.
13. **Real Rates Proxy**: Negative real rates force capital into hard assets.
14. **GDP Revision Momentum**: Positive GDP revisions trigger foreign institutional allocations.
15. **Baltic Dry Surge**: BDI spikes indicate raw material demand and global trade expansion.
16. **Semiconductor Billings Rise**: Semi billings are the earliest indicator of tech hardware cycles.
17. **Housing Starts Beat**: US housing starts drive Canadian lumber and construction materials.
18. **PMI Expansion**: Manufacturing PMI crossing 50 signals cyclical recovery.
19. **Fed vs BoC Divergence**: When Fed hikes and BoC holds, CAD drops, boosting US-exposed TSX stocks.
20. **Commodity Currency Carry**: High yield + rising oil creates massive capital inflows to Canada.

## Testing Rules

> in-sample is 2009-01 to 2022-12 only. **2023-2026 is held out — never run it.** Costs are 0.5%/side for TSX and 0.1%/side for ETFs. Signal at close t, fill at t+1. No margin. Starts every January from 1999 (or the earliest data available). Benchmark is the live VMM bot (vmm_bot/plan.py). Log every variant in TRIALS.md.
