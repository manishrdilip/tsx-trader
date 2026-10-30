# TSX + India Swing Trader

Personal swing-trading system for TSX (Canada) and NSE (India).

**Primary TSX scanner:** `tsx_scan_v2_6_fixed.py`  
**India scanner:** `india_scan.py`  
**Improved risk helpers:** `risk_manager.py`

---

## Quick Start

```bash
pip install -r requirements.txt

# TSX scanner (uses $10,000 account size by default)
ACCOUNT=10000 python tsx_scan_v2_6_fixed.py

# India scanner (generates results/india_report.md + optional Telegram)
ACCOUNT=10000 python india_scan.py
```

Results appear in the `results/` folder.

---

## What the system does

| Component | Purpose |
|-----------|---------|
| `tsx_scan_v2_6_fixed.py` | Primary TSX scanner (2/4 votes + regime + liquidity + ATR) |
| `india_scan.py` | **New** — daily NSE large-cap scanner + report |
| `risk_manager.py` | **New** — volatility/regime-aware position sizing (1.5% base, half in weak markets, portfolio risk cap) |
| `auto_trader.py` | India (Zerodha) position monitor + auto GTT exits |
| `verifier.py` | Claude risk check after every trade → Telegram alert |
| `risk_levels.py` | Single source of truth for ATR stops/targets (3× / 6×) |
| `cache_manager.py` | Speeds up scans |
| GitHub Actions | Daily TSX scan + India scan + order monitoring |

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
python zerodha_token_refresh.py
```
Then update the `KITE_ACCESS_TOKEN` secret (or use the automated refresh workflow).

---

## India

- **Scanner:** `india_scan.py` (or the `India Daily Scan` workflow) produces `results/india_report.md` and can send a Telegram summary.
- **Auto-trader:** Runs on the India laptop (or manually) to place GTT exits on holdings.

---

## Risk rules

- Stop = entry − 3 × ATR14 (capped at −8%)
- Target = entry + 6 × ATR14
- Base risk per trade = **1.5%** (down from 2%)
- Automatically halved when the market is below its 200-day SMA
- Portfolio open-risk cap ≈ 6%

Use `risk_manager.py` helpers in new code for consistent sizing.

---

Research / personal use only. Not financial advice.
