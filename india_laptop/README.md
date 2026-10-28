# Running the India trader on a laptop in India

Zerodha only accepts API orders from a **static IP address** you register with them.
GitHub's servers change IP on every run, so the India jobs run on this laptop instead:

| Time (IST, Mon–Fri) | Job | What it does |
|---|---|---|
| 8:15 AM | Zerodha token refresh | Updates the code (`git pull`), logs in to Zerodha, saves today's token |
| 9:10 AM – 3:40 PM | India order monitor | Claude checks every order you place in Kite → Telegram |
| 9:15 AM – 3:35 PM, every 5 min | India auto-trader | GTT stop + target on each holding, sells the legacy losers |

TSX scans and alerts keep running on GitHub. Nothing changes there.

## Step 1: Get a static IP from Hathway

Contact Hathway (customer care or the Hathway app) and ask for a **static IPv4 address** on the
connection the laptop uses. It's a paid add-on. They'll give you an IP like `103.x.x.x`.

Check it: on the laptop, search "what is my IP" in a browser. Restart the Wi-Fi router, wait
2 minutes, check again. **It must be the same number both times.**

## Step 2: Register the IP with Zerodha

1. Go to <https://developers.kite.trade> and log in.
2. Open **My apps** → your app.
3. In the **IP whitelist / static IP** section, add the static IP from step 1 and save.

## Step 3: Set up the laptop (once, about 15 minutes)

You need the same keys that are saved as GitHub secrets: Kite API key and secret, Zerodha
user ID, password and TOTP secret, Telegram bot token and chat ID, and the Anthropic API key.

1. **Time zone:** Settings → Time & language → Date & time → time zone
   **(UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi**.
2. Click Start, type `PowerShell`, right-click **Windows PowerShell** → **Run as administrator**.
3. Install Git, then **close and reopen** PowerShell as administrator:
   ```powershell
   winget install --id Git.Git -e
   ```
4. Download the trader and run the setup:
   ```powershell
   cd C:\
   git clone https://github.com/manishrdilip/tsx-trader.git
   cd C:\tsx-trader
   powershell -ExecutionPolicy Bypass -File .\india_laptop\setup.ps1
   ```
5. When **Notepad** opens, fill in every value, then **save and close** Notepad. Setup continues.
6. Setup ends with a test. It places **no orders**. You should get on Telegram:
   - 🔑 *Zerodha token refreshed on the India laptop.*
   - ✅ *India laptop connected to Zerodha as … (IP …). N holdings, N active GTTs.*

   If the IP shown isn't the one registered in step 2, Zerodha will reject orders. Fix step 1 or 2.

## Every day

- Keep the laptop **plugged in, switched on and online** on weekdays, 8:00 AM – 3:45 PM IST.
  Setup turns off sleep on the charger and makes closing the lid do nothing.
- About 8:15 AM you should get 🔑 *token refreshed*. If you get ⚠️ *token refresh FAILED*,
  open PowerShell and run:
  ```powershell
  powershell -ExecutionPolicy Bypass -File C:\tsx-trader\india_laptop\run_task.ps1 -Job refresh
  ```
- Logs for each job and day are in `C:\tsx-trader\india_laptop\logs` (kept 14 days).
- The tasks are listed in **Task Scheduler** → **Task Scheduler Library** → **TSX Trader**.

## Troubleshooting

| Telegram says | Fix |
|---|---|
| `No IPs configured for this app` / IP not allowed | The laptop's IP isn't the registered one: repeat steps 1–2 |
| `Incorrect api_key or access_token` | Run the refresh command above |
| `token refresh FAILED` with "Invalid TOTP" | Check `KITE_TOTP_SECRET` in `notepad C:\tsx-trader\.env` and the laptop clock |
| Nothing at all | The laptop was off, asleep or offline |

To change a key: `notepad C:\tsx-trader\.env`, save. To re-run the whole setup safely, repeat step 3.4.
