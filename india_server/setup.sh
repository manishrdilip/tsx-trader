#!/usr/bin/env bash
# One-time setup of the India trader on an Ubuntu 22.04/24.04 server.
#   cd ~/tsx-trader && sudo bash india_server/setup.sh
# Safe to run again.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo bash india_server/setup.sh"; exit 1; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="${SUDO_USER:-root}"
step() { echo; echo "=== $*"; }

step "1/6 India time zone"
timedatectl set-timezone Asia/Kolkata
date

step "2/6 System packages and swap (browser login needs memory)"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv git cron util-linux
if ! swapon --show | grep -q .; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
systemctl enable --now cron

step "3/6 Python packages (a few minutes)"
sudo -u "$RUN_USER" bash -c "cd '$REPO' && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip \
  && .venv/bin/pip install -q kiteconnect anthropic requests pandas 'yfinance>=0.2.61' playwright pyotp PyNaCl"
"$REPO/.venv/bin/playwright" install --with-deps chromium

step "4/6 Your keys (.env)"
if [ ! -f "$REPO/.env" ]; then
  sudo -u "$RUN_USER" cp "$REPO/india_laptop/.env.example" "$REPO/.env"
  chmod 600 "$REPO/.env"; chown "$RUN_USER" "$REPO/.env"
  echo "nano will open. Fill in every value, then press Ctrl+O, Enter, Ctrl+X to save."
  read -rp "Press Enter to open the editor... " _
  sudo -u "$RUN_USER" nano "$REPO/.env"
fi
if grep -Eq '^(KITE_API_KEY|KITE_API_SECRET|KITE_USER_ID|KITE_PASSWORD|KITE_TOTP_SECRET|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|ANTHROPIC_API_KEY)=\s*$' "$REPO/.env"; then
  echo "Some required values are still empty in .env. Run: nano $REPO/.env  then run this setup again."; exit 1
fi

step "5/6 Scheduled jobs (Mon-Fri, India time)"
chmod +x "$REPO/india_server/run_task.sh"
R="$REPO/india_server/run_task.sh"
CRON=$(cat <<CRONEOF
# tsx-trader India jobs (server time zone is Asia/Kolkata)
15 8 * * 1-5 $R refresh
10 9 * * 1-5 flock -n /tmp/india_orders.lock timeout 6h30m $R orders
15-55/5 9 * * 1-5 flock -n /tmp/india_monitor.lock $R monitor
*/5 10-14 * * 1-5 flock -n /tmp/india_monitor.lock $R monitor
0-35/5 15 * * 1-5 flock -n /tmp/india_monitor.lock $R monitor
CRONEOF
)
( sudo -u "$RUN_USER" crontab -l 2>/dev/null | grep -v 'tsx-trader India jobs' | grep -v "$R" || true; echo "$CRON" ) | sudo -u "$RUN_USER" crontab -
sudo -u "$RUN_USER" crontab -l | grep "$R"

step "6/6 Test: token refresh + read-only Zerodha check (no orders)"
sudo -u "$RUN_USER" "$R" refresh
tail -n 6 "$REPO/india_server/logs/refresh-$(date +%F).log"
sudo -u "$RUN_USER" bash -c "cd '$REPO' && .venv/bin/python india_laptop/check_kite.py"
echo; echo "Done. The server runs the jobs by itself; you can log out."
