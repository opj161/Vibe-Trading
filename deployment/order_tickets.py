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

import logging
from typing import Optional

from deployment import ledger, venue_specs
from deployment.tickets import Ticket, make_ticket_id

logger = logging.getLogger(__name__)

SLEEVE_WEIGHTS = {"crypto": 0.30, "macro": 0.70}
STRATEGY_SLEEVE = {"ZA4": "crypto", "M1": "macro"}
_DIRNAME = {1: "long", -1: "short", 0: "flat"}

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


def _crypto_tickets(strategy: str, symbol: str, as_of: str, direction: int, weight: float, sleeve_equity: float, leverage: float) -> list[Ticket]:
    current_venue, current_qty = ledger.current_position_any_venue(symbol, CRYPTO_VENUES)
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


def _macro_tickets(strategy: str, symbol: str, as_of: str, direction: int, weight: float, sleeve_equity: float, leverage: float) -> list[Ticket]:
    venue = "ibkr_ucits"
    current_qty = ledger.current_position(symbol, venue)
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
    crypto_equity: Optional[float] = None,
    macro_equity: Optional[float] = None,
    leverage: float = 1.0,
) -> list[Ticket]:
    """Build today's tickets from a SignalState dict (``.to_json_dict()``
    output or the loaded JSON). Sleeve equity defaults to the ledger's latest
    confirmed snapshot (``ledger.latest_sleeve_equity()``) if not given."""
    if crypto_equity is None or macro_equity is None:
        latest = ledger.latest_sleeve_equity()
        crypto_equity = latest["crypto_equity"] if crypto_equity is None else crypto_equity
        macro_equity = latest["macro_equity"] if macro_equity is None else macro_equity

    as_of = signal_state["as_of_date"]
    tickets: list[Ticket] = []
    for strategy, info in signal_state["strategies"].items():
        sleeve = STRATEGY_SLEEVE.get(strategy)
        if sleeve is None:
            logger.warning("build_tickets: unknown strategy %r, skipping", strategy)
            continue
        sleeve_equity = crypto_equity if sleeve == "crypto" else macro_equity
        builder = _crypto_tickets if sleeve == "crypto" else _macro_tickets
        for symbol, target in info["targets"].items():
            tickets.extend(
                builder(strategy, symbol, as_of, target["direction"], target["target_weight"], sleeve_equity, leverage)
            )
    return tickets
