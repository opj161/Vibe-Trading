"""Fills -> per-run attribution, fee-mode adjustments, settlement fees (plan
§3.1, §5). Single fee code path: the venue always runs `CappedOptionFeeModel`
(charging on every fill including flip-exits); `parity` mode then removes
the flip-exit commission (Vibe charges none on signal-flip exits) and adds
Vibe's own settlement fee formula for expiry legs (Nautilus's expiry fills
carry zero commission -- confirmed both by source, plan §2.7, and by this
project's own Phase 3 fills).

**Platform limitation found and documented in Phase 3 (not silently
patched, per plan §9)**: `BacktestVenueConfig`/`BacktestEngine.add_venue`'s
`settlement_prices` override is wired only into
`SimulatedExchange::process_instrument_close` (a manually-triggered venue
close event) -- NOT into `process_instrument_expirations` /
`matching_engine.process_instrument_expiration`, which is the path that
actually fires for automatic option expiry in a backtest
(`crates/backtest/src/exchange.rs:636-645` calls
`matching_engine.process_instrument_expiration` directly, never touching
`self.settlement_prices`). Verified empirically on a real BTC and a real
SOL smoke run: with `settlement_prices` set, the expiry fill price was
still Nautilus's own strike-precision-rounded intrinsic
(`option_settlement_price`, `engine.rs:2395-2408`, which rounds to the
option's STRIKE price precision -- 2dp in this project -- not the option's
own quote precision), not the override. Consequence: expiry-leg fill
prices from Nautilus differ from Vibe's own intrinsic by strike-precision
rounding (a few cents on price, translating to single-digit-to-low-tens of
dollars on a leg's notional -- confirmed small relative to Gate 4's
±$500/±0.5% tolerance, but NOT bit-exact the way entry fills and flip-exit
fills are). Fix used here: for expiry legs, `attribute_run` uses the leg
planner's own precomputed `intrinsic_per_unit` (already Gate-2-verified to
floating-point-noise precision against the frozen Vibe targets) as the
settlement value, rather than trusting the Nautilus fill price for that one
leg type. Entry fills and flip-exit fills use the REAL Nautilus fill
price/qty/commission throughout (both confirmed bit-exact in Phase 3).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import OPT_FEE_CAP, SETTLE_FEE_RATE  # noqa: E402
from leg_planner import OptionLegPlan  # noqa: E402


@dataclass
class LegAttribution:
    instrument_id: str
    leg_index: int
    exit_kind: str
    entry_fill_px: float
    entry_fill_qty: float
    entry_commission: float
    exit_fill_px: Optional[float]  # None for expiry legs (uses intrinsic_per_unit instead)
    exit_commission_raw: float  # as charged by the venue (0 for expiry, >0 for flip under `native`)
    settlement_value_per_unit: float  # intrinsic_per_unit (expiry) or exit_fill_px*(1) (flip)
    pnl_parity: float
    pnl_native: float


def _fills_for_instrument(fills: list[dict], instrument_id: str) -> list[dict]:
    return [f for f in fills if f["instrument_id"] == instrument_id]


def attribute_leg(leg: OptionLegPlan, fills: list[dict], underlying_end_price: float) -> LegAttribution:
    """Build a `LegAttribution` for one leg from the strategy's raw fills
    ledger (`PlanExecutor.fills`, plan §3.1's `RunAttribution` superset).
    `fills` must already be filtered/sorted to this leg's instrument."""
    leg_fills = sorted(_fills_for_instrument(fills, f"{leg.instrument_id}.DERIBIT"), key=lambda f: f["ts_event"])
    buys = [f for f in leg_fills if f["order_side"] == "BUY"]
    sells = [f for f in leg_fills if f["order_side"] == "SELL"]
    if not buys:
        raise ValueError(f"no entry fill found for leg {leg.instrument_id}#{leg.leg_index}")
    entry = buys[0]
    entry_commission = float(entry["commission"].split()[0]) if entry["commission"] else 0.0

    if leg.exit_kind == "expiry":
        settlement_value = leg.intrinsic_per_unit
        exit_fill_px = None
        exit_commission_raw = 0.0
        settle_fee = min(SETTLE_FEE_RATE * underlying_end_price * leg.quantity, OPT_FEE_CAP * max(settlement_value * leg.quantity, 1e-9))
    else:
        if not sells:
            raise ValueError(f"no exit fill found for flip leg {leg.instrument_id}#{leg.leg_index}")
        exit_ = sells[0]
        exit_fill_px = exit_["last_px"]
        settlement_value = exit_fill_px
        exit_commission_raw = float(exit_["commission"].split()[0]) if exit_["commission"] else 0.0
        settle_fee = 0.0

    exit_val = settlement_value * leg.quantity - (settle_fee if leg.exit_kind == "expiry" else 0.0)
    entry_cost = entry["last_px"] * leg.quantity

    pnl_parity = exit_val - entry_cost - entry_commission
    # Native mode (plan §5): venue commission retained on every fill AND the
    # settlement fee still applies on expiry legs (Nautilus's expiry fill
    # carries zero commission, so the fee is added here in both modes --
    # `exit_val` already includes it for expiry legs). Audit fix 2026-07-02:
    # the original expression used `settlement_value * quantity` directly,
    # silently DROPPING the settlement fee from native mode -- making
    # "native" less conservative than "parity" on expiry legs, backwards
    # from the plan's intent.
    pnl_native = exit_val - exit_commission_raw - entry_cost - entry_commission

    return LegAttribution(
        instrument_id=leg.instrument_id,
        leg_index=leg.leg_index,
        exit_kind=leg.exit_kind,
        entry_fill_px=entry["last_px"],
        entry_fill_qty=entry["last_qty"],
        entry_commission=entry_commission,
        exit_fill_px=exit_fill_px,
        exit_commission_raw=exit_commission_raw,
        settlement_value_per_unit=settlement_value,
        pnl_parity=pnl_parity,
        pnl_native=pnl_native,
    )


def attribute_run(legs: list[OptionLegPlan], fills: list[dict], idx, run) -> dict:
    """Sum leg attributions for one (run, track). `idx` is the daily-index
    Series (for the expiry-leg settlement fee's `underlying_end_price`)."""
    attributions = []
    for leg in legs:
        S_end = float(idx.loc[leg.exit_ts]) if leg.exit_kind == "expiry" else 0.0
        attributions.append(attribute_leg(leg, fills, S_end))
    return {
        "run_id": run.run_id,
        "legs": attributions,
        "pnl_parity_total": sum(a.pnl_parity for a in attributions),
        "pnl_native_total": sum(a.pnl_native for a in attributions),
    }
