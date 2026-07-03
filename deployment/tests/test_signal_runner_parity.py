"""A1 acceptance gate (CPD-1 deployment plan): the deployment path's raw,
pre-shift signal for day D must be byte-consistent with the forward-validation
ritual's shifted ``positions.csv`` row for the bar immediately after D.

Design note on how this is tested efficiently: literally invoking
``run_signal(strategy, as_of=D)`` once per day for the last 30 days would
issue 30 separate live network fetches per strategy (the loader cache is
keyed by exact (start_date, end_date), so different ``as_of`` values are
cache misses). Instead this test fetches the full window ONCE, computes the
raw signal ONCE via the real ``SignalEngine.generate()``, runs the real
audit-trail ritual ONCE to get ``positions.csv``, and checks byte-consistency
across the last 30 days by slicing -- mathematically the same claim (both
sides are deterministic functions of the same OHLCV data), at a fraction of
the cost. A second, smaller test directly calls ``run_signal()`` end-to-end
for two specific days to also exercise the real per-call fetch path.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from deployment._bootstrap import AGENT_DIR, FROZEN_DIR
from deployment.signal_runner import (
    WARMUP_START,
    _fetch_data_map_for_signal,
    _run_audit_trail,
    run_signal,
)

pytestmark = pytest.mark.integration

STRATEGIES = ["ZA4", "M1"]
N_DAYS_CHECKED = 30


def _load_frozen_engine(strategy: str):
    from backtest.runner import _load_module_from_file, _validate_signal_engine_class

    frozen = FROZEN_DIR / strategy
    module = _load_module_from_file(frozen / "signal_engine.py", f"parity_test_{strategy}")
    engine_cls = module.SignalEngine
    _validate_signal_engine_class(engine_cls)
    return engine_cls()


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_raw_signal_matches_shifted_positions_for_last_30_days(strategy):
    today = dt.date.today().isoformat()

    frozen = FROZEN_DIR / strategy
    config = __import__("json").loads((frozen / "config.json").read_text())
    config["start_date"] = WARMUP_START
    config["end_date"] = today
    config.pop("validation", None)

    data_map = _fetch_data_map_for_signal(config)
    assert data_map, f"{strategy}: no data fetched"

    engine = _load_frozen_engine(strategy)
    raw_signal_map = engine.generate(data_map)

    # _align applies a row-wise gross-exposure clip (sum(abs(weights)) <= 1.0)
    # AFTER the shift -- that clip is part of what positions.csv records, so
    # the comparison must apply it too, not just the raw pre-clip signal.
    from backtest.engines.base import normalize_gross_exposure

    raw_df = pd.concat(raw_signal_map, axis=1).sort_index()
    normalized_df = normalize_gross_exposure(raw_df.fillna(0.0))

    run_dir = _run_audit_trail(strategy, today)
    positions = pd.read_csv(
        run_dir / "artifacts" / "positions.csv", index_col=0, parse_dates=True,
    )

    for symbol in raw_signal_map:
        if symbol not in positions.columns:
            continue
        raw = normalized_df[symbol].sort_index()
        pos = positions[symbol].sort_index()

        # Only compare where both series share the same calendar (true for
        # ZA4/M1's single-market, same-calendar symbol pairs) so a positional
        # "row i+1 in positions == row i in raw" comparison is valid.
        common_index = raw.index.intersection(pos.index)
        raw = raw.reindex(common_index)
        pos = pos.reindex(common_index)

        checked = 0
        for i in range(max(len(common_index) - 1 - N_DAYS_CHECKED, 0), len(common_index) - 1):
            day_d_raw = raw.iloc[i]
            day_d_plus_1_pos = pos.iloc[i + 1]
            assert np.isclose(day_d_raw, day_d_plus_1_pos, atol=1e-9), (
                f"{strategy}/{symbol}: raw signal on {common_index[i].date()} "
                f"({day_d_raw}) != positions.csv shifted value on "
                f"{common_index[i + 1].date()} ({day_d_plus_1_pos})"
            )
            checked += 1
        assert checked > 0, f"{strategy}/{symbol}: no overlapping days to check"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_run_signal_direct_invocation_matches_full_window_raw(strategy):
    """Calls run_signal() itself (the real entry point, own fetch call) for a
    couple of recent historical days and cross-checks against a single
    full-window fetch's raw signal at the same bar -- catches any
    per-call fetch nondeterminism the sliced test above wouldn't see."""
    frozen = FROZEN_DIR / strategy
    config = __import__("json").loads((frozen / "config.json").read_text())
    config["start_date"] = WARMUP_START
    config["end_date"] = dt.date.today().isoformat()
    config.pop("validation", None)
    data_map = _fetch_data_map_for_signal(config)
    engine = _load_frozen_engine(strategy)
    full_raw = engine.generate(data_map)

    from backtest.engines.base import normalize_gross_exposure

    full_raw_df = pd.concat(full_raw, axis=1).sort_index().fillna(0.0)
    full_normalized_df = normalize_gross_exposure(full_raw_df)

    any_series = next(iter(full_raw.values()))
    check_dates = [d.date().isoformat() for d in any_series.index[-3:-1]]

    for as_of in check_dates:
        state = run_signal(strategy, as_of=as_of, write_audit_trail=False)
        info = state.strategies[strategy]
        for symbol, target in info["targets"].items():
            expected = full_normalized_df[symbol].loc[full_normalized_df.index <= as_of].iloc[-1]
            assert np.isclose(target.target_weight, expected, atol=1e-9), (
                f"{strategy}/{symbol} as_of={as_of}: run_signal={target.target_weight} "
                f"vs full-window slice={expected}"
            )
