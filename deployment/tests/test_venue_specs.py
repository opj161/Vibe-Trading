"""Unit tests for deployment/venue_specs.py -- live-fetch-with-fallback logic.
Network calls are mocked here (fast, deterministic); a live smoke check lives
in test_order_tickets.py's integration-marked test.
"""

from __future__ import annotations

import pytest
import requests

from deployment import venue_specs


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


class TestToBinanceSymbol:
    def test_strips_hyphen_and_uppercases(self):
        assert venue_specs.to_binance_symbol("btc-usdt") == "BTCUSDT"


class TestRoundDownToStep:
    def test_floors_to_nearest_step(self):
        assert venue_specs.round_down_to_step(0.01234, 0.001) == pytest.approx(0.012)

    def test_exact_multiple_unchanged(self):
        assert venue_specs.round_down_to_step(0.5, 0.1) == pytest.approx(0.5)

    def test_below_one_step_floors_to_zero(self):
        assert venue_specs.round_down_to_step(0.0005, 0.001) == 0.0

    def test_zero_step_is_a_no_op(self):
        assert venue_specs.round_down_to_step(0.1234, 0.0) == 0.1234


class TestSpotFiltersLiveSuccess:
    def test_parses_lot_size_and_notional_from_live_shape(self, monkeypatch):
        payload = {
            "symbols": [{
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001000"},
                    {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                ],
            }],
        }
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(payload))

        out = venue_specs.binance_spot_filters("BTC-USDT")

        assert out == {"step_size": pytest.approx(0.00001), "min_notional": pytest.approx(5.0)}


class TestSpotFiltersFallback:
    def test_falls_back_when_request_raises(self, monkeypatch):
        def _raise(*a, **k):
            raise requests.ConnectionError("no network")
        monkeypatch.setattr(requests, "get", _raise)

        out = venue_specs.binance_spot_filters("BTC-USDT")

        assert out == venue_specs._FALLBACK_SPOT["BTCUSDT"]

    def test_falls_back_when_symbols_missing(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"symbols": []}))

        out = venue_specs.binance_spot_filters("SOL-USDT")

        assert out == venue_specs._FALLBACK_SPOT["SOLUSDT"]

    def test_unknown_symbol_with_no_fallback_raises(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"symbols": []}))
        with pytest.raises(ValueError):
            venue_specs.binance_spot_filters("DOGE-USDT")


class TestFuturesFilters:
    def test_finds_matching_symbol_in_list(self, monkeypatch):
        payload = {
            "symbols": [
                {"symbol": "ETHUSDT", "filters": []},
                {
                    "symbol": "BTCUSDT",
                    "filters": [
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                        {"filterType": "MIN_NOTIONAL", "notional": "50"},
                    ],
                },
            ],
        }
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(payload))

        out = venue_specs.binance_futures_filters("BTC-USDT")

        assert out == {"step_size": pytest.approx(0.001), "min_notional": pytest.approx(50.0)}

    def test_falls_back_on_network_error(self, monkeypatch):
        def _raise(*a, **k):
            raise requests.Timeout()
        monkeypatch.setattr(requests, "get", _raise)

        out = venue_specs.binance_futures_filters("SOL-USDT")

        assert out == venue_specs._FALLBACK_FUTURES["SOLUSDT"]


class TestPricesAndFunding:
    def test_spot_price_parses_payload(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"price": "65000.5"}))
        assert venue_specs.binance_spot_price("BTC-USDT") == pytest.approx(65000.5)

    def test_spot_price_returns_none_on_failure(self, monkeypatch):
        def _raise(*a, **k):
            raise requests.ConnectionError()
        monkeypatch.setattr(requests, "get", _raise)
        assert venue_specs.binance_spot_price("BTC-USDT") is None

    def test_futures_price_uses_mark_price(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse({"markPrice": "61200.1"}))
        assert venue_specs.binance_futures_price("BTC-USDT") == pytest.approx(61200.1)

    def test_funding_annualized_multiplies_8h_rate(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get", lambda *a, **k: _FakeResponse({"lastFundingRate": "0.0001"}),
        )
        out = venue_specs.binance_futures_funding_annualized("BTC-USDT")
        assert out == pytest.approx(0.0001 * 3 * 365)

    def test_funding_annualized_none_on_failure(self, monkeypatch):
        def _raise(*a, **k):
            raise requests.Timeout()
        monkeypatch.setattr(requests, "get", _raise)
        assert venue_specs.binance_futures_funding_annualized("BTC-USDT") is None
