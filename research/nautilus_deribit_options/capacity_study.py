"""Capacity study (fresh assessment 2026-07-03; re-run QUARTERLY for SOL): for every historical H1 put entry, what fraction of that
day's printed volume would our order have been? (Printed volume is a proxy
for book depth -- >100% of a day's prints = clearly capacity-constrained.)"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from data_ctx import load_ctx
from leg_planner import plan_run_track, TRACK_OPT_BUDGET

for und in ["BTC", "SOL_USDC"]:
    ctx = load_ctx(und)
    t = ctx.trades_full
    print(f"\n=== {und} ===  (amount in underlying units: BTC=1/contract, SOL=10/contract, verified)")
    t["date"] = t["trade_dt"].dt.floor("D")
    inst_day_vol = t.groupby(["instrument_name", "date"])["amount"].sum()
    band = ctx.entry_pool.copy(); band["date"] = band["trade_dt"].dt.floor("D")
    band_day_vol = band.groupby("date")["amount"].sum()

    rows = []
    for run in ctx.runs:
        if run.direction >= 0: continue
        res = plan_run_track(run, TRACK_OPT_BUDGET, ctx.entry_pool, ctx.idx, ctx.surf, ctx.half_spread)
        for leg in res.legs:
            d = leg.entry_ts.floor("D")
            iv_ = inst_day_vol.get((leg.instrument_id, d), 0.0)
            bv = band_day_vol.get(d, np.nan)
            rows.append({
                "qty": leg.quantity,
                "inst_day_vol": iv_,
                "band_day_vol": bv,
                "part_inst": leg.quantity / iv_ if iv_ > 0 else np.inf,
                "part_band": leg.quantity / bv if bv and bv > 0 else np.inf,
                "premium_usd": leg.expected_entry_cost,
            })
    df = pd.DataFrame(rows)
    print(f"H1 put entries (short runs, incl rolls): {len(df)}  | premium/entry median ${df.premium_usd.median():,.0f}")
    for col, label in [("part_inst", "vs SAME-INSTRUMENT same-day volume"),
                       ("part_band", "vs ATM-BAND(20-40d) same-day volume")]:
        p = df[col].replace(np.inf, 10.0)
        print(f"  participation {label}: median={df[col].median()*100:6.1f}%  p75={df[col].quantile(.75)*100:6.1f}%  "
              f"p90={df[col].quantile(.90)*100:6.1f}%  >100%: {(df[col]>1).mean()*100:4.1f}% of entries")
    # capacity at 10% band participation
    cap_units = band_day_vol.median() * 0.10
    med_prem_per_unit = (df.premium_usd / df.qty).median()
    cap_premium = cap_units * med_prem_per_unit
    # premium = 10% of notional -> notional capacity
    print(f"  median band day volume: {band_day_vol.median():,.0f} units; at 10% participation ->"
          f" ~${cap_premium:,.0f} premium/day -> ~${cap_premium/0.10:,.0f} strategy notional")
