"""Tests for the data-integrity gate (audit fix 2026-07-03) -- the observed
failure mode is a flaky fetch that silently degrades data (three same-day
runs of frozen M1 drew full-window Sharpe {0.61, 0.44, 0.61}); no ticket may
be built from such a draw.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from deployment import data_integrity
from deployment.data_integrity import DataIntegrityError, check_data_map


def _df(n=400, start="2024-01-01", price=100.0, seed=0):
    idx = pd.date_range(start, periods=n, freq="D")
    rng = np.random.default_rng(seed)
    close = price * np.cumprod(1 + rng.normal(0, 0.01, n))
    return pd.DataFrame({"close": close}, index=idx)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(data_integrity, "STATE_DIR", tmp_path)
    yield tmp_path


class TestNaNAndHistoryChecks:
    def test_clean_data_passes_and_writes_fingerprint(self, _isolated_state):
        # Arrange
        data_map = {"SPY.US": _df()}

        # Act
        check_data_map("M1", data_map)

        # Assert
        fp = _isolated_state / "data_fingerprint_M1.json"
        assert fp.exists()
        bars = json.loads(fp.read_text())["bars"]["SPY.US"]
        assert len(bars) == data_integrity.FINGERPRINT_BARS

    def test_nan_close_fails(self):
        # Arrange
        df = _df()
        df.iloc[100, df.columns.get_loc("close")] = np.nan

        # Act / Assert
        with pytest.raises(DataIntegrityError, match="NaN close"):
            check_data_map("M1", {"SPY.US": df})

    def test_too_few_rows_fails(self):
        with pytest.raises(DataIntegrityError, match="bars fetched"):
            check_data_map("M1", {"SPY.US": _df(n=100)})

    def test_missing_close_column_fails(self):
        df = _df().rename(columns={"close": "px"})
        with pytest.raises(DataIntegrityError, match="no 'close' column"):
            check_data_map("M1", {"SPY.US": df})


class TestHistoryMutation:
    def test_unchanged_history_passes_on_second_run(self):
        data_map = {"SPY.US": _df()}
        check_data_map("M1", data_map)

        check_data_map("M1", data_map)  # must not raise

    def test_uniform_rescale_passes_like_a_dividend_adjustment(self):
        # Arrange: first run fingerprints, second run's whole history is
        # rescaled by one factor (exactly what an ex-div re-adjustment does)
        df = _df()
        check_data_map("M1", {"SPY.US": df})
        rescaled = df * 0.997

        # Act / Assert: allowed
        check_data_map("M1", {"SPY.US": rescaled})

    def test_nonuniform_mutation_fails(self):
        # Arrange: one bar inside the fingerprint window selectively rewritten
        df = _df()
        check_data_map("M1", {"SPY.US": df})
        mutated = df.copy()
        mutated.iloc[-10, mutated.columns.get_loc("close")] *= 1.02  # +2% on one bar

        # Act / Assert
        with pytest.raises(DataIntegrityError, match="NON-uniformly"):
            check_data_map("M1", {"SPY.US": mutated})

    def test_update_fingerprint_false_does_not_advance_state(self, _isolated_state):
        data_map = {"SPY.US": _df()}
        check_data_map("M1", data_map, update_fingerprint=False)

        assert not (_isolated_state / "data_fingerprint_M1.json").exists()

    def test_new_symbol_without_history_is_not_a_failure(self):
        # Universe/config changes are config events, not data events
        check_data_map("M1", {"SPY.US": _df()})
        check_data_map("M1", {"SPY.US": _df(), "GLD.US": _df(seed=1)})  # must not raise
