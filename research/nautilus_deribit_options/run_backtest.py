"""Mode A BacktestNode wiring (plan §3 Mode A, §6 Phase 3/4). Builds the
synthetic catalog for one (run, track) leg chain, wires a `BacktestEngine`
directly (simpler and more debuggable than `BacktestNode` +
`ImportableStrategyConfig` for this project's needs -- `BacktestEngine`
exposes `.cache`/`.portfolio` post-run and accepts a live `PlanExecutor`
strategy instance via `add_strategy()`, so no config-serialization step is
needed), and runs the `PlanExecutor` strategy against it.

Always uses `CappedOptionFeeModel` (plan §5's "single fee code path" --
parity/native/stress fee-mode adjustments happen in `postprocess.py` from
the resulting fills ledger, not via multiple engine configs).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.execution import CappedOptionFeeModel
from nautilus_trader.model import AccountType, BookType, Currency, Money, OmsType, TraderId, Venue

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from catalog_parity import EXIT_QUOTE_OFFSET, build_mode_a_catalog  # noqa: E402
from config import VENUE_NAME  # noqa: E402
from leg_planner import OptionLegPlan, RunTrackResult  # noqa: E402
from strategy_plan import PlanExecutor, PlanExecutorConfig  # noqa: E402


@dataclass
class ModeARunResult:
    engine: BacktestEngine
    strategy: PlanExecutor
    legs: list[OptionLegPlan]


def _ns(ts: pd.Timestamp) -> int:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.value)


def run_mode_a(
    catalog_path: Path,
    underlying: str,
    track_result: RunTrackResult,
    idx: pd.Series,
    half_spread: float,
    starting_balance_usdc: float = 10_000_000.0,
) -> ModeARunResult:
    legs = track_result.legs
    if not legs:
        raise ValueError("no legs to run -- track_result has no entries")

    build = build_mode_a_catalog(catalog_path, underlying, legs, track_result.marks, idx, half_spread)

    venue = Venue(VENUE_NAME)
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId("MODEA-001"),
        run_analysis=False,
    ))
    engine.add_venue(
        venue=venue,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(starting_balance_usdc, Currency.from_str("USDC"))],
        book_type=BookType.L1_MBP,
        fee_model=CappedOptionFeeModel(maker_rate=0.0003, taker_rate=0.0003),
        settlement_prices=build.settlement_prices,
    )
    engine.add_instrument(build.index_instrument)
    for instrument in build.option_instruments.values():
        engine.add_instrument(instrument)
    engine.add_data(build.trades)
    engine.add_data(build.quotes)

    leg_dicts = [
        {
            "instrument_name": leg.instrument_id,
            "entry_ts_ns": _ns(leg.entry_ts),
            "quantity": leg.quantity,
            "exit_kind": leg.exit_kind,
            "exit_ts_ns": _ns(leg.exit_ts + EXIT_QUOTE_OFFSET) if leg.exit_kind == "flip" else 0,
        }
        for leg in legs
    ]
    strategy = PlanExecutor(PlanExecutorConfig(legs=leg_dicts))
    engine.add_strategy(strategy)
    engine.run()

    return ModeARunResult(engine=engine, strategy=strategy, legs=legs)
