"""Frozen parity constants and paths for the Nautilus/Deribit options parity
project (Phases 1-2). Mirrors plan §1.1 exactly -- these are the same
numbers `research/vrp_deribit/phase4_trend_expression_options.py` and
`phase5_sol_expression.py` use, duplicated here (not imported) because the
plan treats them as frozen parity constants belonging to this project, while
the vrp_deribit scripts remain untouched parity oracles.

Do not edit these values without also re-verifying Gate 2 (leg_planner vs.
frozen targets) -- they are inputs to that reconciliation.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VRP_DERIBIT_DIR = REPO_ROOT / "research" / "vrp_deribit"
DERIVED_DIR = VRP_DERIBIT_DIR / "derived"
FROZEN_DIR = DERIVED_DIR / "frozen_20260702"

BTC_TAPE_PATH = REPO_ROOT / "data" / "parquet" / "btc_option_trades_deribit.parquet"
SOL_TAPE_PATH = REPO_ROOT / "data" / "parquet" / "sol_usdc_option_trades_deribit.parquet"

BTC_RUNS_CSV = DERIVED_DIR / "btc_direction_runs.csv"
SOL_RUNS_CSV = DERIVED_DIR / "sol_direction_runs.csv"

BTC_DAILY_INDEX_CSV = DERIVED_DIR / "daily_index.csv"
BTC_TERM_STRUCTURE_CSV = DERIVED_DIR / "term_structure.csv"

FROZEN_BTC_PER_RUN_CSV = FROZEN_DIR / "phase4_per_run.csv"
FROZEN_SOL_PER_RUN_CSV = FROZEN_DIR / "phase5_sol_per_run.csv"

# --- §1.1 frozen constants (identical across BTC/SOL) ---
CAPITAL = 1_000_000.0
ENTRY_NOTIONAL = 500_000.0
SPOT_TAKER = 0.001
OPT_FEE_RATE = 0.0003
OPT_FEE_CAP = 0.125
SETTLE_FEE_RATE = 0.00015
PREMIUM_BUDGET_FRAC = 0.10
DTE_BAND = (20, 40)
ENTRY_FWD_DAYS = 3

# BTC half-spread is hardcoded (phase-2/3 empirical measure, frozen).
# SOL half-spread has no single frozen constant -- it is measured from the
# tape at runtime (median(|price-mark_price|/mark_price) over the ATM-band
# 20-40DTE prints), because the SOL book is thinner and phase5 explicitly
# re-measures it rather than reusing BTC's number. See
# `tape.py::compute_sol_half_spread`.
BTC_HALF_SPREAD = 0.0061

# Underlying IDs: the ID's symbol part must equal the option's `underlying`
# currency code (Nautilus derives underlying-instrument lookups from this;
# verified empirically against the installed nautilus_trader==2.0.0rc1 wheel
# -- CryptoOption(underlying=Currency.from_str("BTC"), ...).underlying == "BTC"
# and IndexInstrument(instrument_id=InstrumentId(Symbol("BTC"), venue)).id ==
# "BTC.DERIBIT").
VENUE_NAME = "DERIBIT"
BTC_UNDERLYING_SYMBOL = "BTC"
SOL_UNDERLYING_SYMBOL = "SOL_USDC"

# Price precision: empirically verified via a round-trip test against the
# real tape (see _tests/test_instruments.py::test_price_precision_round_trips).
# BTC options quoted in USD (price_btc * index_price) span from ~$0.11 to
# ~$161k; rounding to 2dp (the plan's starting-point guess) loses up to
# 2.6% relative on the cheapest prints -- empirically NOT lossless, so BTC
# uses 6dp (verified lossless to float-noise level, max rel err ~4e-16).
# SOL prices are already USD-native and observed to be exact multiples of
# $0.01 in the tape (max/median rel err at 2dp and 4dp both 0.0) -- 4dp is
# used anyway as a safety margin per the plan's starting point.
BTC_PRICE_PRECISION = 6
SOL_PRICE_PRECISION = 4
SIZE_PRECISION = 6
