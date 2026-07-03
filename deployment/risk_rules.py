"""Pre-registered risk tripwires (CPD-1 §A5), as pure functions over the
ledger's equity_snapshots.csv -- independently unit-testable, alerting
through deployment/alerts.py. These are review tripwires, not strategy stops:
the composite's own drawdowns are expected and survivable (bootstrap median
maxDD -18%, per vibe_trading_fresh_assessment_20260703.md §8.4) -- crossing a
threshold means "a human looks at this," not "the strategy is broken."
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from deployment import alerts, ledger

# CPD-1 §A5, verbatim thresholds.
HWM_DRAWDOWN_WARN = -0.15
HWM_DRAWDOWN_CLOSE_ONLY = -0.20
SINGLE_DAY_LOSS_THRESHOLD = -0.06  # ~6 sigma
# signal_runner.py's own STALE_THRESHOLD_DAYS (4) is a shared, generous
# threshold across both sleeves for visibility only. Crypto trades 24/7, so a
# missed-run alert should fire much sooner than that for the crypto sleeve
# specifically -- this is the tighter, alertable check.
CRYPTO_MISSED_RUN_DAYS = 1
MACRO_MISSED_RUN_DAYS = 4  # weekends/holidays routinely produce 3-4 day gaps
QUARTER_TRACKING_ERROR_TOLERANCE_PCT = 3.0
RECONCILIATION_REMINDER_DAYS = 7


def total_equity_series() -> pd.Series:
    """Total account equity (all sleeves/venues summed) per snapshot date,
    sorted ascending. Empty series if no snapshots exist yet."""
    df = ledger.read_equity_snapshots()
    if df.empty:
        return pd.Series(dtype=float)
    by_date = df.groupby("date")["balance_usd"].sum().sort_index()
    by_date.index = pd.to_datetime(by_date.index)
    return by_date


def check_drawdown(equity: pd.Series) -> Optional[dict]:
    """Return the WORSE of the two tripwires currently crossed (close-only
    dominates warn), or None if neither is crossed / too little history."""
    if len(equity) < 2:
        return None
    hwm = equity.cummax()
    dd = (equity / hwm - 1.0)
    current_dd = float(dd.iloc[-1])
    if current_dd <= HWM_DRAWDOWN_CLOSE_ONLY:
        return {"level": HWM_DRAWDOWN_CLOSE_ONLY, "current_dd": current_dd, "action": "close-only mode until human review is logged"}
    if current_dd <= HWM_DRAWDOWN_WARN:
        return {"level": HWM_DRAWDOWN_WARN, "current_dd": current_dd, "action": "reduce new-entry size 50%"}
    return None


def check_single_day_loss(equity: pd.Series) -> Optional[dict]:
    if len(equity) < 2:
        return None
    daily_ret = float(equity.iloc[-1] / equity.iloc[-2] - 1.0)
    if daily_ret <= SINGLE_DAY_LOSS_THRESHOLD:
        return {"loss_pct": daily_ret * 100}
    return None


def check_missed_run(strategy: str, sleeve: str, effective_as_of: str, as_of: str) -> Optional[dict]:
    threshold = CRYPTO_MISSED_RUN_DAYS if sleeve == "crypto" else MACRO_MISSED_RUN_DAYS
    days_stale = (pd.Timestamp(as_of).date() - pd.Timestamp(effective_as_of).date()).days
    if days_stale > threshold:
        return {"strategy": strategy, "days_stale": days_stale, "last_effective_as_of": effective_as_of}
    return None


def check_reconciliation_due() -> Optional[dict]:
    """A reminder, not a real balance-vs-ledger match check (that needs live
    venue balances this deployment layer doesn't poll) -- fires when no
    equity snapshot has been recorded in >= RECONCILIATION_REMINDER_DAYS."""
    df = ledger.read_equity_snapshots()
    if df.empty:
        return {"days_since_last": None}
    last_date = pd.Timestamp(df["date"].max())
    days_since = (pd.Timestamp.now().normalize() - last_date).days
    if days_since >= RECONCILIATION_REMINDER_DAYS:
        return {"days_since_last": days_since}
    return None


def check_tracking_error(cumulative_divergence_pct: float) -> Optional[dict]:
    if cumulative_divergence_pct > QUARTER_TRACKING_ERROR_TOLERANCE_PCT:
        return {"cumulative_divergence_pct": cumulative_divergence_pct, "halt": True}
    return None


def run_risk_checks(signal_state: dict, *, notifier: Optional[alerts.Notifier] = None) -> list[dict]:
    """Run every tripwire against current ledger state + this signal run,
    send an alert for each one that fires, and return the fired list (for
    logging/testing -- callers should not re-derive what fired)."""
    notifier = notifier or alerts.build_notifier()
    fired: list[dict] = []

    equity = total_equity_series()
    dd = check_drawdown(equity)
    if dd is not None:
        notifier.notify(alerts.format_drawdown_alert(dd["level"] * 100, dd["current_dd"] * 100, dd["action"]))
        fired.append({"type": "drawdown", **dd})

    loss = check_single_day_loss(equity)
    if loss is not None:
        notifier.notify(alerts.format_single_day_loss_alert(loss["loss_pct"]))
        fired.append({"type": "single_day_loss", **loss})

    from deployment.order_tickets import STRATEGY_SLEEVE

    as_of = signal_state["as_of_date"]
    for strategy, info in signal_state["strategies"].items():
        sleeve = STRATEGY_SLEEVE.get(strategy, "crypto")
        missed = check_missed_run(strategy, sleeve, info["effective_as_of"], as_of)
        if missed is not None:
            notifier.notify(alerts.format_missed_run(strategy, missed["last_effective_as_of"], missed["days_stale"]))
            fired.append({"type": "missed_run", **missed})

    reconciliation = check_reconciliation_due()
    if reconciliation is not None:
        notifier.notify(
            "\U0001f501 <b>CPD-1 reconciliation due</b>\nNo equity snapshot recorded in "
            f"{reconciliation['days_since_last']} day(s) -- confirm venue balances match the ledger."
        )
        fired.append({"type": "reconciliation_due", **reconciliation})

    return fired
