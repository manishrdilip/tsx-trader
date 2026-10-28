#!/usr/bin/env bash
# Runs one India trader job on the server. Called by cron (see setup.sh).
#   refresh  8:15 AM IST - git pull, then get today's Zerodha token
#   monitor  every 5 min, 9:15-3:35 - auto_trader.py monitor
#   orders   9:10 AM, up to 6.5 h - india_monitor.py (Claude check on your Kite orders)
set -u
job="${1:?usage: run_task.sh refresh|monitor|orders}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
logs="$repo/india_server/logs"; mkdir -p "$logs"
log="$logs/$job-$(date +%F).log"
cd "$repo"; export PYTHONIOENCODING=utf-8
echo "==== $(date '+%F %T') $job" >> "$log"
case "$job" in
  refresh) git pull --ff-only >> "$log" 2>&1; .venv/bin/python zerodha_token_refresh.py >> "$log" 2>&1 ;;
  monitor) .venv/bin/python auto_trader.py monitor >> "$log" 2>&1 ;;
  orders)  .venv/bin/python india_monitor.py >> "$log" 2>&1 ;;
  *) echo "unknown job $job"; exit 1 ;;
esac
find "$logs" -name '*.log' -mtime +14 -delete
