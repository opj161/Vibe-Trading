"""Unit tests for deployment/ledger.py -- append-only CSVs, no network."""

from __future__ import annotations

import pytest

from deployment import ledger


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")


class TestAppendAndRead:
    def test_append_creates_header_on_first_row(self):
        # Arrange / Act
        ledger.append_ledger_row(
            ticket_id="ZA4_BTC-USDT_20260703", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.004, price=65000.0, fee=0.5,
        )
        # Assert
        df = ledger.read_ledger()
        assert list(df.columns) == ledger.LEDGER_COLUMNS
        assert len(df) == 1
        assert df.iloc[0]["ticket_id"] == "ZA4_BTC-USDT_20260703"

    def test_append_is_additive_not_overwriting(self):
        # Arrange
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=1.0, price=1.0,
        )
        # Act
        ledger.append_ledger_row(
            ticket_id="t2", symbol="SOL-USDT", venue="binance_spot",
            side="sell", status="skipped", reason="below minimum",
        )
        # Assert
        df = ledger.read_ledger()
        assert len(df) == 2
        assert set(df["ticket_id"]) == {"t1", "t2"}

    def test_read_ledger_empty_returns_empty_frame_with_columns(self):
        df = ledger.read_ledger()
        assert df.empty
        assert list(df.columns) == ledger.LEDGER_COLUMNS

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError):
            ledger.append_ledger_row(
                ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
                side="buy", status="not-a-real-status",
            )


class TestCurrentPosition:
    def test_no_history_returns_zero(self):
        assert ledger.current_position("BTC-USDT", "binance_spot") == 0.0

    def test_single_confirmed_buy_returns_positive_qty(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.5, price=65000.0,
        )
        assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(0.5)

    def test_buy_then_sell_nets_to_smaller_position(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.5, price=65000.0,
        )
        ledger.append_ledger_row(
            ticket_id="t2", symbol="BTC-USDT", venue="binance_spot",
            side="sell", status="confirmed", qty=0.2, price=66000.0,
        )
        assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(0.3)

    def test_skipped_rows_do_not_affect_position(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="skipped", reason="below minimum",
        )
        assert ledger.current_position("BTC-USDT", "binance_spot") == 0.0

    def test_scoped_by_venue_does_not_net_spot_against_perp(self):
        # Spot long and perp short on the same symbol are different
        # instruments (CPD-1's venue-split rule) -- must not net together.
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.5, price=65000.0,
        )
        ledger.append_ledger_row(
            ticket_id="t2", symbol="BTC-USDT", venue="binance_usdtm",
            side="sell", status="confirmed", qty=0.3, price=65000.0,
        )
        assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(0.5)
        assert ledger.current_position("BTC-USDT", "binance_usdtm") == pytest.approx(-0.3)

    def test_current_position_any_venue_finds_the_nonzero_leg(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_usdtm",
            side="sell", status="confirmed", qty=0.3, price=65000.0,
        )
        venue, qty = ledger.current_position_any_venue(
            "BTC-USDT", ["binance_spot", "binance_usdtm"],
        )
        assert venue == "binance_usdtm"
        assert qty == pytest.approx(-0.3)

    def test_current_position_any_venue_returns_empty_when_flat(self):
        venue, qty = ledger.current_position_any_venue(
            "BTC-USDT", ["binance_spot", "binance_usdtm"],
        )
        assert venue == ""
        assert qty == 0.0

    def test_superseded_row_excluded_from_position(self):
        # Arrange: a wrong confirmation (fat-fingered qty)...
        wrong_row_id = ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=99.0, price=65000.0,
        )
        # Act: ...corrected by a new row (same ticket_id, referencing the wrong row_id),
        # never edited in place
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.4, price=65000.0, supersedes=wrong_row_id,
        )
        # Assert: only the correction counts
        assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(0.4)
        # Original row is still physically present (append-only, never deleted)
        assert len(ledger.read_ledger()) == 2


class TestSleeveEquity:
    def test_no_snapshots_returns_zeros(self):
        assert ledger.latest_sleeve_equity() == {"crypto_equity": 0.0, "macro_equity": 0.0}

    def test_sums_crypto_venues_and_keeps_macro_separate(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0)
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_usdtm", symbol_or_cash="cash", balance_usd=200.0)
        ledger.append_equity_snapshot(date="2026-07-01", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=2800.0)

        out = ledger.latest_sleeve_equity()

        assert out == {"crypto_equity": pytest.approx(1200.0), "macro_equity": pytest.approx(2800.0)}

    def test_only_uses_most_recent_date(self):
        ledger.append_equity_snapshot(date="2026-06-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=500.0)
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0)

        out = ledger.latest_sleeve_equity()

        assert out["crypto_equity"] == pytest.approx(1000.0)
