"""
Phase 4b: hybrid expression combos + spread stress (findings §81).

Phase 4's decomposition showed the options-expression gain is asymmetric:
shorts improve 5-6x as puts (bounded squeezes, no funding, crash gamma),
longs improve on total capture but pay theta in the 8-30d zone. The
mechanism-implied hybrids (pre-registered here before running):

  H1 = SPOT longs + OPT-BUDGET puts for shorts
  H2 = OPT-DELTA calls for longs + OPT-BUDGET puts for shorts
  H3 = SPOT longs + OPT-DELTA puts for shorts

Plus a robustness stress: all option tracks recomputed at DOUBLE the
empirical half-spread (1.22% vs 0.61%) -- deep-ITM exits and stressed
markets trade wider than the ATM median the base number was measured on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "agent"))

import phase4_trend_expression_options as p4  # noqa: E402
from data_prep import parse_instruments  # noqa: E402
from phase3_delta_hedged_backtest import build_vol_surface  # noqa: E402

DERIVED = Path(__file__).resolve().parent / "derived"


def load_all():
    runs = pd.read_csv(DERIVED / "btc_direction_runs.csv", parse_dates=["start", "end"])
    for c in ["start", "end"]:
        if runs[c].dt.tz is not None:
            runs[c] = runs[c].dt.tz_localize(None)
    idx_df = pd.read_csv(DERIVED / "daily_index.csv", parse_dates=["date"])
    idx = idx_df.set_index("date")["index_close"]
    idx.index = idx.index.tz_localize(None)
    term = pd.read_csv(DERIVED / "term_structure.csv", parse_dates=["date"])
    term["date"] = term["date"].dt.tz_localize(None)
    surf = build_vol_surface(term)

    pf = pq.ParquetFile(p4.RAW_PATH)
    trades = pf.read(columns=["instrument_name", "timestamp", "price", "iv", "index_price"]).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    parsed = parse_instruments(pd.Index(trades["instrument_name"].unique())).copy()
    parsed["expiry"] = parsed["expiry"].dt.tz_localize(None)
    trades = trades.join(parsed, on="instrument_name").dropna(subset=["expiry", "strike"])
    trades["dte"] = (trades["expiry"] - trades["trade_dt"]).dt.total_seconds() / 86400.0
    trades = trades[trades["dte"] > 0]
    trades["logm"] = np.log(trades["strike"] / trades["index_price"])
    trades = trades[(trades["dte"].between(*p4.DTE_BAND)) & (trades["logm"].abs() < 0.075)]
    return runs, idx, surf, trades


def main():
    runs, idx, surf, trades = load_all()

    sides = {}
    for d in (1, -1):
        sub = runs[runs["dir"] == d]
        spot, optd, optb, per_run, _ = p4.run_tracks(sub, trades, idx, surf)
        sides[d] = {"spot": spot, "optd": optd, "optb": optb}

    def combo(long_key: str, short_key: str) -> pd.Series:
        return sides[1][long_key].add(sides[-1][short_key], fill_value=0.0).sort_index()

    print("=== Hybrid combos (base 0.61% half-spread) ===")
    p4.metrics(combo("spot", "spot"), "SPOT/SPOT")
    p4.metrics(combo("optd", "optd"), "OPTD/OPTD")
    p4.metrics(combo("optb", "optb"), "OPTB/OPTB")
    p4.metrics(combo("spot", "optb"), "H1 S/OB")
    p4.metrics(combo("optd", "optb"), "H2 OD/OB")
    p4.metrics(combo("spot", "optd"), "H3 S/OD")

    print("\n=== Stress: option tracks at 2x half-spread (1.22%) ===")
    p4.HALF_SPREAD = 0.0122
    sides2 = {}
    for d in (1, -1):
        sub = runs[runs["dir"] == d]
        spot, optd, optb, _, _ = p4.run_tracks(sub, trades, idx, surf)
        sides2[d] = {"spot": spot, "optd": optd, "optb": optb}

    def combo2(lk, sk):
        return sides2[1][lk].add(sides2[-1][sk], fill_value=0.0).sort_index()

    p4.metrics(combo2("optd", "optd"), "OPTD/OPTD*")
    p4.metrics(combo2("optb", "optb"), "OPTB/OPTB*")
    p4.metrics(combo2("spot", "optb"), "H1 S/OB*")
    p4.metrics(combo2("optd", "optb"), "H2 OD/OB*")
    p4.metrics(combo2("spot", "optd"), "H3 S/OD*")


if __name__ == "__main__":
    main()
