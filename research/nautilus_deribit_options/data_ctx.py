"""Shared data-loading context for the phase driver scripts.

Reproduces exactly the loading pattern already Gate-verified in
`_tests/test_mode_a_smoke.py`'s module fixtures (BTC: frozen daily_index +
term_structure -> phase3.build_vol_surface; SOL: everything derived
in-process from the tape via phase5.build_derived), packaged once so every
driver uses the identical context instead of five copies drifting apart.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import (  # noqa: E402
    BTC_HALF_SPREAD,
    BTC_UNDERLYING_SYMBOL,
    SOL_UNDERLYING_SYMBOL,
    VRP_DERIBIT_DIR,
)
from runs_loader import VibeRun, load_btc_runs, load_sol_runs  # noqa: E402
from tape import (  # noqa: E402
    atm_band_entry_pool,
    compute_sol_half_spread,
    load_btc_trades,
    load_sol_trades,
)

if str(VRP_DERIBIT_DIR) not in sys.path:
    sys.path.insert(0, str(VRP_DERIBIT_DIR))

from phase3_delta_hedged_backtest import build_vol_surface  # noqa: E402
from phase5_sol_expression import build_derived  # noqa: E402


@dataclass
class UnderlyingCtx:
    underlying: str
    trades_full: pd.DataFrame  # UNFILTERED parsed tape (Mode B needs full print history)
    entry_pool: pd.DataFrame   # ATM-band 20-40DTE pre-filter (parity entry pool)
    idx: pd.Series
    surf: dict
    half_spread: float
    runs: list[VibeRun]        # BTC: all 110; SOL: the 53 in-tape-window runs


def load_btc_ctx() -> UnderlyingCtx:
    derived = VRP_DERIBIT_DIR / "derived"
    idx = pd.read_csv(derived / "daily_index.csv", parse_dates=["date"]).set_index("date")["index_close"]
    idx.index = idx.index.tz_localize(None)
    term = pd.read_csv(derived / "term_structure.csv", parse_dates=["date"])
    term["date"] = term["date"].dt.tz_localize(None)
    surf = build_vol_surface(term)
    trades_full = load_btc_trades()
    return UnderlyingCtx(
        underlying=BTC_UNDERLYING_SYMBOL,
        trades_full=trades_full,
        entry_pool=atm_band_entry_pool(trades_full),
        idx=idx,
        surf=surf,
        half_spread=BTC_HALF_SPREAD,
        runs=load_btc_runs(),
    )


def load_sol_ctx() -> UnderlyingCtx:
    trades_full = load_sol_trades()
    idx, surf = build_derived(trades_full)
    half_spread = compute_sol_half_spread(trades_full)
    # phase5's own in-window filter: only runs starting inside the tape's
    # index coverage (the "53 in-window" denominator).
    runs = [r for r in load_sol_runs() if r.start >= idx.index.min()]
    return UnderlyingCtx(
        underlying=SOL_UNDERLYING_SYMBOL,
        trades_full=trades_full,
        entry_pool=atm_band_entry_pool(trades_full),
        idx=idx,
        surf=surf,
        half_spread=half_spread,
        runs=runs,
    )


def load_ctx(underlying: str) -> UnderlyingCtx:
    return load_btc_ctx() if underlying == BTC_UNDERLYING_SYMBOL else load_sol_ctx()
