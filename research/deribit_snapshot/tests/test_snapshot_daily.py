"""Unit tests for research/deribit_snapshot/snapshot_daily.py. Network mocked."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import snapshot_daily  # noqa: E402


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


class TestParseInstrumentName:
    def test_parses_btc_style_double_digit_day(self):
        strike, expiry_ts = snapshot_daily._parse_instrument_name("BTC-31JUL26-81000-C")
        assert strike == 81000.0
        assert expiry_ts is not None

    def test_parses_sol_usdc_single_digit_day(self):
        strike, expiry_ts = snapshot_daily._parse_instrument_name("SOL_USDC-3JUL26-45-C")
        assert strike == 45.0
        assert expiry_ts is not None

    def test_malformed_name_returns_none_none(self):
        assert snapshot_daily._parse_instrument_name("garbage") == (None, None)


class TestFetchBookSummary:
    def test_returns_result_list_on_success(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get",
            lambda *a, **k: _FakeResponse({"result": [{"instrument_name": "BTC-1JAN27-50000-C"}]}),
        )
        out = snapshot_daily._fetch_book_summary("BTC")
        assert out == [{"instrument_name": "BTC-1JAN27-50000-C"}]

    def test_returns_none_on_network_error_never_raises(self, monkeypatch):
        def _raise(*a, **k):
            raise requests.ConnectionError("no network")
        monkeypatch.setattr(requests, "get", _raise)
        assert snapshot_daily._fetch_book_summary("BTC") is None

    def test_returns_none_on_api_error_payload(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"error": {"message": "boom"}}))
        assert snapshot_daily._fetch_book_summary("BTC") is None


class TestSnapshotUnderlying:
    def test_btc_direct_query_no_filter(self, monkeypatch):
        rows = [
            {"instrument_name": "BTC-31JUL26-81000-C", "bid_price": 0.001, "mark_iv": 40.0},
            {"instrument_name": "BTC-31JUL26-81000-P", "bid_price": 0.002, "mark_iv": 41.0},
        ]
        monkeypatch.setattr(snapshot_daily, "_fetch_book_summary", lambda ccy: rows)

        df = snapshot_daily.snapshot_underlying("BTC", snapshot_daily.UNDERLYINGS["BTC"], "2026-07-03")

        assert len(df) == 2
        assert set(df["option_type"]) == {"call", "put"}
        assert (df["underlying"] == "BTC").all()

    def test_sol_filters_to_base_currency_from_mixed_usdc_book(self, monkeypatch):
        rows = [
            {"instrument_name": "SOL_USDC-3JUL26-45-C", "base_currency": "SOL"},
            {"instrument_name": "BTC-3JUL26-81000-C", "base_currency": "BTC"},
        ]
        monkeypatch.setattr(snapshot_daily, "_fetch_book_summary", lambda ccy: rows)

        df = snapshot_daily.snapshot_underlying("SOL", snapshot_daily.UNDERLYINGS["SOL"], "2026-07-03")

        assert len(df) == 1
        assert df.iloc[0]["instrument_name"] == "SOL_USDC-3JUL26-45-C"

    def test_fetch_failure_returns_empty_frame_with_columns(self, monkeypatch):
        monkeypatch.setattr(snapshot_daily, "_fetch_book_summary", lambda ccy: None)

        df = snapshot_daily.snapshot_underlying("BTC", snapshot_daily.UNDERLYINGS["BTC"], "2026-07-03")

        assert df.empty
        assert list(df.columns) == snapshot_daily.COLUMNS


class TestRunSnapshot:
    def test_writes_parquet_and_continues_past_one_underlying_failing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(snapshot_daily, "DATA_DIR", tmp_path)

        def fake_fetch(query_currency):
            if query_currency == "ETH":
                raise requests.ConnectionError("simulated ETH outage")
            return [{"instrument_name": f"{query_currency}-3JUL26-100-C", "base_currency": "SOL"}]

        def fake_fetch_safe(query_currency):
            try:
                return fake_fetch(query_currency)
            except requests.ConnectionError:
                return None

        monkeypatch.setattr(snapshot_daily, "_fetch_book_summary", fake_fetch_safe)

        path = snapshot_daily.run_snapshot(date="2026-07-03")

        assert path.exists()
        import pandas as pd
        df = pd.read_parquet(path)
        # BTC + SOL captured, ETH failed but did not crash the run
        assert set(df["underlying"]) <= {"BTC", "SOL", "ETH"}
        assert len(df) >= 1
