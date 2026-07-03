"""Unit tests for research/macro_breadth/run_m1x_study.py's metrics/decision
logic. Never runs the actual backtests -- fixture equity curves only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_m1x_study  # noqa: E402


def _write_equity_csv(path: Path, rows: list[tuple[str, float]]) -> None:
    with path.open("w") as f:
        f.write("timestamp,equity\n")
        for date, equity in rows:
            f.write(f"{date},{equity}\n")


class TestWindowMetrics:
    def test_computes_return_sharpe_and_maxdd(self, tmp_path):
        path = tmp_path / "equity.csv"
        # a steady uptrend with one dip -> nonzero Sharpe and a real drawdown
        # (window_metrics requires >= 5 rows, else it returns NaN metrics)
        rows = [
            ("2020-01-01", 1000.0), ("2020-01-02", 1010.0), ("2020-01-03", 990.0),
            ("2020-01-04", 1050.0), ("2020-01-05", 1060.0),
        ]
        _write_equity_csv(path, rows)

        out = run_m1x_study.window_metrics(path)

        assert out["n_days"] == 5
        assert out["max_dd_pct"] < 0  # the 1010 -> 990 dip
        assert not np.isnan(out["sharpe"])

    def test_window_start_slices_before_computing(self, tmp_path):
        path = tmp_path / "equity.csv"
        rows = [("2020-01-01", 1000.0), ("2020-06-01", 500.0), ("2020-06-02", 510.0), ("2020-06-03", 520.0)]
        _write_equity_csv(path, rows)

        out = run_m1x_study.window_metrics(path, window_start="2020-06-01")

        assert out["n_days"] == 3  # the crash before window_start is excluded

    def test_too_few_rows_returns_nan_metrics(self, tmp_path):
        path = tmp_path / "equity.csv"
        _write_equity_csv(path, [("2020-01-01", 1000.0)])

        out = run_m1x_study.window_metrics(path)

        assert np.isnan(out["sharpe"])


class TestDailyReturns:
    def test_returns_pct_change_series(self, tmp_path):
        path = tmp_path / "equity.csv"
        _write_equity_csv(path, [("2020-01-01", 1000.0), ("2020-01-02", 1100.0)])

        out = run_m1x_study.daily_returns(path)

        assert out == pytest.approx([0.1])


class TestDecidePromotion:
    """Exercises the real decide_promotion() the driver itself calls -- not a
    re-derived copy of its arithmetic, so these can't silently drift from
    what main() actually decides."""

    def test_sharpe_improvement_exactly_at_threshold_with_no_maxdd_worsening_promotes(self):
        # +0.10 sharpe exactly (float noise included), no dd change
        sharpe_delta = 0.70 - 0.60
        maxdd_worsening = 0.0
        assert run_m1x_study.decide_promotion(sharpe_delta, maxdd_worsening) is True

    def test_sharpe_improvement_but_maxdd_worsens_too_much_blocks_promotion(self):
        sharpe_delta = 0.20
        maxdd_worsening = 5.0  # 5pp worse, exceeds the 2pp allowance
        assert run_m1x_study.decide_promotion(sharpe_delta, maxdd_worsening) is False

    def test_below_sharpe_threshold_blocks_promotion_even_with_favorable_maxdd(self):
        sharpe_delta = 0.05
        maxdd_worsening = -10.0  # maxDD improved a lot, still not enough without the sharpe leg
        assert run_m1x_study.decide_promotion(sharpe_delta, maxdd_worsening) is False

    def test_m1x_study_real_result_correctly_fails_promotion(self):
        # The actual §83 numbers -- Sharpe drops, so promotion must be False
        # regardless of the (favorable) maxDD change.
        sharpe_delta = 0.4391 - 0.6135
        maxdd_worsening = -19.6 - (-11.84)
        assert sharpe_delta < 0
        assert run_m1x_study.decide_promotion(sharpe_delta, maxdd_worsening) is False
