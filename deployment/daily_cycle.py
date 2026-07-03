"""``python -m deployment.daily_cycle`` -- the ONE command a scheduler (or a
human) runs per day. Orchestrates, in order:

1. signals for the active profile's deployed + shadow strategies (each behind
   the data-integrity gate; a failed strategy alerts and keeps yesterday's
   state, per signal_runner's merge-preserving convention);
2. order tickets for the deployed strategies (direction flips + one-shot
   resizes), merged into the day's ticket file without clobbering anything
   already confirmed;
3. optional ``--auto-paper``: pending tickets are recorded as hypothetical
   paper fills at the observed reference price + the modeled taker fee
   (REVIEW tickets are auto-SKIPPED with an alert -- never auto-executed;
   idempotent via ledger.has_confirmation, so a rerun cannot double-fill);
4. funding re-check on OPEN perp shorts (the entry-time check alone misses a
   funding regime flip during a median ~10-13 day hold);
5. sleeve marking from public prices -> ``equity_marks.csv`` (the daily risk
   series the drawdown/single-day-loss tripwires need);
6. risk checks (incl. the >5pp sleeve-drift rule) + Telegram daily summary.

Exit codes: 0 clean; 2 at least one strategy failed its signal run; 3 sleeve
equity unconfigured (seed ``equity_snapshots.csv`` first). Failures in later
stages alert + print but do not mask an earlier stage's exit code.

Design note on ``--auto-paper``: CPD-1 §B framed paper mode as a human daily
ritual. The hardening decision (2026-07-03, findings §85) automates the paper
fills because the thing being validated for go-live is the SCHEDULED pipeline
(the go-live gate demands zero missed daily runs), and the human process gets
its own live shakedown at 50% size in Phase 4 regardless. A human can still
confirm/correct any ticket manually with ``python -m deployment.confirm``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from typing import Optional

from deployment import alerts, ledger, marking, order_tickets, profiles, risk_rules, venue_specs
from deployment import signal_runner
from deployment import tickets as tickets_mod
from deployment.data_integrity import DataIntegrityError
from deployment.order_tickets import SleeveEquityUnconfiguredError
from deployment.tickets import Ticket

# The frozen ZA4 config's OKX daily bar closes at 16:00 UTC; a cycle run
# before that reads yesterday's bar and quietly trades one day late.
CRYPTO_BAR_CLOSE_UTC_HOUR = 16


def run_signals(profile: profiles.Profile, as_of: Optional[str], *,
                write_audit_trail: bool, notifier: alerts.Notifier) -> tuple[Optional[dict], list[str]]:
    """Run every profile strategy through signal_runner; returns (merged
    signal-state dict or None, failed strategy names). Mirrors
    signal_runner.main()'s behavior, reused as a library."""
    states, failed = [], []
    for name in profile.all_strategies:
        try:
            states.append(signal_runner.run_signal(name, as_of, write_audit_trail=write_audit_trail))
        except DataIntegrityError as exc:
            failed.append(name)
            notifier.notify(alerts.format_data_integrity_alert(name, str(exc)))
            print(f"[daily_cycle] DATA INTEGRITY FAILURE {name}: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - one strategy's fetch hiccup must not kill the cycle
            failed.append(name)
            notifier.notify(alerts.format_data_integrity_alert(name, f"signal run failed: {exc}"))
            print(f"[daily_cycle] SIGNAL FAILURE {name}: {exc}", file=sys.stderr)
    if not states:
        return None, failed
    merged = signal_runner.merge_states(states)
    signal_runner.write_state(merged)
    return merged.to_json_dict(), failed


def merge_day_tickets(as_of: str, new_tickets: list[Ticket], *, paper: Optional[bool]) -> list[Ticket]:
    """Union today's existing ticket file with newly built tickets, keyed by
    ticket_id. An already-confirmed/skipped ticket keeps its original row (it
    was the basis of a recorded action); an unconfirmed one is replaced by
    the fresh build (a rerun after a data fix may legitimately resize it)."""
    existing = {t.ticket_id: t for t in tickets_mod.read_tickets(as_of)}
    for t in new_tickets:
        old = existing.get(t.ticket_id)
        if old is not None and ledger.has_confirmation(t.ticket_id, paper=paper):
            continue
        existing[t.ticket_id] = t
    merged = list(existing.values())
    tickets_mod.write_tickets(as_of, merged)
    return merged


def auto_paper_fill(ticket: Ticket, *, notifier: alerts.Notifier) -> Optional[str]:
    """Record one pending ticket as a hypothetical PAPER fill (or skip).
    Returns a short outcome string for the summary, or None if nothing was
    recorded."""
    if ledger.has_confirmation(ticket.ticket_id, paper=True):
        return None
    if ticket.side == "skip" or ticket.status == "review":
        reason = ("auto-paper: REVIEW ticket held for human decision"
                  if ticket.status == "review" else f"auto-paper: {ticket.reason}")
        ledger.append_ledger_row(
            ticket_id=ticket.ticket_id, symbol=ticket.symbol, venue=ticket.venue,
            side=ticket.side, status="skipped", reason=reason, paper=True,
        )
        if ticket.status == "review":
            notifier.notify(alerts.format_funding_review(ticket.human_text))
        return f"SKIP {ticket.ticket_id}"

    if ticket.qty <= 0:
        return None
    if ticket.notional_usd > 0:
        price = ticket.notional_usd / ticket.qty
    else:
        # Close/resize tickets carry no notional -- mark at the current price.
        price = marking.fetch_mark_price(ticket.symbol, ticket.venue)
    if price is None or price <= 0:
        notifier.notify(alerts.format_data_integrity_alert(
            ticket.strategy, f"auto-paper: no price for {ticket.symbol}@{ticket.venue}; "
                             f"ticket {ticket.ticket_id} left pending"))
        return None
    fee = venue_specs.PAPER_FEE_RATES.get(ticket.venue, 0.001) * price * ticket.qty
    ledger.append_ledger_row(
        ticket_id=ticket.ticket_id, symbol=ticket.symbol, venue=ticket.venue,
        side=ticket.side, status="confirmed", qty=ticket.qty, price=price,
        fee=fee, reason=f"auto-paper: {ticket.reason}", paper=True,
    )
    return f"{ticket.side.upper()} {ticket.qty:g} {ticket.symbol} @ {price:,.2f}"


def check_open_short_funding(*, paper: Optional[bool], notifier: alerts.Notifier) -> list[dict]:
    """Daily funding re-check on open perp shorts -- entry-time checks miss a
    regime flip mid-hold. Same threshold and REVIEW semantics as the ticket
    builder's entry check."""
    fired = []
    for (symbol, venue), qty in ledger.open_positions(paper=paper).items():
        if venue != "binance_usdtm" or qty >= 0:
            continue
        funding = venue_specs.binance_futures_funding_annualized(symbol)
        if funding is None:
            continue
        cost_to_short = -funding
        if cost_to_short > venue_specs.FUNDING_REVIEW_THRESHOLD_ANNUAL:
            text = (f"open short {symbol} ({qty:g}) now pays {cost_to_short * 100:.1f}%/yr "
                    f"funding (threshold {venue_specs.FUNDING_REVIEW_THRESHOLD_ANNUAL * 100:.0f}%) "
                    f"-- review whether to keep the leg on")
            notifier.notify(alerts.format_funding_review(text))
            fired.append({"symbol": symbol, "cost_to_short_annual": cost_to_short})
    return fired


def mark_sleeves(profile: profiles.Profile, as_of: str, *, paper: bool) -> Optional[dict]:
    """Value each profile sleeve from public marks and append today's rows to
    the marks series. None (with a stderr note) when no anchor snapshot
    exists yet -- marking before the seed would just record zeros."""
    anchor = ledger.sleeve_equity_asof(as_of)
    if anchor["anchor_date"] is None:
        print("[daily_cycle] no equity snapshot yet -- skipping marking "
              "(seed equity_snapshots.csv to start the paper clock)", file=sys.stderr)
        return None
    positions = ledger.open_positions(paper=paper)
    marks = marking.fetch_mark_prices(positions)
    sleeve_equities: dict[str, float] = {}
    for sleeve in sorted({a.sleeve for a in profile.allocations.values()}):
        valuation = marking.value_sleeve(sleeve, paper=paper, mark_prices=marks, anchor_date=as_of)
        sleeve_equities[sleeve] = valuation["equity"]
        for pair in valuation["unmarked"]:
            print(f"[daily_cycle] WARNING: unmarked open position {pair}", file=sys.stderr)
    marking.append_marks(date=as_of, mode_paper=paper, sleeve_equities=sleeve_equities)
    return sleeve_equities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--profile", default=None,
                        help=f"Deployment profile (default: {profiles.DEPLOYED_PROFILE_NAME})")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--auto-paper", action="store_true",
                        help="Record pending tickets as hypothetical paper fills (paper mode only)")
    parser.add_argument("--no-audit-trail", action="store_true",
                        help="Skip the subprocess backtest runs (faster; tracking report "
                             "needs the audit trail, so only use for debugging)")
    args = parser.parse_args()
    if args.auto_paper and args.mode != "paper":
        parser.error("--auto-paper requires --mode paper")

    profile = profiles.PROFILES[args.profile] if args.profile else profiles.active_profile()
    paper = args.mode == "paper"
    as_of = args.as_of or dt.datetime.now(dt.timezone.utc).date().isoformat()
    notifier = alerts.build_notifier()

    now_utc = dt.datetime.now(dt.timezone.utc)
    if args.as_of is None and now_utc.hour < CRYPTO_BAR_CLOSE_UTC_HOUR:
        print(f"[daily_cycle] WARNING: running before {CRYPTO_BAR_CLOSE_UTC_HOUR}:00 UTC -- "
              f"the crypto daily bar hasn't closed; the ZA4 signal will be one bar stale",
              file=sys.stderr)

    # 1. Signals (deployed + shadow), integrity-gated.
    state, failed = run_signals(profile, args.as_of,
                                write_audit_trail=not args.no_audit_trail, notifier=notifier)
    if state is None:
        print("[daily_cycle] every strategy failed -- no state, no tickets", file=sys.stderr)
        sys.exit(2)

    # 2. Tickets (flips + one-shot resizes), merged into today's file.
    try:
        built = order_tickets.build_tickets(state, profile=profile, paper=paper)
    except SleeveEquityUnconfiguredError as exc:
        notifier.notify(f"🛑 <b>CPD-1 daily cycle blocked</b>\n{exc}")
        print(f"[daily_cycle] {exc}", file=sys.stderr)
        sys.exit(3)
    built.extend(order_tickets.resize_tickets(profile=profile, as_of=as_of, paper=paper))
    day_tickets = merge_day_tickets(state["as_of_date"], built, paper=paper)
    new_pending = [t for t in built if not ledger.has_confirmation(t.ticket_id, paper=paper)]
    if new_pending:
        notifier.notify(alerts.format_signal_flip([t.human_text for t in new_pending],
                                                  state["as_of_date"]))

    # 3. Auto-paper fills (idempotent).
    fills = []
    if args.auto_paper:
        for t in new_pending:
            outcome = auto_paper_fill(t, notifier=notifier)
            if outcome:
                fills.append(outcome)

    # 4. Funding re-check on open shorts.
    funding_fired = check_open_short_funding(paper=paper, notifier=notifier)

    # 5. Sleeve marking -> daily risk series.
    sleeve_equities = mark_sleeves(profile, as_of, paper=paper)

    # 6. Risk checks + daily summary.
    risk_fired = risk_rules.run_risk_checks(
        state, notifier=notifier, profile=profile,
        sleeve_equities=sleeve_equities, mode_paper=paper,
    )
    fired_names = [f["type"] for f in risk_fired] + (["open_short_funding"] if funding_fired else [])
    ticket_lines = [t.human_text for t in new_pending] or [f"(fills: {f})" for f in fills]
    notifier.notify(alerts.format_daily_summary(
        as_of=state["as_of_date"], profile_name=profile.name, mode=args.mode,
        ticket_lines=ticket_lines, sleeve_equities=sleeve_equities or {},
        fired_checks=fired_names,
    ))

    print(json.dumps({
        "as_of": state["as_of_date"], "profile": profile.name, "mode": args.mode,
        "signal_failures": failed,
        "tickets_today": [t.ticket_id for t in day_tickets],
        "new_pending": [t.ticket_id for t in new_pending],
        "auto_paper_fills": fills,
        "sleeve_equities": sleeve_equities,
        "risk_checks_fired": fired_names,
    }, indent=2))
    sys.exit(2 if failed else 0)


if __name__ == "__main__":
    main()
