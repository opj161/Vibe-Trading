#!/usr/bin/env bash
# One-time VM environment setup. Run ON the VM (or: ssh Ubuntu-VM 'bash -s' < deploy/bootstrap_vm.sh).
set -euo pipefail

DEST="${VM_PATH:-/home/opj/projects/Vibe-Trading}"
cd "$DEST"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r deploy/requirements-vm.txt

mkdir -p deployment/state research/deribit_snapshot/data deploy/logs agent/runs

echo "[bootstrap] venv ready: $DEST/.venv ($(.venv/bin/python --version))"
