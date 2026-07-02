"""Both symbol formats, expiry 08:00 UTC, unparsed-name drop."""
import pandas as pd
import pyarrow as pa
import pytest

import tape as T


def _fake_parquet_file(df: pd.DataFrame):
    table = pa.Table.from_pandas(df)
    return lambda path: type("F", (), {"read": lambda self, columns=None: table})()


def _btc_frame(names, timestamps_ms):
    n = len(names)
    return pd.DataFrame({
        "instrument_name": names,
        "timestamp": timestamps_ms,
        "price": [0.05] * n,
        "mark_price": [0.05] * n,
        "iv": [65.0] * n,
        "index_price": [60000.0] * n,
        "amount": [1.0] * n,
    })


def test_btc_symbol_format_parses_expiry_strike_type(monkeypatch, tmp_path):
    # Arrange: one well-formed BTC name plus one malformed name.
    names = ["BTC-1JAN26-60000-C", "BTC-garbage-name"]
    ts0 = int(pd.Timestamp("2025-12-30", tz="UTC").value // 1_000_000)
    df = _btc_frame(names, [ts0, ts0])

    monkeypatch.setattr(T.pq, "ParquetFile", _fake_parquet_file(df))

    # Act
    out = T.load_btc_trades(path="unused")

    # Assert: malformed name dropped, well-formed name parsed correctly
    assert len(out) == 1
    row = out.iloc[0]
    assert row["instrument_name"] == "BTC-1JAN26-60000-C"
    assert row["strike"] == 60000.0
    assert row["opt_type"] == "C"
    assert row["expiry"] == pd.Timestamp("2026-01-01 08:00:00")


def test_sol_symbol_format_parses_expiry_strike_type(monkeypatch):
    # Arrange
    names = ["SOL_USDC-15MAR25-150-P", "not-a-real-instrument"]
    ts0 = int(pd.Timestamp("2025-03-10", tz="UTC").value // 1_000_000)
    df = pd.DataFrame({
        "instrument_name": names,
        "timestamp": [ts0, ts0],
        "price": [12.0, 12.0],
        "mark_price": [12.0, 12.0],
        "iv": [80.0, 80.0],
        "index_price": [150.0, 150.0],
        "amount": [100.0, 100.0],
    })
    monkeypatch.setattr(T.pq, "ParquetFile", _fake_parquet_file(df))

    # Act
    out = T.load_sol_trades(path="unused")

    # Assert
    assert len(out) == 1
    row = out.iloc[0]
    assert row["instrument_name"] == "SOL_USDC-15MAR25-150-P"
    assert row["strike"] == 150.0
    assert row["opt_type"] == "P"
    assert row["expiry"] == pd.Timestamp("2025-03-15 08:00:00")


def test_post_expiry_prints_are_dropped(monkeypatch):
    # Arrange: a print timestamped AFTER its own instrument's expiry.
    name = "BTC-1JAN25-60000-C"
    ts_after_expiry = int(pd.Timestamp("2025-01-02", tz="UTC").value // 1_000_000)
    df = _btc_frame([name], [ts_after_expiry])
    monkeypatch.setattr(T.pq, "ParquetFile", _fake_parquet_file(df))

    # Act
    out = T.load_btc_trades(path="unused")

    # Assert: dte <= 0 rows are filtered out entirely
    assert out.empty


def test_atm_band_entry_pool_filters_dte_and_moneyness():
    # Arrange: three rows -- one in-band, one out-of-DTE, one out-of-moneyness
    df = pd.DataFrame({
        "dte": [30.0, 100.0, 30.0],
        "logm": [0.01, 0.01, 0.5],
    })

    # Act
    out = T.atm_band_entry_pool(df)

    # Assert
    assert len(out) == 1
    assert out.iloc[0]["dte"] == 30.0


def test_compute_sol_half_spread_matches_median_relative_deviation():
    # Arrange: ATM-band rows with a known median |price-mark|/mark
    df = pd.DataFrame({
        "dte": [30.0, 30.0, 30.0],
        "logm": [0.0, 0.0, 0.0],
        "price": [10.0, 11.0, 9.0],
        "mark_price": [10.0, 10.0, 10.0],
    })

    # Act
    hs = T.compute_sol_half_spread(df)

    # Assert: relative deviations are [0.0, 0.1, 0.1] -> median 0.1
    assert hs == pytest.approx(0.1)
