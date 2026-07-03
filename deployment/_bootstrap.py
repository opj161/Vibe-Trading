"""Shared path constants + sys.path setup for the deployment/ package.

``deployment/`` is a top-level package (sibling to ``agent/``), so its modules
need ``agent/`` on ``sys.path`` to import ``backtest.*`` -- whether invoked
directly (cron), via ``python -m deployment.<mod>``, or under pytest (pytest
also sets this via ``pyproject.toml``'s ``pythonpath``, but direct/cron
invocation does not get that for free, so this module makes every entry point
work the same way). Mirrors the self-bootstrap pattern already used by
``research/nautilus_deribit_options``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_DIR / "agent"
DEPLOYMENT_DIR = REPO_DIR / "deployment"
STATE_DIR = DEPLOYMENT_DIR / "state"
FROZEN_DIR = REPO_DIR / "forward_validation" / "frozen"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

STATE_DIR.mkdir(parents=True, exist_ok=True)
