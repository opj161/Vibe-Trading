"""Parse the direction-run ledgers (`btc_direction_runs.csv` /
`sol_direction_runs.csv`) into `VibeRun` records, per plan §3.2.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import BTC_RUNS_CSV, SOL_RUNS_CSV  # noqa: E402


@dataclass(frozen=True)
class VibeRun:
    run_id: str
    underlying: str  # "BTC" | "SOL_USDC"
    start: pd.Timestamp
    end: pd.Timestamp
    direction: int
    days: int


def _load_runs_csv(path: Path, underlying: str) -> list[VibeRun]:
    df = pd.read_csv(path, parse_dates=["start", "end"])
    for c in ("start", "end"):
        if df[c].dt.tz is not None:
            df[c] = df[c].dt.tz_localize(None)
    runs = []
    for i, r in df.iterrows():
        runs.append(
            VibeRun(
                run_id=f"{underlying}-{i:04d}",
                underlying=underlying,
                start=pd.Timestamp(r["start"]),
                end=pd.Timestamp(r["end"]),
                direction=int(r["dir"]),
                days=int(r["days"]),
            )
        )
    return runs


def load_btc_runs(path: Path = BTC_RUNS_CSV) -> list[VibeRun]:
    return _load_runs_csv(path, "BTC")


def load_sol_runs(path: Path = SOL_RUNS_CSV) -> list[VibeRun]:
    """Note: unlike phase5_sol_expression.py::main, this does NOT filter to
    `runs["start"] >= idx.index.min()` (the "53 in-window" filter) -- that
    filter depends on the SOL index series, which is a tape-derived
    artifact, not a property of the run ledger itself. Callers that need
    the in-window subset (matching the frozen 53-run denominator) must
    apply that filter themselves against their own loaded index, exactly as
    phase5 does. Raw `sol_direction_runs.csv` has 127 rows (2020-11 onward);
    only 53 fall inside the SOL tape window (2024-03-11 -> 2026-07-02)."""
    return _load_runs_csv(path, "SOL_USDC")
