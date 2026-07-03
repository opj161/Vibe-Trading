"""Unit tests for deployment/order_tickets.py. ledger/venue_specs calls are
mocked (fixture data only, no network) -- a live end-to-end check is part of
the Phase A acceptance E2E test.
"""

from __future__ import annotations

import pytest

from deployment import ledger, order_tickets, venue_specs


def _signal_state(strategy: str, symbol: str, direction: int, weight: float, as_of="2026-07-03") -> dict:
    return {
        "as_of_date": as_of,
        "generated_at": "2026-07-03T00:00:00+00:00",
        "strategies": {
            strategy: {
                "engine_sha256": "deadbeef",
                "effective_as_of": as_of,
                "stale": False,
                "targets": {
                    symbol: {
                        "prev_direction": 0, "direction": direction,
                        "target_weight": weight, "flipped": True,
                    },
                },
            },
        },
    }


class TestCryptoNoExistingPosition:
    def test_flat_target_with_no_position_produces_no_ticket(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        state = _signal_state("ZA4", "BTC-USDT", 0, 0.0)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert out == []

    def test_long_target_opens_a_single_spot_ticket(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
        monkeypatch.setattr(
            venue_specs, "binance_spot_filters", lambda sym: {"step_size": 0.00001, "min_notional": 5.0},
        )
        state = _signal_state("ZA4", "BTC-USDT", 1, 0.3)  # 30% of 1000 crypto equity = $300

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert len(out) == 1
        t = out[0]
        assert t.venue == "binance_spot"
        assert t.side == "buy"
        # Floored to the 0.00001 step size, not the raw unrounded quotient
        assert t.qty == pytest.approx(300.0 / 65000.0, abs=1e-5)
        assert t.status == "pending"

    def test_short_target_opens_a_single_usdtm_ticket(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_futures_price", lambda sym: 60000.0)
        monkeypatch.setattr(
            venue_specs, "binance_futures_filters", lambda sym: {"step_size": 0.001, "min_notional": 50.0},
        )
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: 0.10)
        state = _signal_state("ZA4", "BTC-USDT", -1, -0.3)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert len(out) == 1
        t = out[0]
        assert t.venue == "binance_usdtm"
        assert t.side == "sell"
        assert t.status == "pending"
        assert "favorable" in t.reason


class TestCryptoFlip:
    def test_long_to_short_flip_produces_close_and_open_tickets(self, monkeypatch):
        # Currently 0.5 BTC long on spot
        monkeypatch.setattr(
            ledger, "current_position_any_venue",
            lambda symbol, venues: ("binance_spot", 0.5),
        )
        monkeypatch.setattr(venue_specs, "binance_futures_price", lambda sym: 60000.0)
        monkeypatch.setattr(
            venue_specs, "binance_futures_filters", lambda sym: {"step_size": 0.001, "min_notional": 50.0},
        )
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: 0.05)
        state = _signal_state("ZA4", "BTC-USDT", -1, -0.2)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert len(out) == 2
        close, open_ = out
        assert close.venue == "binance_spot" and close.side == "sell" and close.qty == pytest.approx(0.5)
        assert open_.venue == "binance_usdtm" and open_.side == "sell"

    def test_magnitude_only_change_same_direction_produces_no_ticket(self, monkeypatch):
        # Already long on spot; new target is still long (weight changed, direction didn't)
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("binance_spot", 0.3))
        state = _signal_state("ZA4", "BTC-USDT", 1, 0.6)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert out == []  # entry-locked sizing: no rebalance on magnitude alone


class TestCryptoQuantization:
    def test_below_venue_minimum_skips_never_forces_minimum(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
        monkeypatch.setattr(
            venue_specs, "binance_spot_filters", lambda sym: {"step_size": 0.00001, "min_notional": 500.0},
        )
        # tiny target notional: 0.001 * 1000 = $1, well under the $500 min
        state = _signal_state("ZA4", "BTC-USDT", 1, 0.001)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert len(out) == 1
        assert out[0].side == "skip"
        assert "min" in out[0].reason.lower()
        assert out[0].qty == 0.0

    def test_price_unavailable_skips_with_clear_reason(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: None)
        state = _signal_state("ZA4", "BTC-USDT", 1, 0.3)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert out[0].side == "skip"
        assert "price unavailable" in out[0].reason


class TestCryptoFundingReview:
    def test_unfavorable_funding_above_threshold_flags_review(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_futures_price", lambda sym: 60000.0)
        monkeypatch.setattr(
            venue_specs, "binance_futures_filters", lambda sym: {"step_size": 0.001, "min_notional": 50.0},
        )
        # Negative raw funding -> shorts PAY -> unfavorable, well above the 15%/yr threshold
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: -0.20)
        state = _signal_state("ZA4", "BTC-USDT", -1, -0.3)

        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=0.0)

        assert out[0].status == "review"
        assert "REVIEW" in out[0].reason


class TestMacro:
    def test_long_target_produces_buy_ticket_naming_ucits_candidates(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position", lambda *a, **k: 0.0)
        monkeypatch.setattr(venue_specs, "macro_reference_price", lambda sym: 700.0)
        state = _signal_state("M1", "SPY.US", 1, 0.4)  # 40% of 700 macro equity = $280

        out = order_tickets.build_tickets(state, crypto_equity=0.0, macro_equity=700.0)

        assert len(out) == 1
        t = out[0]
        assert t.venue == "ibkr_ucits"
        assert t.side == "buy"
        assert "SPYL" in t.human_text or "VUAA" in t.human_text

    def test_short_target_flags_review_not_silently_assumed(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position", lambda *a, **k: 0.0)
        state = _signal_state("M1", "GLD.US", -1, -0.13)

        out = order_tickets.build_tickets(state, crypto_equity=0.0, macro_equity=2800.0)

        assert len(out) == 1
        assert out[0].status == "review"
        assert out[0].side == "skip"
        assert "short" in out[0].reason.lower()

    def test_long_to_short_flip_still_closes_the_existing_long(self, monkeypatch):
        """Audit regression (2026-07-03): a macro long->short flip must emit
        the CLOSE ticket for the held long (the signal unambiguously says
        exit) alongside the REVIEW ticket for the undecided short expression
        -- the original code returned only the REVIEW ticket, silently
        stranding the long open."""
        # Arrange: holding 2 shares long, signal flips to short
        monkeypatch.setattr(ledger, "current_position", lambda *a, **k: 2.0)
        state = _signal_state("M1", "GLD.US", -1, -0.13)

        # Act
        out = order_tickets.build_tickets(state, crypto_equity=0.0, macro_equity=2800.0)

        # Assert: close ticket first (SELL the long), then the REVIEW skip
        assert len(out) == 2
        assert out[0].side == "sell"
        assert out[0].qty == 2.0
        assert "close" in out[0].human_text.lower()
        assert out[1].status == "review"
        assert out[1].side == "skip"

    def test_below_ibkr_floor_skips(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position", lambda *a, **k: 0.0)
        monkeypatch.setattr(venue_specs, "macro_reference_price", lambda sym: 700.0)
        state = _signal_state("M1", "SPY.US", 1, 0.001)  # tiny notional

        out = order_tickets.build_tickets(state, crypto_equity=0.0, macro_equity=700.0)

        assert out[0].side == "skip"
        assert "floor" in out[0].reason.lower()

    def test_flat_target_no_position_produces_no_ticket(self, monkeypatch):
        monkeypatch.setattr(ledger, "current_position", lambda *a, **k: 0.0)
        state = _signal_state("M1", "SPY.US", 0, 0.0)

        out = order_tickets.build_tickets(state, crypto_equity=0.0, macro_equity=700.0)

        assert out == []


class TestBuildTicketsEquitySource:
    def test_uses_ledger_latest_sleeve_equity_when_not_given(self, monkeypatch):
        monkeypatch.setattr(ledger, "latest_sleeve_equity", lambda: {"crypto_equity": 500.0, "macro_equity": 1000.0})
        monkeypatch.setattr(ledger, "current_position_any_venue", lambda *a, **k: ("", 0.0))
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
        monkeypatch.setattr(
            venue_specs, "binance_spot_filters", lambda sym: {"step_size": 0.00001, "min_notional": 5.0},
        )
        state = _signal_state("ZA4", "BTC-USDT", 1, 0.5)

        out = order_tickets.build_tickets(state)

        assert len(out) == 1
        assert out[0].notional_usd == pytest.approx(0.5 * 500.0, rel=1e-2)

    def test_unknown_strategy_is_skipped_without_crashing(self, monkeypatch):
        state = _signal_state("NOT_A_REAL_STRATEGY", "XYZ", 1, 0.5)
        out = order_tickets.build_tickets(state, crypto_equity=1000.0, macro_equity=1000.0)
        assert out == []
