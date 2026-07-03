#!/usr/bin/env bash
# Pull the VM's authoritative deployment state back to the dev machine --
# ledger, marks, signal states, snapshotter parquet, cron logs. Additive only
# (no --delete): the VM is the system of record while the paper/live cycle
# runs there; pull, inspect, and commit the append-only CSVs to git.
#
# NEVER run daily_cycle in paper mode locally while the VM cycle is live --
# that would fork the ledger.
set -euo pipefail

HOST="${VM_HOST:-Ubuntu-VM}"
DEST="${VM_PATH:-/home/opj/projects/Vibe-Trading}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

rsync -az "$HOST:$DEST/deployment/state/" "$REPO/deployment/state/"
rsync -az "$HOST:$DEST/research/deribit_snapshot/data/" "$REPO/research/deribit_snapshot/data/"
rsync -az "$HOST:$DEST/deploy/logs/" "$REPO/deploy/logs/"

echo "[pull] state synced from $HOST:$DEST"
echo "[pull] append-only records worth committing:"
ls -la "$REPO/deployment/state/"*.csv 2>/dev/null || echo "  (no ledger CSVs yet)"
