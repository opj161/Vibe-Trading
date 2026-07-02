"""CryptoOption / IndexInstrument factories, normalized-linear USDC quoting
for BOTH underlyings (plan §4.1). BTC option prices must be pre-converted to
USD (`price_btc * index_price`) by the caller before being passed here as
`price_usd` -- this module does not do unit conversion itself, to keep the
BTC-vs-SOL premium-convention asymmetry (the highest-risk item in the plan,
§1.5) explicit and visible at the call site rather than hidden in a factory.

Underlying IDs: `BTC.DERIBIT` / `SOL_USDC.DERIBIT`. Verified empirically
(2026-07-02, nautilus_trader==2.0.0rc1) that the option's `underlying` field
is stored as the raw Currency code string ("BTC" / not a Nautilus-internal
alias) and that this equals the venue-underlying InstrumentId's symbol part
-- i.e. `CryptoOption(underlying=Currency.from_str("BTC"), ...).underlying`
prints as `BTC`, matching `InstrumentId(Symbol("BTC"), Venue("DERIBIT"))`
== `BTC.DERIBIT`. This is how Nautilus's matching engine resolves the
underlying instrument for expiry/settlement (plan §4.1 note referencing
engine.rs:2335).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
from nautilus_trader.model import (
    CryptoOption,
    Currency,
    IndexInstrument,
    InstrumentId,
    OptionKind,
    Price,
    Quantity,
    Symbol,
    Venue,
)

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import (  # noqa: E402
    BTC_PRICE_PRECISION,
    BTC_UNDERLYING_SYMBOL,
    SIZE_PRECISION,
    SOL_PRICE_PRECISION,
    SOL_UNDERLYING_SYMBOL,
    VENUE_NAME,
)

VENUE = Venue(VENUE_NAME)
QUOTE_SETTLEMENT_CCY = "USDC"

_BTC_NAME_RE = re.compile(r"^BTC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])$")
_SOL_NAME_RE = re.compile(r"^SOL_USDC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])$")
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parsed_symbol(instrument_name: str, underlying: str) -> tuple[pd.Timestamp, float, str]:
    """Parse a Deribit option instrument name into (expiry, strike,
    opt_type) using the same regex/format as the reused Vibe parsers
    (data_prep.parse_instruments / phase5_sol_expression.parse_sol_instruments)
    -- duplicated here only for the single-name case needed when building
    one CryptoOption from a leg-plan row; bulk parsing still goes through
    the imported Vibe functions in tape.py. Expiry is always 08:00 UTC."""
    pattern = _BTC_NAME_RE if underlying == "BTC" else _SOL_NAME_RE
    m = pattern.match(instrument_name)
    if not m:
        raise ValueError(f"unparseable instrument name for underlying {underlying}: {instrument_name!r}")
    day, mon, yy, strike, cp = m.groups()
    year = 2000 + int(yy)
    month = _MONTHS[mon]
    expiry = pd.Timestamp(year=year, month=month, day=int(day), hour=8, tz="UTC")
    opt_type = "CALL" if cp == "C" else "PUT"
    return expiry, float(strike), opt_type


def build_index_instrument(underlying: str) -> IndexInstrument:
    """Build the `{underlying}.{venue}` IndexInstrument. `underlying` must
    be "BTC" or "SOL_USDC" -- this string becomes both the raw symbol and
    (via InstrumentId) must equal every option's `underlying` currency code
    for the same underlying."""
    price_precision = BTC_PRICE_PRECISION if underlying == BTC_UNDERLYING_SYMBOL else SOL_PRICE_PRECISION
    symbol = Symbol(underlying)
    return IndexInstrument(
        instrument_id=InstrumentId(symbol, VENUE),
        raw_symbol=symbol,
        currency=Currency.from_str("USD"),
        price_precision=price_precision,
        size_precision=SIZE_PRECISION,
        price_increment=Price(10 ** -price_precision, price_precision),
        size_increment=Quantity(10 ** -SIZE_PRECISION, SIZE_PRECISION),
        ts_event=0,
        ts_init=0,
    )


def build_option_instrument(
    instrument_name: str,
    underlying: str,
    ts_event: int = 0,
    ts_init: int = 0,
) -> CryptoOption:
    """Build a normalized-linear USDC-quoted CryptoOption for `underlying`
    in {"BTC", "SOL_USDC"}. `is_inverse=False` for BOTH underlyings (plan
    §4.1) -- BTC's true inverse convention is deliberately not modeled here;
    the caller pre-converts BTC prices to USD before this instrument is
    used for quoting."""
    if underlying not in (BTC_UNDERLYING_SYMBOL, SOL_UNDERLYING_SYMBOL):
        raise ValueError(f"unknown underlying: {underlying!r}")
    expiry, strike, opt_type_name = parsed_symbol(instrument_name, underlying)
    price_precision = BTC_PRICE_PRECISION if underlying == BTC_UNDERLYING_SYMBOL else SOL_PRICE_PRECISION
    strike_precision = 2

    symbol = Symbol(instrument_name)
    instrument_id = InstrumentId(symbol, VENUE)
    expiration_ns = int(expiry.value)

    return CryptoOption(
        instrument_id=instrument_id,
        raw_symbol=symbol,
        underlying=Currency.from_str(underlying),
        quote_currency=Currency.from_str(QUOTE_SETTLEMENT_CCY),
        settlement_currency=Currency.from_str(QUOTE_SETTLEMENT_CCY),
        is_inverse=False,
        option_kind=OptionKind.CALL if opt_type_name == "CALL" else OptionKind.PUT,
        strike_price=Price(strike, strike_precision),
        activation_ns=0,
        expiration_ns=expiration_ns,
        price_precision=price_precision,
        size_precision=SIZE_PRECISION,
        price_increment=Price(10 ** -price_precision, price_precision),
        size_increment=Quantity(10 ** -SIZE_PRECISION, SIZE_PRECISION),
        ts_event=ts_event,
        ts_init=ts_init,
        multiplier=Quantity(1, 0),
        lot_size=Quantity(1, 0),
    )
