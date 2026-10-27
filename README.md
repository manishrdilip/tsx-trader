# Trade Verifier — India + TSX

Calls Claude API after every trade to verify it against your swing-trading plan.
Sends a Telegram alert: ✅ APPROVED, 🚨 FLAG, or ⚠️ ERROR.

---

## Files

| File | Purpose |
|---|---|
| `verifier.py` | Core Claude verification engine (both portfolios) |
| `india_monitor.py` | Zerodha/Kite poller — runs locally or via GitHub Actions |
| `tsx_monitor.py` | Wealthsimple verifier — manual CLI or GitHub Actions |
| `notifier.py` | Telegram alert sender |
| `.github/workflows/india_monitor.yml` | Auto-polls NSE orders every 5 min during market hours |
| `.github/workflows/tsx_monitor.yml` | Manual trigger after each Wealthsimple trade |

---

## Setup (one-time)

### 1. GitHub Secrets
Go to your repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `KITE_API_KEY` | kite.trade → My Apps |
| `KITE_ACCESS_TOKEN` | Generated daily — see Zerodha section below |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram → /newbot |
| `TELEGRAM_CHAT_ID` | Message @userinfobot on Telegram |

### 2. Telegram setup
1. Open Telegram → search @BotFather → `/newbot`
2. Copy the token → add as `TELEGRAM_BOT_TOKEN` secret
3. Message your new bot once, then message @userinfobot → copy your chat ID → add as `TELEGRAM_CHAT_ID`

### 3. Zerodha access token (daily refresh)
Zerodha access tokens expire every day. You have two options:

**Option A — Manual (simple):** Each morning before trading, run:
```bash
python generate_token.py   # logs you in via browser, saves token
```
Then update the `KITE_ACCESS_TOKEN` GitHub secret with today's token.

**Option B — Automated:** Use `kiteconnect`'s token automation with a cron job on your end that generates and updates the secret via GitHub API. (More complex — do this after Option A is working.)

---

## India portfolio — how it works

GitHub Actions runs `india_monitor.yml` every 5 minutes during NSE hours (9:15–15:30 IST, Mon–Fri).
Each run fetches your Zerodha orders, finds any new COMPLETE orders since the last run, and sends each one to Claude for verification.

The seen-order list is cached between runs so you never get duplicate alerts.

## TSX portfolio — how it works

Wealthsimple has no API, so you trigger verification manually after each trade.

**From GitHub UI:**
1. Go to Actions → TSX Trade Verifier → Run workflow
2. Fill in: BUY/SELL, symbol (e.g. MSA.TO), qty, price, avg_cost (for SELL), scanner_signal
3. Claude verifies and sends Telegram alert within ~10 seconds

**From command line:**
```bash
# BUY example
python tsx_monitor.py manual --trade BUY --symbol MSA.TO --qty 5 --price 9.50 --signal yes

# SELL example
python tsx_monitor.py manual --trade SELL --symbol MSA.TO --qty 5 --price 9.78 --avg_cost 9.50 --signal yes
```

---

## Example Telegram alerts

**BUY approved:**
```
✅ TRADE APPROVED — TSX
Symbol: MSA.TO
Order: gh-20261027093012
Reason: Scanner-triggered BUY with valid uptrend setup and bullish candlestick.
💡 Set profit target at $9.79 (+3%) and stop-loss at $9.41 (-1%).
```

**SELL flagged (early exit):**
```
🚨 TRADE FLAG — INDIA
Symbol: SANGAMIND
Order: 1234567890
Reason: SELL executed at only +1.2% — below the +3% profit target.
📋 Violations: Early exit before reaching +3% target
P&L: +1.20% (below target)
💡 Review whether news or a technical break triggered this exit; document the reason.
```

---

## Plan rules embedded in verifier.py

| Rule | India | TSX |
|---|---|---|
| Profit target | +3% | +3% |
| Stop-loss | -1% | -1% |
| Monthly goal | 2.5% | 2.0% |
| Max positions | 10 | 5 |
| Entry signal required | Scanner + bullish candle + uptrend | All scans agree + bullish candle + uptrend |
