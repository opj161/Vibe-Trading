"""Data-integrity gate for the deployment signal path (audit fix 2026-07-03).

Why this exists — observed, not hypothetical: during the CPD-1 audit, three
same-day runs of the byte-identical frozen M1 config returned full-window
Sharpe {0.61, 0.44, 0.61} — the middle draw's fetch delivered silently
degraded data that warped 21 years of flip dates (40 extra trades, maxDD
−19.6% → −34.6%) while every spot-checked close still matched to ~1e-6. A
live daily run that catches such a draw would emit confidently wrong
tickets. So: no ticket may be built from a fetch that fails these checks.

Checks (per strategy, on the fetched ``data_map`` before signal generation):

1. **NaN closes** — any NaN in any symbol's ``close`` fails (NaNs propagate
   silently through EMA/SMA/sign chains; this is the likeliest mechanism of
   the observed bad draw).
2. **Minimum history** — fewer than ``MIN_ROWS`` bars for any symbol fails
   (a truncated fetch shifts every lookback).
3. **History mutation vs yesterday's fingerprint** — the last
   ``FINGERPRINT_BARS`` (date, close) pairs are persisted per
   strategy/symbol after each passing run; on the next run, overlapping
   dates are compared. A *uniform* multiplicative shift across all
   overlapping bars is ALLOWED (that is exactly what a legitimate
   dividend/split re-adjustment looks like — the whole history rescales by
   one factor) and logged; a *non-uniform* mutation (bars moved by
   different factors, spread > ``NONUNIFORM_TOL``) fails — real history
   does not selectively rewrite individual bars.

On failure callers must not write signal state and must not build tickets —
``run_signal`` raises ``DataIntegrityError`` and ``main()`` routes it to a
Telegram alert (see ``alerts.format_data_integrity_alert``).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from deployment._bootstrap import STATE_DIR

logger = logging.getLogger(__name__)

MIN_ROWS = 250
FINGERPRINT_BARS = 30
NONUNIFORM_TOL = 0.002  # max spread of per-bar new/old ratios before failing


class DataIntegrityError(RuntimeError):
    """Fetched data failed an integrity check; no signal/tickets may be produced."""


def _fingerprint_path(strategy: str) -> Path:
    return STATE_DIR / f"data_fingerprint_{strategy}.json"


def _extract_tail(data_map: dict) -> dict:
    """{symbol: {iso_date: close}} for the last FINGERPRINT_BARS bars."""
    out: dict[str, dict[str, float]] = {}
    for symbol, df in data_map.items():
        closes = df["close"].dropna().tail(FINGERPRINT_BARS)
        out[symbol] = {
            (idx.date().isoformat() if hasattr(idx, "date") else str(idx)): float(v)
            for idx, v in closes.items()
        }
    return out


def check_data_map(strategy: str, data_map: dict, *, update_fingerprint: bool = True) -> None:
    """Run all checks; raise DataIntegrityError on the first failure.

    ``update_fingerprint=False`` lets read-only callers (tests, dry runs)
    validate without advancing the persisted fingerprint.
    """
    # 1. NaN closes + 2. minimum history
    for symbol, df in data_map.items():
        if "close" not in df.columns:
            raise DataIntegrityError(f"{strategy}/{symbol}: fetched data has no 'close' column")
        n_nan = int(df["close"].isna().sum())
        if n_nan:
            raise DataIntegrityError(
                f"{strategy}/{symbol}: {n_nan} NaN close(s) in fetched data — "
                f"refusing to generate a signal from degraded data"
            )
        if len(df) < MIN_ROWS:
            raise DataIntegrityError(
                f"{strategy}/{symbol}: only {len(df)} bars fetched (< {MIN_ROWS}) — "
                f"truncated fetch would shift every lookback"
            )

    # 3. history mutation vs the previous run's fingerprint
    fp_path = _fingerprint_path(strategy)
    previous: Optional[dict] = None
    if fp_path.exists():
        try:
            previous = json.loads(fp_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("data_integrity: unreadable fingerprint %s (%s) — treating as first run", fp_path, exc)

    current = _extract_tail(data_map)
    if previous:
        for symbol, prev_bars in previous.get("bars", {}).items():
            if symbol not in current:
                continue  # universe change is a config event, not a data event
            overlap = sorted(set(prev_bars) & set(current[symbol]))
            if len(overlap) < 3:
                continue  # not enough shared history to compare
            ratios = [current[symbol][d] / prev_bars[d] for d in overlap if prev_bars[d]]
            spread = max(ratios) - min(ratios)
            if spread > NONUNIFORM_TOL:
                raise DataIntegrityError(
                    f"{strategy}/{symbol}: history mutated NON-uniformly since the previous run "
                    f"(per-bar new/old ratios span {min(ratios):.6f}..{max(ratios):.6f}, "
                    f"spread {spread:.6f} > {NONUNIFORM_TOL}) over {len(overlap)} overlapping bars — "
                    f"real history does not selectively rewrite individual bars"
                )
            level = abs(sum(ratios) / len(ratios) - 1.0)
            if level > 1e-6:
                logger.info(
                    "data_integrity: %s/%s uniformly re-scaled by %+.4f%% since previous run "
                    "(consistent with a dividend/split re-adjustment) — accepted",
                    strategy, symbol, level * 100,
                )

    if update_fingerprint:
        fp_path.write_text(json.dumps({
            "written_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "bars": current,
        }, indent=2))
