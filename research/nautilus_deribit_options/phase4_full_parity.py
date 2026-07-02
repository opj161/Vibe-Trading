"""Phase 4 driver (Gate 4): full (run x track) Nautilus execution vs the
Gate-2-verified leg planner, regenerating
`derived/phase4_nautilus_vs_legplanner.csv`.

Rewritten 2026-07-02 during the post-implementation audit: the original
session's driver scripts were never committed (only their CSV outputs were),
leaving Gate 4 unreproducible. This driver regenerates the artifact from
the same verified components (`leg_planner` -> `run_backtest.run_mode_a` ->
`postprocess.attribute_run`) whose wiring is unit-tested in
`_tests/test_mode_a_smoke.py`.

Usage:
    python phase4_full_parity.py [--underlying BTC|SOL_USDC|both] [--sample N]
        [--out derived/phase4_nautilus_vs_legplanner.csv]

`--sample N` runs only the first N (run, track) pairs per underlying that
have >=1 leg -- used to cross-validate an existing artifact cheaply.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from data_ctx import load_ctx  # noqa: E402
from leg_planner import TRACK_OPT_BUDGET, TRACK_OPT_DELTA, plan_run_track  # noqa: E402
from postprocess import attribute_run  # noqa: E402
from run_backtest import run_mode_a  # noqa: E402

DERIVED = _THIS_DIR / "derived"


def run_underlying(underlying: str, sample: int | None) -> list[dict]:
    ctx = load_ctx(underlying)
    rows: list[dict] = []
    executed = 0
    for run in ctx.runs:
        for track in (TRACK_OPT_DELTA, TRACK_OPT_BUDGET):
            res = plan_run_track(run, track, ctx.entry_pool, ctx.idx, ctx.surf, ctx.half_spread)
            row = {
                "underlying": underlying,
                "run_id": run.run_id,
                "track": track,
                "leg_planner_pnl": res.total_pnl,
                "nautilus_pnl": None,
                "n_legs": len(res.legs),
                "error": "",
            }
            if res.legs:
                if sample is not None and executed >= sample:
                    continue
                tmp = Path(tempfile.mkdtemp(prefix="modea_"))
                try:
                    result = run_mode_a(tmp / "catalog", underlying, res, ctx.idx, ctx.half_spread)
                    attr = attribute_run(res.legs, result.strategy.fills, ctx.idx, run)
                    row["nautilus_pnl"] = attr["pnl_parity_total"]
                    getattr(result.engine, "dispose", lambda: None)()
                except Exception as e:  # keep going; report the failure
                    row["error"] = repr(e)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                executed += 1
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="both", choices=["BTC", "SOL_USDC", "both"])
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--out", default=str(DERIVED / "phase4_nautilus_vs_legplanner.csv"))
    args = ap.parse_args()

    unds = ["BTC", "SOL_USDC"] if args.underlying == "both" else [args.underlying]
    rows: list[dict] = []
    for und in unds:
        rows.extend(run_underlying(und, args.sample))

    df = pd.DataFrame(rows)
    comparable = df.dropna(subset=["nautilus_pnl"])
    diffs = (comparable["nautilus_pnl"] - comparable["leg_planner_pnl"]).abs()
    print(f"pairs={len(df)}  executed={len(comparable)}  errors={(df['error'] != '').sum()}")
    if len(comparable):
        print(f"max |nautilus - leg_planner| = ${diffs.max():.2f}   mean ${diffs.mean():.4f}")
    if args.sample is None:
        df.to_csv(args.out, index=False)
        print(f"saved {args.out}")
    else:
        # sample mode: cross-check against the stored artifact instead of overwriting
        stored = pd.read_csv(DERIVED / "phase4_nautilus_vs_legplanner.csv")
        merged = comparable.merge(stored, on=["underlying", "run_id", "track"], suffixes=("", "_stored"))
        d = (merged["nautilus_pnl"] - merged["nautilus_pnl_stored"]).abs()
        print(f"sample cross-check vs stored artifact: n={len(merged)}, max diff ${d.max():.4f}")


if __name__ == "__main__":
    main()
