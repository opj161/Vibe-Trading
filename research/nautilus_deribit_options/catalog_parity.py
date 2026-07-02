"""Mode A synthetic catalog builder (plan §3 Mode A, §4.2). Builds a
ParquetDataCatalog containing only the instruments/quotes/index-trades
needed to execute a precomputed `OptionLegPlan` ledger (from
`leg_planner.py`) on a real NautilusTrader backtest venue.

Per leg: a QuoteTick at the entry print timestamp (bid/ask derived from the
REAL entry print price +/- half-spread -- the fill must equal Vibe's
`price*(1+/-hs)` exactly), one QuoteTick per subsequent UTC leg-date at a
fixed synthetic time (bid/ask from the BS-surface mark +/- hs), and for a
flip exit, one more QuoteTick at the exit timestamp (bid = mark*(1-hs)).
Expiry exits need no exit QuoteTick -- native cash settlement handles them.
The `settlement_prices` dict (built here as
{instrument_id: Price(intrinsic_per_unit)}) is still passed to the venue,
but the Phase 3 finding (see `postprocess.py`'s module docstring) is that
in nautilus_trader==2.0.0rc1 this override does NOT reach the
automatic-expiry path -- so `postprocess.attribute_run` uses the leg
planner's exact `intrinsic_per_unit` for expiry legs rather than the
Nautilus fill price.

For every leg date (not just entry/exit) a `TradeTick` is also written for
the underlying `IndexInstrument`, so the matching engine's cached `Last`
price is populated as required for option-expiry processing
(cache.price needs a TradeTick, not an IndexPriceUpdate -- plan §2.6).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from nautilus_trader.model import (
    AggressorSide,
    IndexInstrument,
    InstrumentId,
    Price,
    Quantity,
    TradeId,
)
from nautilus_trader.model import QuoteTick, TradeTick
from nautilus_trader.persistence import ParquetDataCatalog

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import BTC_UNDERLYING_SYMBOL, SIZE_PRECISION, VENUE_NAME  # noqa: E402
from instruments import build_index_instrument, build_option_instrument  # noqa: E402
from leg_planner import OptionLegPlan  # noqa: E402

SYNTH_TIME = pd.Timedelta(microseconds=1_000)  # 00:00:00.001 UTC each leg-date
EXIT_QUOTE_OFFSET = SYNTH_TIME + pd.Timedelta(microseconds=500)  # disambiguates a flip-exit tick
# from that same leg-date's own daily-mark tick (both land on `leg.exit_ts`,
# since flip-exit always happens ON the run's last leg date) -- exported so
# `run_backtest.py`'s strategy-action lookup keys use the identical timestamp.
_BIG_SIZE = Quantity(1_000_000, SIZE_PRECISION)


def _ns(ts: pd.Timestamp) -> int:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.value)


@dataclass(frozen=True)
class CatalogBuildResult:
    catalog: ParquetDataCatalog
    option_instruments: dict[str, object]  # instrument_name -> CryptoOption
    index_instrument: IndexInstrument
    settlement_prices: dict[InstrumentId, Price]  # for BacktestVenueConfig(settlement_prices=...)
    quotes: list[QuoteTick]  # also returned in-memory (BacktestEngine.add_data doesn't need a catalog read-back)
    trades: list[TradeTick]


def build_mode_a_catalog(
    catalog_path: Path,
    underlying: str,
    legs: list[OptionLegPlan],
    leg_daily_pnl: dict[tuple[str, int], pd.Series],  # (instrument_name, leg_index) -> per-unit mark Series (index=leg_dates)
    idx: pd.Series,
    half_spread: float,
) -> CatalogBuildResult:
    catalog_path = Path(catalog_path)
    catalog_path.mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(str(catalog_path))

    index_instrument = build_index_instrument(underlying)
    is_btc = underlying == BTC_UNDERLYING_SYMBOL

    option_instruments: dict[str, object] = {}
    quotes: list[QuoteTick] = []
    trades: list[TradeTick] = []
    settlement_prices: dict[InstrumentId, Price] = {}
    seen_index_dates: set[pd.Timestamp] = set()
    entry_index_trades: list[tuple[int, float]] = []  # (ts_ns, S_entry), exact-print-time index ticks

    trade_seq = 0
    for leg in legs:
        name = leg.instrument_id
        if name not in option_instruments:
            option_instruments[name] = build_option_instrument(name, underlying, ts_event=0, ts_init=0)
        instrument = option_instruments[name]
        price_prec = instrument.price_precision
        key = (name, leg.leg_index)
        per_unit_marks = leg_daily_pnl[key]  # Series: date -> per-unit USD mark

        # entry: bid/ask from the REAL entry print price (leg.expected_ask
        # already IS ask_per_unit == price_native*(1+hs)*S or *(1+hs)) --
        # derive the "mid" price implied by removing the spread so bid can
        # be computed too (bid is never actually hit at entry -- only ask
        # matters for the BUY fill -- but QuoteTick requires both sides).
        entry_ask = leg.expected_ask
        entry_mid = entry_ask / (1 + half_spread)
        entry_bid = entry_mid * (1 - half_spread)
        entry_ns = _ns(leg.entry_ts)
        # Index TradeTick 1ns before the entry quote, at the ENTRY PRINT's own
        # S_entry (not a daily close) -- CappedOptionFeeModel resolves
        # underlying_price for linear fees from cache Last (plan §2.5), and
        # without this the fee would silently use the prior day's close,
        # producing a fee that does not match Vibe's `OPT_FEE_RATE * S_entry
        # * quantity` formula (verified empirically: ~150 vs ~220 on a real leg).
        entry_index_trades.append((entry_ns - 1, leg.entry_index_price))
        quotes.append(QuoteTick(
            instrument_id=instrument.id,
            bid_price=Price(entry_bid, price_prec),
            ask_price=Price(entry_ask, price_prec),
            bid_size=_BIG_SIZE,
            ask_size=_BIG_SIZE,
            ts_event=entry_ns,
            ts_init=entry_ns,
        ))

        # daily marks (including entry date's own synthetic-time quote and
        # every subsequent leg date) from the BS-surface per-unit value.
        for d, mark in per_unit_marks.items():
            d_ns = _ns(pd.Timestamp(d) + SYNTH_TIME)
            bid = mark * (1 - half_spread)
            ask = mark * (1 + half_spread)
            if bid <= 0:
                bid = max(mark * 0.5, 1e-8)
            quotes.append(QuoteTick(
                instrument_id=instrument.id,
                bid_price=Price(bid, price_prec),
                ask_price=Price(ask, price_prec),
                bid_size=_BIG_SIZE,
                ask_size=_BIG_SIZE,
                ts_event=d_ns,
                ts_init=d_ns,
            ))
            if pd.Timestamp(d) not in seen_index_dates:
                seen_index_dates.add(pd.Timestamp(d))

        if leg.exit_kind == "flip":
            exit_mark = float(per_unit_marks.iloc[-1])
            exit_bid = exit_mark * (1 - half_spread)
            exit_ns = _ns(leg.exit_ts + EXIT_QUOTE_OFFSET)
            quotes.append(QuoteTick(
                instrument_id=instrument.id,
                bid_price=Price(exit_bid, price_prec),
                ask_price=Price(exit_mark * (1 + half_spread), price_prec),
                bid_size=_BIG_SIZE,
                ask_size=_BIG_SIZE,
                ts_event=exit_ns,
                ts_init=exit_ns,
            ))
        else:  # expiry -- settlement_prices override carries the intrinsic per-unit payout
            # `leg.intrinsic_per_unit` (leg_planner.py) is Vibe's own daily-close intrinsic,
            # NOT the BS-surface mark -- this is what makes native cash settlement match
            # Vibe's settlement formula exactly (plan §2.8/§4.2).
            settlement_prices[instrument.id] = Price(max(leg.intrinsic_per_unit, 0.0), price_prec)

    for d in sorted(seen_index_dates):
        d_ns = _ns(pd.Timestamp(d) + SYNTH_TIME)
        px = float(idx.loc[pd.Timestamp(d)])
        trade_seq += 1
        trades.append(TradeTick(
            instrument_id=index_instrument.id,
            price=Price(px, index_instrument.price_precision),
            size=Quantity(1, index_instrument.size_precision),
            aggressor_side=AggressorSide.BUYER,
            trade_id=TradeId(f"IDX-{trade_seq}"),
            ts_event=d_ns,
            ts_init=d_ns,
        ))
    for ts_ns, s_entry in entry_index_trades:
        trade_seq += 1
        trades.append(TradeTick(
            instrument_id=index_instrument.id,
            price=Price(s_entry, index_instrument.price_precision),
            size=Quantity(1, index_instrument.size_precision),
            aggressor_side=AggressorSide.BUYER,
            trade_id=TradeId(f"IDX-ENTRY-{trade_seq}"),
            ts_event=ts_ns,
            ts_init=ts_ns,
        ))

    catalog.write_instruments([index_instrument, *option_instruments.values()])
    if quotes:
        quotes.sort(key=lambda q: q.ts_event)
        catalog.write_quote_ticks(quotes)
    if trades:
        trades.sort(key=lambda t: t.ts_event)
        catalog.write_trade_ticks(trades)

    return CatalogBuildResult(catalog, option_instruments, index_instrument, settlement_prices, quotes, trades)
