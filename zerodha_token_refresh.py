"""
Zerodha daily token auto-refresh.
Logs into Kite using Playwright, extracts request_token from redirect,
generates access_token, then pushes it to GitHub Secrets automatically.

Runs as a GitHub Action every morning at 3:30 AM UTC (9:00 AM IST).

Required GitHub Secrets:
  KITE_API_KEY       — from kite.trade/account/apps
  KITE_API_SECRET    — from kite.trade/account/apps
  KITE_USER_ID       — your Zerodha login ID (e.g. AB1234)
  KITE_PASSWORD      — your Zerodha password
  KITE_TOTP_SECRET   — the base32 TOTP secret from Zerodha's 2FA setup
                       (Settings → Security → External TOTP → show secret)
  GH_TOKEN           — GitHub Personal Access Token with repo+secrets scope
  GH_REPO            — your repo in owner/repo format (e.g. dilip/trade-verifier)
"""

import os
import re
import sys
import json
import base64
import asyncio
import logging
import requests
import pyotp
from kiteconnect import KiteConnect
from playwright.async_api import async_playwright
from nacl import encoding, public  # PyNaCl — for encrypting the secret

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config from env ───────────────────────────────────────────────────────────

API_KEY     = os.environ["KITE_API_KEY"]
API_SECRET  = os.environ["KITE_API_SECRET"]
USER_ID     = os.environ["KITE_USER_ID"]
PASSWORD    = os.environ["KITE_PASSWORD"]
TOTP_SECRET = os.environ["KITE_TOTP_SECRET"]
GH_TOKEN    = os.environ["GH_TOKEN"]
GH_REPO     = os.environ["GH_REPO"]   # e.g. "dilip/trade-verifier"

KITE_LOGIN_URL = f"https://kite.trade/connect/login?api_key={API_KEY}&v=3"

# ── Step 1: Browser login → get request_token ─────────────────────────────────

async def get_request_token() -> str:
    log.info("Launching browser to log into Zerodha...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # Navigate to Kite login
        await page.goto(KITE_LOGIN_URL)
        await page.wait_for_load_state("networkidle")

        # Fill user ID and password
        await page.fill('input[type="text"]', USER_ID)
        await page.fill('input[type="password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")

        # Fill TOTP (2FA)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        log.info("Generated TOTP: %s", totp)
        await page.fill('input[type="number"], input[label="External TOTP"]', totp)
        await page.click('button[type="submit"]')

        # Wait for redirect to callback URL containing request_token
        log.info("Waiting for redirect with request_token...")
        for _ in range(30):
            url = page.url
            if "request_token=" in url:
                match = re.search(r"request_token=([^&]+)", url)
                if match:
                    request_token = match.group(1)
                    log.info("Got request_token: %s...", request_token[:8])
                    await browser.close()
                    return request_token
            await asyncio.sleep(1)

        # Fallback: check for TOTP field still visible (wrong TOTP timing)
        await browser.close()
        raise RuntimeError("Timed out waiting for request_token in redirect URL.")

# ── Step 2: Generate access_token from request_token ─────────────────────────

def generate_access_token(request_token: str) -> str:
    kite = KiteConnect(api_key=API_KEY)
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = data["access_token"]
    log.info("Generated access_token: %s...", access_token[:8])
    return access_token

# ── Step 3: Push access_token to GitHub Secrets ───────────────────────────────

def get_repo_public_key() -> tuple[str, str]:
    """Returns (key_id, public_key_base64) for encrypting the secret."""
    url = f"https://api.github.com/repos/{GH_REPO}/actions/secrets/public-key"
    r = requests.get(url, headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    })
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]

def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt secret value using repo's public key (libsodium sealed box)."""
    pk = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode())
    return base64.b64encode(sealed).decode()

def push_github_secret(secret_name: str, secret_value: str):
    key_id, pub_key = get_repo_public_key()
    encrypted = encrypt_secret(pub_key, secret_value)

    url = f"https://api.github.com/repos/{GH_REPO}/actions/secrets/{secret_name}"
    r = requests.put(url, headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    }, json={
        "encrypted_value": encrypted,
        "key_id": key_id,
    })
    if r.status_code in (201, 204):
        log.info("✅ GitHub secret %s updated successfully.", secret_name)
    else:
        raise RuntimeError(f"Failed to update secret: {r.status_code} {r.text}")

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    try:
        request_token = await get_request_token()
        access_token  = generate_access_token(request_token)
        push_github_secret("KITE_ACCESS_TOKEN", access_token)
        log.info("🎉 Token refresh complete. india_monitor will use the new token.")
    except Exception as e:
        log.error("Token refresh FAILED: %s", e)
        # Notify via Telegram if configured
        try:
            from notifier import send_telegram
            send_telegram(f"⚠️ Zerodha token refresh FAILED: {e}\nLog into Kite manually and update KITE\\_ACCESS\\_TOKEN secret.")
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
