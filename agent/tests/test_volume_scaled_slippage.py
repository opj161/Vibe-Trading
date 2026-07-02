"""Tests for the opt-in volume_scaled_slippage_rate utility.

Not wired into any engine's default execution path (see the function's own
docstring) — this is a well-tested capability available the moment
less-liquid-instrument research needs it, without risking a breaking change
to every engine's apply_slippage signature today.
"""

from __future__ import annotations

import pytest

from backtest.engines.base import volume_scaled_slippage_rate


class TestVolumeScaledSlippageRate:
    def test_zero_volume_falls_back_to_base_rate(self):
        assert volume_scaled_slippage_rate(0.0005, 100_000.0, 0.0) == 0.0005

    def test_negative_volume_falls_back_to_base_rate(self):
        assert volume_scaled_slippage_rate(0.0005, 100_000.0, -1.0) == 0.0005

    def test_tiny_trade_relative_to_volume_barely_scales(self):
        rate = volume_scaled_slippage_rate(0.0005, 1_000.0, 100_000_000.0)
        assert rate == pytest.approx(0.0005, rel=1e-3)

    def test_trade_equal_to_full_bar_volume_scales_per_coefficient(self):
        # participation = 1.0, impact_coefficient default 0.1 -> multiplier 1.1
        rate = volume_scaled_slippage_rate(0.0005, 100.0, 100.0)
        assert rate == pytest.approx(0.0005 * 1.1)

    def test_larger_trade_scales_more_than_smaller_trade(self):
        small = volume_scaled_slippage_rate(0.0005, 1_000.0, 100_000.0)
        large = volume_scaled_slippage_rate(0.0005, 50_000.0, 100_000.0)
        assert large > small

    def test_multiplier_is_capped(self):
        rate = volume_scaled_slippage_rate(
            0.0005, trade_notional=1_000_000.0, bar_dollar_volume=1.0,
            max_multiplier=5.0,
        )
        assert rate == pytest.approx(0.0005 * 5.0)

    def test_custom_impact_coefficient(self):
        rate = volume_scaled_slippage_rate(
            0.001, trade_notional=100.0, bar_dollar_volume=100.0,
            impact_coefficient=0.5,
        )
        assert rate == pytest.approx(0.001 * 1.5)
