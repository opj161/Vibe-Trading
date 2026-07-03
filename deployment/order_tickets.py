"""Turns a SignalState (deployment/signal_runner.py) into human-readable order
tickets, per CPD-1 §A2.

Only fires a ticket on a direction change (entry-locked sizing, CLAUDE.md --
the real backtest engine never resizes mid-hold on a magnitude-only change,
so neither does this). Sizing is scoped per-strategy sleeve (30% crypto / 70%
macro, CPD-1's frozen composite split) and per-symbol weight is already
gross-normalized within its own strategy's book by
``backtest.engines.base.normalize_gross_exposure`` (applied in
signal_runner.py) -- so target_notional = |target_weight| * sleeve_equity *
leverage.

Venue-split rule (CPD-1, funding-attribution-driven): crypto longs are always
Binance spot, crypto shorts are always Binance USDT-M perps -- the same
symbol can therefore need up to two tickets on a flip (close the old leg on
its own venue, open the new leg on the other). Sub-minimum targets are a
SKIP with a reason, never a forced minimum (CLAUDE.md §8.3).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from typing import Optional

from deployment._bootstrap import FROZEN_DIR, STATE_DIR
from deployment import ledger, profiles, venue_specs
from deployment.tickets import Ticket, make_ticket_id, write_tickets

logger = logging.getLogger(__name__)

_DIRNAME = {1: "long", -1: "short", 0: "flat"}


class SleeveEquityUnconfiguredError(RuntimeError):
    """A sleeve with live targets has no configured equity. Previously this
    sized every ticket off $0 and produced a wall of misleading "rounds below
    venue min" SKIPs (2026-07-03 reassessment §3.3) -- it must fail loudly."""

CRYPTO_VENUES = ["binance_spot", "binance_usdtm"]

# CPD-1 §A2: UCITS candidates named at build time, lowest unit price /
# adequate spread preferred -- verify tradability at the user's IBKR entity
# before the first order (documented in GO_LIVE_CHECKLIST.md).
MACRO_UCITS_CANDIDATES = {
    "SPY.US": ["SPYL (SPDR, ~EUR13/sh)", "VUAA (Vanguard, ~$90/sh)"],
    "GLD.US": ["4GLD (Xetra-Gold)", "EGLN (iShares physical gold)"],
}

# IBKR fractional shares from ~$1; kept conservative.
IBKR_MIN_NOTIONAL = 5.0


def _direction_of(weight: float) -> int:
    return 1 if weight > 1e-9 else (-1 if weight < -1e-9 else 0)


def _crypto_target_venue(direction: int) -> str:
    if direction > 0:
        return "binance_spot"
    if direction < 0:
        return "binance_usdtm"
    return ""


def _close_ticket(strategy: str, symbol: str, as_of: str, venue: str, qty: float, note: str) -> Ticket:
    side = "sell" if qty > 0 else "buy"
    return Ticket(
        ticket_id=make_ticket_id(strategy, symbol, as_of) + "_close",
        strategy=strategy, symbol=symbol, venue=venue, side=side, qty=abs(qty),
        notional_usd=0.0, reason=note,
        human_text=f"{venue.upper()}: {side.upper()} {abs(qty)} {symbol} (close) -- {note}",
    )


def _skip_ticket(strategy: str, symbol: str, as_of: str, venue: str, reason: str) -> Ticket:
    return Ticket(
        ticket_id=make_ticket_id(strategy, symbol, as_of), strategy=strategy, symbol=symbol,
        venue=venue, side="skip", qty=0.0, notional_usd=0.0, reason=reason,
        human_text=f"{venue.upper() or 'N/A'}: SKIP {symbol} -- {reason}",
    )


def _crypto_open_ticket(
    strategy: str, symbol: str, as_of: str, direction: int, notional: float, flip_note: str,
) -> Ticket:
    venue = _crypto_target_venue(direction)
    price = venue_specs.binance_spot_price(symbol) if direction > 0 else venue_specs.binance_futures_price(symbol)
    if price is None or price <= 0:
        return _skip_ticket(strategy, symbol, as_of, venue, f"price unavailable; {flip_note}")

    filters = (
        venue_specs.binance_spot_filters(symbol) if direction > 0
        else venue_specs.binance_futures_filters(symbol)
    )
    raw_qty = notional / price
    qty = venue_specs.round_down_to_step(raw_qty, filters["step_size"])
    actual_notional = qty * price
    if qty <= 0 or actual_notional < filters["min_notional"]:
        return _skip_ticket(
            strategy, symbol, as_of, venue,
            f"target notional ${notional:,.2f} rounds to ${actual_notional:,.2f} < "
            f"venue min ${filters['min_notional']:,.2f}; {flip_note}",
        )

    side = "buy" if direction > 0 else "sell"
    reason = f"{flip_note}"
    status = "pending"
    if direction < 0:
        funding = venue_specs.binance_futures_funding_annualized(symbol)
        if funding is not None:
            # Positive raw funding = longs pay shorts (this session's live check
            # + CLAUDE.md's documented convention) -- a short's own benefit is
            # +funding, cost is -funding.
            cost_to_short = -funding
            favorable = cost_to_short <= 0
            reason += f"; funding check: {funding * 100:+.3f}%/yr ({'favorable' if favorable else 'unfavorable'})"
            if cost_to_short > venue_specs.FUNDING_REVIEW_THRESHOLD_ANNUAL:
                status = "review"
                reason += " -- REVIEW: exceeds +15%/yr threshold"

    verb = side.upper()
    human = f"BINANCE {'SPOT' if direction > 0 else 'USDT-M'}: {verb} {qty} {symbol.replace('-', '')} (~${actual_notional:,.0f}) -- {reason}"
    return Ticket(
        ticket_id=make_ticket_id(strategy, symbol, as_of), strategy=strategy, symbol=symbol,
        venue=venue, side=side, qty=qty, notional_usd=actual_notional, reason=reason,
        status=status, human_text=human,
    )


def _crypto_tickets(strategy: str, symbol: str, as_of: str, direction: int, weight: float, sleeve_equity: float, leverage: float, paper: Optional[bool]) -> list[Ticket]:
    current_venue, current_qty = ledger.current_position_any_venue(symbol, CRYPTO_VENUES, paper=paper)
    current_direction = _direction_of(current_qty)
    target_venue = _crypto_target_venue(direction)

    if direction == current_direction and target_venue == current_venue:
        return []  # entry-locked: no ticket for a magnitude-only change

    flip_note = f"{strategy} {symbol} flip {_DIRNAME[current_direction]}->{_DIRNAME[direction]}"
    out: list[Ticket] = []
    if current_direction != 0:
        out.append(_close_ticket(strategy, symbol, as_of, current_venue, current_qty, flip_note))
    if direction != 0:
        notional = abs(weight) * sleeve_equity * leverage
        out.append(_crypto_open_ticket(strategy, symbol, as_of, direction, notional, flip_note))
    return out


def _macro_tickets(strategy: str, symbol: str, as_of: str, direction: int, weight: float, sleeve_equity: float, leverage: float, paper: Optional[bool]) -> list[Ticket]:
    venue = "ibkr_ucits"
    current_qty = ledger.current_position(symbol, venue, paper=paper)
    current_direction = _direction_of(current_qty)
    if direction == current_direction:
        return []

    flip_note = f"{strategy} {symbol} flip {_DIRNAME[current_direction]}->{_DIRNAME[direction]}"

    if direction < 0:
        # CPD-1's venue map only names LONG UCITS proxies (§A2); shorting a
        # UCITS ETF (IBKR margin short, an inverse ETF, or holding flat) is a
        # real product/regulatory decision the plan never made -- flag, don't
        # assume (hard constraint #6). The CLOSE of any existing long is NOT
        # part of that undecided question, though -- the signal
        # unambiguously says exit the long, and stranding it open until the
        # short-expression decision lands would silently diverge from the
        # engine (audit fix 2026-07-03: the original code returned only the
        # REVIEW ticket, leaving the long in place).
        out: list[Ticket] = []
        if current_direction > 0:
            out.append(_close_ticket(strategy, symbol, as_of, venue, current_qty, flip_note))
        return out + [Ticket(
            ticket_id=make_ticket_id(strategy, symbol, as_of), strategy=strategy, symbol=symbol,
            venue=venue, side="skip", qty=0.0, notional_usd=0.0, status="review",
            reason=f"{flip_note}: M1 signal is SHORT on {symbol}, but CPD-1's venue map only "
                   f"specifies LONG UCITS proxies ({', '.join(MACRO_UCITS_CANDIDATES.get(symbol, []))}) "
                   f"-- short expression is an undecided user choice (margin short via IBKR, an "
                   f"inverse ETF, or hold flat/cash). Human must decide before executing.",
            human_text=f"IBKR: REVIEW {symbol} short -- no short-expression venue decided yet",
        )]

    out: list[Ticket] = []
    if current_direction != 0:
        out.append(_close_ticket(strategy, symbol, as_of, venue, current_qty, flip_note))

    if direction == 0:
        return out  # flat: closing (if any) is the whole story

    notional = abs(weight) * sleeve_equity * leverage
    price = venue_specs.macro_reference_price(symbol)
    candidates = ", ".join(MACRO_UCITS_CANDIDATES.get(symbol, [f"(no UCITS candidate configured for {symbol})"]))
    if price is None or price <= 0:
        out.append(_skip_ticket(strategy, symbol, as_of, venue, f"reference price unavailable; {flip_note}"))
        return out
    if notional < IBKR_MIN_NOTIONAL:
        out.append(_skip_ticket(
            strategy, symbol, as_of, venue,
            f"target notional ${notional:,.2f} < IBKR fractional floor ${IBKR_MIN_NOTIONAL}; {flip_note}",
        ))
        return out

    approx_shares = notional / price
    human = (
        f"IBKR: BUY ~${notional:,.2f} of one of [{candidates}] "
        f"(approx {approx_shares:.4f} shares @ SPY/GLD-proxy ref price ${price:,.2f}) -- {flip_note}. "
        f"Verify exact UCITS fill price/ticker at order time."
    )
    out.append(Ticket(
        ticket_id=make_ticket_id(strategy, symbol, as_of), strategy=strategy, symbol=symbol,
        venue=venue, side="buy", qty=approx_shares, notional_usd=notional, reason=flip_note,
        human_text=human,
    ))
    return out


def build_tickets(
    signal_state: dict,
    *,
    profile: Optional[profiles.Profile] = None,
    crypto_equity: Optional[float] = None,
    macro_equity: Optional[float] = None,
    leverage: float = 1.0,
    paper: Optional[bool] = None,
) -> list[Ticket]:
    """Build today's tickets from a SignalState dict (``.to_json_dict()``
    output or the loaded JSON). Sleeve equity defaults to the ledger's latest
    confirmed snapshot (``ledger.latest_sleeve_equity()``) if not given.

    Only strategies in ``profile.allocations`` produce tickets; shadow
    strategies present in the state (e.g. ZD2) are ignored here by design --
    their daily runs exist for forward-arbitration evidence, not orders.

    Args:
        paper: Scope the "current position" lookups to one ledger mode --
            the paper book and the live book are separate position sets and
            must not see each other's holdings. None (all rows) is only
            correct while exactly one mode has ever been recorded.

    Raises:
        SleeveEquityUnconfiguredError: A strategy has a nonzero target but
            its sleeve's equity is unset/zero.
    """
    profile = profile or profiles.active_profile()
    if crypto_equity is None or macro_equity is None:
        latest = ledger.latest_sleeve_equity()
        crypto_equity = latest["crypto_equity"] if crypto_equity is None else crypto_equity
        macro_equity = latest["macro_equity"] if macro_equity is None else macro_equity

    as_of = signal_state["as_of_date"]
    tickets: list[Ticket] = []
    for strategy, info in signal_state["strategies"].items():
        alloc = profile.allocations.get(strategy)
        if alloc is None:
            if strategy not in profile.shadow_strategies:
                logger.warning("build_tickets: strategy %r not in profile %r, skipping",
                               strategy, profile.name)
            continue
        sleeve_equity = crypto_equity if alloc.sleeve == "crypto" else macro_equity
        has_live_target = any(t["direction"] != 0 for t in info["targets"].values())
        if has_live_target and sleeve_equity <= 0:
            raise SleeveEquityUnconfiguredError(
                f"{strategy} ({alloc.sleeve} sleeve) has live targets but sleeve equity is "
                f"{sleeve_equity} -- seed equity_snapshots.csv (ledger.append_equity_snapshot) "
                f"or pass --crypto-equity/--macro-equity explicitly"
            )
        builder = _crypto_tickets if alloc.sleeve == "crypto" else _macro_tickets
        for symbol, target in info["targets"].items():
            tickets.extend(
                builder(strategy, symbol, as_of, target["direction"], target["target_weight"], sleeve_equity, leverage, paper)
            )
    return tickets


def resize_tickets(
    *,
    profile: Optional[profiles.Profile] = None,
    as_of: Optional[str] = None,
    paper: Optional[bool] = None,
) -> list[Ticket]:
    """One-shot resize tickets for deployed strategies whose frozen config
    sets ``one_shot_resize`` (ZD2: short entries at half size, quantity
    doubled once after ``trigger_bars`` held bars).

    Without this, the ticket layer -- which otherwise only fires on direction
    changes -- could never express ZD2 at all, silently rigging the
    ZA4-vs-ZD2 forward arbitration (2026-07-03 reassessment §3.2). Mirrors
    ``base.py::_maybe_one_shot_resize`` semantics: fires once per position
    lifetime (ledger analogue: a ``_resize`` ticket_id inside the current
    streak), only for the configured direction, at the first daily cycle
    where held days >= trigger_bars.
    """
    profile = profile or profiles.active_profile()
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date().isoformat()
    out: list[Ticket] = []
    for strategy, alloc in profile.allocations.items():
        config_path = FROZEN_DIR / strategy / "config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text())
        spec = config.get("one_shot_resize")
        if not spec:
            continue
        direction_filter = spec.get("direction", "both")
        trigger_bars = int(spec.get("trigger_bars", 10))
        multiplier = float(spec.get("multiplier", 2.0))
        if multiplier == 1.0:
            continue
        venues = CRYPTO_VENUES if alloc.sleeve == "crypto" else ["ibkr_ucits"]
        for symbol in config.get("codes", []):
            venue, qty = ledger.current_position_any_venue(symbol, venues, paper=paper)
            if abs(qty) <= 1e-12:
                continue
            pos_direction = 1 if qty > 0 else -1
            if direction_filter == "long" and pos_direction != 1:
                continue
            if direction_filter == "short" and pos_direction != -1:
                continue
            info = ledger.position_entry_info(symbol, venue, paper=paper)
            if info is None or info["resize_recorded"]:
                continue
            held_days = (
                dt.date.fromisoformat(as_of) - dt.date.fromisoformat(info["entry_date"])
            ).days
            if held_days < trigger_bars:
                continue
            # multiplier > 1 grows the position (same side as the entry);
            # < 1 shrinks it (opposite side).
            grow = multiplier > 1.0
            side = ("buy" if pos_direction > 0 else "sell") if grow else ("sell" if pos_direction > 0 else "buy")
            delta_qty = abs(qty) * abs(multiplier - 1.0)
            note = (
                f"{strategy} {symbol} one-shot resize x{multiplier:g} at {held_days}d held "
                f"(trigger {trigger_bars} bars, frozen config) -- "
                f"{'add to' if grow else 'reduce'} the open {_DIRNAME[pos_direction]}"
            )
            out.append(Ticket(
                ticket_id=make_ticket_id(strategy, symbol, as_of) + "_resize",
                strategy=strategy, symbol=symbol, venue=venue, side=side,
                qty=delta_qty, notional_usd=0.0, reason=note,
                human_text=f"{venue.upper()}: {side.upper()} {delta_qty:g} {symbol} (resize) -- {note}",
            ))
    return out


def main() -> None:
    """``python -m deployment.order_tickets`` -- build (and by default write)
    today's tickets from the latest signal state. The daily loop must be
    runnable without copy-pasting Python snippets (GO_LIVE_CHECKLIST Phase 1
    referenced this exact command before it existed -- reassessment §3.3)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(STATE_DIR / "latest.json"),
                        help="SignalState JSON (default: deployment/state/latest.json)")
    parser.add_argument("--profile", default=None,
                        help=f"Deployment profile (default: active -- {profiles.DEPLOYED_PROFILE_NAME})")
    parser.add_argument("--crypto-equity", type=float, default=None)
    parser.add_argument("--macro-equity", type=float, default=None)
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--mode", choices=["paper", "live"], default="paper",
                        help="Which ledger book the position lookups use (default: paper)")
    parser.add_argument("--no-write", action="store_true",
                        help="Print tickets without writing state/tickets_<date>.json")
    args = parser.parse_args()

    profile = profiles.PROFILES[args.profile] if args.profile else profiles.active_profile()
    state = json.loads(open(args.state).read())
    paper = args.mode == "paper"
    try:
        tickets = build_tickets(
            state, profile=profile, crypto_equity=args.crypto_equity,
            macro_equity=args.macro_equity, leverage=args.leverage, paper=paper,
        )
    except SleeveEquityUnconfiguredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(3)
    tickets.extend(resize_tickets(profile=profile, as_of=state["as_of_date"], paper=paper))

    if not args.no_write:
        out_path = write_tickets(state["as_of_date"], tickets)
        print(f"[order_tickets] wrote {out_path}", file=sys.stderr)
    if not tickets:
        print("No tickets today (no direction changes, no pending resizes).")
    for t in tickets:
        print(t.human_text)


if __name__ == "__main__":
    main()
