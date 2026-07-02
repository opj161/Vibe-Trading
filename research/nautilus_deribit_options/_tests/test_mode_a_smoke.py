"""Phase 3 Gate 3 regression: BTC-0009 and SOL_USDC-0095 (both chosen because
their opt_budget leg chain includes a mid-run expiry roll, exercising native
cash settlement) run end-to-end through a real NautilusTrader BacktestEngine
and reconcile against the leg planner's own (Gate-2-verified) P&L to well
under the plan's <=$1/run tolerance. Slow (each run loads the full raw
tape) -- not part of the routine fast test suite; run explicitly:
`pytest -m slow research/nautilus_deribit_options/_tests/test_mode_a_smoke.py`.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

_THIS_DIR = Path(__file__).resolve().parent
_PKG_DIR = _THIS_DIR.parent
_VRP_DIR = _PKG_DIR.parent / "vrp_deribit"
for p in (_PKG_DIR, _VRP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def btc_ctx():
    from tape import load_btc_trades, atm_band_entry_pool
    from runs_loader import load_btc_runs
    from config import BTC_HALF_SPREAD, VRP_DERIBIT_DIR
    from phase3_delta_hedged_backtest import build_vol_surface

    derived = VRP_DERIBIT_DIR / "derived"
    idx = pd.read_csv(derived / "daily_index.csv", parse_dates=["date"]).set_index("date")["index_close"]
    idx.index = idx.index.tz_localize(None)
    term = pd.read_csv(derived / "term_structure.csv", parse_dates=["date"])
    term["date"] = term["date"].dt.tz_localize(None)
    surf = build_vol_surface(term)
    trades = atm_band_entry_pool(load_btc_trades())
    runs = {r.run_id: r for r in load_btc_runs()}
    return trades, idx, surf, BTC_HALF_SPREAD, runs


@pytest.fixture(scope="module")
def sol_ctx():
    from tape import load_sol_trades, atm_band_entry_pool, compute_sol_half_spread
    from runs_loader import load_sol_runs
    from phase5_sol_expression import build_derived

    raw = load_sol_trades()
    trades = atm_band_entry_pool(raw)
    half_spread = compute_sol_half_spread(raw)
    idx, surf = build_derived(raw)
    runs = {r.run_id: r for r in load_sol_runs()}
    return trades, idx, surf, half_spread, runs


def test_btc_roll_run_reconciles_to_leg_planner(btc_ctx, tmp_path):
    from leg_planner import plan_run_track, TRACK_OPT_BUDGET
    from run_backtest import run_mode_a
    from postprocess import attribute_run

    trades, idx, surf, half_spread, runs = btc_ctx
    run = runs["BTC-0009"]
    res = plan_run_track(run, TRACK_OPT_BUDGET, trades, idx, surf, half_spread)
    assert len(res.legs) >= 2 and res.legs[0].exit_kind == "expiry", "fixture run must exercise a mid-run roll"

    result = run_mode_a(tmp_path / "catalog_btc", "BTC", res, idx, half_spread)
    attr = attribute_run(res.legs, result.strategy.fills, idx, run)

    assert abs(res.total_pnl - attr["pnl_parity_total"]) <= 1.0
    entry0 = attr["legs"][0]
    assert entry0.entry_fill_px == pytest.approx(res.legs[0].expected_ask, abs=1e-3)
    assert entry0.entry_fill_qty == pytest.approx(res.legs[0].quantity, abs=1e-3)
    assert entry0.settlement_value_per_unit == pytest.approx(res.legs[0].intrinsic_per_unit, abs=1e-6)


def test_sol_roll_run_reconciles_to_leg_planner(sol_ctx, tmp_path):
    from leg_planner import plan_run_track, TRACK_OPT_BUDGET
    from run_backtest import run_mode_a
    from postprocess import attribute_run

    trades, idx, surf, half_spread, runs = sol_ctx
    run = runs["SOL_USDC-0095"]
    res = plan_run_track(run, TRACK_OPT_BUDGET, trades, idx, surf, half_spread)
    assert len(res.legs) >= 2 and res.legs[0].exit_kind == "expiry"

    result = run_mode_a(tmp_path / "catalog_sol", "SOL_USDC", res, idx, half_spread)
    attr = attribute_run(res.legs, result.strategy.fills, idx, run)

    assert abs(res.total_pnl - attr["pnl_parity_total"]) <= 1.0


def test_expiry_fill_carries_zero_commission(btc_ctx, tmp_path):
    """Plan §2.7 / engine.rs:2643: Nautilus's automatic expiry settlement
    fills carry zero commission (unlike a real flip-exit SELL, which is
    charged the venue's normal fee) -- postprocess.py must add Vibe's own
    settlement fee manually rather than trusting the venue's commission."""
    from leg_planner import plan_run_track, TRACK_OPT_BUDGET
    from run_backtest import run_mode_a

    trades, idx, surf, half_spread, runs = btc_ctx
    run = runs["BTC-0009"]
    res = plan_run_track(run, TRACK_OPT_BUDGET, trades, idx, surf, half_spread)
    result = run_mode_a(tmp_path / "catalog_btc2", "BTC", res, idx, half_spread)

    expiry_leg_instrument = f"{res.legs[0].instrument_id}.DERIBIT"
    settlement_sell = next(
        f for f in result.strategy.fills
        if f["order_side"] == "SELL" and f["instrument_id"] == expiry_leg_instrument
    )
    assert settlement_sell["commission"] == "0.00000000 USDC"

    flip_leg_instrument = f"{res.legs[1].instrument_id}.DERIBIT"
    flip_sell = next(
        f for f in result.strategy.fills
        if f["order_side"] == "SELL" and f["instrument_id"] == flip_leg_instrument
    )
    assert float(flip_sell["commission"].split()[0]) > 0.0
