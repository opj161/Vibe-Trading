#!/usr/bin/env bash
# Push the code to the always-on Ubuntu-VM (deploy/README.md).
#
#   ./deploy/deploy_to_vm.sh              # code only
#   ./deploy/deploy_to_vm.sh --with-env   # also push .env (Telegram/HL-testnet keys)
#
# VM-local state is NEVER touched: deployment/state/, the snapshotter's
# data/, and deploy/logs/ are excluded, and --delete-excluded is NOT used.
set -euo pipefail

HOST="${VM_HOST:-Ubuntu-VM}"
DEST="${VM_PATH:-/home/opj/projects/Vibe-Trading}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

ssh "$HOST" "mkdir -p '$DEST'"

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude '.claude/' \
  --exclude '.serena/' \
  --exclude '.pytest_cache/' \
  --exclude '.devcontainer/' \
  --exclude '.github/' \
  --exclude '__pycache__/' \
  --exclude 'node_modules/' \
  --exclude 'data/' \
  --exclude 'frontend/' \
  --exclude 'assets/' \
  --exclude 'wiki/' \
  --exclude 'agent/runs/' \
  --exclude 'Vibe-Trading.zip' \
  --exclude 'deployment/state/' \
  --exclude 'research/deribit_snapshot/data/' \
  --exclude 'deploy/logs/' \
  "$REPO/" "$HOST:$DEST/"

if [[ "${1:-}" == "--with-env" ]]; then
  rsync -az "$REPO/.env" "$HOST:$DEST/.env"
  echo "[deploy] .env pushed"
fi

echo "[deploy] code synced to $HOST:$DEST"
