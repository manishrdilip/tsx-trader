"""Live monitor for the VMM TFSA during market hours. Plain-rule alerts, plus the AI drop check
(ai_judge): on a sudden stock-specific drop Claude and Gemini debate; if BOTH say it is real company bad news,
it sells that holding (only when DRY_RUN=false and TRADING_ENABLED=true).

Every check (every 5 min, 9:30-16:05 Toronto, one long job per day) it reads the account's holdings from the SnapTrade
snapshot and pushes a phone alert (ntfy app, topic NTFY_TOPIC) when a holding:
  - is down DROP_ALERT_PCT% or more today vs yesterday's close, or
  - trades below its 200-day average (the VMM sell line; the bot acts only on the close).
Each alert fires once per ticker per day (results/vmm_bot/alerts.json).
Usage: python live_watch.py snapshot.json [--test]
"""
import json, os, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd, yfinance as yf

TZ = ZoneInfo("America/Toronto")
TOPIC = os.environ.get("NTFY_TOPIC", "tsx-dilip-fe7bc02c")
DROP = float(os.environ.get("DROP_ALERT_PCT", "8"))
TRAIL = float(os.environ.get("VMM_TRAIL_PCT", "28") or 28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTECTED = {t.strip().upper() for t in os.environ.get("VMM_PROTECTED", "XIU.TO,AIQ.TO,SPCX.TO,SPCX").split(",") if t.strip()}
SEEN = os.path.join(ROOT, "results", "vmm_bot", "alerts.json")


def push(title, msg, priority="high", tags="warning"):
    req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=msg.encode(), method="POST",
                                 headers={"Title": title, "Priority": priority, "Tags": tags})
    try:
        urllib.request.urlopen(req, timeout=30)
        print("pushed:", title, "|", msg)
    except Exception as e:  # never let a notification failure stop the other checks
        print("push failed:", title, "|", e)


def ai_check(t, last, snap, seen, now):
    """Sudden stock-specific drop -> Claude + Gemini debate -> sell only if both agree it's real bad news."""
    try:
        sys.path.insert(0, ROOT)
        from ai_judge import judge
        res = judge.check_holding(t, last, "XIU.TO", now.date(), seen, os.path.join(ROOT, "results", "vmm_bot"))
    except Exception as e:
        print("ai check failed", t, e); return
    if not res:
        return
    det = res.get("detect", {})
    head = f"{t} {det.get('stock_chg_pct')}% vs XIU {det.get('market_chg_pct')}% ({det.get('z')} sigma). {res['summary']}"
    if res["decision"] != "SELL":
        push(f"AI drop check: KEEP {t}", head + " No action: the bot keeps it under its normal rules.", "high", "mag"); return
    judge.add_block(os.path.join(ROOT, "results", "vmm_bot", "ai_blocks.json"), t, now.date())
    live = os.environ.get("DRY_RUN", "true").lower() == "false" and os.environ.get("TRADING_ENABLED", "").lower() == "true"
    pos = [p for p in snap.get("positions", []) if to_yahoo(p.get("symbol")) == t and (p.get("units") or 0) > 0]
    units = int(sum(float(p["units"]) for p in pos)) if pos else 0
    if not live or units <= 0:
        push(f"AI drop check: SELL {t} (not sent)", head + (" Trading is off." if not live else " No whole shares held."), "urgent", "rotating_light"); return
    import subprocess, tempfile
    plan = {"orders": [{"action": "SELL", "ticker": t, "broker_symbol": pos[0]["symbol"], "units": units,
                        "limit": round(last * 0.97, 2), "reason": "AI drop check: both AIs agreed (company bad news)"}]}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump(plan, f); f.close()
    r = subprocess.run(["node", os.path.join(ROOT, "vmm_bot", "broker.mjs"), "execute", f.name, f.name + ".out"],
                       capture_output=True, text=True, timeout=300)
    print(r.stdout, r.stderr)
    try:
        res_out = json.load(open(f.name + ".out")).get("results", [])
    except Exception:
        res_out = []
    ok = r.returncode == 0 and any(x.get("action") == "SELL" and x.get("status") not in ("ERROR", "BLOCKED", "DRY_RUN")
                                   for x in res_out)
    push(f"AI drop check: SOLD {t}" if ok else f"AI drop check: SELL {t} FAILED", head + (
        f" Sell {units} @ {plan['orders'][0]['limit']} sent; not bought back for {judge.BLOCK_DAYS} days." if ok
        else f" Order problem: {(r.stdout + r.stderr)[-300:]} Check Wealthsimple."), "urgent", "rotating_light")


def to_yahoo(s):
    s = (s or "").upper()
    return s if "." in s else s + ".TO"


def main(snap_path, test=False):
    if test:
        push("VMM live monitor is on", "You'll get an alert on a big drop or a sell-line break.", "default", "white_check_mark")
        return
    now = datetime.now(TZ)
    if now.weekday() > 4 or not (9 * 60 + 30 <= now.hour * 60 + now.minute <= 16 * 60 + 5):
        print("market closed"); return
    snap = json.load(open(snap_path))
    today0 = now.date().isoformat()
    seen0 = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    try:
        xi = yf.download("XIU.TO", period="5d", interval="15m", progress=False, threads=False, multi_level_index=False)["Close"].dropna()
        xd = yf.download("XIU.TO", period="10d", interval="1d", progress=False, threads=False, multi_level_index=False)["Close"].dropna()
        vx = yf.download("^VIX", period="10d", interval="1d", progress=False, threads=False, multi_level_index=False)["Close"].dropna()
        xchg = (float(xi.iloc[-1]) / float(xd[xd.index.date < now.date()].iloc[-1]) - 1) * 100
        vl, vp = float(vx.iloc[-1]), float(vx.iloc[-2])
        why = ([f"XIU {xchg:+.1f}% today"] if xchg <= -2 else []) + ([f"VIX {vl:.1f}"] if vl >= 30 else []) \
              + ([f"VIX jumped {(vl/vp-1)*100:.0f}%"] if (vl / vp - 1) * 100 >= 20 else [])
        print(f"market: XIU {xchg:+.1f}%, VIX {vl:.1f}")
        if why and seen0.get("market:guard") != today0:
            push("MARKET SHOCK - guard mode", "; ".join(why) + ". Bot pauses new buys and VEQT selling; sell rules stay on. Watching every 10 min.", "urgent", "rotating_light")
            seen0["market:guard"] = today0
            json.dump(seen0, open(SEEN, "w"), indent=1)
    except Exception as e:
        print("market check failed:", e)
    tickers = sorted({to_yahoo(p["symbol"]) for p in snap["positions"] if p.get("symbol") and (p.get("units") or 0) > 0}
                     - PROTECTED)  # only stocks the bot manages
    if not tickers:
        print("no holdings"); return
    today = now.date().isoformat()
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    seen = {k: v for k, v in seen.items() if v == today}
    try:
        peaks = json.load(open(os.path.join(ROOT, "results", "vmm_bot", "state.json"))).get("peaks", {})
    except Exception:
        peaks = {}
    for t in tickers:  # one ticker at a time: avoids yfinance cache locks; one bad ticker never stops the rest
        try:
            daily = yf.download(t, period="1y", interval="1d", auto_adjust=False, progress=False, threads=False, multi_level_index=False)
            intra = yf.download(t, period="1d", interval="1m", auto_adjust=False, progress=False, threads=False, multi_level_index=False)
            d = daily["Close"].dropna()
            d = d[d.index.date < now.date()]
            last = float(intra["Close"].dropna().iloc[-1])
            prev = float(d.iloc[-1])
        except Exception as e:
            print(t, "no data:", e); continue
        sma = float(d.iloc[-200:].mean()) if len(d) >= 200 else None
        chg = (last / prev - 1) * 100
        print(f"{t}: {last:.2f} ({chg:+.1f}%), sell line {sma:.2f}" if sma else f"{t}: {last:.2f} ({chg:+.1f}%)")
        peak = peaks.get(t)
        trail_line = peak * (1 - TRAIL / 100) if peak else None
        slow = os.environ.get("VMM_MODE", "slow").strip().lower() == "slow"  # TFSA bot runs slow mode
        ai_check(t, last, snap, seen, now)
        if chg <= -DROP and seen.get(t + ":drop") != today:
            if slow:
                msg = f"Now {last:.2f} vs {prev:.2f} yesterday. Today the bot only sells if it closes below the 28% line" + (
                    f" ({trail_line:.2f})." if trail_line else ".")
                if sma and last < sma:
                    msg += f" It is below the 200d line ({sma:.2f}), so it sells at the next monthly review if still below."
            else:
                msg = f"Now {last:.2f} vs {prev:.2f} yesterday. No action needed unless it closes below the sell line" + (
                    f" ({sma:.2f})." if sma else ".")
            push(f"{t} down {chg:.1f}% today", msg)
            seen[t + ":drop"] = today
        if sma and last < sma and seen.get(t + ":line") != today:
            push(f"{t} below sell line", f"Now {last:.2f}, sell line {sma:.2f}. " + (
                 "If still below at the monthly review (1st run of the month, held 91+ days), the bot sells then"
                 + (f"; it sells sooner only below the 28% line ({trail_line:.2f})." if trail_line else ".")
                 if slow else "If it CLOSES below, the bot sells at the next run."), "urgent", "rotating_light")
            seen[t + ":line"] = today
        if peak and last <= peak * (1 - TRAIL / 100) and seen.get(t + ":trail") != today:
            push(f"{t} hit the 28% line", f"Now {last:.2f}, high {peak:.2f}, 28% line {peak*(1-TRAIL/100):.2f}. "
                 "If it closes there, the bot sells at the next run.", "urgent", "rotating_light")
            seen[t + ":trail"] = today
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, open(SEEN, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "", "--test" in sys.argv)
