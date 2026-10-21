"""Watches your open positions (positions.csv) during market hours and pushes a phone alert
(ntfy app, topic in NTFY_TOPIC) when a take-profit or stop is reached, and on the day-30 exit.
Each alert is sent once; the status column is updated and committed by the workflow."""
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo
import urllib.request

import pandas as pd

TOPIC = os.environ.get("NTFY_TOPIC", "tsx-dilip-fe7bc02c")
TZ = ZoneInfo("America/Toronto")
FILE = "positions.csv"


def push(title, msg, priority="urgent", tags="money_with_wings"):
    req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=msg.encode(), method="POST",
                                 headers={"Title": title, "Priority": priority, "Tags": tags})
    urllib.request.urlopen(req, timeout=30)
    print("pushed:", title)


def last_price(t):
    import yfinance as yf
    d = yf.download(t, period="1d", interval="1m", progress=False, auto_adjust=False)
    if d is None or d.empty:
        return None, None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return float(d["Close"].dropna().iloc[-1]), (float(d["High"].max()), float(d["Low"].min()))


def main():
    now = datetime.now(TZ)
    test = "--test" in sys.argv
    if test:
        push("TSX alerts are working", "You'll get a message here when a target or stop is hit.", "default", "white_check_mark")
        return
    if now.weekday() > 4 or not (9 * 60 + 30 <= now.hour * 60 + now.minute <= 16 * 60 + 5):
        print("market closed", now)
        return
    pos = pd.read_csv(FILE, dtype=str, keep_default_na=False)
    changed = False
    for i, p in pos.iterrows():
        if p.status != "open":
            continue
        sh, stop, tgt = int(p.shares), float(p.stop), float(p.target)
        px, hl = last_price(p.ticker)
        if px is None:
            continue
        hi, lo = hl
        name = p.ticker.replace(".TO", "").replace(".V", "")
        if hi >= tgt:
            profit = sh * (tgt - float(p.fill))
            push(f"🎯 {name} hit target ${tgt:.2f}",
                 f"Now ${px:.2f}. SELL NOW: 1) Activity -> cancel the {name} stop-loss order. "
                 f"2) Sell all {sh} shares (limit a few cents under the bid). Profit about +${profit:.2f}.")
            pos.loc[i, "status"] = "target_alerted"
            changed = True
        elif lo <= stop:
            loss = sh * (float(p.fill) - stop)
            push(f"🛑 {name} reached stop ${stop:.2f}",
                 f"Now ${px:.2f}. Your stop-loss order should have sold it (about -${loss:.2f}). "
                 f"Open Wealthsimple and check it filled. If not, sell all {sh} shares now.", "high", "warning")
            pos.loc[i, "status"] = "stop_alerted"
            changed = True
        elif date.fromisoformat(p.exit_by) <= now.date() and now.hour >= 14:
            push(f"⏰ {name}: day 30 - sell today",
                 f"Now ${px:.2f}. Time limit reached. Cancel the {name} stop-loss order and sell all {sh} "
                 f"shares before the 4:00 pm close.", "high", "alarm_clock")
            pos.loc[i, "status"] = "timeout_alerted"
            changed = True
    if changed:
        pos.to_csv(FILE, index=False)


if __name__ == "__main__":
    main()
