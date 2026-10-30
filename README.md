# TSX + India Swing Trader

Personal swing-trading system for TSX (Canada) and NSE (India).

**Primary scanner (use this one):** `tsx_scan_v2_6_fixed.py`

---

## Quick Start

```bash
pip install -r requirements.txt

# Run the primary scanner (uses $10,000 account size by default)
ACCOUNT=10000 python tsx_scan_v2_6_fixed.py

# Or set a different account size
ACCOUNT=25000 python tsx_scan_v2_6_fixed.py
```

Results appear in the `results/` folder.

---

## What the system does

| Component | Purpose |
|-----------|---------|
| `tsx_scan_v2_6_fixed.py` | **Primary** TSX scanner (2/4 votes + regime + liquidity + ATR) |
| `auto_trader.py` | India (Zerodha) position monitor + auto GTT exits |
| `verifier.py` | Claude risk check after every trade → Telegram alert |
| `risk_levels.py` | Single source of truth for ATR stops/targets (3× / 6×) |
| `cache_manager.py` | Speeds up scans (30 sec after first run) |
| GitHub Actions | Daily TSX scan + India order monitoring |

Older scanners (`tsx_scan.py`, `_v2`, `_v2_5`) are kept only for reference.

---

## Required Secrets (GitHub → Settings → Secrets)

| Secret | Source |
|--------|--------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `KITE_API_KEY` | kite.trade → My Apps |
| `KITE_ACCESS_TOKEN` | Daily token (see below) |
| `TELEGRAM_BOT_TOKEN` | @BotFather |
| `TELEGRAM_CHAT_ID` | @userinfobot |

---

## Zerodha daily token

```bash
python zerodha_token_refresh.py   # or your preferred method
```
Then update the `KITE_ACCESS_TOKEN` secret (or use the automated refresh workflow).

---

## India auto-trader

Runs every 5 min during market hours via GitHub Actions (`india_monitor.yml`).
- Places exchange-side GTT OCO exits (stop + target)
- Closes legacy losers
- Sends Telegram alerts

---

## TSX verification

Wealthsimple has no API, so trigger manually after each trade:

```bash
python tsx_monitor.py manual --trade BUY --symbol MSA.TO --qty 5 --price 9.50 --signal yes
```

Or use the GitHub Actions workflow “TSX Trade Verifier”.

---

## Risk rules (from `risk_levels.py`)

- Stop = entry − 3 × ATR14 (capped at −8%)
- Target = entry + 6 × ATR14
- Risk per trade ≈ 2% of account (adjusted for overlapping positions)

---

Research / personal use only. Not financial advice.
