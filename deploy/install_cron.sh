#!/usr/bin/env bash
# Install/refresh the CPD-1 cron entries on the VM (idempotent: replaces any
# line tagged VIBE-CPD1, leaves everything else in the crontab alone).
# Times are UTC -- the crontab is written with CRON_TZ=UTC so a VM timezone
# change can never silently shift the 16:00-UTC bar-close alignment.
set -euo pipefail

DEST="${VM_PATH:-/home/opj/projects/Vibe-Trading}"

{ crontab -l 2>/dev/null | grep -v 'VIBE-CPD1' | grep -v '^CRON_TZ=UTC$' || true
  echo "CRON_TZ=UTC"
  echo "10 16 * * * $DEST/deploy/run_daily.sh          # VIBE-CPD1-daily"
  echo "40 16 * * * $DEST/deploy/run_snapshot.sh       # VIBE-CPD1-snapshot"
  echo "0 17 * * 1  $DEST/deploy/run_weekly_report.sh  # VIBE-CPD1-weekly"
} | crontab -

echo "[cron] installed:"
crontab -l | grep VIBE-CPD1
