"""Phase 7 driver (Gate 7): robustness grid over (budget frac, DTE band,
moneyness band, spread multiplier), BTC, regenerating
`derived/phase7_grid.csv`.

Rewritten 2026-07-02 during the post-implementation audit. The original
session's grid driver was never committed, and its output disagreed with
the Gate-4/5-verified H1 at the DEFAULT parameter cell (it reported
$1,511,127 where the verified value is $1,563,289 -- a $52k unexplained
divergence in its own baseline). This rewrite:

1. uses the verified H1 convention (spot longs + opt_budget shorts,
   no-entry shorts contribute zero -- Vibe's own; the lost driver's
   claimed "spot fallback ... matching Vibe's own convention" was wrong
   about Vibe),
2. **self-checks**: the default cell (budget 10%, DTE 20-40, moneyness
   7.5%, spread 1x) must reproduce the Gate-5 H1 total to <= $1 or the
   script aborts,
3. exploits exact linearity of opt_budget leg P&L in `budget_frac`
   (quantity = budget/ask; entry cost, capped fee, marks, exit value are
   all proportional to quantity; selection is quantity-independent), so
   only the (DTE x moneyness x spread) = 27 combinations are planned and
   the 3 budget levels are analytic scalings -- with one numerical
   verification cell re-planned explicitly to guard the linearity claim.

Honesty note: the expectation below is re-stated from the plan (§6 Phase
7); the original session's claimed pre-registration cannot be verified
because its script was lost. Expectation: H1's edge over spot should be
broadly positive across most of the grid without a single dominant cell;
a narrow winning sliver would itself be the finding (fragility).

Usage:
    python phase7_grid.py
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import PREMIUM_BUDGET_FRAC  # noqa: E402
from data_ctx import load_btc_ctx  # noqa: E402
from leg_planner import TRACK_OPT_BUDGET, plan_run_track, spot_pnl_total  # noqa: E402
from tape import atm_band_entry_pool  # noqa: E402

DERIVED = _THIS_DIR / "derived"

BUDGETS = (0.05, 0.10, 0.15)
DTE_BANDS = ((14, 30), (20, 40), (30, 60))
MONEYNESS = (0.05, 0.075, 0.10)
SPREADS = (1.0, 2.0, 3.0)


def shorts_optb_total(ctx, pool, dte_band, moneyness, hs, budget_frac=PREMIUM_BUDGET_FRAC) -> float:
    total = 0.0
    for run in ctx.runs:
        if run.direction >= 0:
            continue
        res = plan_run_track(
            run, TRACK_OPT_BUDGET, pool, ctx.idx, ctx.surf, hs,
            dte_band=dte_band, moneyness_band=moneyness, budget_frac=budget_frac,
        )
        total += res.total_pnl
    return total


def main() -> None:
    ctx = load_btc_ctx()
    longs_spot = sum(
        (spot_pnl_total(r, ctx.idx) or 0.0) for r in ctx.runs if r.direction > 0
    )
    spot_total = sum((spot_pnl_total(r, ctx.idx) or 0.0) for r in ctx.runs)
    print(f"longs_spot={longs_spot:,.0f}  spot_total={spot_total:,.0f}")

    # --- self-check: default cell must reproduce the Gate-5 H1 ---
    default_pool = atm_band_entry_pool(ctx.trades_full, (20, 40), 0.075)
    shorts_default = shorts_optb_total(ctx, default_pool, (20, 40), 0.075, ctx.half_spread)
    h1_default = longs_spot + shorts_default
    stored = pd.read_csv(DERIVED / "phase5_1x.csv")
    b = stored[(stored.underlying == "BTC") & (stored.track == "opt_budget") & (stored["dir"] < 0)]
    spot_stored = pd.read_csv(DERIVED / "phase5_spot.csv")
    s = spot_stored[spot_stored.underlying == "BTC"].fillna({"spot_pnl": 0.0})
    h1_gate5 = float(s[s["dir"] > 0].spot_pnl.sum() + b.pnl_parity.sum())
    print(f"self-check: default cell H1={h1_default:,.2f} vs Gate-5 H1={h1_gate5:,.2f}")
    if abs(h1_default - h1_gate5) > 1.0:
        raise SystemExit("SELF-CHECK FAILED: default grid cell does not reproduce the verified H1")

    # --- linearity verification: one explicit budget=0.05 cell ---
    shorts_005 = shorts_optb_total(ctx, default_pool, (20, 40), 0.075, ctx.half_spread, budget_frac=0.05)
    scaled = shorts_default * (0.05 / PREMIUM_BUDGET_FRAC)
    print(f"linearity check: planned(0.05)={shorts_005:,.2f} vs scaled={scaled:,.2f}")
    if abs(shorts_005 - scaled) > 1.0:
        raise SystemExit("LINEARITY CHECK FAILED: budget scaling is not exact; run all budgets explicitly")

    rows = []
    for dte_band, moneyness, spread in itertools.product(DTE_BANDS, MONEYNESS, SPREADS):
        pool = atm_band_entry_pool(ctx.trades_full, dte_band, moneyness)
        hs = ctx.half_spread * spread
        shorts_10 = shorts_optb_total(ctx, pool, dte_band, moneyness, hs)
        for budget in BUDGETS:
            h1 = longs_spot + shorts_10 * (budget / PREMIUM_BUDGET_FRAC)
            rows.append({
                "budget": budget,
                "dte_band": str(tuple(dte_band)),
                "moneyness": moneyness,
                "spread_mult": spread,
                "h1_total": h1,
                "spot_total": spot_total,
                "h1_beats_spot": h1 > spot_total,
            })
        print(f"dte={dte_band} m={moneyness} spread={spread}x  shorts@10%={shorts_10:+,.0f}")

    df = pd.DataFrame(rows)
    df.to_csv(DERIVED / "phase7_grid.csv", index=False)
    n_win = int(df.h1_beats_spot.sum())
    print(f"\nH1 beats spot in {n_win}/{len(df)} cells")
    print(f"edge range: min={df.h1_total.min() - spot_total:+,.0f}  max={df.h1_total.max() - spot_total:+,.0f}")
    worst = df.loc[df.h1_total.idxmin()]
    best = df.loc[df.h1_total.idxmax()]
    print(f"worst cell: budget={worst.budget} dte={worst.dte_band} m={worst.moneyness} spread={worst.spread_mult}")
    print(f"best  cell: budget={best.budget} dte={best.dte_band} m={best.moneyness} spread={best.spread_mult}")


if __name__ == "__main__":
    main()
