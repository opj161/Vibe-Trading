"""Unit tests for deployment/tickets.py -- ticket schema + persistence."""

from __future__ import annotations

import pytest

from deployment import tickets as tickets_mod
from deployment.tickets import Ticket, find_ticket, make_ticket_id, read_tickets, write_tickets


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tickets_mod, "STATE_DIR", tmp_path)


def _sample_ticket(ticket_id="ZA4_BTC-USDT_20260703") -> Ticket:
    return Ticket(
        ticket_id=ticket_id, strategy="ZA4", symbol="BTC-USDT", venue="binance_spot",
        side="buy", qty=0.004, notional_usd=260.0, reason="ZA4 BTC flip flat->long",
    )


class TestMakeTicketId:
    def test_normalizes_hyphenated_date(self):
        assert make_ticket_id("ZA4", "BTC-USDT", "2026-07-03") == "ZA4_BTC-USDT_20260703"

    def test_as_of_date_round_trips(self):
        t = _sample_ticket()
        assert t.as_of_date == "20260703"


class TestPersistence:
    def test_write_then_read_round_trips(self):
        write_tickets("2026-07-03", [_sample_ticket()])

        out = read_tickets("2026-07-03")

        assert len(out) == 1
        assert out[0] == _sample_ticket()

    def test_read_missing_date_returns_empty_list(self):
        assert read_tickets("2099-01-01") == []

    def test_find_ticket_locates_across_files(self):
        write_tickets("2026-07-01", [_sample_ticket("ZA4_BTC-USDT_20260701")])
        write_tickets("2026-07-03", [_sample_ticket("ZA4_BTC-USDT_20260703")])

        found = find_ticket("ZA4_BTC-USDT_20260701")

        assert found is not None
        assert found.ticket_id == "ZA4_BTC-USDT_20260701"

    def test_find_ticket_returns_none_when_absent(self):
        assert find_ticket("does-not-exist") is None
