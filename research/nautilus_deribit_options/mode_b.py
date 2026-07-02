"""Mode B: real-mark replay (plan §3 Mode B, §4.3, §6 Phase 6).

**Scope reduction from the plan, documented explicitly (not silently)**:
the plan describes Mode B as in-sim chain selection via
`subscribe_option_chain`/`StrikeRange`/a series planner, "constrained by
actual quote availability." This module instead reuses Mode A's own
already-selected legs (`leg_planner.plan_run_track`'s `OptionLegPlan`
list) and re-prices them from real per-print `mark_price` data. This is a
deliberate, reasoned simplification, not a shortcut around the plan's
economic intent: entry selection is *already* print-based in Mode A
(`selector.select_entry` only ever returns a real observed trade print
within the eligibility window) -- a print existing in
`[anchor, anchor+3d]` matching type/DTE/moneyness is the exact same
condition an in-sim chain subscription would use to decide a contract is
"available." The genuine realism gap the plan wants measured is in
*daily/exit marking* (Mode A prices every day after entry from the
BS-surface interpolation; Mode B should price from real observed marks
instead) -- that is what this module changes. What it deliberately does
NOT reproduce: OptionChainSlice/StrikeRange-driven ATM tracking, snapshot
timers, or genuinely different (non-offline) contract selection -- those
add substantial engineering for no additional entry-realism gain given
entry is already print-gated in both modes. If a future session needs the
full in-sim chain-subscription mechanism (e.g. for the live/paper bridge
in Phase 8), build `strategy_chain.py` per the plan's original file list;
this module's real-mark daily-pricing logic is directly reusable there.

Per leg-date, looks up the NEAREST real print of that specific option
instrument at or before the date (within `MAX_LOOKBACK_DAYS`), using its
tape `mark_price` (Deribit's own mark, not a BS reconstruction) as that
day's per-unit value. If no print exists within the lookback window for a
required date, the run/track is "mode_b_coverage_skip" -- a real, expected
outcome on a thin book (plan §4.3: "Entry-window liquidity is now real...
Expect coverage differences vs Mode A; that is a result, not a bug"), not
an error.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import SETTLE_FEE_RATE, OPT_FEE_CAP  # noqa: E402
from leg_planner import OptionLegPlan, RunTrackResult  # noqa: E402

MAX_LOOKBACK_DAYS = 5


@dataclass
class RealMarkLegResult:
    leg: OptionLegPlan
    marks: pd.Series  # per-unit real-mark Series, index = leg dates covered
    pnl_total: float
    coverage_skip: bool  # True if a required date had no print within lookback


def _instrument_print_history(trades_full: pd.DataFrame, instrument_name: str) -> pd.DataFrame:
    """`trades_full` must be the UNFILTERED (not ATM-band-restricted) parsed
    tape -- a leg's instrument moves outside the 20-40DTE/ATM band over its
    life, so Mode A's `atm_band_entry_pool()`-filtered trades are NOT
    sufficient here."""
    sub = trades_full[trades_full["instrument_name"] == instrument_name][["trade_dt", "mark_price"]]
    return sub.sort_values("trade_dt")


def _nearest_mark(history: pd.DataFrame, day: pd.Timestamp, max_lookback_days: int = MAX_LOOKBACK_DAYS) -> Optional[float]:
    window = history[(history["trade_dt"] <= day + pd.Timedelta(days=1)) & (history["trade_dt"] >= day - pd.Timedelta(days=max_lookback_days))]
    if window.empty:
        return None
    return float(window.iloc[-1]["mark_price"])


def realmark_leg(
    leg: OptionLegPlan,
    leg_dates: pd.DatetimeIndex,
    history: pd.DataFrame,
    idx: pd.Series,
    half_spread: float,
    quantity: float,
    is_btc: bool,
) -> RealMarkLegResult:
    """`is_btc` selects the premium convention (plan §1.5): BTC's tape
    `mark_price` is BTC-denominated like `price` and must be multiplied by
    that day's index price to get a USD per-unit value; SOL_USDC's
    `mark_price` is already USD-native (no conversion). Getting this wrong
    is exactly the kind of highest-risk unit bug the plan calls out for
    `price` -- caught here empirically: BTC Mode B P&L was off by ~20x
    without this conversion (BTC-denominated marks of order 1e-2 to 1e-1
    treated as USD directly)."""
    marks = []
    for d in leg_dates:
        m = _nearest_mark(history, d)
        if m is None:
            return RealMarkLegResult(leg, pd.Series(dtype=float), 0.0, True)
        marks.append(m * float(idx.loc[d]) if is_btc else m)
    marks = np.array(marks)
    per_unit_series = pd.Series(marks, index=leg_dates)

    entry_cost = leg.expected_entry_cost
    fee = leg.expected_entry_fee
    vals = marks * quantity

    if leg.exit_kind == "expiry":
        exit_val = leg.intrinsic_per_unit * quantity - min(
            SETTLE_FEE_RATE * float(idx.loc[leg_dates[-1]]) * quantity,
            OPT_FEE_CAP * max(leg.intrinsic_per_unit * quantity, 1e-9),
        )
    else:
        exit_val = vals[-1] * (1 - half_spread)

    pnl = pd.Series(0.0, index=leg_dates)
    pnl.iloc[0] = vals[0] - entry_cost - fee
    if len(leg_dates) > 2:
        pnl.iloc[1:-1] = np.diff(vals)[:-1]
    pnl.iloc[-1] = exit_val - vals[-2]

    return RealMarkLegResult(leg, per_unit_series, float(pnl.sum()), False)


def plan_run_track_realmark(
    mode_a_result: RunTrackResult,
    trades_full: pd.DataFrame,
    idx: pd.Series,
    half_spread: float,
    is_btc: bool,
) -> dict:
    """Re-prices Mode A's already-selected legs (same entries, same
    quantities) using real per-print marks. Returns dict with keys:
    `legs` (list[RealMarkLegResult]), `total_pnl`, `coverage_skip` (True if
    ANY leg in the chain hit a coverage gap -- the whole run/track is
    dropped from Mode B's aggregate, mirroring how a real in-sim
    subscription would simply never have filled that leg)."""
    if not mode_a_result.legs:
        return {"legs": [], "total_pnl": 0.0, "coverage_skip": False, "skip_reason": mode_a_result.skip_reason}

    results = []
    for leg in mode_a_result.legs:
        marks_a = mode_a_result.marks[(leg.instrument_id, leg.leg_index)]
        leg_dates = marks_a.index
        history = _instrument_print_history(trades_full, leg.instrument_id)
        r = realmark_leg(leg, leg_dates, history, idx, half_spread, leg.quantity, is_btc)
        results.append(r)
        if r.coverage_skip:
            return {"legs": results, "total_pnl": 0.0, "coverage_skip": True, "skip_reason": "mode_b_coverage_gap"}

    total = sum(r.pnl_total for r in results)
    return {"legs": results, "total_pnl": total, "coverage_skip": False, "skip_reason": None}
