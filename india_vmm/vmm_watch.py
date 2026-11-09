"""India VMM watcher, run on the India server.

  python india_vmm/vmm_watch.py         every 5 min 9:15-15:30 IST: alerts + watchdog (no trading itself)
  python india_vmm/vmm_watch.py --pre   ~9:05 IST: pre-market Telegram report

Alerts (Telegram, once per day each):
  - a bot holding within 5% of its 200-day sell line, or below it
  - a bot order filled / rejected / cancelled
  - AM run missing at 9:55 or PM run missing at 15:05 -> starts the run itself (watchdog)
Also writes results/india_vmm/alerts.json and publishes results (india_vmm/publish.py).
"""
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import run as vmm  # noqa: E402  (loads .env and the Kite token)

ALERTS = os.path.join(vmm.OUT, "alerts.json")
NEAR = 0.05


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def main():
    pre = "--pre" in sys.argv
    now = vmm.ist_now()
    today = now.date().isoformat()
    hm = now.hour * 100 + now.minute
    if now.weekday() >= 5:
        return
    state = vmm.load_state()
    al = load(ALERTS, {})
    if al.get("date") != today:
        al = {"date": today, "sent": [], "seen_orders": {}, "log": []}

    def alert(key, text):
        if key in al["sent"]:
            return
        al["sent"].append(key)
        al["log"].append({"time": now.strftime("%H:%M"), "text": text})
        vmm.notify(text)

    from broker import KiteBroker
    try:
        b = KiteBroker()
        hold = {h["tradingsymbol"].upper() + ".NS": h for h in b.k.holdings() if int(h.get("quantity") or 0) > 0}
        orders = [o for o in b.k.orders() if (o.get("tag") or "") == "indiavmm"]
        cash = b.cash()
    except Exception as e:
        alert("broker-error", f"India VMM watch: cannot reach Zerodha ({e}). Token refresh or IP problem?")
        vmm.save_json(ALERTS, al)
        return

    ledger = state.get("ledger", {})
    lines = state.get("lines", {})
    rows = []
    for t, q in sorted(ledger.items()):
        h = hold.get(t)
        ln = lines.get(t, {})
        ltp = float(h.get("last_price") or 0) if h else 0.0
        sma = ln.get("sma200")
        gap = (ltp / sma - 1) if (sma and ltp) else None
        rows.append((t, q, ltp, sma, gap, ln.get("r12")))
        if gap is not None and not pre:
            if gap < 0:
                alert(f"below:{t}", f"India VMM: {t[:-3]} {ltp:.2f} is BELOW its 200-day line {sma:.2f}. "
                                    f"Likely sold at the next run if it closes there.")
            elif gap < NEAR:
                alert(f"near:{t}", f"India VMM: {t[:-3]} {ltp:.2f} is {gap * 100:.1f}% above its 200-day line {sma:.2f}.")

    if pre:
        kc = state.get("keep_cut")
        msg = [f"India VMM pre-market {today}",
               f"Trading {'ON' if os.environ.get('TRADING_ENABLED', '').lower() == 'true' else 'OFF (dry run)'}; "
               f"market filter {'ON' if state.get('market_ok') else 'OFF (no new buys)'}; cash Rs {cash:,.0f}",
               f"Keep cut (12m): {kc * 100:.0f}%" if kc is not None else "Keep cut: n/a"]
        for t, q, ltp, sma, gap, r12 in rows:
            flag = ""
            if gap is not None and gap < 0:
                flag = "  <-- BELOW 200d"
            elif gap is not None and gap < NEAR:
                flag = "  <-- within 5% of 200d"
            if r12 is not None and kc is not None and r12 < kc:
                flag += "  <-- 12m below keep cut"
            msg.append(f"{t[:-3]} x{q}: {ltp:.2f}, 200d {sma}, "
                       f"{'n/a' if gap is None else f'{gap * 100:+.1f}%'}, 12m "
                       f"{'n/a' if r12 is None else f'{r12 * 100:.0f}%'}{flag}")
        if not rows:
            msg.append("No bot holdings yet.")
        msg.append("Runs today: 9:40 and 14:45.")
        vmm.notify("\n".join(msg))
    else:
        for o in orders:
            oid, st = str(o.get("order_id")), o.get("status")
            if st in ("COMPLETE", "REJECTED", "CANCELLED") and al["seen_orders"].get(oid) != st:
                al["seen_orders"][oid] = st
                extra = f" ({o.get('status_message')})" if st != "COMPLETE" and o.get("status_message") else ""
                alert(f"order:{oid}:{st}", f"India VMM order {st}: {o.get('transaction_type')} {o.get('quantity')} "
                                           f"{o.get('tradingsymbol')} @ {o.get('average_price') or o.get('price')}{extra}")
        for slot, due in (("AM", 955), ("PM", 1505)):
            if hm >= due and hm < 1520 and not vmm.slot_done(state, today, slot):
                if (slot == "PM" or hm < 1330) and f"watchdog:{slot}" not in al["sent"]:
                    alert(f"watchdog:{slot}", f"India VMM: {slot} run missing at {now:%H:%M}; starting it now.")
                    subprocess.run(["flock", "-n", "/tmp/india_vmm.lock", sys.executable,
                                    os.path.join(HERE, "run.py"), "--live"], timeout=900)

    vmm.save_json(ALERTS, al)
    try:
        import publish
        publish.main()
    except Exception as e:
        print("publish failed:", e)


if __name__ == "__main__":
    main()
