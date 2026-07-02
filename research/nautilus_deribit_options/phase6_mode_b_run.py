"""Phase 6 driver (Gate 6): Mode B real-mark replay, regenerating
`derived/phase6_mode_b.csv` and printing the corrected H1 comparison.

Rewritten 2026-07-02 during the post-implementation audit. The original
session's (uncommitted, lost) driver produced a Gate 6 report table whose
"H1 (Mode A)" column did NOT use the Gate-4/5-verified H1 assembly (it
reported BTC $1,511,127 where the verified Vibe-convention H1 is
$1,563,289) -- the per-leg Mode B library (`mode_b.py`) was fine (its
covered-shorts diffs reproduce exactly from the stored CSV), but the
aggregate H1 table was assembled with an unverified variant. This driver
uses the single verified convention throughout:

    H1 = spot P&L over long runs + opt_budget P&L over short runs,
    no-entry short runs contribute ZERO (Vibe's own convention).

Mode B only re-prices the *option* legs (H1's longs are spot and identical
in both modes), so the honest Mode-B headline is:

    H1_B = H1_A + (mode_b - mode_a) summed over covered short opt_budget legs

with coverage-skipped legs (no real print within the 5-day lookback on a
required leg date) held at their Mode A value and reported separately --
plus the covered-shorts-only decomposition, which is the genuinely
informative apples-to-apples number.

Usage:
    python phase6_mode_b_run.py [--underlying BTC|SOL_USDC|both]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import BTC_UNDERLYING_SYMBOL  # noqa: E402
from data_ctx import load_ctx  # noqa: E402
from leg_planner import (  # noqa: E402
    TRACK_OPT_BUDGET,
    TRACK_OPT_DELTA,
    plan_run_track,
    spot_pnl_total,
)
from mode_b import plan_run_track_realmark  # noqa: E402

DERIVED = _THIS_DIR / "derived"


def run_underlying(underlying: str) -> pd.DataFrame:
    ctx = load_ctx(underlying)
    is_btc = underlying == BTC_UNDERLYING_SYMBOL
    rows = []
    for run in ctx.runs:
        spot = spot_pnl_total(run, ctx.idx)
        for track in (TRACK_OPT_DELTA, TRACK_OPT_BUDGET):
            res = plan_run_track(run, track, ctx.entry_pool, ctx.idx, ctx.surf, ctx.half_spread)
            mb = plan_run_track_realmark(res, ctx.trades_full, ctx.idx, ctx.half_spread, is_btc)
            rows.append({
                "underlying": underlying,
                "run_id": run.run_id,
                "track": track,
                "dir": run.direction,
                "spot_pnl": spot,
                "mode_a_pnl": res.total_pnl,
                "mode_a_legs": len(res.legs),
                "mode_b_pnl": mb["total_pnl"],
                "mode_b_coverage_skip": mb["coverage_skip"],
                "mode_a_skip_reason": res.skip_reason or "",
            })
    return pd.DataFrame(rows)


def report(df: pd.DataFrame, underlying: str) -> None:
    d = df[df.underlying == underlying]
    spot_per_run = d[d.track == TRACK_OPT_BUDGET].fillna({"spot_pnl": 0.0})
    longs_spot = float(spot_per_run[spot_per_run["dir"] > 0].spot_pnl.sum())
    spot_total = float(spot_per_run.spot_pnl.sum())

    b = d[(d.track == TRACK_OPT_BUDGET) & (d["dir"] < 0)]
    h1_a = longs_spot + float(b.mode_a_pnl.sum())

    covered = b[(b.mode_a_legs > 0) & (~b.mode_b_coverage_skip)]
    uncovered = b[(b.mode_a_legs > 0) & (b.mode_b_coverage_skip)]
    cov_a = float(covered.mode_a_pnl.sum())
    cov_b = float(covered.mode_b_pnl.sum())
    h1_b = h1_a + (cov_b - cov_a)  # uncovered legs held at Mode A value

    print(f"\n=== {underlying} ===")
    print(f"spot baseline (all runs)              : {spot_total:12,.0f}")
    print(f"H1 Mode A (verified Vibe convention)  : {h1_a:12,.0f}")
    print(f"H1 Mode B (covered legs re-marked)    : {h1_b:12,.0f}   -> H1 > spot: {h1_b > spot_total}")
    print(f"covered short opt_budget runs         : {len(covered)}  (Mode A {cov_a:+,.0f} -> Mode B {cov_b:+,.0f}, "
          f"diff {cov_b - cov_a:+,.0f})")
    print(f"coverage-skipped short runs           : {len(uncovered)}  (held at Mode A value {float(uncovered.mode_a_pnl.sum()):+,.0f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="both", choices=["BTC", "SOL_USDC", "both"])
    args = ap.parse_args()
    unds = ["BTC", "SOL_USDC"] if args.underlying == "both" else [args.underlying]

    frames = [run_underlying(u) for u in unds]
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(DERIVED / "phase6_mode_b.csv", index=False)
    print(f"saved {DERIVED / 'phase6_mode_b.csv'}  ({len(df)} rows)")
    for u in unds:
        report(df, u)


if __name__ == "__main__":
    main()
