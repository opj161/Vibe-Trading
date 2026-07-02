"""Tests for deflated_sharpe_ratio and probability_of_backtest_overfitting.

Both consolidate a formula this repo's own research log independently
hand-derived (correctly) at least eight times in throwaway scripts before
being promoted here as a single, tested, reusable implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.validation import deflated_sharpe_ratio, probability_of_backtest_overfitting


# ---------------------------------------------------------------------------
# deflated_sharpe_ratio
# ---------------------------------------------------------------------------


class TestDeflatedSharpeRatio:
    def test_insufficient_observations_returns_error(self):
        result = deflated_sharpe_ratio(np.array([0.01, 0.02]))
        assert "error" in result

    def test_zero_variance_returns_error(self):
        result = deflated_sharpe_ratio(np.zeros(50))
        assert "error" in result

    def test_single_trial_reduces_to_plain_psr(self):
        """With n_trials=1, DSR must equal PSR-at-zero exactly (no
        multi-trial deflation term applied)."""
        rng = np.random.default_rng(0)
        returns = rng.normal(0.001, 0.01, size=500)
        result = deflated_sharpe_ratio(returns, n_trials=1)
        assert result["dsr"] == result["psr_at_zero"]
        assert result["expected_max_sharpe_null"] == 0.0
        assert result["n_trials"] == 1

    def test_more_trials_with_dispersion_lowers_dsr(self):
        """Holding the selected strategy's own returns fixed, increasing
        n_trials (or the cross-trial Sharpe dispersion) must only ever
        decrease DSR relative to the single-trial PSR — the core
        multi-trial-selection-bias correction the whole formula exists for."""
        rng = np.random.default_rng(1)
        returns = rng.normal(0.0015, 0.01, size=500)

        single = deflated_sharpe_ratio(returns, n_trials=1)
        multi_low_disp = deflated_sharpe_ratio(
            returns, n_trials=13, sharpe_std_across_trials=0.1,
        )
        multi_high_disp = deflated_sharpe_ratio(
            returns, n_trials=13, sharpe_std_across_trials=0.8,
        )

        assert multi_low_disp["dsr"] <= single["dsr"]
        assert multi_high_disp["dsr"] <= multi_low_disp["dsr"]
        assert multi_high_disp["expected_max_sharpe_null"] > multi_low_disp["expected_max_sharpe_null"]

    def test_negative_sharpe_std_raises(self):
        with pytest.raises(ValueError):
            deflated_sharpe_ratio(
                np.random.default_rng(0).normal(0, 0.01, 100),
                n_trials=5,
                sharpe_std_across_trials=-0.1,
            )

    def test_annualized_sharpe_matches_manual_calculation(self):
        returns = np.array([0.01, -0.005, 0.02, 0.0, -0.01, 0.015] * 20)
        result = deflated_sharpe_ratio(returns, bars_per_year=252)
        expected_annual_sharpe = (
            returns.mean() / returns.std(ddof=1) * np.sqrt(252)
        )
        assert result["observed_sharpe"] == pytest.approx(expected_annual_sharpe, abs=1e-3)

    def test_skew_and_kurtosis_reported_correctly(self):
        rng = np.random.default_rng(2)
        returns = rng.normal(0.001, 0.01, size=1000)
        result = deflated_sharpe_ratio(returns)
        # A large, symmetric normal sample should have skew/excess-kurtosis near 0.
        assert abs(result["skew"]) < 0.3
        assert abs(result["kurtosis_excess"]) < 0.5

    def test_accepts_pandas_series(self):
        s = pd.Series(np.random.default_rng(3).normal(0.001, 0.01, 100))
        result = deflated_sharpe_ratio(s)
        assert "dsr" in result


# ---------------------------------------------------------------------------
# probability_of_backtest_overfitting
# ---------------------------------------------------------------------------


class TestProbabilityOfBacktestOverfitting:
    def test_odd_n_splits_raises(self):
        df = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (100, 3)))
        with pytest.raises(ValueError):
            probability_of_backtest_overfitting(df, n_splits=15)

    def test_insufficient_observations_returns_error(self):
        df = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (4, 3)))
        result = probability_of_backtest_overfitting(df, n_splits=16)
        assert "error" in result

    def test_single_strategy_column_returns_error(self):
        df = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (200, 1)))
        result = probability_of_backtest_overfitting(df, n_splits=16)
        assert "error" in result

    def test_one_dominant_strategy_gives_low_pbo(self):
        """If one strategy is genuinely, consistently better than the rest
        across the whole sample, the in-sample winner should usually still
        rank well out-of-sample -> low PBO."""
        rng = np.random.default_rng(42)
        n_obs = 320
        n_strategies = 5
        # Strategy 0 has a real, consistent positive drift; the rest are
        # pure noise around zero.
        data = rng.normal(0.0, 0.01, size=(n_obs, n_strategies))
        data[:, 0] = rng.normal(0.004, 0.01, size=n_obs)
        df = pd.DataFrame(data)

        result = probability_of_backtest_overfitting(df, n_splits=16)
        # Must be clearly, substantially below the ~0.5 pure-noise baseline
        # (the other test in this class) -- a real, consistent effect
        # discriminates from noise even if not literally near 0.
        assert result["pbo"] < 0.4
        assert result["n_combinations"] == 12870  # C(16, 8)
        assert result["n_strategies"] == 5

    def test_pure_noise_strategies_give_high_pbo(self):
        """When every column is indistinguishable noise, the in-sample
        'winner' each split is essentially a random draw, so it should rank
        at/below the OOS median roughly half the time -> PBO near 0.5."""
        rng = np.random.default_rng(7)
        data = rng.normal(0.0, 0.01, size=(320, 6))
        df = pd.DataFrame(data)

        result = probability_of_backtest_overfitting(df, n_splits=16)
        assert 0.3 < result["pbo"] < 0.75

    def test_output_keys_present(self):
        rng = np.random.default_rng(1)
        df = pd.DataFrame(rng.normal(0, 0.01, (200, 4)))
        result = probability_of_backtest_overfitting(df, n_splits=10)
        for key in ("pbo", "n_combinations", "n_strategies", "n_splits", "logit_mean", "logit_std"):
            assert key in result
        assert result["n_combinations"] == 252  # C(10, 5)
