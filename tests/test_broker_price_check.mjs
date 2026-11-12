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

const { preTradeCheck } = await import("../vmm_bot/broker.mjs");
const o = (action, sym, units, limit) => ({ action, ticker: sym + ".TO", broker_symbol: sym + ".TO", units, limit });
const snap = { cash_cad: 100, positions: [{ symbol: "AAA.TO", units: 10 }] };

test("never sells more than held", () => {
  const r = preTradeCheck([o("SELL", "AAA", 50, 1)], snap, []);
  assert.equal(r.keep[0].units, 10);
  assert.equal(preTradeCheck([o("SELL", "ZZZ", 5, 1)], snap, []).keep.length, 0);
});

test("skips orders already sent today", () => {
  const r = preTradeCheck([o("BUY", "BBB", 1, 10)], snap, [{ symbol: "BBB.TO", action: "BUY" }]);
  assert.equal(r.keep.length, 0);
});

test("unreadable broker history blocks buys, keeps sells", () => {
  const r = preTradeCheck([o("BUY", "BBB", 1, 10), o("SELL", "AAA", 1, 1)], snap, null);
  assert.deepEqual(r.keep.map((x) => x.action), ["SELL"]);
});

test("buys must fit in cash plus sell proceeds", () => {
  const r = preTradeCheck([o("SELL", "AAA", 10, 5), o("BUY", "BBB", 10, 10), o("BUY", "CCC", 10, 10)], snap, []);
  assert.deepEqual(r.keep.map((x) => x.ticker), ["AAA.TO", "BBB.TO"]); // 100 + 50 = 150 room
});

test("daily order limit stops everything", () => {
  const many = Array.from({ length: 3 }, (_, i) => ({ symbol: "X" + i, action: "BUY" }));
  assert.equal(preTradeCheck([o("SELL", "AAA", 1, 1)], snap, many, 3).keep.length, 0);
});
