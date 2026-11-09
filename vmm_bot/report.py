"""Writes results/vmm_bot/report.md + log, saves state only after a live run, sends Telegram if configured.
Usage: python report.py plan.json exec.json
"""
import json, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from notifier import send_telegram  # noqa: E402

import urllib.request
TOPIC = os.environ.get("NTFY_TOPIC", "tsx-dilip-fe7bc02c")


def push(title, msg, priority="default", tags="chart_with_upwards_trend"):
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=msg.encode(), method="POST",
                               headers={"Title": title, "Priority": priority, "Tags": tags}), timeout=30)
    except Exception as e:
        print("push failed", e)


OUT = os.path.join(ROOT, "results", "vmm_bot")


def main(plan_path, exec_path):
    if not os.path.exists(plan_path):
        msg = "*VMM bot*: stopped before planning (see the Snapshot/Plan step log). No orders placed."
        send_telegram(msg); print(msg); return
    plan = json.load(open(plan_path))
    ex = json.load(open(exec_path)) if os.path.exists(exec_path) else {"live": False, "results": []}
    os.makedirs(OUT, exist_ok=True)
    mode = "LIVE" if ex["live"] else "DRY RUN"
    L = [f"# VMM bot — {dt.date.today()} ({mode})",
         f"Signals from close of {plan['signal_date']}. Account equity ${plan['equity_cad']:,.2f}, cash ${plan['cash_cad']:,.2f}.",
         f"XIU above 200-day: {'yes' if plan['xiu_ok'] else 'NO (new buys paused)'}. Momentum share {plan['mom_share']*100:.0f}%.", ""]
    res = ex["results"] or [dict(o, status="PLANNED") for o in plan["orders"]]
    if res:
        L += ["| Status | Action | Shares | Stock | Limit | Why |", "|---|---|---|---|---|---|"]
        L += [f"| {r['status']} | {r['action']} | {r['units']} | {r['ticker']} | {r['limit']} | {r.get('reason','')}{' — '+r['error'] if r.get('error') else ''} |" for r in res]
    else:
        L.append("No orders today.")
    if plan["holdings"]:
        L += ["", "| Holding | Close | Sell line (200d) | % above | 12m % |", "|---|---|---|---|---|"]
        L += [f"| {h['ticker']} | {h['close']} | {h['sell_line']} | {h['pct_above']} | {h['r12_pct']} |" for h in plan["holdings"]]
    L += [""] + [f"- {n}" for n in plan["notes"]]
    md = "\n".join(L)
    open(os.path.join(OUT, "report.md"), "w").write(md + "\n")
    with open(os.path.join(OUT, "log.jsonl"), "a") as f:
        f.write(json.dumps({"date": str(dt.date.today()), "mode": mode, "plan": plan, "exec": ex}) + "\n")
    if ex["live"]:
        json.dump(plan["new_state"], open(os.path.join(OUT, "state.json"), "w"), indent=2)
    lines = [f"*VMM bot ({mode})* {dt.date.today()}"]
    lines += [f"{r['status']} {r['action']} {r['units']} {r['ticker']} @ {r['limit']}" for r in res] or ["No orders today."]
    errs = [r for r in res if r["status"] == "ERROR"]
    if errs:
        lines.append(f"⚠️ {len(errs)} order error(s) — check report.md")
    send_telegram("\n".join(lines))
    sells = [r for r in res if r["action"] == "SELL"]
    buys = [r for r in res if r["action"] == "BUY"]
    body = [f"{r['status']} {r['action']} {r['units']} {r['ticker']} @ {r['limit']} ({r.get('reason','')[:60]})" for r in res]
    if plan.get("guard"):
        body.insert(0, "GUARD MODE: " + "; ".join(plan["guard"]) + " - no new buys today")
    body.append(f"Idle cash after orders: ${plan.get('idle_cash', 0):,.2f}")
    if errs:
        body.append(f"{len(errs)} order error(s) - check report.md")
    title = f"VMM {plan.get('run_slot','')} run: {len(sells)} sell, {len(buys)} buy" + (" (GUARD)" if plan.get("guard") else "")
    push(title, "\n".join(body), "high" if (sells or errs or plan.get("guard")) else "default",
         "warning" if (errs or plan.get("guard")) else "moneybag")
    print(md)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
