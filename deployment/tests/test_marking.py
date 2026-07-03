"""Unit tests for deployment/marking.py + the ledger filters it relies on --
fixture data only, no network."""

from __future__ import annotations

import pytest

from deployment import ledger, marking


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(marking, "MARKS_PATH", tmp_path / "equity_marks.csv")


def _fill(*, symbol="BTC-USDT", venue="binance_spot", side="buy", qty=1.0,
          price=100.0, fee=0.0, paper=True, ticket_id="t"):
    ledger.append_ledger_row(
        ticket_id=ticket_id, symbol=symbol, venue=venue, side=side,
        status="confirmed", qty=qty, price=price, fee=fee, paper=paper,
    )


class TestLedgerFilters:
    def test_paper_filter_separates_modes(self):
        _fill(paper=True, qty=1.0)
        _fill(paper=False, qty=2.0)

        assert len(ledger.confirmed_fills(paper=True)) == 1
        assert len(ledger.confirmed_fills(paper=False)) == 1
        assert len(ledger.confirmed_fills()) == 2

    def test_position_respects_paper_filter(self):
        _fill(paper=True, qty=1.0)
        _fill(paper=False, qty=2.0)

        assert ledger.current_position("BTC-USDT", "binance_spot", paper=True) == pytest.approx(1.0)
        assert ledger.current_position("BTC-USDT", "binance_spot", paper=False) == pytest.approx(2.0)

    def test_open_positions_lists_nonzero_pairs_only(self):
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=1.0)
        _fill(symbol="BTC-USDT", venue="binance_spot", side="sell", qty=1.0)  # closed
        _fill(symbol="SOL-USDT", venue="binance_usdtm", side="sell", qty=3.0)

        out = ledger.open_positions(paper=True)

        assert out == {("SOL-USDT", "binance_usdtm"): pytest.approx(-3.0)}

    def test_sleeve_equity_asof_picks_latest_at_or_before(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=1000.0)
        ledger.append_equity_snapshot(date="2026-08-01", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=2000.0)

        asof = ledger.sleeve_equity_asof("2026-07-15")

        assert asof["crypto_equity"] == pytest.approx(1000.0)
        assert asof["anchor_date"] == "2026-07-01"

    def test_position_entry_info_tracks_current_streak(self):
        _fill(side="buy", qty=1.0, ticket_id="ZA4_BTC-USDT_20260701")
        _fill(side="sell", qty=1.0, ticket_id="ZA4_BTC-USDT_20260705")  # flat again
        _fill(side="sell", qty=2.0, ticket_id="ZA4_BTC-USDT_20260710")  # new short streak

        info = ledger.position_entry_info("BTC-USDT", "binance_spot", paper=True)

        assert info is not None
        assert info["qty"] == pytest.approx(-2.0)
        assert info["resize_recorded"] is False

    def test_position_entry_info_sees_recorded_resize(self):
        _fill(side="sell", qty=2.0, ticket_id="ZD2_BTC-USDT_20260701")
        _fill(side="sell", qty=2.0, ticket_id="ZD2_BTC-USDT_20260711_resize")

        info = ledger.position_entry_info("BTC-USDT", "binance_spot", paper=True)

        assert info is not None
        assert info["qty"] == pytest.approx(-4.0)
        assert info["resize_recorded"] is True

    def test_position_entry_info_none_when_flat(self):
        _fill(side="buy", qty=1.0)
        _fill(side="sell", qty=1.0)

        assert ledger.position_entry_info("BTC-USDT", "binance_spot", paper=True) is None


class TestValueSleeve:
    def test_seed_plus_flows_plus_marks(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=1000.0)
        _fill(side="buy", qty=0.01, price=60000.0, fee=0.6)

        v = marking.value_sleeve(
            "crypto", paper=True,
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            anchor_date="2026-07-01",
        )

        assert v["cash_flow"] == pytest.approx(-600.6)
        assert v["position_value"] == pytest.approx(650.0)
        assert v["equity"] == pytest.approx(1000.0 - 600.6 + 650.0)
        assert v["carryover"] == {}

    def test_unmarked_open_position_is_reported_not_zeroed(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=1000.0)
        _fill(side="buy", qty=0.01, price=60000.0)

        v = marking.value_sleeve("crypto", paper=True, mark_prices={}, anchor_date="2026-07-01")

        assert v["unmarked"] == [("BTC-USDT", "binance_spot")]
        assert v["position_value"] == 0.0

    def test_short_position_marks_negative(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_usdtm",
                                      symbol_or_cash="cash", balance_usd=1000.0)
        _fill(venue="binance_usdtm", side="sell", qty=1.0, price=150.0, symbol="SOL-USDT")

        v = marking.value_sleeve(
            "crypto", paper=True,
            mark_prices={("SOL-USDT", "binance_usdtm"): 120.0},
            anchor_date="2026-07-01",
        )

        # sold at 150 (+150 cash), open -1 marked at 120 (-120) -> +30 pnl
        assert v["equity"] == pytest.approx(1000.0 + 150.0 - 120.0)


class TestMarksSeries:
    def test_append_and_total_series(self):
        marking.append_marks(date="2026-07-01", mode_paper=True,
                             sleeve_equities={"crypto": 300.0, "macro": 700.0})
        marking.append_marks(date="2026-07-02", mode_paper=True,
                             sleeve_equities={"crypto": 310.0, "macro": 705.0})

        series = marking.equity_series(mode_paper=True)

        assert len(series) == 2
        assert series.iloc[0] == pytest.approx(1000.0)
        assert series.iloc[-1] == pytest.approx(1015.0)

    def test_rerun_same_date_keeps_last_row(self):
        marking.append_marks(date="2026-07-01", mode_paper=True,
                             sleeve_equities={"crypto": 300.0})
        marking.append_marks(date="2026-07-01", mode_paper=True,
                             sleeve_equities={"crypto": 305.0})

        series = marking.equity_series(mode_paper=True)

        assert len(series) == 1
        assert series.iloc[0] == pytest.approx(305.0)

    def test_mode_filter(self):
        marking.append_marks(date="2026-07-01", mode_paper=True,
                             sleeve_equities={"crypto": 300.0})
        marking.append_marks(date="2026-07-01", mode_paper=False,
                             sleeve_equities={"crypto": 999.0})

        assert marking.equity_series(mode_paper=True).iloc[0] == pytest.approx(300.0)
        assert marking.equity_series(mode_paper=False).iloc[0] == pytest.approx(999.0)

    def test_fetch_mark_prices_omits_failures(self):
        prices = marking.fetch_mark_prices(
            {("BTC-USDT", "binance_spot"): 1.0, ("SOL-USDT", "binance_usdtm"): -1.0},
            fetch=lambda sym, venue: 65000.0 if sym == "BTC-USDT" else None,
        )

        assert prices == {("BTC-USDT", "binance_spot"): 65000.0}
