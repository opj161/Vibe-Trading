"""Phase 5 driver (Gate 5): native-fee + spread sensitivity, regenerating
`derived/phase5_1x.csv`, `derived/phase5_2x.csv`, `derived/phase5_spot.csv`
and printing the 8-cell H1-vs-spot table.

Rewritten 2026-07-02 during the post-implementation audit (original driver
was never committed). Same execution path as phase4_full_parity.py, run at
1x and 2x the measured half-spread, capturing both `pnl_parity` (Vibe fee
convention: flip-exits free, settlement fee added) and `pnl_native`
(Nautilus's charged commission retained on every fill) from the same fills
ledger per plan §5's single-fee-code-path design.

H1 assembly convention (Vibe's own, from `phase4b/phase5:combo`):
    H1 = spot P&L over long-direction runs + opt_budget P&L over
    short-direction runs, where a short run with no option entry
    contributes ZERO (the puts leg stays flat -- it does NOT fall back to
    spot; see findings §82.3's skipped-shorts integrity discussion).

Usage:
    python phase5_sensitivity.py [--underlying BTC|SOL_USDC|both]
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
from leg_planner import (  # noqa: E402
    TRACK_OPT_BUDGET,
    TRACK_OPT_DELTA,
    plan_run_track,
    spot_pnl_total,
)
from postprocess import attribute_run  # noqa: E402
from run_backtest import run_mode_a  # noqa: E402

DERIVED = _THIS_DIR / "derived"


def run_underlying(underlying: str) -> tuple[dict[float, list[dict]], list[dict]]:
    ctx = load_ctx(underlying)
    by_mult: dict[float, list[dict]] = {1.0: [], 2.0: []}
    spot_rows: list[dict] = []

    for run in ctx.runs:
        spot_rows.append({
            "underlying": underlying, "run_id": run.run_id, "dir": run.direction,
            "spot_pnl": spot_pnl_total(run, ctx.idx),
        })
        for mult in (1.0, 2.0):
            hs = ctx.half_spread * mult
            for track in (TRACK_OPT_DELTA, TRACK_OPT_BUDGET):
                res = plan_run_track(run, track, ctx.entry_pool, ctx.idx, ctx.surf, hs)
                row = {
                    "underlying": underlying, "run_id": run.run_id, "track": track,
                    "dir": run.direction, "days": run.days, "n_legs": len(res.legs),
                    "pnl_parity": 0.0, "pnl_native": 0.0,
                }
                if res.legs:
                    tmp = Path(tempfile.mkdtemp(prefix="modea5_"))
                    try:
                        result = run_mode_a(tmp / "catalog", underlying, res, ctx.idx, hs)
                        attr = attribute_run(res.legs, result.strategy.fills, ctx.idx, run)
                        row["pnl_parity"] = attr["pnl_parity_total"]
                        row["pnl_native"] = attr["pnl_native_total"]
                        getattr(result.engine, "dispose", lambda: None)()
                    finally:
                        shutil.rmtree(tmp, ignore_errors=True)
                by_mult[mult].append(row)
    return by_mult, spot_rows


def h1_total(spot_df: pd.DataFrame, opt_df: pd.DataFrame, und: str, col: str) -> float:
    s = spot_df[spot_df.underlying == und].fillna({"spot_pnl": 0.0})
    b = opt_df[(opt_df.underlying == und) & (opt_df.track == TRACK_OPT_BUDGET)]
    return float(s[s["dir"] > 0].spot_pnl.sum() + b[b["dir"] < 0][col].sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="both", choices=["BTC", "SOL_USDC", "both"])
    args = ap.parse_args()
    unds = ["BTC", "SOL_USDC"] if args.underlying == "both" else [args.underlying]

    all_by_mult: dict[float, list[dict]] = {1.0: [], 2.0: []}
    all_spot: list[dict] = []
    for und in unds:
        by_mult, spot_rows = run_underlying(und)
        for m in (1.0, 2.0):
            all_by_mult[m].extend(by_mult[m])
        all_spot.extend(spot_rows)

    spot_df = pd.DataFrame(all_spot)
    spot_df.to_csv(DERIVED / "phase5_spot.csv", index=False)
    for m, label in ((1.0, "1x"), (2.0, "2x")):
        df = pd.DataFrame(all_by_mult[m])
        df.to_csv(DERIVED / f"phase5_{label}.csv", index=False)

    print("\n=== H1 (spot longs + budget puts shorts) vs spot, all combinations ===")
    for und in unds:
        spot_total = float(spot_df[spot_df.underlying == und].spot_pnl.fillna(0.0).sum())
        for m, label in ((1.0, "1x"), (2.0, "2x")):
            df = pd.DataFrame(all_by_mult[m])
            for col in ("pnl_parity", "pnl_native"):
                h1 = h1_total(spot_df, df, und, col)
                verdict = "H1 > spot" if h1 > spot_total else "H1 <= spot  ***FAIL***"
                print(f"{und:9s} {label} {col.split('_')[1]:6s} spot={spot_total:12,.0f}  H1={h1:12,.0f}  {verdict}")


if __name__ == "__main__":
    main()
