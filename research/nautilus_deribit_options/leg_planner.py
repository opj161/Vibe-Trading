"""The full per-run leg-chain builder, reproducing plan §1.3 exactly for
both the BTC (`phase4_trend_expression_options.py`) and SOL
(`phase5_sol_expression.py`) parity oracles. Reuses the imported BS/surface
helpers from `research/vrp_deribit/phase3_delta_hedged_backtest.py` (BTC)
and `phase5_sol_expression.py` (SOL) rather than reimplementing them.

Key algebraic note verified while implementing this (not in the plan, but
true of both oracle scripts): because the daily-mark P&L layout is a
telescoping sum of `diff(vals)`, a leg's TOTAL P&L always reduces to
`exit_val - entry_cost - fee`, independent of the intermediate daily marks.
The full daily array is still computed and returned (needed for
`_tests/test_leg_planner.py`'s no-lookahead/roll-chaining checks and for
any future Nautilus-side per-day attribution), but Gate 2's per-run total
reconciliation depends only on this identity holding, which both oracle
scripts share by construction (same code shape, `pnl.iloc[0] = vals[0] -
entry_cost - fee`, `pnl.iloc[1:-1] = diff(vals)[:-1]`, `pnl.iloc[-1] =
exit_val - vals[-2]`).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import (  # noqa: E402
    BTC_UNDERLYING_SYMBOL,
    DTE_BAND,
    ENTRY_NOTIONAL,
    OPT_FEE_CAP,
    OPT_FEE_RATE,
    PREMIUM_BUDGET_FRAC,
    SETTLE_FEE_RATE,
    SPOT_TAKER,
    VRP_DERIBIT_DIR,
)
from runs_loader import VibeRun  # noqa: E402
from selector import select_entry  # noqa: E402

if str(VRP_DERIBIT_DIR) not in sys.path:
    sys.path.insert(0, str(VRP_DERIBIT_DIR))

from phase3_delta_hedged_backtest import bs_price_and_delta  # noqa: E402
from phase3_delta_hedged_backtest import interp_iv as btc_interp_iv  # noqa: E402
from phase3_delta_hedged_backtest import nearest_surf as btc_nearest_surf  # noqa: E402
from phase5_sol_expression import bs_usd  # noqa: E402
from phase5_sol_expression import interp_iv as sol_interp_iv  # noqa: E402
from phase5_sol_expression import nearest_surf as sol_nearest_surf  # noqa: E402

TRACK_OPT_DELTA = "opt_delta"
TRACK_OPT_BUDGET = "opt_budget"
MIN_DELTA_FLOOR = 0.05
IV_FLOOR = 5.0  # vol points


@dataclass(frozen=True)
class OptionLegPlan:
    """Mode A executable ledger row (plan §3.2)."""

    run_id: str
    track: str  # "opt_delta" | "opt_budget"
    instrument_id: str
    entry_ts: pd.Timestamp
    quantity: float
    expected_ask: float
    expected_entry_cost: float
    expected_entry_fee: float
    exit_kind: str  # "flip" | "expiry"
    exit_ts: pd.Timestamp
    leg_index: int
    pnl_total: float = 0.0
    intrinsic_per_unit: Optional[float] = None  # set only when exit_kind == "expiry"
    entry_index_price: float = 0.0  # S_entry -- the entry print's own index_price (not a daily close)


@dataclass(frozen=True)
class _Convention:
    is_btc: bool
    pricer_fn: Callable
    interp_iv_fn: Callable
    nearest_surf_fn: Callable


BTC_CONVENTION = _Convention(True, bs_price_and_delta, btc_interp_iv, btc_nearest_surf)
SOL_CONVENTION = _Convention(False, bs_usd, sol_interp_iv, sol_nearest_surf)


def convention_for(underlying: str) -> _Convention:
    return BTC_CONVENTION if underlying == BTC_UNDERLYING_SYMBOL else SOL_CONVENTION


def _ask_per_unit(price_native: float, S: float, half_spread: float, is_btc: bool) -> float:
    return price_native * (1 + half_spread) * S if is_btc else price_native * (1 + half_spread)


def _usd_value_per_unit(pricer_fn, S, K, T, sigma, opt_type, is_btc) -> tuple[float, float]:
    v, delta = pricer_fn(S, K, T, sigma, opt_type)
    return (v * S if is_btc else v), delta


def run_dates(run: VibeRun, idx: pd.Series) -> pd.DatetimeIndex:
    """Daily-index dates in [run.start, run.end] -- the shared date window
    every track (spot + both option tracks) uses to decide the <2-dates
    skip and to anchor leg 0."""
    return idx.index[(idx.index >= run.start) & (idx.index <= run.end)]


def spot_pnl_total(run: VibeRun, idx: pd.Series) -> Optional[float]:
    """SPOT baseline: frozen-quantity, engine-faithful. Returns None if the
    run has <2 daily-index dates (the run is entirely skipped, not just its
    option legs)."""
    dates = run_dates(run, idx)
    if len(dates) < 2:
        return None
    S0 = idx.loc[dates[0]]
    qty = ENTRY_NOTIONAL / S0
    diffs = np.diff(idx.loc[dates].values)
    pnl = run.direction * qty * diffs
    total = float(pnl.sum())
    total -= SPOT_TAKER * ENTRY_NOTIONAL
    total -= SPOT_TAKER * qty * idx.loc[dates[-1]]
    return total


def plan_leg(
    run: VibeRun,
    track: str,
    leg_start: pd.Timestamp,
    dates_end: pd.Timestamp,
    qty_spot: float,
    trades: pd.DataFrame,
    idx: pd.Series,
    surf: dict,
    half_spread: float,
    convention: _Convention,
    leg_index: int,
    min_amount: Optional[float] = None,
    dte_band: tuple[float, float] = DTE_BAND,
    moneyness_band: float = 0.075,
    budget_frac: float = PREMIUM_BUDGET_FRAC,
) -> Optional[tuple[OptionLegPlan, pd.Series]]:
    """Build and price ONE leg starting at `leg_start`. Returns
    (OptionLegPlan, daily_pnl_series) or None if no eligible entry print
    exists in [leg_start, leg_start+3d], or the entry print's floored date
    is >= dates_end (mirrors both oracle scripts' `entry["entry_dt"] >=
    dates[-1]: break`).

    `min_amount`, if set, rounds `quantity` to the nearest venue lot step
    (plan §2.10: BTC options 0.1 BTC, SOL_USDC 10-SOL contracts) BEFORE any
    cost/fee/mark computation -- a "corrected-mode stress" per the plan,
    deliberately NOT part of parity mode (which uses continuous quantity,
    matching Vibe's own no-lot-rounding assumption exactly)."""
    opt_type = "C" if run.direction > 0 else "P"
    row = select_entry(trades, leg_start, opt_type, dte_band=dte_band, moneyness_band=moneyness_band)
    if row is None:
        return None
    entry_dt = row["trade_dt"].floor("D")
    if entry_dt >= dates_end:
        return None

    expiry = pd.Timestamp(row["expiry"])
    strike = float(row["strike"])
    S_entry = float(row["index_price"])
    iv_entry = float(row["iv"])
    price_native = float(row["price"])

    T0 = max((expiry - entry_dt).total_seconds(), 1) / (365 * 86400)
    _, delta0 = convention.pricer_fn(S_entry, strike, T0, iv_entry / 100.0, opt_type)

    ask_per_unit = _ask_per_unit(price_native, S_entry, half_spread, convention.is_btc)
    if track == TRACK_OPT_DELTA:
        quantity = qty_spot / max(abs(delta0), MIN_DELTA_FLOOR)
    else:
        quantity = (budget_frac * ENTRY_NOTIONAL) / max(ask_per_unit, 1e-9)

    if min_amount is not None and min_amount > 0:
        quantity = max(round(quantity / min_amount) * min_amount, min_amount)

    entry_cost = ask_per_unit * quantity
    fee = min(OPT_FEE_RATE * S_entry * quantity, OPT_FEE_CAP * entry_cost)

    end = min(expiry.floor("D"), dates_end)
    leg_dates = idx.index[(idx.index >= entry_dt) & (idx.index <= end)]
    if len(leg_dates) < 2:
        return None

    vals = []
    for d in leg_dates:
        Sd = idx.loc[d]
        T = max((expiry - d).total_seconds(), 0) / (365 * 86400)
        sigma = max(
            convention.interp_iv_fn(convention.nearest_surf_fn(surf, d), max(T * 365, 0.5), iv_entry),
            IV_FLOOR,
        ) / 100.0
        v_usd, _ = _usd_value_per_unit(convention.pricer_fn, Sd, strike, T, sigma, opt_type, convention.is_btc)
        vals.append(v_usd * quantity)
    vals = np.array(vals)

    is_expiry_exit = end >= expiry.floor("D")
    S_end = idx.loc[leg_dates[-1]]
    intrinsic_per_unit = None
    if is_expiry_exit:
        intrinsic_per_unit = max(S_end - strike, 0.0) if opt_type == "C" else max(strike - S_end, 0.0)
        intrinsic = intrinsic_per_unit * quantity
        exit_val = intrinsic - min(SETTLE_FEE_RATE * S_end * quantity, OPT_FEE_CAP * max(intrinsic, 1e-9))
        exit_kind = "expiry"
    else:
        exit_val = vals[-1] * (1 - half_spread)
        exit_kind = "flip"

    pnl = pd.Series(0.0, index=leg_dates)
    pnl.iloc[0] = vals[0] - entry_cost - fee
    if len(leg_dates) > 2:
        pnl.iloc[1:-1] = np.diff(vals)[:-1]
    pnl.iloc[-1] = exit_val - vals[-2]

    marks_per_unit = pd.Series(vals / quantity, index=leg_dates)

    instrument_id = str(row["instrument_name"]) if "instrument_name" in row.index else ""

    plan = OptionLegPlan(
        run_id=run.run_id,
        track=track,
        instrument_id=instrument_id,
        entry_ts=row["trade_dt"],
        quantity=float(quantity),
        expected_ask=float(ask_per_unit),
        expected_entry_cost=float(entry_cost),
        expected_entry_fee=float(fee),
        exit_kind=exit_kind,
        exit_ts=leg_dates[-1],
        leg_index=leg_index,
        pnl_total=float(pnl.sum()),
        intrinsic_per_unit=intrinsic_per_unit,
        entry_index_price=S_entry,
    )
    return plan, pnl, marks_per_unit


@dataclass
class RunTrackResult:
    run_id: str
    track: str
    legs: list
    total_pnl: float
    entry_found: bool
    skip_reason: Optional[str]
    marks: dict = None  # (instrument_id, leg_index) -> per-unit mark pd.Series, for catalog_parity.py


def plan_run_track(
    run: VibeRun,
    track: str,
    trades: pd.DataFrame,
    idx: pd.Series,
    surf: dict,
    half_spread: float,
    min_amount: Optional[float] = None,
    dte_band: tuple[float, float] = DTE_BAND,
    moneyness_band: float = 0.075,
    budget_frac: float = PREMIUM_BUDGET_FRAC,
) -> RunTrackResult:
    """Build the full roll chain for one (run, track) pair -- plan §1.3's
    `while leg_start < dates[-1]` loop. `min_amount` is the optional
    lot-rounding stress param, passed through to every `plan_leg` call."""
    convention = convention_for(run.underlying)
    dates = run_dates(run, idx)
    if len(dates) < 2:
        return RunTrackResult(run.run_id, track, [], 0.0, False, "insufficient_dates", {})

    S0 = idx.loc[dates[0]]
    qty_spot = ENTRY_NOTIONAL / S0

    leg_start = dates[0]
    legs: list[OptionLegPlan] = []
    marks: dict = {}
    total = 0.0
    entry_found = False
    leg_index = 0
    while leg_start < dates[-1]:
        result = plan_leg(run, track, leg_start, dates[-1], qty_spot, trades, idx, surf, half_spread, convention, leg_index,
                           min_amount, dte_band, moneyness_band, budget_frac)
        if result is None:
            break
        plan, pnl_series, marks_series = result
        entry_found = True
        legs.append(plan)
        marks[(plan.instrument_id, plan.leg_index)] = marks_series
        total += plan.pnl_total
        leg_end = pnl_series.index[-1]
        if leg_end >= dates[-1]:
            break
        leg_start = leg_end + pd.Timedelta(days=1)
        leg_index += 1

    skip_reason = None if entry_found else "no_option_entry"
    return RunTrackResult(run.run_id, track, legs, total, entry_found, skip_reason, marks)


def plan_run(
    run: VibeRun,
    trades: pd.DataFrame,
    idx: pd.Series,
    surf: dict,
    half_spread: float,
) -> dict:
    """Convenience wrapper: builds both tracks + spot for one run. Returns a
    dict with keys spot/opt_delta/opt_budget/legs_opt_delta/legs_opt_budget/
    skip_reason (None unless <2 dates). `start` in the returned dict is the
    daily-index-floored `dates[0]` (matching the frozen per-run CSVs'
    `start` column convention), NOT the raw `run.start` timestamp."""
    dates = run_dates(run, idx)
    if len(dates) < 2:
        return {
            "run_id": run.run_id, "start": run.start, "dir": run.direction, "days": run.days,
            "spot": None, "opt_delta": None, "opt_budget": None,
            "legs_opt_delta": [], "legs_opt_budget": [], "skip_reason": "insufficient_dates",
        }
    spot = spot_pnl_total(run, idx)
    od = plan_run_track(run, TRACK_OPT_DELTA, trades, idx, surf, half_spread)
    ob = plan_run_track(run, TRACK_OPT_BUDGET, trades, idx, surf, half_spread)
    return {
        "run_id": run.run_id, "start": dates[0], "dir": run.direction, "days": run.days,
        "spot": spot, "opt_delta": od.total_pnl, "opt_budget": ob.total_pnl,
        "legs_opt_delta": od.legs, "legs_opt_budget": ob.legs,
        "skip_reason": None,
    }
