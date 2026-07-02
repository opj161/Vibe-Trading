"""Gate-2 fixture-level tests: roll chaining across multiple expiries, the
<2-dates run skip, and a Gate-2-style reproduction on a fixture subset of
real runs (SOL tape -- fast to load, ~2s) asserting <=$1 tolerance against
the frozen `phase5_sol_per_run.csv` targets.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

import config as C
import leg_planner as LP
import runs_loader as RL
import tape as T
from runs_loader import VibeRun

if str(C.VRP_DERIBIT_DIR) not in sys.path:
    sys.path.insert(0, str(C.VRP_DERIBIT_DIR))


def _flat_scenario():
    """Constant-S, 41-day fixture used for structural (non-parity) checks:
    a run that spans one mid-run expiry (forcing a roll) and ends before
    the rolled leg's own expiry (forcing a flip exit)."""
    day0 = pd.Timestamp("2024-01-01")
    dates = pd.date_range(day0, day0 + pd.Timedelta(days=40), freq="D")
    idx = pd.Series(60000.0, index=dates)
    surf = {d: {30.0: 60.0} for d in dates}
    trades = pd.DataFrame([
        {
            "trade_dt": day0, "opt_type": "C", "dte": 25.0, "logm": 0.0,
            "expiry": day0 + pd.Timedelta(days=25), "strike": 60000.0,
            "index_price": 60000.0, "iv": 60.0, "price": 0.03,
            "instrument_name": "BTC-leg1-60000-C",
        },
        {
            "trade_dt": day0 + pd.Timedelta(days=26), "opt_type": "C", "dte": 30.0, "logm": 0.0,
            "expiry": day0 + pd.Timedelta(days=56), "strike": 60000.0,
            "index_price": 60000.0, "iv": 60.0, "price": 0.03,
            "instrument_name": "BTC-leg2-60000-C",
        },
    ])
    run = VibeRun(run_id="test-roll", underlying="BTC", start=day0, end=day0 + pd.Timedelta(days=40),
                  direction=1, days=40)
    return run, trades, idx, surf


def test_roll_chaining_across_multiple_expiries():
    # Arrange
    run, trades, idx, surf = _flat_scenario()

    # Act
    res = LP.plan_run_track(run, LP.TRACK_OPT_DELTA, trades, idx, surf, half_spread=0.0061)

    # Assert: two legs -- first hits its own expiry mid-run (forcing the
    # roll), second is exited by the run ending before its own expiry
    assert len(res.legs) == 2
    leg1, leg2 = res.legs
    assert leg1.exit_kind == "expiry"
    assert leg2.exit_kind == "flip"
    # Roll continuity: leg2 starts the day after leg1's exit date
    assert leg2.entry_ts.floor("D") == leg1.exit_ts + pd.Timedelta(days=1)
    assert res.entry_found is True
    assert res.skip_reason is None


def test_min_amount_rounds_quantity_to_nearest_lot_step():
    # Arrange
    run, trades, idx, surf = _flat_scenario()

    # Act
    unrounded = LP.plan_run_track(run, LP.TRACK_OPT_BUDGET, trades, idx, surf, half_spread=0.0061)
    rounded = LP.plan_run_track(run, LP.TRACK_OPT_BUDGET, trades, idx, surf, half_spread=0.0061, min_amount=0.1)

    # Assert: rounding changes quantity to an exact multiple of the lot
    # step without breaking the leg chain structure, and the effect on P&L
    # is small (a lot-size stress, not a different strategy)
    assert len(rounded.legs) == len(unrounded.legs) == 2
    for leg in rounded.legs:
        ratio = leg.quantity / 0.1
        assert ratio == pytest.approx(round(ratio), abs=1e-9)
    assert unrounded.legs[0].quantity != rounded.legs[0].quantity
    assert abs(rounded.total_pnl - unrounded.total_pnl) < 0.01 * abs(unrounded.total_pnl)


def test_no_lookahead_leg_chain_never_selects_pre_leg_start_prints():
    # Arrange: a print exists BEFORE the run even starts -- must never be
    # selected as the first leg's entry.
    run, trades, idx, surf = _flat_scenario()
    stale_print = trades.iloc[[0]].copy()
    stale_print["trade_dt"] = run.start - pd.Timedelta(days=10)
    stale_print["instrument_name"] = "BTC-stale-60000-C"
    trades_with_stale = pd.concat([stale_print, trades], ignore_index=True)

    # Act
    res = LP.plan_run_track(run, LP.TRACK_OPT_DELTA, trades_with_stale, idx, surf, half_spread=0.0061)

    # Assert: first leg's entry is still the day0 print, not the stale one
    assert res.legs[0].instrument_id == "BTC-leg1-60000-C"


def test_insufficient_dates_run_is_skipped_entirely():
    # Arrange: a run whose [start, end] spans a single daily-index date
    day0 = pd.Timestamp("2024-01-01")
    idx = pd.Series([60000.0], index=[day0])
    run = VibeRun(run_id="test-skip", underlying="BTC", start=day0, end=day0, direction=1, days=0)
    trades = pd.DataFrame(columns=["trade_dt", "opt_type", "dte", "logm", "expiry", "strike",
                                    "index_price", "iv", "price", "instrument_name"])

    # Act
    result = LP.plan_run(run, trades, idx, {}, half_spread=0.0061)

    # Assert: whole run skipped -- no legs attempted, all pnl fields None
    assert result["skip_reason"] == "insufficient_dates"
    assert result["spot"] is None
    assert result["opt_delta"] is None
    assert result["opt_budget"] is None
    assert result["legs_opt_delta"] == []


def test_no_option_entry_ends_leg_chain_without_error():
    # Arrange: valid run window but an empty trades pool -- no entry ever found
    day0 = pd.Timestamp("2024-01-01")
    dates = pd.date_range(day0, day0 + pd.Timedelta(days=10), freq="D")
    idx = pd.Series(60000.0, index=dates)
    run = VibeRun(run_id="test-noentry", underlying="BTC", start=day0, end=dates[-1], direction=1, days=10)
    trades = pd.DataFrame(columns=["trade_dt", "opt_type", "dte", "logm", "expiry", "strike",
                                    "index_price", "iv", "price", "instrument_name"])

    # Act
    res = LP.plan_run_track(run, LP.TRACK_OPT_DELTA, trades, idx, {}, half_spread=0.0061)

    # Assert
    assert res.legs == []
    assert res.total_pnl == 0.0
    assert res.entry_found is False
    assert res.skip_reason == "no_option_entry"


@pytest.fixture(scope="module")
def sol_gate2_fixture():
    """Loads the real SOL tape (fast, ~1-2s) and reproduces phase5's exact
    long-first-then-short assembly order for the first 10 in-window runs,
    to keep the fixture-subset test cheap while still exercising real tape
    data end to end."""
    if not C.SOL_TAPE_PATH.exists():
        pytest.skip("raw SOL tape not present")
    sol_trades = T.load_sol_trades()
    half_spread = T.compute_sol_half_spread(sol_trades)
    pool = T.atm_band_entry_pool(sol_trades)
    from phase5_sol_expression import build_derived  # noqa: E402
    idx, surf = build_derived(sol_trades)

    runs = RL.load_sol_runs()
    in_window = [r for r in runs if r.start >= idx.index.min()]
    long_runs = [r for r in in_window if r.direction == 1][:5]
    short_runs = [r for r in in_window if r.direction == -1][:5]
    return {
        "pool": pool, "idx": idx, "surf": surf, "half_spread": half_spread,
        "long_runs": long_runs, "short_runs": short_runs,
    }


def test_gate2_style_reproduction_on_sol_fixture_subset(sol_gate2_fixture):
    """Reproduces Gate 2's methodology on a 10-run subset: compute
    opt_delta/opt_budget/spot totals via the leg planner, in phase5's own
    long-then-short assembly order, and diff against the frozen per-run
    targets at <=$1 absolute tolerance."""
    f = sol_gate2_fixture

    def compute(runs):
        rows = []
        for r in runs:
            out = LP.plan_run(r, f["pool"], f["idx"], f["surf"], f["half_spread"])
            if out["skip_reason"] is None:
                rows.append(out)
        return rows

    rows = compute(f["long_runs"]) + compute(f["short_runs"])
    assert rows, "fixture produced no comparable rows -- check run window/tape alignment"

    mine = pd.DataFrame(rows)[["start", "dir", "days", "spot", "opt_delta", "opt_budget"]].reset_index(drop=True)
    frozen_full = pd.read_csv(C.FROZEN_SOL_PER_RUN_CSV, parse_dates=["start"])
    frozen_full = frozen_full[["start", "dir", "days", "spot", "opt_delta", "opt_budget"]].reset_index(drop=True)

    # Match by (start, dir, days) -- a precise natural key shared by both
    # sides, robust to either side's subset ordering.
    merged = mine.merge(frozen_full, on=["start", "dir", "days"], suffixes=("_mine", "_frozen"))
    assert len(merged) == len(mine), (
        f"only {len(merged)}/{len(mine)} fixture rows matched a frozen row by (start,dir,days) -- "
        "run selection/window logic has likely drifted from phase5_sol_expression.py"
    )

    for col in ("spot", "opt_delta", "opt_budget"):
        diff = (merged[f"{col}_mine"] - merged[f"{col}_frozen"]).abs()
        assert diff.max() <= 1.0, f"{col} exceeds $1 tolerance: max diff {diff.max():.4f}"
