# Batch 3 — reverse-engineering big winners (pre-registered before any result)

Question: before a TSX stock made a contest-style move, was there something observable that predicted it?

Event ("winner") at day i: an eligible stock whose close rises >= +50% at some point within the next 60 trading days.
Also recorded: "blow-up" = falls >= -30% within the next 60 days (to see if a condition just means "volatile").
Features at close i (causal only): r5, r20, r60, r120, r250, v20, v60, d50, d200, h52 (gap to 52w high), ldv (log dollar volume),
relvol (5d/60d volume), range20 compression (20d range / 120d range), price level, XIU above 200d, breadth (% stocks > 200d).
Sampled every 5th trading day per stock (to limit overlap).

Step 1 (dev 2009-2022 only): base rates; per-feature decile hit rates of winners and blow-ups; lift = hit rate / base rate.
Step 2 (dev only): decision tree (depth 3, min leaf 2% of rows) predicting winners; best leaf by
(winner rate - blow-up rate) with >= 500 dev rows becomes a buy rule.
Step 3: rule tested in the engine: $5,000, 10 slots, whole shares, next-open fills, 0.5%/side; exit at +50% target,
25% trailing stop, or 60 trading days. Dev first; eval 2023-latest once after committing the rule.
Pass bar unchanged (beat exact VMM by >= 3 pts in eval, DD no worse than VMM + 5, beat VMM in dev).
