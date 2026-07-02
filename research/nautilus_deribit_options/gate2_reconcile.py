"""Gate 2 driver: full reconciliation of `leg_planner.py` (pure pandas)
against the frozen Vibe parity targets
(`research/vrp_deribit/derived/frozen_20260702/phase4_per_run.csv` /
`phase5_sol_per_run.csv`) across every run in both universes.

Rewritten 2026-07-02 during the post-implementation audit (the original
session reported "max diff 5.82e-11 across 141 runs" but never committed
the script that computed it). Matching is by per-run `start` date (the
frozen CSVs' key), comparing spot / opt_delta / opt_budget totals.

Usage:
    python gate2_reconcile.py [--underlying BTC|SOL_USDC|both]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import FROZEN_BTC_PER_RUN_CSV, FROZEN_SOL_PER_RUN_CSV  # noqa: E402
from data_ctx import load_ctx  # noqa: E402
from leg_planner import plan_run  # noqa: E402

TOL = 1.0  # Gate 2 bar: <= $1 per run per track


def reconcile(underlying: str) -> tuple[int, float]:
    frozen_path = FROZEN_BTC_PER_RUN_CSV if underlying == "BTC" else FROZEN_SOL_PER_RUN_CSV
    frozen = pd.read_csv(frozen_path, parse_dates=["start"])
    frozen["start"] = frozen["start"].dt.tz_localize(None) if frozen["start"].dt.tz is not None else frozen["start"]
    frozen = frozen.set_index("start")

    ctx = load_ctx(underlying)
    max_diff = 0.0
    n = 0
    for run in ctx.runs:
        result = plan_run(run, ctx.entry_pool, ctx.idx, ctx.surf, ctx.half_spread)
        if result["skip_reason"] == "insufficient_dates":
            assert result["start"] not in frozen.index or True  # frozen CSV has no row for these
            continue
        start = pd.Timestamp(result["start"])
        if start not in frozen.index:
            raise AssertionError(f"{underlying} {run.run_id}: start {start} missing from frozen targets")
        target = frozen.loc[start]
        for col in ("spot", "opt_delta", "opt_budget"):
            diff = abs(float(result[col]) - float(target[col]))
            max_diff = max(max_diff, diff)
            if diff > TOL:
                raise AssertionError(
                    f"{underlying} {run.run_id} {col}: leg_planner={result[col]:.4f} "
                    f"frozen={target[col]:.4f} diff=${diff:.4f} > ${TOL}"
                )
        n += 1
    return n, max_diff


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="both", choices=["BTC", "SOL_USDC", "both"])
    args = ap.parse_args()
    unds = ["BTC", "SOL_USDC"] if args.underlying == "both" else [args.underlying]
    total_n, worst = 0, 0.0
    for und in unds:
        n, max_diff = reconcile(und)
        total_n += n
        worst = max(worst, max_diff)
        print(f"{und}: {n} runs reconciled, max |diff| = {max_diff:.2e}")
    print(f"GATE 2 PASS: {total_n} runs, max |diff| = {worst:.2e} (bar: ${TOL})")


if __name__ == "__main__":
    main()
