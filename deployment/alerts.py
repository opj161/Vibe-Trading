"""Telegram alerting for the CPD-1 deployment loop.

Ports edgeforge's ``production/notifier.py`` pattern (raw ``httpx``, no SDK
dependency -- ``httpx`` is already a base dependency of this repo) rather than
pulling in ``python-telegram-bot``. Delivery is always best-effort and never
raises into a caller's control flow: a failed send is logged and reported as
not-delivered, never an exception.
"""

from __future__ import annotations

import html
import os
import sys
from typing import Protocol

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10.0
MAX_MESSAGE_LEN = 4096  # Telegram sendMessage `text` hard limit


class Notifier(Protocol):
    """Pushes a plain-text alert to the operator. Returns True iff delivered."""

    def notify(self, text: str) -> bool: ...


class NullNotifier:
    """No-op notifier used when Telegram is not configured."""

    def notify(self, text: str) -> bool:
        del text
        return False


class TelegramNotifier:
    """Delivers alerts via the Telegram Bot API. Never raises on transport failure."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        api_base: str = TELEGRAM_API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._api_base = api_base
        self._timeout = timeout

    def notify(self, text: str) -> bool:
        if not 1 <= len(text) <= MAX_MESSAGE_LEN:
            print(
                f"alerts: refusing to send message of length {len(text)} (must be 1..{MAX_MESSAGE_LEN})",
                file=sys.stderr,
            )
            return False
        url = f"{self._api_base}/bot{self._token}/sendMessage"
        try:
            resp = httpx.post(
                url, json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return bool(resp.json().get("ok", False))
        except (httpx.HTTPError, ValueError) as exc:
            print(f"alerts: Telegram send failed: {exc}", file=sys.stderr)
            return False


def build_notifier() -> Notifier:
    """TelegramNotifier when TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID are set
    (``.env``), else a NullNotifier -- alerts are always logged to stdout/
    stderr by callers regardless, this is purely the out-of-band push."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return TelegramNotifier(token, chat_id)
    return NullNotifier()


# ---- Alert-type formatters (CPD-1 §A4's five trigger types) ----

def format_signal_flip(ticket_human_texts: list[str], as_of: str) -> str:
    lines = [f"\U0001f4c8 <b>CPD-1 signal update {html.escape(as_of)}</b>"]
    for t in ticket_human_texts:
        lines.append(html.escape(t))
    return "\n".join(lines)


def format_funding_review(ticket_human_text: str) -> str:
    return f"⚠️ <b>CPD-1 funding REVIEW</b>\n{html.escape(ticket_human_text)}"


def format_missed_run(strategy: str, last_effective_as_of: str, days_stale: int) -> str:
    return (
        f"\U0001f6a8 <b>CPD-1 missed/stale run</b>\n"
        f"{html.escape(strategy)}: last signal is {days_stale} day(s) stale "
        f"(last bar {html.escape(last_effective_as_of)})"
    )


def format_drawdown_alert(level_pct: float, current_dd_pct: float, action: str) -> str:
    return (
        f"\U0001f6a8 <b>CPD-1 drawdown alert</b>\n"
        f"Drawdown {current_dd_pct:.1f}% crossed the {level_pct:.0f}% tripwire.\n"
        f"Action: {html.escape(action)}"
    )


def format_single_day_loss_alert(loss_pct: float) -> str:
    return (
        f"\U0001f6a8 <b>CPD-1 single-day loss alert</b>\n"
        f"{loss_pct:.1f}% loss in one day (≥6σ tripwire). "
        f"Verify data/fills before any new order."
    )


def format_data_integrity_alert(strategy: str, error_message: str) -> str:
    return (
        f"\U0001f6a8 <b>CPD-1 DATA INTEGRITY failure</b>\n"
        f"{html.escape(strategy)}: {html.escape(error_message)}\n"
        f"No signal state written, no tickets built. Re-run after the data "
        f"source recovers; do not trade on the previous day's tickets."
    )


def format_tracking_error_summary(cumulative_divergence_pct: float, quarter_tolerance_pct: float = 3.0) -> str:
    status = "HALT new entries" if cumulative_divergence_pct > quarter_tolerance_pct else "within tolerance"
    return (
        f"\U0001f4ca <b>CPD-1 weekly tracking-error report</b>\n"
        f"Cumulative divergence this quarter: {cumulative_divergence_pct:.2f}% of equity "
        f"(tolerance {quarter_tolerance_pct:.1f}%) -- {status}"
    )


def format_sleeve_drift_alert(
    crypto_share_pct: float, target_crypto_share_pct: float, drift_pp: float
) -> str:
    return (
        f"⚖️ <b>CPD-1 sleeve drift</b>\n"
        f"Crypto sleeve is {crypto_share_pct:.1f}% of account vs target "
        f"{target_crypto_share_pct:.1f}% ({drift_pp:+.1f}pp, >5pp tripwire) -- "
        f"rebalance sleeves per the CPD-1 monthly/5pp rule."
    )


def format_daily_summary(
    *,
    as_of: str,
    profile_name: str,
    mode: str,
    ticket_lines: list[str],
    sleeve_equities: dict[str, float],
    fired_checks: list[str],
) -> str:
    lines = [f"\U0001f5d3 <b>CPD-1 daily cycle {html.escape(as_of)}</b> "
             f"[{html.escape(profile_name)}/{html.escape(mode)}]"]
    if ticket_lines:
        lines.append("Tickets:")
        lines.extend(html.escape(t) for t in ticket_lines)
    else:
        lines.append("No tickets today (no direction changes).")
    equity_bits = ", ".join(f"{s}: ${v:,.0f}" for s, v in sleeve_equities.items())
    if equity_bits:
        lines.append(f"Marked equity -- {equity_bits}")
    if fired_checks:
        lines.append("⚠️ Checks fired: " + ", ".join(html.escape(c) for c in fired_checks))
    return "\n".join(lines)
