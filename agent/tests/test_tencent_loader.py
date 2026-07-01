"""Tests for the Tencent A-share loader's 500-bar-cap chunking.

Tencent's kline endpoint silently caps every response at 500 bars,
returning only the most recent 500 trading days of the requested span.
``_fetch_one`` must therefore chunk long spans into windows that stay
under the cap and stitch the results back together.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from backtest.loaders.tencent_loader import DataLoader


def _make_df(start: str, end: str) -> pd.DataFrame:
    idx = pd.bdate_range(start, end)
    return pd.DataFrame(
        {
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 100.0,
        },
        index=idx,
    )


class TestTencentChunking:
    def test_long_span_is_chunked_into_multiple_windows(self):
        loader = DataLoader()
        calls = []

        def fake_window(tencent_code, start_date, end_date):
            calls.append((start_date, end_date))
            return _make_df(start_date, end_date)

        with patch.object(loader, "_fetch_window", side_effect=fake_window):
            df = loader._fetch_one("600519.SH", "2020-01-01", "2026-07-01")

        assert len(calls) >= 3, f"6.5y span should need >=3 chunks, got {calls}"
        # Every chunk must stay under the 500-trading-bar cap.
        for start_date, end_date in calls:
            span = pd.Timestamp(end_date) - pd.Timestamp(start_date)
            assert span.days <= DataLoader._MAX_WINDOW_DAYS
        # Stitched result covers the whole span with no duplicate dates.
        assert df.index[0] == pd.Timestamp("2020-01-01")
        assert df.index[-1] == pd.Timestamp("2026-07-01")
        assert not df.index.duplicated().any()

    def test_short_span_uses_single_window(self):
        loader = DataLoader()
        calls = []

        def fake_window(tencent_code, start_date, end_date):
            calls.append((start_date, end_date))
            return _make_df(start_date, end_date)

        with patch.object(loader, "_fetch_window", side_effect=fake_window):
            loader._fetch_one("600519.SH", "2026-01-01", "2026-06-30")

        assert len(calls) == 1

    def test_truncating_backend_still_yields_full_span(self):
        """Even if each window response is capped at 500 rows, chunked
        windows are individually under the cap, so the stitched result
        covers the entire requested span (the original bug returned only
        the most recent 500 bars of a 6.5-year request)."""
        loader = DataLoader()

        def fake_window(tencent_code, start_date, end_date):
            df = _make_df(start_date, end_date)
            return df.tail(500)  # emulate the server-side cap

        with patch.object(loader, "_fetch_window", side_effect=fake_window):
            df = loader._fetch_one("600519.SH", "2020-01-01", "2026-07-01")

        # ~1690 business days in the span; the pre-fix behaviour returned 500.
        assert len(df) > 1400
        assert df.index[0] <= pd.Timestamp("2020-01-03")

    def test_empty_chunks_for_prelisting_period_are_skipped(self):
        loader = DataLoader()

        def fake_window(tencent_code, start_date, end_date):
            # Asset "lists" on 2024-01-01: earlier windows return nothing.
            if pd.Timestamp(end_date) < pd.Timestamp("2024-01-01"):
                return None
            return _make_df(max(pd.Timestamp(start_date), pd.Timestamp("2024-01-01")), end_date)

        with patch.object(loader, "_fetch_window", side_effect=fake_window):
            df = loader._fetch_one("600519.SH", "2020-01-01", "2026-07-01")

        assert df is not None
        assert df.index[0] >= pd.Timestamp("2024-01-01")
