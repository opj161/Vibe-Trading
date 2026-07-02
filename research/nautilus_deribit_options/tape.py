"""Load/parse the raw BTC and SOL_USDC Deribit option tapes into normalized
trades DataFrames, reusing the Vibe parsers (`research/vrp_deribit/
data_prep.py::parse_instruments` for BTC, `phase5_sol_expression.py::
parse_sol_instruments` for SOL) rather than reimplementing instrument-name
parsing -- per CLAUDE.md's "reuse the parity oracle, don't duplicate it"
rule and the plan's explicit instruction.

Follows the same sys.path-insertion pattern already used by
`phase4b_hybrid_and_stress.py` / `phase4_trend_expression_options.py` /
`phase5_sol_expression.py` to import sibling modules from
`research/vrp_deribit/` without modifying that package.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import BTC_TAPE_PATH, DTE_BAND, SOL_TAPE_PATH, VRP_DERIBIT_DIR  # noqa: E402

if str(VRP_DERIBIT_DIR) not in sys.path:
    sys.path.insert(0, str(VRP_DERIBIT_DIR))

from data_prep import parse_instruments  # noqa: E402
from phase5_sol_expression import parse_sol_instruments  # noqa: E402

BTC_TRADE_COLUMNS = ["instrument_name", "timestamp", "price", "mark_price", "iv", "index_price", "amount"]
SOL_TRADE_COLUMNS = ["instrument_name", "timestamp", "price", "mark_price", "iv", "index_price", "amount"]


def _finalize(df: pd.DataFrame, parsed: pd.DataFrame) -> pd.DataFrame:
    """Common post-parse steps: join parsed attrs, drop unparsed rows,
    compute dte/log-moneyness. Shared by both tapes -- pure arithmetic, no
    convention-specific logic, so sharing this does not risk drifting from
    either parity oracle (each oracle does the exact same four lines
    inline)."""
    df = df.join(parsed, on="instrument_name")
    df = df.dropna(subset=["expiry", "strike"])
    df["dte"] = (df["expiry"] - df["trade_dt"]).dt.total_seconds() / 86400.0
    df = df[df["dte"] > 0]
    df["logm"] = np.log(df["strike"] / df["index_price"])
    return df


def load_btc_trades(path=BTC_TAPE_PATH, columns=None) -> pd.DataFrame:
    """Load the BTC option tape (inverse convention: `price` is BTC per 1
    BTC of underlying). Mirrors `phase4_trend_expression_options.py::main`'s
    load path exactly (naive/UTC-stripped trade_dt, expiry tz-stripped to
    match)."""
    cols = columns or BTC_TRADE_COLUMNS
    trades = pq.ParquetFile(path).read(columns=cols).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    parsed = parse_instruments(pd.Index(trades["instrument_name"].unique())).copy()
    parsed["expiry"] = parsed["expiry"].dt.tz_localize(None)
    return _finalize(trades, parsed)


def load_sol_trades(path=SOL_TAPE_PATH, columns=None) -> pd.DataFrame:
    """Load the SOL_USDC option tape (linear convention: `price` is USDC
    per 1 SOL, no index multiplication). Mirrors
    `phase5_sol_expression.py::main`'s load path exactly (parse_sol_instruments
    already returns naive timestamps -- no tz_localize needed on `expiry`)."""
    cols = columns or SOL_TRADE_COLUMNS
    trades = pq.ParquetFile(path).read(columns=cols).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    trades["date"] = trades["trade_dt"].dt.floor("D")
    parsed = parse_sol_instruments(pd.Index(trades["instrument_name"].unique()))
    return _finalize(trades, parsed)


def atm_band_entry_pool(trades: pd.DataFrame, dte_band=DTE_BAND, moneyness: float = 0.075) -> pd.DataFrame:
    """The ATM-band, DTE-band pre-filter both phase4 and phase5 apply once
    before the leg-selection loop (a pure performance reduction -- the
    selector re-applies the same conditions, so pre-filtering here changes
    nothing behaviorally)."""
    return trades[(trades["dte"].between(*dte_band)) & (trades["logm"].abs() < moneyness)]


def compute_sol_half_spread(trades: pd.DataFrame, dte_band=DTE_BAND, moneyness: float = 0.075) -> float:
    """SOL's half-spread has no frozen constant (unlike BTC's 0.0061) --
    phase5 measures it at runtime from the tape itself:
    median(|price - mark_price| / mark_price) over ATM-band 20-40DTE
    prints. Reproduced verbatim from `phase5_sol_expression.py::main`."""
    atm = atm_band_entry_pool(trades, dte_band, moneyness)
    rel = ((atm["price"] - atm["mark_price"]).abs() / atm["mark_price"].replace(0, np.nan)).dropna()
    return float(rel.median())
