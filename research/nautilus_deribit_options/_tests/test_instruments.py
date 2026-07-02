"""CryptoOption/IndexInstrument construction, precision round-trips,
underlying-ID convention {underlying}.{venue}. Also verifies
Currency("USDC") wiring works.
"""
import numpy as np
import pyarrow.parquet as pq
import pytest
from nautilus_trader.model import Currency, OptionKind

import config as C
import instruments as I


def test_parsed_symbol_btc_extracts_strike_type_expiry_08utc():
    # Arrange / Act
    expiry, strike, opt_type = I.parsed_symbol("BTC-1JAN26-60000-C", "BTC")

    # Assert
    assert strike == 60000.0
    assert opt_type == "CALL"
    assert str(expiry) == "2026-01-01 08:00:00+00:00"


def test_parsed_symbol_sol_extracts_strike_type_expiry_08utc():
    # Arrange / Act
    expiry, strike, opt_type = I.parsed_symbol("SOL_USDC-15MAR25-150-P", "SOL_USDC")

    # Assert
    assert strike == 150.0
    assert opt_type == "PUT"
    assert str(expiry) == "2025-03-15 08:00:00+00:00"


def test_build_option_instrument_btc_round_trips_to_correct_kind_strike_underlying():
    # Arrange / Act
    opt = I.build_option_instrument("BTC-1JAN26-60000-C", "BTC")

    # Assert
    assert opt.option_kind == OptionKind.CALL
    assert float(opt.strike_price) == 60000.0
    assert str(opt.underlying) == "BTC"
    assert str(opt.id) == "BTC-1JAN26-60000-C.DERIBIT"


def test_build_option_instrument_sol_round_trips_to_correct_kind_strike_underlying():
    # Arrange / Act
    opt = I.build_option_instrument("SOL_USDC-15MAR25-150-P", "SOL_USDC")

    # Assert
    assert opt.option_kind == OptionKind.PUT
    assert float(opt.strike_price) == 150.0
    assert str(opt.underlying) == "SOL_USDC"
    assert str(opt.id) == "SOL_USDC-15MAR25-150-P.DERIBIT"


def test_underlying_id_symbol_equals_option_underlying_for_both_venues():
    # Arrange
    btc_idx = I.build_index_instrument("BTC")
    sol_idx = I.build_index_instrument("SOL_USDC")
    btc_opt = I.build_option_instrument("BTC-1JAN26-60000-C", "BTC")
    sol_opt = I.build_option_instrument("SOL_USDC-15MAR25-150-P", "SOL_USDC")

    # Act / Assert: this is the exact invariant plan §4.1 flags as required
    # for Nautilus's matching engine to resolve the underlying instrument
    # (engine.rs:2335) -- the IndexInstrument's symbol must equal the
    # option's `underlying` field, string-for-string.
    assert str(btc_idx.id) == "BTC.DERIBIT"
    assert str(btc_idx.id.symbol) == str(btc_opt.underlying)
    assert str(sol_idx.id) == "SOL_USDC.DERIBIT"
    assert str(sol_idx.id.symbol) == str(sol_opt.underlying)


def test_currency_usdc_wiring():
    # Arrange / Act
    opt = I.build_option_instrument("BTC-1JAN26-60000-C", "BTC")

    # Assert
    assert str(opt.quote_currency) == "USDC"
    assert str(opt.settlement_currency) == "USDC"
    assert Currency.from_str("USDC") is not None


def test_build_option_instrument_rejects_unknown_underlying():
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        I.build_option_instrument("ETH-1JAN26-3000-C", "ETH")


@pytest.mark.parametrize(
    "path,price_col,precision",
    [
        (C.BTC_TAPE_PATH, "price_usd", C.BTC_PRICE_PRECISION),
        (C.SOL_TAPE_PATH, "price", C.SOL_PRICE_PRECISION),
    ],
)
def test_price_precision_round_trips_real_tape_prices_losslessly(path, price_col, precision):
    """Empirical verification (plan §4.1: 'Verify chosen precision
    round-trips the smallest synthetic price in the tape window' -- a unit
    test, not an assumption). For BTC the USD-converted price
    (price_btc * index_price) is what actually gets quoted (plan §4.1's
    'BTC option prices are pre-converted to USD... when generating quotes'),
    so that's what must round-trip, not the raw BTC-denominated field."""
    if not path.exists():
        pytest.skip(f"raw tape not present: {path}")
    cols = ["price", "index_price"] if price_col == "price_usd" else ["price"]
    df = pq.ParquetFile(path).read(columns=cols).to_pandas()
    if price_col == "price_usd":
        values = df["price"] * df["index_price"]
    else:
        values = df["price"]
    values = values[values > 0]

    rounded = values.round(precision)
    rel_err = ((values - rounded).abs() / values).to_numpy()

    # "No information loss" == max relative error is float-noise level, not
    # a real quantization artifact (< 1e-9 rather than exactly 0.0, since
    # round() + float division introduces tiny representable-value noise).
    assert np.nanmax(rel_err) < 1e-9, (
        f"price_precision={precision} loses real information for {path.name}: "
        f"max relative error {np.nanmax(rel_err):.6e}"
    )
