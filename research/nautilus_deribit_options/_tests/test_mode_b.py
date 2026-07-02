"""mode_b.py regression tests. Focused on the BTC mark-price unit-conversion
bug found during Phase 6 (§1.5's premium-convention asymmetry applies to
`mark_price`, not just `price`) -- guards against reintroducing it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_THIS_DIR = Path(__file__).resolve().parent
_PKG_DIR = _THIS_DIR.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

import mode_b as MB  # noqa: E402
from leg_planner import OptionLegPlan  # noqa: E402


def _fixture_leg(exit_kind="flip"):
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    return OptionLegPlan(
        run_id="test", track="opt_budget", instrument_id="X-1", entry_ts=dates[0],
        quantity=10.0, expected_ask=100.0, expected_entry_cost=1000.0, expected_entry_fee=1.0,
        exit_kind=exit_kind, exit_ts=dates[-1], leg_index=0, intrinsic_per_unit=5.0 if exit_kind == "expiry" else None,
    ), dates


def test_btc_mark_price_is_multiplied_by_index_price():
    # Arrange: BTC-denominated mark_price of 0.002, index at 50000 -> USD mark = 100
    leg, dates = _fixture_leg()
    history = pd.DataFrame({"trade_dt": dates, "mark_price": [0.002, 0.0021, 0.0019]})
    idx = pd.Series([50000.0, 51000.0, 49000.0], index=dates)

    # Act
    result = MB.realmark_leg(leg, dates, history, idx, half_spread=0.0061, quantity=10.0, is_btc=True)

    # Assert: per-unit mark on the LAST date (no forward-peek ambiguity)
    # must be mark_price * index, not raw mark_price
    assert not result.coverage_skip
    assert result.marks.iloc[-1] == pytest.approx(0.0019 * 49000.0)


def test_sol_mark_price_is_used_directly_no_conversion():
    # Arrange: SOL mark_price already USD-native
    leg, dates = _fixture_leg()
    history = pd.DataFrame({"trade_dt": dates, "mark_price": [12.5, 12.6, 12.4]})
    idx = pd.Series([150.0, 151.0, 149.0], index=dates)

    # Act
    result = MB.realmark_leg(leg, dates, history, idx, half_spread=0.0131, quantity=10.0, is_btc=False)

    # Assert: no conversion applied -- last-date mark equals its raw tape value
    assert not result.coverage_skip
    assert result.marks.iloc[-1] == pytest.approx(12.4)


def test_missing_print_beyond_lookback_triggers_coverage_skip():
    # Arrange: no prints at all near the required dates
    leg, dates = _fixture_leg()
    history = pd.DataFrame({"trade_dt": [pd.Timestamp("2023-01-01")], "mark_price": [0.001]})
    idx = pd.Series([50000.0] * 3, index=dates)

    # Act
    result = MB.realmark_leg(leg, dates, history, idx, half_spread=0.0061, quantity=10.0, is_btc=True)

    # Assert
    assert result.coverage_skip is True
    assert result.pnl_total == 0.0
