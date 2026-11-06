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
if (!SNAPTRADE_CLIENT_ID || !SNAPTRADE_CONSUMER_KEY) die("SnapTrade secrets missing");
if (!VMM_ACCOUNT_ID) die("VMM_ACCOUNT_ID missing (pinned account)");

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

async function check(file) {
  const plan = JSON.parse(fs.readFileSync(file, "utf8"));
  const { orders } = plan;
  guard(orders, plan);
  if (!orders.length) { console.log("no orders to check"); return; }
  const syms = [...new Set(orders.map((o) => o.broker_symbol))].join(",");
  const q = await st.trading.getUserAccountQuotes({ accountId: acct, symbols: syms, useTicker: true });
  const found = new Set((q.data || []).map((x) => x.symbol?.symbol || x.symbol?.raw_symbol));
  for (const o of orders) console.log(`${o.broker_symbol}: ${found.has(o.broker_symbol) ? "OK" : "NOT FOUND by broker"}`);
}

async function execute(file, out) {
  const plan = JSON.parse(fs.readFileSync(file, "utf8"));
  const { orders } = plan;
  guard(orders, plan);
  const results = [];
  const live = !DRY_RUN && ENABLED;
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
try {
  if (cmd === "snapshot") await snapshot(a);
  else if (cmd === "check") await check(a);
  else if (cmd === "execute") await execute(a, b);
  else die("unknown command");
} catch (e) {
  die(e?.responseBody ? JSON.stringify(e.responseBody) : e?.message || String(e));
}
