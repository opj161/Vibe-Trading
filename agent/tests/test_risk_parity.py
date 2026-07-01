"""Tests for risk parity optimizer."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.optimizers.risk_parity import RiskParityOptimizer


class TestRiskParityCalcWeights:
    """Unit tests for the core weight calculation."""

    def test_equal_vol_gives_equal_weight(self) -> None:
        """Assets with identical volatility → equal weights."""
        n = 3
        vol = 0.02
        cov = np.eye(n) * vol**2
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        np.testing.assert_allclose(w, np.ones(n) / n, atol=1e-6)

    def test_weights_sum_to_one(self) -> None:
        rng = np.random.default_rng(42)
        n = 5
        A = rng.standard_normal((100, n))
        cov = np.cov(A.T)
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        assert abs(w.sum() - 1.0) < 1e-10

    def test_weights_nonnegative(self) -> None:
        rng = np.random.default_rng(7)
        n = 4
        A = rng.standard_normal((100, n))
        cov = np.cov(A.T)
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        assert np.all(w >= -1e-12)

    def test_higher_vol_gets_lower_weight(self) -> None:
        """Asset with higher volatility should get lower weight."""
        cov = np.diag([0.01, 0.04])  # vol = 0.1 vs 0.2
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        assert w[0] > w[1], "Lower-vol asset should have higher weight"

    def test_zero_vol_fallback(self) -> None:
        """Zero volatility → equal weight fallback."""
        cov = np.zeros((3, 3))
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        np.testing.assert_allclose(w, np.ones(3) / 3, atol=1e-10)

    def test_negatively_correlated_multi_asset_stays_nonnegative(self) -> None:
        """Regression for a real bug: the old undamped multiplicative
        iteration diverged into large-magnitude NEGATIVE weights on a
        realistic n>2 portfolio with a genuinely negatively-correlated
        asset (e.g. equities vs. bonds) -- silently flipping signal
        direction downstream. Every prior test used i.i.d./weakly-
        correlated synthetic returns and never caught this. Reproduced
        with an equities/gold/bonds/FX-style covariance structure."""
        rng = np.random.default_rng(0)
        n = 2000
        eq = rng.normal(0, 0.012, n)
        bond = -0.5 * eq + rng.normal(0, 0.006, n)
        gold = 0.1 * eq + rng.normal(0, 0.010, n)
        fx = -0.2 * eq + rng.normal(0, 0.003, n)
        cov = np.cov(np.column_stack([eq, gold, bond, fx]).T)

        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})

        assert np.all(w >= 0), f"weights must stay non-negative, got {w}"
        assert abs(w.sum() - 1.0) < 1e-8

        # Genuine ERC property: marginal risk contributions should be
        # equal across assets, not just "not negative".
        port_vol = np.sqrt(w @ cov @ w)
        rc = w * (cov @ w) / port_vol
        assert np.allclose(rc, rc.mean(), rtol=0.02), f"risk contributions not equal: {rc}"

    def test_single_asset(self) -> None:
        cov = np.array([[0.04]])
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        np.testing.assert_allclose(w, [1.0], atol=1e-10)

    def test_empty_portfolio(self) -> None:
        cov = np.empty((0, 0))
        opt = RiskParityOptimizer()
        w = opt._calc_weights({"cov": cov})
        assert len(w) == 0


class TestRiskParityOptimize:
    """Integration test for the module-level optimize function."""

    def test_optimize_preserves_sign(self) -> None:
        """Optimizer should preserve signal direction (long/short)."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        codes = ["A", "B"]
        rng = np.random.default_rng(42)
        ret = pd.DataFrame(rng.normal(0, 0.02, (100, 2)), index=dates, columns=codes)
        pos = pd.DataFrame(0.0, index=dates, columns=codes)
        # A is long, B is short after lookback period
        pos.iloc[60:, 0] = 1.0
        pos.iloc[60:, 1] = -1.0

        opt = RiskParityOptimizer(lookback=60)
        result = opt.optimize(ret, pos, dates)

        # After lookback, signs should be preserved
        assert (result.iloc[61:, 0] >= 0).all(), "A should remain long"
        assert (result.iloc[61:, 1] <= 0).all(), "B should remain short"

    def test_dt_own_return_excluded_from_its_own_weight(self) -> None:
        """dt's own return requires dt's close, which isn't observed until
        after the weight computed for dt has already been executed at dt's
        open — so it must not affect dt's own weight (previously it did,
        via an inclusive ``ret.loc[:dt]`` slice; see CLAUDE.md)."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        codes = ["A", "B"]
        rng = np.random.default_rng(5)
        base_ret = pd.DataFrame(rng.normal(0, 0.01, (100, 2)), index=dates, columns=codes)
        pos = pd.DataFrame(0.0, index=dates, columns=codes)
        pos.iloc[70:, 0] = 1.0
        pos.iloc[70:, 1] = 1.0

        dt = dates[75]
        dt_next = dates[76]
        ret_outlier = base_ret.copy()
        # Huge same-day outlier on B: only visible if the window leaks dt's
        # own not-yet-observed return.
        ret_outlier.loc[dt, "B"] = 5.0

        opt = RiskParityOptimizer(lookback=60)
        result_base = opt.optimize(base_ret, pos, dates)
        result_outlier = opt.optimize(ret_outlier, pos, dates)

        pd.testing.assert_series_equal(result_base.loc[dt], result_outlier.loc[dt])
        # Sanity: the outlier does matter once it's legitimately in history.
        assert not result_base.loc[dt_next].equals(result_outlier.loc[dt_next])

    def test_single_asset_unchanged(self) -> None:
        """Optimizer with 1 asset returns input unchanged."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        ret = pd.DataFrame(np.random.default_rng(1).normal(0, 0.02, (100, 1)), index=dates, columns=["A"])
        pos = pd.DataFrame(1.0, index=dates, columns=["A"])

        opt = RiskParityOptimizer(lookback=60)
        result = opt.optimize(ret, pos, dates)
        pd.testing.assert_frame_equal(result, pos)

    def test_respect_magnitude_defaults_off_and_matches_sign_only(self) -> None:
        """Default (respect_magnitude=False) is unchanged from sign-only behavior."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        codes = ["A", "B"]
        rng = np.random.default_rng(3)
        ret = pd.DataFrame(rng.normal(0, 0.02, (100, 2)), index=dates, columns=codes)
        pos = pd.DataFrame(0.0, index=dates, columns=codes)
        pos.iloc[60:, 0] = 1.0
        pos.iloc[60:, 1] = -0.3  # different magnitude, same vol -> would differ if respected

        sign_only = RiskParityOptimizer(lookback=60).optimize(ret, pos, dates)
        explicit_off = RiskParityOptimizer(lookback=60, respect_magnitude=False).optimize(
            ret, pos, dates
        )
        pd.testing.assert_frame_equal(sign_only, explicit_off)

    def test_respect_magnitude_scales_weight_by_conviction(self) -> None:
        """respect_magnitude=True lets a stronger raw signal get a larger weight."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        codes = ["A", "B"]
        # Identical volatility for A and B so risk-parity alone would split 50/50;
        # any weight skew must come from the magnitude scaling.
        rng = np.random.default_rng(3)
        shared_noise = rng.normal(0, 0.02, 100)
        ret = pd.DataFrame({"A": shared_noise, "B": shared_noise}, index=dates)
        pos = pd.DataFrame(0.0, index=dates, columns=codes)
        pos.iloc[60:, 0] = 1.0  # full-conviction long
        pos.iloc[60:, 1] = -0.3  # weaker-conviction short

        result = RiskParityOptimizer(lookback=60, respect_magnitude=True).optimize(
            ret, pos, dates
        )

        # Signs still preserved...
        assert (result.iloc[61:, 0] >= 0).all()
        assert (result.iloc[61:, 1] <= 0).all()
        # ...but the higher-conviction long now outweighs the weaker short,
        # unlike the equal-vol 50/50 split sign-only mode would produce.
        assert (result.iloc[61:, 0].abs() > result.iloc[61:, 1].abs()).all()

    def test_respect_magnitude_zero_signal_falls_back_gracefully(self) -> None:
        """All-active-signals-near-zero at a date doesn't crash (division guard)."""
        dates = pd.bdate_range("2025-01-01", periods=100)
        codes = ["A", "B"]
        rng = np.random.default_rng(5)
        ret = pd.DataFrame(rng.normal(0, 0.02, (100, 2)), index=dates, columns=codes)
        pos = pd.DataFrame(0.0, index=dates, columns=codes)
        pos.iloc[60:, 0] = 1.0
        pos.iloc[60:, 1] = -1.0

        result = RiskParityOptimizer(lookback=60, respect_magnitude=True).optimize(
            ret, pos, dates
        )
        assert not result.isna().any().any()
