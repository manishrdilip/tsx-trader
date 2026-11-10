// Offline test of the broker price check. Run: VMM_TEST=1 node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
process.env.VMM_TEST = "1";
const { priceCheck } = await import("../vmm_bot/broker.mjs");

const buy = (t, close) => ({ action: "BUY", ticker: t + ".TO", broker_symbol: t, units: 1, limit: +(close * 1.01).toFixed(2) });
const sell = (t, close) => ({ action: "SELL", ticker: t + ".TO", broker_symbol: t, units: 1, limit: +(close * 0.97).toFixed(2) });

test("normal daily move passes", () => {
  const r = priceCheck([buy("AAA", 10)], { AAA: 9.3 }, 0.15); // -7% today
  assert.equal(r.keep.length, 1);
  assert.equal(r.warnings.length, 0);
});

test("bad data blocks the buy", () => {
  const r = priceCheck([buy("AAA", 10)], { AAA: 5 }, 0.15);
  assert.equal(r.keep.length, 0);
  assert.match(r.warnings[0], /BUY skipped/);
});

test("missing broker quote blocks the buy", () => {
  assert.equal(priceCheck([buy("AAA", 10)], {}, 0.15).keep.length, 0);
});

test("sell always goes through, with a warning on mismatch", () => {
  const r = priceCheck([sell("BBB", 10)], { BBB: 5 }, 0.15);
  assert.equal(r.keep.length, 1);
  assert.match(r.warnings[0], /SELL kept/);
  assert.equal(priceCheck([sell("BBB", 10)], {}, 0.15).keep.length, 1);
});
