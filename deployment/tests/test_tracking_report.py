"""Unit tests for deployment/tracking_report.py -- fixture data only, no
network. Each of the five 2026-07-03 reassessment defects (mixed windows,
mixed paper/live modes, latest-equity denominator, unweighted strategy
average, wrong macro reference curve) has a dedicated regression test here.
"""

from __future__ import annotations

import pytest

from deployment import ledger, marking, profiles, tracking_report


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(marking, "MARKS_PATH", tmp_path / "equity_marks.csv")
    monkeypatch.setattr(tracking_report, "AGENT_DIR", tmp_path / "agent")


CPD1_LF = profiles.PROFILES["cpd1_lf"]
CTD_ZA4 = profiles.PROFILES["ctd_za4"]


def _write_equity_csv(run_dir, rows):
    (run_dir / "artifacts").mkdir(parents=True)
    path = run_dir / "artifacts" / "equity.csv"
    with path.open("w") as f:
        f.write("timestamp,equity\n")
        for date, equity in rows:
            f.write(f"{date},{equity}\n")


def _paper_curve(tmp_path, strategy, rows, run_date="20260801"):
    runs = tmp_path / "agent" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    _write_equity_csv(runs / f"deploy_{strategy}_{run_date}", rows)


def _fill(*, symbol, venue, side, qty, price, fee=0.0, paper=True, recorded_at=None, ticket_id="t"):
    """Append a confirmed fill, optionally with an explicit recorded_at (the
    public API always stamps 'now', which the windowing tests can't use)."""
    if recorded_at is None:
        ledger.append_ledger_row(
            ticket_id=ticket_id, symbol=symbol, venue=venue, side=side,
            status="confirmed", qty=qty, price=price, fee=fee, paper=paper,
        )
        return
    ledger._append_row(ledger.LEDGER_PATH, ledger.LEDGER_COLUMNS, {
        "row_id": f"row_{recorded_at}_{symbol}_{side}",
        "ticket_id": ticket_id, "recorded_at": recorded_at, "symbol": symbol,
        "venue": venue, "side": side, "status": "confirmed", "qty": qty,
        "price": price, "fee": fee, "reason": "", "paper": paper, "supersedes": "",
    })


class TestAnchorDenominator:
    def test_no_snapshot_at_or_before_since_date_raises(self):
        ledger.append_equity_snapshot(
            date="2026-08-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=750.0,
        )
        with pytest.raises(ValueError, match="no equity snapshot"):
            tracking_report.build_report(
                since_date="2026-07-01", mark_prices={}, paper=True, profile=CTD_ZA4,
            )

    def test_denominator_is_anchor_equity_not_latest(self, tmp_path):
        """Reassessment defect #3: a later, larger snapshot must not shrink
        the measured live return."""
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0,
        )
        # Account doubled later -- must NOT become the denominator.
        ledger.append_equity_snapshot(
            date="2026-08-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=2000.0,
        )
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.01, price=60000.0,
              recorded_at="2026-07-02T10:00:00+00:00")
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1050.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01",
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            paper=True, profile=CTD_ZA4,
        )

        # live pnl = 0.01 * (65000-60000) = 50 over ANCHOR 1000 -> 5%
        assert out["by_sleeve"]["crypto"]["return_pct"] == pytest.approx(5.0)
        assert out["live_return_pct"] == pytest.approx(5.0)


class TestModeSeparation:
    def test_live_rows_excluded_from_paper_report(self, tmp_path):
        """Reassessment defect #2: paper and live ledger rows must never mix."""
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0,
        )
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.01, price=60000.0,
              paper=True, recorded_at="2026-07-02T10:00:00+00:00")
        # A LIVE fill that would double the measured PnL if mixed in.
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.01, price=60000.0,
              paper=False, recorded_at="2026-07-02T11:00:00+00:00")
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1050.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01",
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            paper=True, profile=CTD_ZA4,
        )

        assert out["by_sleeve"]["crypto"]["pnl_usd"] == pytest.approx(50.0)


class TestWindowing:
    def test_fills_before_window_are_excluded(self, tmp_path):
        """Reassessment defect #1: a closed round trip BEFORE the window must
        not leak into this window's live P&L."""
        # Old, closed +$5000 round trip, well before the window.
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.1, price=50000.0,
              recorded_at="2026-05-01T10:00:00+00:00")
        _fill(symbol="BTC-USDT", venue="binance_spot", side="sell", qty=0.1, price=55000.0,
              recorded_at="2026-05-20T10:00:00+00:00")
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0,
        )
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.01, price=60000.0,
              recorded_at="2026-07-02T10:00:00+00:00")
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1050.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01",
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            paper=True, profile=CTD_ZA4,
        )

        assert out["by_sleeve"]["crypto"]["pnl_usd"] == pytest.approx(50.0)
        assert out["warnings"] == []  # closed pre-window position: no carryover

    def test_open_carryover_position_is_flagged(self, tmp_path):
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.1, price=50000.0,
              recorded_at="2026-05-01T10:00:00+00:00")  # still open at the anchor
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0,
        )
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1050.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01",
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            paper=True, profile=CTD_ZA4,
        )

        assert any("carryover" in w or "unvalued" in w for w in out["warnings"])


class TestProfileWeighting:
    def test_composite_uses_sleeve_weights_not_mean(self, tmp_path):
        """Reassessment defect #4: ZA4 +10% at 30% weight and M1LF +2% at 70%
        weight must composite to 4.4%, not the unweighted 6%."""
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=300.0,
        )
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=700.0,
        )
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1100.0)])
        _paper_curve(tmp_path, "M1LF", [("2026-07-01", 1000.0), ("2026-08-02", 1020.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01", mark_prices={}, paper=True, profile=CPD1_LF,
        )

        assert out["paper_return_pct"] == pytest.approx(0.3 * 10.0 + 0.7 * 2.0)

    def test_macro_reference_is_m1lf_curve(self, tmp_path):
        """Reassessment defect #5: with the cpd1_lf profile the macro paper
        reference must be the deploy_M1LF curve; a deploy_M1 curve must not
        be consulted at all."""
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=300.0,
        )
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=700.0,
        )
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1000.0)])
        _paper_curve(tmp_path, "M1LF", [("2026-07-01", 1000.0), ("2026-08-02", 1030.0)])
        # Full-M1 curve says -10%; it must be ignored under cpd1_lf.
        _paper_curve(tmp_path, "M1", [("2026-07-01", 1000.0), ("2026-08-02", 900.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01", mark_prices={}, paper=True, profile=CPD1_LF,
        )

        assert "M1LF" in out["by_strategy_paper_return_pct"]
        assert "M1" not in out["by_strategy_paper_return_pct"]
        assert out["paper_return_pct"] == pytest.approx(0.7 * 3.0)

    def test_missing_paper_curve_is_warned_and_reweighted(self, tmp_path):
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=300.0,
        )
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=700.0,
        )
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1100.0)])
        # No M1LF curve at all.

        out = tracking_report.build_report(
            since_date="2026-07-01", mark_prices={}, paper=True, profile=CPD1_LF,
        )

        assert out["by_strategy_paper_return_pct"]["M1LF"] is None
        assert any("M1LF" in w for w in out["warnings"])
        # Renormalized over the strategies that have data: just ZA4.
        assert out["paper_return_pct"] == pytest.approx(10.0)


class TestEndToEnd:
    def test_matching_live_and_paper_gives_zero_divergence(self, tmp_path):
        ledger.append_equity_snapshot(
            date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0,
        )
        _fill(symbol="BTC-USDT", venue="binance_spot", side="buy", qty=0.01, price=60000.0,
              recorded_at="2026-07-02T10:00:00+00:00")
        _paper_curve(tmp_path, "ZA4", [("2026-07-01", 1000.0), ("2026-08-02", 1050.0)])

        out = tracking_report.build_report(
            since_date="2026-07-01",
            mark_prices={("BTC-USDT", "binance_spot"): 65000.0},
            paper=True, profile=CTD_ZA4,
        )

        assert out["live_return_pct"] == pytest.approx(5.0)
        assert out["paper_return_pct"] == pytest.approx(5.0)
        assert out["divergence_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_paper_curve_helpers_still_work(self, tmp_path):
        _paper_curve(tmp_path, "ZA4", [
            ("2026-06-30", 1000.0), ("2026-07-01", 1050.0), ("2026-07-03", 1100.0),
        ], run_date="20260703")

        pct = tracking_report.paper_return_pct_since("ZA4", "2026-07-01")

        assert pct == pytest.approx((1100.0 / 1050.0 - 1.0) * 100)
