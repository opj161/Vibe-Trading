"""Unit tests for deployment/confirm.py -- the human confirmation CLI."""

from __future__ import annotations

import sys

import pytest

from deployment import confirm, ledger
from deployment import tickets as tickets_mod
from deployment.tickets import Ticket, write_tickets


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(tickets_mod, "STATE_DIR", tmp_path)


def _seed_ticket() -> Ticket:
    t = Ticket(
        ticket_id="ZA4_BTC-USDT_20260703", strategy="ZA4", symbol="BTC-USDT",
        venue="binance_spot", side="buy", qty=0.004, notional_usd=260.0,
        reason="ZA4 BTC flip flat->long",
    )
    write_tickets("2026-07-03", [t])
    return t


def _run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["confirm.py", *args])
    confirm.main()


class TestConfirmFill:
    def test_confirming_a_fill_appends_confirmed_row(self, monkeypatch):
        _seed_ticket()

        _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--px", "65000", "--qty", "0.004", "--fee", "0.5")

        df = ledger.read_ledger()
        assert len(df) == 1
        row = df.iloc[0]
        assert row["status"] == "confirmed"
        assert row["side"] == "buy"
        assert row["symbol"] == "BTC-USDT"
        assert float(row["qty"]) == pytest.approx(0.004)
        assert float(row["price"]) == pytest.approx(65000.0)

    def test_paper_flag_is_recorded(self, monkeypatch):
        _seed_ticket()

        _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--px", "65000", "--qty", "0.004", "--paper")

        row = ledger.read_ledger().iloc[0]
        assert bool(row["paper"]) is True

    def test_missing_ticket_exits_nonzero(self, monkeypatch):
        with pytest.raises(SystemExit) as exc:
            _run_cli(monkeypatch, "does-not-exist", "--px", "1", "--qty", "1")
        assert exc.value.code != 0
        assert ledger.read_ledger().empty

    def test_fill_without_px_or_qty_exits_nonzero(self, monkeypatch):
        _seed_ticket()
        with pytest.raises(SystemExit):
            _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703")


class TestSkip:
    def test_skip_appends_skipped_row_with_reason(self, monkeypatch):
        _seed_ticket()

        _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--skip", "--reason", "below venue minimum")

        row = ledger.read_ledger().iloc[0]
        assert row["status"] == "skipped"
        assert row["reason"] == "below venue minimum"

    def test_skip_without_reason_exits_nonzero(self, monkeypatch):
        _seed_ticket()
        with pytest.raises(SystemExit):
            _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--skip")

    def test_skip_combined_with_px_exits_nonzero(self, monkeypatch):
        _seed_ticket()
        with pytest.raises(SystemExit):
            _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--skip", "--reason", "x", "--px", "1")


class TestCorrection:
    def test_supersedes_marks_prior_row_excluded_from_position(self, monkeypatch, capsys):
        _seed_ticket()
        _run_cli(monkeypatch, "ZA4_BTC-USDT_20260703", "--px", "65000", "--qty", "99")
        wrong_row_id = ledger.read_ledger().iloc[0]["row_id"]

        # Same ticket_id (deterministic per strategy/symbol/day) -- the correction
        # is disambiguated by referencing the specific wrong row_id, not the ticket_id.
        _run_cli(
            monkeypatch, "ZA4_BTC-USDT_20260703", "--px", "65000", "--qty", "0.004",
            "--supersedes", wrong_row_id,
        )

        assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(0.004)
        assert len(ledger.read_ledger()) == 2
