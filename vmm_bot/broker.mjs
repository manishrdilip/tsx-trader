// SnapTrade broker I/O for the VMM bot. Personal API key auth (no user secret needed).
// Usage:
//   node broker.mjs snapshot <out.json>        -> positions, cash, open orders of the pinned account
//   node broker.mjs check <orders.json>        -> verify each symbol resolves to a quote (no trading)
//   node broker.mjs execute <orders.json> <out.json>  -> place orders ONLY if DRY_RUN=false and TRADING_ENABLED=true
import { Snaptrade, SnaptradeAuth } from "snaptrade-typescript-sdk";
import fs from "fs";

const { SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, VMM_ACCOUNT_ID } = process.env;
const DRY_RUN = (process.env.DRY_RUN ?? "true").toLowerCase() !== "false";
const ENABLED = (process.env.TRADING_ENABLED ?? "false").toLowerCase() === "true";
const MAX_ORDER = Number(process.env.MAX_ORDER_CAD ?? "800");
const MAX_ORDERS = Number(process.env.MAX_ORDERS_PER_RUN ?? "25");

function die(msg) { console.error("FATAL: " + msg); process.exit(1); }
if (!process.env.VMM_TEST) {
  if (!SNAPTRADE_CLIENT_ID || !SNAPTRADE_CONSUMER_KEY) die("SnapTrade secrets missing");
  if (!VMM_ACCOUNT_ID) die("VMM_ACCOUNT_ID missing (pinned account)");
}

const st = new Snaptrade({ auth: SnaptradeAuth.personalApiKey({ clientId: SNAPTRADE_CLIENT_ID, consumerKey: SNAPTRADE_CONSUMER_KEY }) });
const acct = VMM_ACCOUNT_ID;
const num = (v) => (v == null ? null : Number(v));

async function snapshot(out) {
  const [pos, bal, ord] = await Promise.all([
    st.accountInformation.getAllAccountPositions({ accountId: acct }),
    st.accountInformation.getUserAccountBalance({ accountId: acct }),
    st.accountInformation.getUserAccountOrders({ accountId: acct, state: "open" }),
  ]);
  const raw = pos.data?.results ?? pos.data ?? [];
  const positions = raw.map((p) => {
    const i = p.instrument ?? p.symbol?.symbol ?? {};
    return { symbol: i.raw_symbol || i.symbol, units: num(p.units), price: num(p.price), currency: i.currency?.code || i.currency || p.currency };
  });
  const cad = (bal.data || []).find((b) => (b.currency?.code || b.currency) === "CAD") || (bal.data || [])[0] || {};
  const snap = {
    account_id: acct, time: new Date().toISOString(),
    cash_cad: num(cad.cash) ?? 0, buying_power_cad: num(cad.buying_power),
    positions,
    open_orders: (ord.data || []).map((o) => ({ id: o.brokerage_order_id, symbol: o.universal_symbol?.symbol || o.symbol, action: o.action, units: num(o.total_quantity), status: o.status })),
  };
  fs.writeFileSync(out, JSON.stringify(snap, null, 2));
  console.log(`snapshot: ${positions.length} positions, cash CAD ${snap.cash_cad}`);
}

function guard(orders, plan = {}) {
  // per-order cap scales with the account (plan.order_cap), but never above 25% of its money
  const cap = Math.max(MAX_ORDER, Math.min(Number(plan.order_cap) || 0, 0.25 * (Number(plan.equity_cad) || 0)));
  if (orders.length > MAX_ORDERS) die(`too many orders (${orders.length} > ${MAX_ORDERS})`);
  for (const o of orders) {
    if (!["BUY", "SELL"].includes(o.action)) die(`bad action ${o.action}`);
    if (!(o.units > 0) || !Number.isInteger(o.units)) die(`bad units for ${o.symbol}`);
    if (!(o.limit > 0)) die(`no limit price for ${o.symbol}`);
    if (o.action === "BUY" && o.units * o.limit > cap + 0.01) die(`${o.symbol} order $${(o.units * o.limit).toFixed(2)} exceeds order cap ${cap.toFixed(2)}`);
  }
}

const PRICE_BAND = Number(process.env.VMM_PRICE_BAND_PCT ?? "15") / 100;

// Pure helper (unit-tested): compare each order's reference close with the broker's live price.
// BUY with no broker quote, or live price more than PRICE_BAND away -> dropped (likely bad Yahoo data).
// SELL is never blocked (exits must go through); a mismatch only adds a warning.
export function priceCheck(orders, quotes, band = PRICE_BAND) {
  const keep = [], warnings = [];
  for (const o of orders) {
    const ref = o.action === "BUY" ? o.limit / 1.01 : o.limit / 0.97;
    const live = quotes[o.broker_symbol];
    const off = live > 0 ? Math.abs(live / ref - 1) : null;
    if (o.action === "BUY" && (off === null || off > band)) {
      warnings.push(`${o.ticker}: BUY skipped, ${off === null ? "no broker quote" : `broker ${live} vs data ${ref.toFixed(2)} (${(off * 100).toFixed(0)}% apart)`}`);
      continue;
    }
    if (o.action === "SELL" && off !== null && off > band)
      warnings.push(`${o.ticker}: SELL kept, but broker ${live} vs data ${ref.toFixed(2)} (${(off * 100).toFixed(0)}% apart) - check prices`);
    keep.push(o);
  }
  return { keep, warnings };
}

// Pure helper (unit-tested): last safety layer before any order is sent, using broker truth.
//  1. never sell more shares than the account holds (no accidental short); 0 held -> sell dropped
//  2. idempotency: skip any symbol+action already sent to the broker today (protects against a
//     re-run after a failed state commit, a ghost run, or a manual Run workflow)
//  3. if the account already sent MAX_ORDERS today -> send nothing more (runaway-loop breaker)
//  4. total BUY cost must fit in cash + this run's sell proceeds; extra buys are dropped
//  5. todayOrders === null (broker order history unreadable) -> no BUYs this run; sells still go
export function preTradeCheck(orders, snap, todayOrders, maxOrders = MAX_ORDERS) {
  const keep = [], warnings = [];
  const held = {};
  for (const p of snap?.positions || []) if (p.symbol) held[String(p.symbol).toUpperCase()] = (held[String(p.symbol).toUpperCase()] || 0) + Math.floor(Number(p.units) || 0);
  const sent = new Set((todayOrders || []).map((o) => `${String(o.action).toUpperCase()}:${String(o.symbol).toUpperCase()}`));
  if (todayOrders && todayOrders.length >= maxOrders) {
    return { keep: [], warnings: [`daily order limit: ${todayOrders.length} orders already sent today, nothing more sent`] };
  }
  for (let o of orders) {
    const sym = String(o.broker_symbol).toUpperCase();
    if (sent.has(`${o.action}:${sym}`)) { warnings.push(`${o.ticker}: ${o.action} skipped, already sent to the broker today`); continue; }
    if (o.action === "BUY" && todayOrders === null) { warnings.push(`${o.ticker}: BUY skipped, could not read today's broker orders`); continue; }
    if (o.action === "SELL") {
      const h = held[sym] ?? held[sym.replace(/\.TO$/, "")] ?? 0;
      if (h <= 0) { warnings.push(`${o.ticker}: SELL dropped, account holds 0 shares`); continue; }
      if (o.units > h) { warnings.push(`${o.ticker}: SELL cut from ${o.units} to ${h} shares (all that is held)`); o = { ...o, units: h }; }
    }
    keep.push(o);
  }
  let room = (Number(snap?.cash_cad) || 0) + keep.filter((o) => o.action === "SELL").reduce((a, o) => a + o.units * o.limit, 0);
  const out = [];
  for (const o of keep) {
    if (o.action === "BUY") {
      const cost = o.units * o.limit;
      if (cost > room + 0.01) { warnings.push(`${o.ticker}: BUY dropped, $${cost.toFixed(2)} is more than cash left $${room.toFixed(2)}`); continue; }
      room -= cost;
    }
    out.push(o);
  }
  return { keep: out, warnings };
}

async function todaysOrders() {
  try {
    const r = await st.accountInformation.getUserAccountOrders({ accountId: acct, state: "all", days: 1 });
    const today = new Date().toLocaleDateString("en-CA", { timeZone: "America/Toronto" });
    return (r.data || [])
      .filter((o) => !o.time_placed || new Date(o.time_placed).toLocaleDateString("en-CA", { timeZone: "America/Toronto" }) === today)
      .filter((o) => !/REJECT|FAILED/i.test(String(o.status || "")))
      .map((o) => ({ symbol: o.universal_symbol?.symbol || o.symbol?.symbol || o.symbol, action: o.action, status: o.status }));
  } catch (e) {
    console.error("could not read today's orders:", e?.message || e);
    return null;
  }
}

async function check(file) {
  const plan = JSON.parse(fs.readFileSync(file, "utf8"));
  const { orders } = plan;
  guard(orders, plan);
  if (!orders.length) { console.log("no orders to check"); return; }
  const syms = [...new Set(orders.map((o) => o.broker_symbol))].join(",");
  const q = await st.trading.getUserAccountQuotes({ accountId: acct, symbols: syms, useTicker: true });
  const quotes = {};
  for (const x of q.data || []) {
    const s = x.symbol?.symbol || x.symbol?.raw_symbol;
    const bid = num(x.bid_price), ask = num(x.ask_price);
    const live = num(x.last_trade_price) || (bid > 0 && ask > 0 ? (bid + ask) / 2 : null);
    if (s) quotes[s] = live;
  }
  const { keep, warnings } = priceCheck(orders, quotes);
  for (const o of orders) console.log(`${o.broker_symbol}: broker ${quotes[o.broker_symbol] ?? "NOT FOUND"}`);
  for (const w of warnings) console.log("PRICE CHECK: " + w);
  plan.orders = keep;
  plan.price_check = warnings;
  plan.notes = [...(plan.notes || []), ...warnings.map((w) => "Price check: " + w)];
  fs.writeFileSync(file, JSON.stringify(plan, null, 2));
}

async function execute(file, out) {
  const plan = JSON.parse(fs.readFileSync(file, "utf8"));
  const { orders } = plan;
  guard(orders, plan);
  const results = [];
  const live = !DRY_RUN && ENABLED;
  if (live) {
    let snap = null;
    try { snap = JSON.parse(fs.readFileSync(process.env.SNAP_FILE || "/tmp/snap.json", "utf8")); } catch { die("no account snapshot: refusing to trade"); }
    const { keep, warnings } = preTradeCheck(orders, snap, await todaysOrders());
    for (const w of warnings) { console.log("PRE-TRADE: " + w); results.push({ action: "-", units: 0, ticker: "", broker_symbol: "", limit: 0, status: "BLOCKED", error: w }); }
    orders.length = 0; orders.push(...keep);
  }
  console.log(live ? "LIVE MODE: placing orders" : `DRY RUN (DRY_RUN=${DRY_RUN}, TRADING_ENABLED=${ENABLED}): no orders sent`);
  // sells first so a failed buy never leaves an unintended position
  for (const o of [...orders].sort((a, b) => (a.action === "SELL" ? -1 : 1))) {
    if (!live) { results.push({ ...o, status: "DRY_RUN" }); continue; }
    try {
      const r = await st.trading.placeForceOrder({
        account_id: acct, action: o.action, symbol: o.broker_symbol,
        order_type: "Limit", price: o.limit, time_in_force: "Day", units: o.units,
      });
      results.push({ ...o, status: r.data?.status || "SUBMITTED", order_id: r.data?.brokerage_order_id });
    } catch (e) {
      results.push({ ...o, status: "ERROR", error: String(e?.responseBody ? JSON.stringify(e.responseBody) : e?.message || e).slice(0, 300) });
    }
  }
  fs.writeFileSync(out, JSON.stringify({ live, results }, null, 2));
  for (const r of results) console.log(`${r.status} ${r.action} ${r.units} ${r.broker_symbol} @ ${r.limit}${r.error ? " :: " + r.error : ""}`);
}

const [cmd, a, b] = process.argv.slice(2);
if (!process.env.VMM_TEST) try {
  if (cmd === "snapshot") await snapshot(a);
  else if (cmd === "check") await check(a);
  else if (cmd === "execute") await execute(a, b);
  else die("unknown command");
} catch (e) {
  die(e?.responseBody ? JSON.stringify(e.responseBody) : e?.message || String(e));
}
