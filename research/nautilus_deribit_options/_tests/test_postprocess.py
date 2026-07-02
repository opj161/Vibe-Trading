"""postprocess.py fee-mode tests (plan §5, §7 test list's test_fee_modes /
test_postprocess): parity mode removes flip-exit commission; native mode
retains it; expiry legs carry the Vibe settlement fee in BOTH modes
(regression for the audit-found bug where native mode silently dropped the
settlement fee, making "native" less conservative than "parity" on expiry
legs -- backwards from the plan's intent).
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

from config import OPT_FEE_CAP, SETTLE_FEE_RATE  # noqa: E402
from leg_planner import OptionLegPlan  # noqa: E402
from postprocess import attribute_leg  # noqa: E402


def _leg(exit_kind: str, intrinsic: float | None = None) -> OptionLegPlan:
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    return OptionLegPlan(
        run_id="test", track="opt_budget", instrument_id="BTC-TEST-50000-P",
        entry_ts=dates[0], quantity=10.0, expected_ask=100.0,
        expected_entry_cost=1000.0, expected_entry_fee=2.5,
        exit_kind=exit_kind, exit_ts=dates[-1], leg_index=0,
        intrinsic_per_unit=intrinsic,
    )


def _entry_fill(px: float = 100.0, commission: float = 2.5) -> dict:
    return {
        "instrument_id": "BTC-TEST-50000-P.DERIBIT", "order_side": "BUY",
        "last_px": px, "last_qty": 10.0, "commission": f"{commission} USDC",
        "ts_event": 1,
    }


def _exit_fill(px: float, commission: float) -> dict:
    return {
        "instrument_id": "BTC-TEST-50000-P.DERIBIT", "order_side": "SELL",
        "last_px": px, "last_qty": 10.0, "commission": f"{commission} USDC",
        "ts_event": 2,
    }


def test_flip_leg_parity_excludes_exit_commission_native_includes_it():
    # Arrange
    leg = _leg("flip")
    fills = [_entry_fill(commission=2.5), _exit_fill(px=90.0, commission=1.8)]

    # Act
    attr = attribute_leg(leg, fills, underlying_end_price=0.0)

    # Assert: parity = exit_val - entry_cost - entry_fee (no exit fee);
    # native = parity - exit_commission
    expected_parity = 90.0 * 10.0 - 100.0 * 10.0 - 2.5
    assert attr.pnl_parity == pytest.approx(expected_parity)
    assert attr.pnl_native == pytest.approx(expected_parity - 1.8)
    assert attr.exit_commission_raw == pytest.approx(1.8)


def test_expiry_leg_settlement_fee_applied_in_both_modes():
    # Arrange: intrinsic 50/unit, qty 10, S_end 60000
    leg = _leg("expiry", intrinsic=50.0)
    fills = [_entry_fill(commission=2.5)]
    s_end = 60000.0

    # Act
    attr = attribute_leg(leg, fills, underlying_end_price=s_end)

    # Assert: Vibe settlement fee = min(rate*S_end*qty, cap*intrinsic_value)
    intrinsic_value = 50.0 * 10.0
    settle_fee = min(SETTLE_FEE_RATE * s_end * 10.0, OPT_FEE_CAP * intrinsic_value)
    expected = intrinsic_value - settle_fee - 100.0 * 10.0 - 2.5
    assert attr.pnl_parity == pytest.approx(expected)
    # Regression: native must ALSO carry the settlement fee (Nautilus's
    # expiry fill has zero commission, so nothing else covers it) -- with
    # no flip-exit commission on an expiry leg, native == parity exactly.
    assert attr.pnl_native == pytest.approx(expected)


def test_expiry_leg_uses_intrinsic_not_fill_price():
    # Arrange: a (stray) SELL fill exists at a wrong price -- expiry legs
    # must ignore it and settle at intrinsic_per_unit (the settlement_prices
    # override does not reach automatic expiry in 2.0.0rc1; see
    # postprocess.py module docstring).
    leg = _leg("expiry", intrinsic=50.0)
    fills = [_entry_fill(), _exit_fill(px=49.87, commission=0.0)]

    # Act
    attr = attribute_leg(leg, fills, underlying_end_price=60000.0)

    # Assert
    assert attr.settlement_value_per_unit == pytest.approx(50.0)
    assert attr.exit_fill_px is None


def test_flip_leg_missing_exit_fill_raises():
    # Arrange
    leg = _leg("flip")
    fills = [_entry_fill()]

    # Act / Assert
    with pytest.raises(ValueError, match="no exit fill"):
        attribute_leg(leg, fills, underlying_end_price=0.0)
