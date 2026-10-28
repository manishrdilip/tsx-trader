"""
Read-only connection check for the India laptop. Places NO orders.
Shows this PC's public IP, then reads profile, holdings and GTTs from Kite
and sends the result to Telegram.
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import local_env  # noqa: E402,F401
from kiteconnect import KiteConnect  # noqa: E402
from notifier import send_telegram  # noqa: E402

ip = urllib.request.urlopen("https://api.ipify.org", timeout=15).read().decode()
print(f"Public IP of this laptop: {ip}  (this must be registered in the Kite developer console)")

kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
kite.set_access_token(os.environ["KITE_ACCESS_TOKEN"])
try:
    user = kite.profile()["user_name"]
    holdings = kite.holdings()
    gtts = [g for g in kite.get_gtts() if g.get("status") == "active"]
except Exception as e:
    msg = f"❌ India laptop check FAILED (IP {ip}): {e}"
    print(msg)
    send_telegram(msg)
    sys.exit(1)

msg = (f"✅ India laptop connected to Zerodha as {user} (IP {ip}).\n"
       f"{len(holdings)} holdings, {len(gtts)} active GTTs.")
print(msg)
send_telegram(msg)
