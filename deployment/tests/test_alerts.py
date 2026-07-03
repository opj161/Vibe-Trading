"""Unit tests for deployment/alerts.py. Network is mocked."""

from __future__ import annotations

import httpx
import pytest

from deployment import alerts


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=None, response=self)

    def json(self):
        return self._payload


class TestNullNotifier:
    def test_notify_always_returns_false(self):
        assert alerts.NullNotifier().notify("hello") is False


class TestBuildNotifier:
    def test_returns_null_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        assert isinstance(alerts.build_notifier(), alerts.NullNotifier)

    def test_returns_telegram_when_env_set(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
        assert isinstance(alerts.build_notifier(), alerts.TelegramNotifier)

    def test_returns_null_when_only_token_set(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        assert isinstance(alerts.build_notifier(), alerts.NullNotifier)


class TestTelegramNotifierSend:
    def test_successful_send_returns_true(self, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"ok": True}))
        notifier = alerts.TelegramNotifier("tok", "123")
        assert notifier.notify("hello") is True

    def test_api_failure_returns_false_never_raises(self, monkeypatch):
        def _raise(*a, **k):
            raise httpx.ConnectError("no network", request=None)
        monkeypatch.setattr(httpx, "post", _raise)
        notifier = alerts.TelegramNotifier("tok", "123")
        assert notifier.notify("hello") is False

    def test_empty_message_rejected_without_network_call(self, monkeypatch):
        called = []
        monkeypatch.setattr(httpx, "post", lambda *a, **k: called.append(1) or _FakeResponse({"ok": True}))
        assert alerts.TelegramNotifier("tok", "123").notify("") is False
        assert called == []

    def test_oversized_message_rejected(self, monkeypatch):
        called = []
        monkeypatch.setattr(httpx, "post", lambda *a, **k: called.append(1) or _FakeResponse({"ok": True}))
        assert alerts.TelegramNotifier("tok", "123").notify("x" * 5000) is False
        assert called == []


class TestFormatters:
    def test_format_signal_flip_includes_all_tickets(self):
        out = alerts.format_signal_flip(["BUY 1 BTC", "SELL 1 SOL"], "2026-07-03")
        assert "BUY 1 BTC" in out
        assert "SELL 1 SOL" in out
        assert "2026-07-03" in out

    def test_format_drawdown_alert_includes_level_and_action(self):
        out = alerts.format_drawdown_alert(15.0, -16.2, "reduce new-entry size 50%")
        assert "15" in out
        assert "reduce new-entry size 50%" in out

    def test_format_tracking_error_summary_flags_halt_over_tolerance(self):
        out = alerts.format_tracking_error_summary(5.0, quarter_tolerance_pct=3.0)
        assert "HALT" in out

    def test_format_tracking_error_summary_within_tolerance(self):
        out = alerts.format_tracking_error_summary(1.0, quarter_tolerance_pct=3.0)
        assert "within tolerance" in out
