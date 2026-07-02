"""Tests for the data-sufficiency tripwire in cached_loader_fetch.

Two independent loader bugs (OKX's recent-window-only candle endpoint,
Tencent's 500-bar response cap) silently truncated long-window requests and
were only caught because the resulting bar count looked suspiciously low —
there was no automated check. ``_warn_if_insufficient_coverage`` is that
check: a best-effort, warn-only tripwire applied uniformly to every loader
routed through ``cached_loader_fetch``.
"""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from backtest.loaders import base


def _frame(dates: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx
    )


class TestWarnIfInsufficientCoverage:
    def test_warns_on_large_truncation_gap(self, caplog):
        """Reproduces the historical Tencent bug shape: a 6.5-year request
        silently returning only the most recent ~2 years."""
        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            base._warn_if_insufficient_coverage(
                source="tencent",
                symbol="600519.SH",
                start_date="2020-01-01",
                end_date="2026-07-01",
                frame=_frame(["2024-06-01", "2026-07-01"]),
            )
        assert any("missing" in r.message for r in caplog.records)
        assert any("600519.SH" in r.message for r in caplog.records)

    def test_no_warning_when_coverage_matches_request(self, caplog):
        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            base._warn_if_insufficient_coverage(
                source="okx",
                symbol="BTC-USDT",
                start_date="2023-01-01",
                end_date="2023-06-30",
                frame=_frame(["2023-01-02", "2023-06-30"]),
            )
        assert caplog.records == []

    def test_no_warning_for_small_gap_under_threshold(self, caplog):
        """A few missing days (weekends/holidays at the boundary, or a
        genuinely late listing by a small margin) must not fire."""
        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            base._warn_if_insufficient_coverage(
                source="yfinance",
                symbol="AAPL.US",
                start_date="2023-01-01",
                end_date="2023-01-31",
                frame=_frame(["2023-01-03", "2023-01-31"]),
            )
        assert caplog.records == []

    def test_no_warning_for_short_window_absolute_floor(self, caplog):
        """A short request (e.g. a quick 30-day smoke test) should not fire
        even if the loader starts a few days late — the 90-day absolute
        floor exists precisely to avoid flooding logs on short windows."""
        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            base._warn_if_insufficient_coverage(
                source="okx",
                symbol="NEWLISTING-USDT",
                start_date="2023-01-01",
                end_date="2023-01-30",
                frame=_frame(["2023-01-20", "2023-01-30"]),
            )
        assert caplog.records == []

    def test_none_or_empty_frame_does_not_warn_or_raise(self, caplog):
        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            base._warn_if_insufficient_coverage(
                source="okx", symbol="X-USDT", start_date="2020-01-01",
                end_date="2026-01-01", frame=None,
            )
            base._warn_if_insufficient_coverage(
                source="okx", symbol="X-USDT", start_date="2020-01-01",
                end_date="2026-01-01", frame=pd.DataFrame(),
            )
        assert caplog.records == []

    def test_malformed_dates_are_swallowed_not_raised(self):
        """Never let the tripwire itself break a real fetch."""
        base._warn_if_insufficient_coverage(
            source="okx", symbol="X-USDT", start_date="not-a-date",
            end_date="also-not-a-date", frame=_frame(["2023-01-01"]),
        )

    def test_cached_loader_fetch_triggers_the_check_on_fresh_fetch(self, tmp_path, monkeypatch, caplog):
        """End-to-end: cached_loader_fetch must invoke the tripwire on a
        cache-miss fetch, exactly the code path both real bugs went
        through undetected."""
        monkeypatch.setattr(base, "loader_cache_enabled", lambda: False)

        def fetch():
            return _frame(["2024-06-01", "2026-07-01"])

        with caplog.at_level(logging.WARNING, logger="backtest.loaders.base"):
            result = base.cached_loader_fetch(
                source="tencent", symbol="600519.SH", timeframe="1D",
                start_date="2020-01-01", end_date="2026-07-01",
                fields=None, fetch=fetch,
            )
        assert result is not None
        assert any("600519.SH" in r.message for r in caplog.records)
