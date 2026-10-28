"""
Local settings for running the India trader on a PC instead of GitHub Actions.

Loads KEY=value lines from `.env` in the repo folder into the environment
(values already set win), and the day's Kite access token from `.kite_token`
(written by zerodha_token_refresh.py). Both files are git-ignored.
On GitHub Actions neither file exists, so this does nothing there.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
TOKEN_FILE = ROOT / ".kite_token"


def load():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ.setdefault(key.strip(), value)
    if TOKEN_FILE.exists() and not os.environ.get("KITE_ACCESS_TOKEN"):
        os.environ["KITE_ACCESS_TOKEN"] = TOKEN_FILE.read_text(encoding="utf-8").strip()


load()
