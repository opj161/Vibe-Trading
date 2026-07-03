"""Unit tests for deployment/risk_rules.py -- pure functions over ledger state."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from deployment import alerts, ledger, risk_rules


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")


class _RecordingNotifier:
    def __init__(self):
        self.sent = []

    def notify(self, text: str) -> bool:
        self.sent.append(text)
        return True


def _seed_equity(dates_and_totals: list[tuple[str, float]]) -> None:
    for date, total in dates_and_totals:
        ledger.append_equity_snapshot(date=date, venue="binance_spot", symbol_or_cash="cash", balance_usd=total)


class TestTotalEquitySeries:
    def test_empty_history_returns_empty_series(self):
        assert risk_rules.total_equity_series().empty

    def test_sums_multiple_venues_per_date(self):
        ledger.append_equity_snapshot(date="2026-07-01", venue="binance_spot", symbol_or_cash="cash", balance_usd=500.0)
        ledger.append_equity_snapshot(date="2026-07-01", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=1500.0)
        series = risk_rules.total_equity_series()
        assert len(series) == 1
        assert series.iloc[0] == pytest.approx(2000.0)


class TestDrawdown:
    def test_no_drawdown_when_at_high_water_mark(self):
        equity = pd.Series([1000.0, 1050.0, 1100.0])
        assert risk_rules.check_drawdown(equity) is None

    def test_below_warn_threshold_fires_warn(self):
        equity = pd.Series([1000.0, 1000.0 * (1 - 0.16)])
        out = risk_rules.check_drawdown(equity)
        assert out is not None
        assert out["level"] == risk_rules.HWM_DRAWDOWN_WARN
        assert "reduce" in out["action"]

    def test_below_close_only_threshold_fires_close_only_not_warn(self):
        equity = pd.Series([1000.0, 1000.0 * (1 - 0.25)])
        out = risk_rules.check_drawdown(equity)
        assert out["level"] == risk_rules.HWM_DRAWDOWN_CLOSE_ONLY
        assert "close-only" in out["action"]

    def test_small_drawdown_under_threshold_fires_nothing(self):
        equity = pd.Series([1000.0, 950.0])  # -5%, well under -15%
        assert risk_rules.check_drawdown(equity) is None

    def test_single_data_point_is_inconclusive(self):
        assert risk_rules.check_drawdown(pd.Series([1000.0])) is None


class TestSingleDayLoss:
    def test_large_one_day_drop_fires(self):
        equity = pd.Series([1000.0, 930.0])  # -7%
        out = risk_rules.check_single_day_loss(equity)
        assert out is not None
        assert out["loss_pct"] == pytest.approx(-7.0, abs=0.01)

    def test_small_one_day_move_does_not_fire(self):
        equity = pd.Series([1000.0, 990.0])  # -1%
        assert risk_rules.check_single_day_loss(equity) is None


class TestMissedRun:
    def test_crypto_sleeve_alerts_after_one_day(self):
        out = risk_rules.check_missed_run("ZA4", "crypto", "2026-07-01", "2026-07-03")
        assert out is not None
        assert out["days_stale"] == 2

    def test_crypto_sleeve_no_alert_when_fresh(self):
        assert risk_rules.check_missed_run("ZA4", "crypto", "2026-07-02", "2026-07-03") is None

    def test_macro_sleeve_tolerates_a_long_weekend(self):
        # Friday close -> Tuesday run, 4 calendar days, still within the macro threshold
        assert risk_rules.check_missed_run("M1", "macro", "2026-06-29", "2026-07-03") is None

    def test_macro_sleeve_alerts_beyond_its_threshold(self):
        out = risk_rules.check_missed_run("M1", "macro", "2026-06-25", "2026-07-03")
        assert out is not None


class TestReconciliationDue:
    def test_no_history_is_immediately_due(self):
        out = risk_rules.check_reconciliation_due()
        assert out is not None
        assert out["days_since_last"] is None

    def test_recent_snapshot_not_due(self):
        today = dt.date.today().isoformat()
        ledger.append_equity_snapshot(date=today, venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0)
        assert risk_rules.check_reconciliation_due() is None

    def test_stale_snapshot_is_due(self):
        old_date = (dt.date.today() - dt.timedelta(days=10)).isoformat()
        ledger.append_equity_snapshot(date=old_date, venue="binance_spot", symbol_or_cash="cash", balance_usd=1000.0)
        out = risk_rules.check_reconciliation_due()
        assert out is not None
        assert out["days_since_last"] >= risk_rules.RECONCILIATION_REMINDER_DAYS


class TestTrackingError:
    def test_under_tolerance_is_none(self):
        assert risk_rules.check_tracking_error(1.5) is None

    def test_over_tolerance_flags_halt(self):
        out = risk_rules.check_tracking_error(4.0)
        assert out is not None
        assert out["halt"] is True


class TestRunRiskChecksIntegration:
    def _signal_state(self, effective_as_of="2026-07-03", as_of="2026-07-03"):
        return {
            "as_of_date": as_of,
            "strategies": {
                "ZA4": {"effective_as_of": effective_as_of},
                "M1": {"effective_as_of": effective_as_of},
            },
        }

    def test_clean_state_fires_only_reconciliation_reminder(self):
        # No equity history at all -> reconciliation is due, nothing else fires
        notifier = _RecordingNotifier()
        fired = risk_rules.run_risk_checks(self._signal_state(), notifier=notifier)
        types = {f["type"] for f in fired}
        assert types == {"reconciliation_due"}
        assert len(notifier.sent) == 1

    def test_drawdown_and_missed_run_both_fire_and_notify(self):
        _seed_equity([("2026-06-30", 1000.0), ("2026-07-03", 800.0)])  # -20%
        notifier = _RecordingNotifier()

        fired = risk_rules.run_risk_checks(
            self._signal_state(effective_as_of="2026-06-30", as_of="2026-07-03"), notifier=notifier,
        )

        types = {f["type"] for f in fired}
        assert "drawdown" in types
        assert "missed_run" in types
        assert len(notifier.sent) == len(fired)
