"""Mode A strategy (plan §3 Mode A, §6 Phase 3): executes a precomputed
`OptionLegPlan` ledger. No selection logic runs inside the strategy --
selection already happened offline in `leg_planner.py`. On each incoming
QuoteTick, the strategy checks whether `(instrument_id, ts_event)` matches a
pending action from the plan:

- entry timestamp -> submit a market BUY for the leg's quantity (the
  catalog's QuoteTick ask at that exact timestamp equals Vibe's
  `ask_per_unit`, so a marketable buy fills at Vibe's exact entry price).
- flip-exit timestamp -> submit a market SELL for the same quantity
  (closes the position; the catalog's bid at that timestamp equals Vibe's
  `exit_val` per-unit price).

Expiry exits need no order at all -- native cash settlement (plan §2.6)
closes the position automatically. NOTE (Phase 3 finding, see
`postprocess.py`'s module docstring): the venue's `settlement_prices`
override does NOT reach the automatic-expiry path in
nautilus_trader==2.0.0rc1, so the settlement fill price is Nautilus's own
strike-precision-rounded intrinsic; `postprocess.attribute_run` substitutes
the leg planner's exact `intrinsic_per_unit` for expiry legs instead.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Self

from nautilus_trader.model import InstrumentId, OrderSide, QuoteTick, Quantity
from nautilus_trader.trading import Strategy, StrategyConfig

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import SIZE_PRECISION, VENUE_NAME  # noqa: E402


class PlanExecutorConfig(StrategyConfig):
    """`legs` is a list of plain dicts (JSON-serializable for
    ImportableStrategyConfig): instrument_name, entry_ts_ns, quantity,
    exit_kind ("flip"|"expiry"), exit_ts_ns. Follows the same
    pop-custom-fields-in-__new__ pattern as Nautilus's own
    `examples/backtest/tardis_option_chain.py::OptionChainBacktestConfig`,
    since v2's `StrategyConfig` is a plain pyo3 class (positional __init__
    over strategy_id/order_id_tag/... internals), not a msgspec Struct."""

    _CUSTOM_FIELDS = ("legs",)

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        for key in cls._CUSTOM_FIELDS:
            kwargs.pop(key, None)
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, legs: list[dict] = (), **kwargs: Any) -> None:
        super().__init__()
        self.legs = list(legs)


class PlanExecutor(Strategy):
    def __init__(self, config: PlanExecutorConfig) -> None:
        super().__init__(config)
        self._legs = list(config.legs)
        # (instrument_id_str, ts_event_ns) -> ("entry"|"exit", quantity)
        self._actions: dict[tuple[str, int], tuple[str, float]] = {}
        self._instrument_ids: set[str] = set()
        for leg in self._legs:
            iid = f"{leg['instrument_name']}.{VENUE_NAME}"
            self._instrument_ids.add(iid)
            self._actions[(iid, int(leg["entry_ts_ns"]))] = ("entry", float(leg["quantity"]))
            if leg["exit_kind"] == "flip":
                self._actions[(iid, int(leg["exit_ts_ns"]))] = ("exit", float(leg["quantity"]))
        self.fills: list[dict] = []

    def on_start(self) -> None:
        for iid in self._instrument_ids:
            self.subscribe_quotes(InstrumentId.from_str(iid))

    def on_quote(self, quote: QuoteTick) -> None:
        key = (str(quote.instrument_id), quote.ts_event)
        action = self._actions.pop(key, None)
        if action is None:
            return
        kind, qty = action
        instrument = self.cache.instrument(quote.instrument_id)
        quantity = Quantity(qty, instrument.size_precision if instrument else SIZE_PRECISION)
        side = OrderSide.BUY if kind == "entry" else OrderSide.SELL
        order = self.order_factory.market(
            instrument_id=quote.instrument_id,
            order_side=side,
            quantity=quantity,
            time_in_force=None,
            reduce_only=(kind == "exit"),
        )
        self.submit_order(order)

    def on_order_filled(self, event: Any) -> None:
        self.fills.append({
            "instrument_id": str(event.instrument_id),
            "order_side": str(event.order_side),
            "last_qty": float(event.last_qty),
            "last_px": float(event.last_px),
            "commission": str(event.commission) if event.commission is not None else None,
            "ts_event": event.ts_event,
        })

    def on_stop(self) -> None:
        for iid in self._instrument_ids:
            self.unsubscribe_quotes(InstrumentId.from_str(iid))
