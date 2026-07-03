#!/usr/bin/env bash
# Cron entry point: the CPD-1 daily cycle (paper mode, auto-fills).
# Scheduled at 16:10 UTC -- just after the OKX daily bar close the frozen
# ZA4 config keys on. Logs per-day; nonzero exits land in the log AND in
# Telegram (daily_cycle alerts on its own failures).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO/deploy/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d)"

{
  echo "=== daily_cycle $(date -u -Iseconds) ==="
  "$REPO/.venv/bin/python" -m deployment.daily_cycle --auto-paper
  echo "=== exit $? ==="
} >> "$LOG_DIR/daily_$STAMP.log" 2>&1
