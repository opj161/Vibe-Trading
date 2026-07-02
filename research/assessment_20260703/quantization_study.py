"""H1 put-leg quantization at retail scale: per-entry short notional grid,
exact via leg-P&L linearity in quantity. Two policies:
  floor  -- floor(q/lot) lots, skip leg if 0 (never overspend)
  min1   -- max(round(q/lot),1) lots (always enter, may overspend premium)
"""
import sys
import numpy as np, pandas as pd
R = "/home/j_opp/projects/Vibe-Trading"
sys.path.insert(0, f"{R}/research/nautilus_deribit_options")
from data_ctx import load_ctx
from leg_planner import plan_run_track, TRACK_OPT_BUDGET

GRID = [250, 500, 1000, 2500, 5000, 12500, 25000]  # per-entry short notional $
BASE = 500_000.0

for und, lot in [("BTC", 0.1), ("SOL_USDC", 10.0)]:
    ctx = load_ctx(und)
    legs = []
    for run in ctx.runs:
        if run.direction >= 0: continue
        res = plan_run_track(run, TRACK_OPT_BUDGET, ctx.entry_pool, ctx.idx, ctx.surf, ctx.half_spread)
        for leg in res.legs:
            legs.append({"q": leg.quantity, "pnl": leg.pnl_total,
                         "ask": leg.expected_ask, "prem": leg.expected_entry_cost})
    df = pd.DataFrame(legs)
    df["ppu"] = df.pnl / df.q       # P&L per underlying unit (exact, linearity)
    ideal_pnl_frac = df.pnl.sum() / BASE   # short-side H1 P&L per $ of entry notional
    print(f"\n=== {und} (lot={lot} units, {len(df)} legs; unrounded short-leg P&L = "
          f"{ideal_pnl_frac*100:+.1f}% of per-entry notional over the window) ===")
    print(f"{'notional':>9} | {'floor: entered':>14} {'P&L retention':>13} | {'min1: overspend':>15} {'P&L retention':>13}")
    for N in GRID:
        s = N / BASE
        q = df.q * s
        # floor policy
        lots_f = np.floor(q / lot)
        qf = lots_f * lot
        entered = (lots_f > 0).mean()
        ret_f = (qf * df.ppu).sum() / (q * df.ppu).sum()
        # min1 policy
        lots_m = np.maximum(np.round(q / lot), 1)
        qm = lots_m * lot
        overspend = (qm * df.ask).sum() / (q * df.ask).sum()
        ret_m = (qm * df.ppu).sum() / (q * df.ppu).sum()
        print(f"${N:>8,} | {entered*100:13.0f}% {ret_f*100:12.0f}% | {overspend:14.2f}x {ret_m*100:12.0f}%")
