#!/usr/bin/env bash
# Cron entry point: daily Deribit chain snapshot (CPD-1 Phase C).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO/deploy/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%d)"

{
  echo "=== snapshot $(date -u -Iseconds) ==="
  "$REPO/.venv/bin/python" "$REPO/research/deribit_snapshot/snapshot_daily.py"
  echo "=== exit $? ==="
} >> "$LOG_DIR/snapshot_$STAMP.log" 2>&1
