#!/usr/bin/env bash
# Cron entry point: weekly tracking-error report (Mondays). --since defaults
# to the earliest equity snapshot (deployment start).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO/deploy/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d)"

{
  echo "=== weekly tracking report $(date -u -Iseconds) ==="
  "$REPO/.venv/bin/python" -m deployment.tracking_report --mode paper
  echo "=== exit $? ==="
} >> "$LOG_DIR/weekly_$STAMP.log" 2>&1
