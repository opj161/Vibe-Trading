"""Unit tests for the pure/mockable pieces of deployment/hl_testnet_drill.py.
The live async order-lifecycle flow (run_drill) is inherently an integration
smoke test against the real Hyperliquid testnet -- it was verified live
during the build session (DRILL PASS, real venue_order_id) and is not
re-mocked here; the risk this module carries lives in testnet_mid_price's
HTTP parsing and the pass/fail aggregation, both covered below.
"""

from __future__ import annotations

import httpx
import pytest

from deployment import hl_testnet_drill as drill


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=None, response=self)

    def json(self):
        return self._payload


class TestTestnetMidPrice:
    def test_parses_mid_for_requested_coin(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"BTC": "61420.0", "ETH": "3000.0"}))
        assert drill.testnet_mid_price("BTC") == pytest.approx(61420.0)

    def test_missing_coin_raises(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"ETH": "3000.0"}))
        with pytest.raises(RuntimeError):
            drill.testnet_mid_price("BTC")


class TestDrillPassed:
    def test_all_steps_true_passes(self):
        result = {
            "connected": True, "submitted": True, "accepted": True,
            "canceled": True, "confirmed_closed": True,
        }
        assert drill.drill_passed(result) is True

    def test_any_false_step_fails(self):
        result = {
            "connected": True, "submitted": True, "accepted": False,
            "canceled": True, "confirmed_closed": True,
        }
        assert drill.drill_passed(result) is False

    def test_missing_key_fails_closed(self):
        assert drill.drill_passed({"connected": True}) is False

    def test_real_drill_result_from_the_build_session_passes(self):
        # The literal result from the live 2026-07-03 run.
        result = {
            "connected": True, "account_address": "0x85411699631e80d8d2c78d3001226a9d3caf21f3",
            "balance_usdc": "AccountBalance(total=998.98605000 USDC, locked=0.00000000 USDC, free=998.98605000 USDC)",
            "submitted": True, "venue_order_id": "55885199953", "accepted": True,
            "canceled": True, "confirmed_closed": True,
        }
        assert drill.drill_passed(result) is True


class TestSafetyInvariants:
    def test_discount_keeps_order_well_below_market(self):
        # A resting BUY must rest meaningfully below mid or it risks filling.
        assert drill.DISCOUNT <= 0.85

    def test_no_mainnet_api_endpoint_anywhere_in_module_source(self):
        import inspect
        source = inspect.getsource(drill)
        assert "api.hyperliquid.xyz" not in source  # the real mainnet host
        assert "hyperliquid-testnet.xyz" in source  # the only host this module should ever hit

    def test_environment_is_hardcoded_testnet_not_configurable(self):
        import inspect
        source = inspect.getsource(drill.run_drill)
        assert "HyperliquidEnvironment.TESTNET" in source
        assert "MAINNET" not in source
