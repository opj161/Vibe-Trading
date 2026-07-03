"""Unit + end-to-end tests for deployment/daily_cycle.py -- fixture data
only, no network, no real Telegram (build_notifier is always monkeypatched;
the repo .env may hold real credentials)."""

from __future__ import annotations

import json
import sys

import pytest

from deployment import (
    alerts, daily_cycle, ledger, marking, order_tickets, profiles,
    signal_runner, venue_specs,
)
from deployment import tickets as tickets_mod
from deployment.tickets import Ticket


class CaptureNotifier:
    def __init__(self):
        self.messages: list[str] = []

    def notify(self, text: str) -> bool:
        self.messages.append(text)
        return True


@pytest.fixture()
def notifier():
    return CaptureNotifier()


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch, notifier):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(marking, "MARKS_PATH", tmp_path / "equity_marks.csv")
    monkeypatch.setattr(tickets_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(signal_runner, "STATE_DIR", tmp_path)
    monkeypatch.setattr(alerts, "build_notifier", lambda: notifier)


def _ticket(**kw) -> Ticket:
    base = dict(
        ticket_id="ZA4_BTC-USDT_20260703", strategy="ZA4", symbol="BTC-USDT",
        venue="binance_spot", side="buy", qty=0.01, notional_usd=650.0,
        reason="test", status="pending", human_text="BINANCE SPOT: BUY 0.01 BTCUSDT",
    )
    base.update(kw)
    return Ticket(**base)


class TestMergeDayTickets:
    def test_new_tickets_are_added(self):
        merged = daily_cycle.merge_day_tickets("2026-07-03", [_ticket()], paper=True)
        assert len(merged) == 1
        assert tickets_mod.read_tickets("2026-07-03")[0].ticket_id == "ZA4_BTC-USDT_20260703"

    def test_rerun_does_not_clobber_confirmed_ticket(self):
        original = _ticket(qty=0.01)
        daily_cycle.merge_day_tickets("2026-07-03", [original], paper=True)
        ledger.append_ledger_row(
            ticket_id=original.ticket_id, symbol=original.symbol, venue=original.venue,
            side="buy", status="confirmed", qty=0.01, price=65000.0, paper=True,
        )

        resized = _ticket(qty=0.02)  # a rerun that recomputed differently
        merged = daily_cycle.merge_day_tickets("2026-07-03", [resized], paper=True)

        assert len(merged) == 1
        assert merged[0].qty == pytest.approx(0.01)  # confirmed original wins

    def test_rerun_replaces_unconfirmed_ticket(self):
        daily_cycle.merge_day_tickets("2026-07-03", [_ticket(qty=0.01)], paper=True)
        merged = daily_cycle.merge_day_tickets("2026-07-03", [_ticket(qty=0.02)], paper=True)
        assert len(merged) == 1
        assert merged[0].qty == pytest.approx(0.02)


class TestAutoPaperFill:
    def test_pending_ticket_fills_at_reference_price_plus_fee(self, notifier):
        out = daily_cycle.auto_paper_fill(_ticket(), notifier=notifier)

        assert out is not None and "BUY" in out
        fills = ledger.confirmed_fills(paper=True)
        assert len(fills) == 1
        row = fills.iloc[0]
        assert float(row["price"]) == pytest.approx(65000.0)
        assert float(row["fee"]) == pytest.approx(0.001 * 65000.0 * 0.01)

    def test_idempotent_on_rerun(self, notifier):
        daily_cycle.auto_paper_fill(_ticket(), notifier=notifier)
        again = daily_cycle.auto_paper_fill(_ticket(), notifier=notifier)

        assert again is None
        assert len(ledger.confirmed_fills(paper=True)) == 1

    def test_review_ticket_is_skipped_never_executed(self, notifier):
        t = _ticket(status="review", side="sell", venue="binance_usdtm")

        out = daily_cycle.auto_paper_fill(t, notifier=notifier)

        assert out.startswith("SKIP")
        assert ledger.confirmed_fills(paper=True).empty  # no fill
        df = ledger.read_ledger()
        assert (df["status"] == "skipped").all()
        assert any("REVIEW" in m or "funding" in m for m in notifier.messages)

    def test_close_ticket_marks_at_current_price(self, notifier, monkeypatch):
        monkeypatch.setattr(marking, "fetch_mark_price", lambda sym, venue: 64000.0)
        t = _ticket(ticket_id="ZA4_BTC-USDT_20260703_close", side="sell",
                    qty=0.01, notional_usd=0.0)

        daily_cycle.auto_paper_fill(t, notifier=notifier)

        row = ledger.confirmed_fills(paper=True).iloc[0]
        assert float(row["price"]) == pytest.approx(64000.0)

    def test_no_price_leaves_ticket_pending_with_alert(self, notifier, monkeypatch):
        monkeypatch.setattr(marking, "fetch_mark_price", lambda sym, venue: None)
        t = _ticket(ticket_id="x_close", side="sell", qty=0.01, notional_usd=0.0)

        out = daily_cycle.auto_paper_fill(t, notifier=notifier)

        assert out is None
        assert ledger.confirmed_fills(paper=True).empty
        assert notifier.messages  # alert sent


class TestOpenShortFundingCheck:
    def test_costly_open_short_fires_review(self, notifier, monkeypatch):
        ledger.append_ledger_row(
            ticket_id="t", symbol="SOL-USDT", venue="binance_usdtm",
            side="sell", status="confirmed", qty=3.0, price=150.0, paper=True,
        )
        # Negative raw funding -> shorts pay 20%/yr, above the 15% threshold.
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: -0.20)

        fired = daily_cycle.check_open_short_funding(paper=True, notifier=notifier)

        assert len(fired) == 1
        assert fired[0]["symbol"] == "SOL-USDT"
        assert notifier.messages

    def test_favorable_funding_is_quiet(self, notifier, monkeypatch):
        ledger.append_ledger_row(
            ticket_id="t", symbol="SOL-USDT", venue="binance_usdtm",
            side="sell", status="confirmed", qty=3.0, price=150.0, paper=True,
        )
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: 0.10)

        assert daily_cycle.check_open_short_funding(paper=True, notifier=notifier) == []
        assert notifier.messages == []

    def test_spot_longs_are_ignored(self, notifier, monkeypatch):
        ledger.append_ledger_row(
            ticket_id="t", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.01, price=65000.0, paper=True,
        )
        monkeypatch.setattr(venue_specs, "binance_futures_funding_annualized", lambda sym: -0.99)

        assert daily_cycle.check_open_short_funding(paper=True, notifier=notifier) == []


class TestMarkSleeves:
    def test_no_snapshot_skips_marking(self):
        out = daily_cycle.mark_sleeves(profiles.PROFILES["cpd1_lf"], "2026-07-03", paper=True)
        assert out is None
        assert marking.read_marks().empty

    def test_marks_both_sleeves(self, monkeypatch):
        ledger.append_equity_snapshot(date="2026-07-02", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=750.0)
        ledger.append_equity_snapshot(date="2026-07-02", venue="ibkr_ucits",
                                      symbol_or_cash="cash", balance_usd=1750.0)
        monkeypatch.setattr(marking, "fetch_mark_price", lambda sym, venue: 66000.0)

        out = daily_cycle.mark_sleeves(profiles.PROFILES["cpd1_lf"], "2026-07-03", paper=True)

        assert out == {"crypto": pytest.approx(750.0), "macro": pytest.approx(1750.0)}
        assert len(marking.equity_series(mode_paper=True)) == 1


def _fake_state(as_of="2026-07-03"):
    return signal_runner.SignalState(
        as_of_date=as_of,
        generated_at=f"{as_of}T16:10:00+00:00",
        strategies={
            "ZA4": {
                "engine_sha256": "deadbeef", "effective_as_of": as_of, "stale": False,
                "targets": {
                    "BTC-USDT": signal_runner.SymbolTarget(0, 1, 0.3, True),
                    "SOL-USDT": signal_runner.SymbolTarget(0, 0, 0.0, False),
                },
            },
        },
    )


class TestMainEndToEnd:
    def test_full_auto_paper_day(self, monkeypatch, notifier, capsys):
        ledger.append_equity_snapshot(date="2026-07-02", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=750.0)
        ledger.append_equity_snapshot(date="2026-07-02", venue="ibkr_ucits",
                                      symbol_or_cash="cash", balance_usd=1750.0)
        monkeypatch.setattr(signal_runner, "run_signal",
                            lambda name, as_of, write_audit_trail=True:
                            _fake_state() if name == "ZA4" else (_ for _ in ()).throw(
                                daily_cycle.DataIntegrityError(f"{name}: fixture has no data")))
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
        monkeypatch.setattr(venue_specs, "binance_spot_filters",
                            lambda sym: {"step_size": 0.00001, "min_notional": 5.0})
        monkeypatch.setattr(marking, "fetch_mark_price", lambda sym, venue: 65000.0)
        monkeypatch.setattr(sys, "argv", [
            "daily_cycle.py", "--as-of", "2026-07-03", "--mode", "paper", "--auto-paper",
        ])

        with pytest.raises(SystemExit) as exc:
            daily_cycle.main()

        # M1LF + ZD2 "failed" (fixture), ZA4 succeeded -> exit 2, but the ZA4
        # leg is fully processed: ticket built, auto-filled, marked, summarized.
        assert exc.value.code == 2
        fills = ledger.confirmed_fills(paper=True)
        assert len(fills) == 1
        assert fills.iloc[0]["symbol"] == "BTC-USDT"
        summary = json.loads(capsys.readouterr().out)
        assert summary["auto_paper_fills"]
        assert summary["sleeve_equities"]["crypto"] > 0
        assert any("daily cycle" in m for m in notifier.messages)

    def test_rerun_same_day_is_idempotent(self, monkeypatch, notifier, capsys):
        ledger.append_equity_snapshot(date="2026-07-02", venue="binance_spot",
                                      symbol_or_cash="cash", balance_usd=750.0)
        ledger.append_equity_snapshot(date="2026-07-02", venue="ibkr_ucits",
                                      symbol_or_cash="cash", balance_usd=1750.0)
        monkeypatch.setattr(signal_runner, "run_signal",
                            lambda name, as_of, write_audit_trail=True: _fake_state())
        monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
        monkeypatch.setattr(venue_specs, "binance_spot_filters",
                            lambda sym: {"step_size": 0.00001, "min_notional": 5.0})
        monkeypatch.setattr(marking, "fetch_mark_price", lambda sym, venue: 65000.0)
        monkeypatch.setattr(sys, "argv", [
            "daily_cycle.py", "--as-of", "2026-07-03", "--mode", "paper", "--auto-paper",
            "--profile", "ctd_za4",
        ])

        for _ in range(2):
            with pytest.raises(SystemExit) as exc:
                daily_cycle.main()
            assert exc.value.code in (0, 2)
            capsys.readouterr()

        # One fill, not two -- and the position lookup means the second run
        # builds no new open ticket either.
        assert len(ledger.confirmed_fills(paper=True)) == 1

    def test_unseeded_equity_exits_3(self, monkeypatch, notifier):
        monkeypatch.setattr(signal_runner, "run_signal",
                            lambda name, as_of, write_audit_trail=True: _fake_state())
        monkeypatch.setattr(sys, "argv", [
            "daily_cycle.py", "--as-of", "2026-07-03", "--mode", "paper",
            "--profile", "ctd_za4",
        ])

        with pytest.raises(SystemExit) as exc:
            daily_cycle.main()

        assert exc.value.code == 3
        assert any("blocked" in m for m in notifier.messages)
