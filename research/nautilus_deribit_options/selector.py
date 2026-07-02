"""The Vibe parity selector (plan §1.3): given a leg_start anchor date and a
window of eligible trades, find the EARLIEST print in
`[leg_start, leg_start + 3 calendar days]` matching option type (C for long
runs, P for short runs), `20 <= DTE <= 40`, `|ln(strike/index_price)| <
0.075`.

The plan's source analysis (verified independently against both
`phase4_trend_expression_options.py::find_option_entry` and
`phase5_sol_expression.py::find_option_entry`) shows the selection line is
`w.loc[(w["trade_dt"] - anchor).abs().idxmin()]` over a window that is
*already* filtered to `trade_dt >= anchor` -- so every `(trade_dt - anchor)`
value in the window is non-negative, meaning `.abs()` is a no-op and
`idxmin()` always picks the smallest raw `trade_dt - anchor`, i.e. the
EARLIEST print. It is mathematically NOT "nearest ATM" (there's no
moneyness term in the objective at all -- moneyness is only a boolean
pre-filter, not part of what's being minimized). This module implements
"earliest-in-window" directly (not by computing `.abs().idxmin()`), and
`_tests/test_selector_parity.py` includes a fixture where earliest and
nearest-ATM diverge, to guard against re-introducing the nearest-ATM bug
this project's design explicitly rejected.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import DTE_BAND, ENTRY_FWD_DAYS  # noqa: E402

MONEYNESS_BAND = 0.075


def select_entry(
    trades: pd.DataFrame,
    anchor: pd.Timestamp,
    opt_type: str,
    dte_band: tuple[float, float] = DTE_BAND,
    moneyness_band: float = MONEYNESS_BAND,
    fwd_days: int = ENTRY_FWD_DAYS,
) -> Optional[pd.Series]:
    """Return the earliest-in-window eligible print as a pandas Series (a
    row of `trades`), or None if no eligible print exists.

    `trades` must have columns: trade_dt, opt_type, dte, logm (or strike +
    index_price, from which logm can be derived by the caller before
    calling this -- kept as `logm` here to match tape.py's precomputed
    column and avoid recomputing per call).

    No-lookahead: only prints with `anchor <= trade_dt <= anchor + fwd_days`
    are eligible -- a print from before `anchor`, or from beyond the
    forward window, is never selectable.
    """
    window = trades[
        (trades["trade_dt"] >= anchor)
        & (trades["trade_dt"] <= anchor + pd.Timedelta(days=fwd_days))
        & (trades["opt_type"] == opt_type)
        & (trades["dte"].between(*dte_band))
        & (trades["logm"].abs() < moneyness_band)
    ]
    if window.empty:
        return None
    # Earliest-in-window: window is already restricted to trade_dt >= anchor,
    # so the smallest trade_dt is the smallest (trade_dt - anchor) and (since
    # non-negative) also the smallest |trade_dt - anchor| -- i.e. this is
    # exactly equivalent to Vibe's `.abs().idxmin()` on this window, made
    # explicit rather than relying on the sign coincidence.
    row = window.loc[window["trade_dt"].idxmin()]
    return row
