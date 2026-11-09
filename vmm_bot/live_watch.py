"""Live monitor for the VMM TFSA during market hours. Plain rules, no AI, never trades.

Every run (every 10 min, 9:30-16:00 Toronto) it reads the account's holdings from the SnapTrade
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
    tickers = sorted({to_yahoo(p["symbol"]) for p in snap["positions"] if p.get("symbol") and (p.get("units") or 0) > 0}
                     - PROTECTED)  # only stocks the bot manages
    if not tickers:
        print("no holdings"); return
    today = now.date().isoformat()
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    seen = {k: v for k, v in seen.items() if v == today}
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
        if chg <= -DROP and seen.get(t + ":drop") != today:
            push(f"{t} down {chg:.1f}% today", f"Now {last:.2f} vs {prev:.2f} yesterday. No action needed unless it closes below the sell line"
                 + (f" ({sma:.2f})." if sma else "."))
            seen[t + ":drop"] = today
        if sma and last < sma and seen.get(t + ":line") != today:
            push(f"{t} below sell line", f"Now {last:.2f}, sell line {sma:.2f}. If it CLOSES below, the bot sells at tomorrow's open.", "urgent", "rotating_light")
            seen[t + ":line"] = today
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, open(SEEN, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "", "--test" in sys.argv)
