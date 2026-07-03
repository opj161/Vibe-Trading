"""Unit tests for deployment/tracking_report.py -- fixture data only, no network."""

from __future__ import annotations

import pytest

from deployment import ledger, tracking_report


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(tracking_report, "AGENT_DIR", tmp_path / "agent")


def _write_equity_csv(run_dir, rows):
    (run_dir / "artifacts").mkdir(parents=True)
    path = run_dir / "artifacts" / "equity.csv"
    with path.open("w") as f:
        f.write("timestamp,equity\n")
        for date, equity in rows:
            f.write(f"{date},{equity}\n")


class TestRealizedAndUnrealizedPnl:
    def test_no_fills_returns_zero(self):
        assert tracking_report.realized_and_unrealized_pnl("BTC-USDT", "binance_spot", 65000.0) == 0.0

    def test_closed_round_trip_realizes_profit(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=1.0, price=60000.0, fee=1.0,
        )
        ledger.append_ledger_row(
            ticket_id="t2", symbol="BTC-USDT", venue="binance_spot",
            side="sell", status="confirmed", qty=1.0, price=65000.0, fee=1.0,
        )
        pnl = tracking_report.realized_and_unrealized_pnl("BTC-USDT", "binance_spot", 999999.0)
        # bought at 60000, sold at 65000, minus 2 in fees; mark price irrelevant (flat now)
        assert pnl == pytest.approx(65000.0 - 60000.0 - 2.0)

    def test_open_position_is_marked_to_current_price(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=1.0, price=60000.0, fee=0.0,
        )
        pnl = tracking_report.realized_and_unrealized_pnl("BTC-USDT", "binance_spot", 65000.0)
        # -60000 cash out + 1.0 * 65000 mark-to-market = +5000
        assert pnl == pytest.approx(5000.0)

    def test_other_symbol_venue_pairs_are_excluded(self):
        ledger.append_ledger_row(
            ticket_id="t1", symbol="SOL-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=10.0, price=80.0,
        )
        assert tracking_report.realized_and_unrealized_pnl("BTC-USDT", "binance_spot", 65000.0) == 0.0


class TestPaperEquityCurve:
    def test_no_runs_returns_none(self):
        assert tracking_report.latest_paper_equity_curve("ZA4") is None

    def test_finds_most_recent_run_by_name_sort(self, tmp_path):
        runs = tmp_path / "agent" / "runs"
        runs.mkdir(parents=True)
        _write_equity_csv(runs / "deploy_ZA4_20260701", [("2026-07-01", 1000.0)])
        _write_equity_csv(runs / "deploy_ZA4_20260703", [("2026-07-03", 1010.0)])

        curve = tracking_report.latest_paper_equity_curve("ZA4")

        assert curve is not None
        assert curve.iloc[-1] == pytest.approx(1010.0)

    def test_return_pct_since_computes_cumulative_return(self, tmp_path):
        runs = tmp_path / "agent" / "runs"
        runs.mkdir(parents=True)
        _write_equity_csv(runs / "deploy_ZA4_20260703", [
            ("2026-06-30", 1000.0), ("2026-07-01", 1050.0), ("2026-07-03", 1100.0),
        ])

        pct = tracking_report.paper_return_pct_since("ZA4", "2026-07-01")

        assert pct == pytest.approx((1100.0 / 1050.0 - 1.0) * 100)

    def test_return_pct_since_none_when_no_data_in_window(self, tmp_path):
        runs = tmp_path / "agent" / "runs"
        runs.mkdir(parents=True)
        _write_equity_csv(runs / "deploy_ZA4_20260703", [("2026-06-01", 1000.0)])

        assert tracking_report.paper_return_pct_since("ZA4", "2026-07-01") is None


class TestBuildReport:
    def test_no_data_produces_none_divergence(self, tmp_path):
        out = tracking_report.build_report(since_date="2026-07-01", mark_prices={})
        assert out["live_return_pct"] is None
        assert out["divergence_pct"] is None

    def test_computes_divergence_from_live_and_paper(self, tmp_path):
        runs = tmp_path / "agent" / "runs"
        runs.mkdir(parents=True)
        _write_equity_csv(runs / "deploy_ZA4_20260703", [
            ("2026-07-01", 1000.0), ("2026-07-03", 1050.0),  # +5% paper
        ])
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0)
        ledger.append_ledger_row(
            ticket_id="t1", symbol="BTC-USDT", venue="binance_spot",
            side="buy", status="confirmed", qty=0.01, price=60000.0,
        )

        out = tracking_report.build_report(
            since_date="2026-07-01", mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
        )

        # live pnl = 0.01 * (65000-60000) = 50; reference equity = 1000 -> +5% live too
        assert out["live_return_pct"] == pytest.approx(5.0)
        assert out["divergence_pct"] == pytest.approx(0.0, abs=0.01)
