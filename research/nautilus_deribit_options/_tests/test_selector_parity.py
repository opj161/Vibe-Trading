"""earliest-eligible vs nearest-ATM discrimination; window bounds;
no-lookahead; DTE/moneyness filters; roll chaining.
"""
import pandas as pd
import pytest

import selector as S


def _row(trade_dt, opt_type, dte, logm, tag):
    return {"trade_dt": pd.Timestamp(trade_dt), "opt_type": opt_type, "dte": dte, "logm": logm, "tag": tag}


def test_earliest_eligible_not_nearest_atm():
    """Discrimination fixture: two eligible prints in the window. The
    LATER print is closer to ATM (smaller |logm|); the EARLIER print is
    further from ATM. Vibe's selector must pick the earlier one -- if it
    picked nearest-ATM instead, this test would fail, guarding against
    reintroducing that (rejected) selection rule."""
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([
        _row(anchor + pd.Timedelta(hours=1), "C", 30, 0.05, "earlier_further_from_atm"),
        _row(anchor + pd.Timedelta(hours=2), "C", 30, 0.001, "later_nearer_atm"),
    ])

    # Act
    row = S.select_entry(trades, anchor, "C")

    # Assert: earliest-in-window wins, not nearest-ATM
    assert row["tag"] == "earlier_further_from_atm"


def test_no_lookahead_prints_before_anchor_rejected():
    # Arrange: an eligible print exists, but 1 hour BEFORE anchor
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([
        _row(anchor - pd.Timedelta(hours=1), "C", 30, 0.0, "before_anchor"),
    ])

    # Act
    row = S.select_entry(trades, anchor, "C")

    # Assert
    assert row is None


def test_no_lookahead_prints_beyond_forward_window_rejected():
    # Arrange: print at anchor + 3 days + 1 second (just past ENTRY_FWD_DAYS)
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([
        _row(anchor + pd.Timedelta(days=3, seconds=1), "C", 30, 0.0, "just_too_late"),
    ])

    # Act
    row = S.select_entry(trades, anchor, "C", fwd_days=3)

    # Assert
    assert row is None


def test_print_exactly_at_forward_window_boundary_accepted():
    # Arrange: print at exactly anchor + 3 days -- boundary is inclusive
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([
        _row(anchor + pd.Timedelta(days=3), "C", 30, 0.0, "exactly_at_boundary"),
    ])

    # Act
    row = S.select_entry(trades, anchor, "C", fwd_days=3)

    # Assert
    assert row is not None
    assert row["tag"] == "exactly_at_boundary"


@pytest.mark.parametrize("dte,eligible", [(19.9, False), (20.0, True), (40.0, True), (40.1, False)])
def test_dte_band_boundaries(dte, eligible):
    # Arrange
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([_row(anchor, "C", dte, 0.0, "x")])

    # Act
    row = S.select_entry(trades, anchor, "C", dte_band=(20, 40))

    # Assert
    assert (row is not None) == eligible


@pytest.mark.parametrize("logm,eligible", [(-0.076, False), (-0.074, True), (0.074, True), (0.076, False)])
def test_moneyness_band_boundaries(logm, eligible):
    # Arrange
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([_row(anchor, "C", 30, logm, "x")])

    # Act
    row = S.select_entry(trades, anchor, "C", moneyness_band=0.075)

    # Assert
    assert (row is not None) == eligible


def test_option_type_filter_excludes_wrong_type():
    # Arrange: only a PUT print available, but a CALL is requested
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame([_row(anchor, "P", 30, 0.0, "wrong_type")])

    # Act
    row = S.select_entry(trades, anchor, "C")

    # Assert
    assert row is None


def test_empty_window_returns_none():
    # Arrange
    anchor = pd.Timestamp("2024-01-01")
    trades = pd.DataFrame(columns=["trade_dt", "opt_type", "dte", "logm"])

    # Act
    row = S.select_entry(trades, anchor, "C")

    # Assert
    assert row is None
