"""
Phase 0: parse the raw Deribit BTC option trade tape into compact, reusable
derived series.

Input:  data/parquet/btc_option_trades_deribit.parquet (23.8M trades,
        2016-11-29 -> 2026-07-02, real trade-level data: price, mark_price,
        iv, index_price, amount, direction per trade; from
        github.com/RiveChen/deribit-historical-data).

Output (research/vrp_deribit/derived/):
  - daily_index.csv   : date, index_close, log_return  (BTC index price,
                         reconstructed from the option tape's own
                         index_price field -- the same index Deribit itself
                         settles options against, so no separate spot-price
                         source/alignment question).
  - atm_iv_30d.csv     : date, atm_iv_30d (volume-weighted IV of trades with
                         20-40 DTE and |log-moneyness| < 7.5%), n_trades used.
  - term_structure.csv : date, dte_bucket, iv (volume-weighted), n_trades --
                         same construction at 7/14/30/60/90 DTE for context.

All three are pure descriptive reductions of the raw tape -- no strategy
logic, no lookahead (each day's IV number uses only trades printed that day).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

RAW_PATH = Path(__file__).resolve().parents[2] / "data" / "parquet" / "btc_option_trades_deribit.parquet"
OUT_DIR = Path(__file__).resolve().parent / "derived"

_INSTRUMENT_RE = re.compile(r"^BTC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])$")
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_instruments(names: pd.Index) -> pd.DataFrame:
    """Parse unique BTC option instrument names into (expiry, strike, type).

    Deribit format: BTC-{D}{MMM}{YY}-{STRIKE}-{C|P}, expiry at 08:00 UTC.
    A handful of legacy/combo/malformed names may not match; they are
    dropped (flagged in the return via all-NaN rows) rather than crashing.
    """
    rows = []
    for name in names:
        m = _INSTRUMENT_RE.match(name)
        if not m:
            rows.append((name, pd.NaT, np.nan, None))
            continue
        day, mon, yy, strike, cp = m.groups()
        year = 2000 + int(yy)
        month = _MONTHS.get(mon)
        if month is None:
            rows.append((name, pd.NaT, np.nan, None))
            continue
        expiry = pd.Timestamp(year=year, month=month, day=int(day), hour=8, tz="UTC")
        rows.append((name, expiry, float(strike), cp))
    return pd.DataFrame(rows, columns=["instrument_name", "expiry", "strike", "opt_type"]).set_index("instrument_name")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pf = pq.ParquetFile(RAW_PATH)
    cols = ["instrument_name", "timestamp", "iv", "index_price", "amount"]
    tbl = pf.read(columns=cols)
    df = tbl.to_pandas()
    print(f"loaded {len(df):,} trades")

    df["trade_dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["date"] = df["trade_dt"].dt.floor("D")

    # --- daily index price series (last print of each UTC day) ---
    idx = (
        df[["date", "trade_dt", "index_price"]]
        .sort_values("trade_dt")
        .groupby("date", as_index=False)
        .last()[["date", "index_price"]]
        .rename(columns={"index_price": "index_close"})
        .sort_values("date")
    )
    idx["log_return"] = np.log(idx["index_close"]).diff()
    idx.to_csv(OUT_DIR / "daily_index.csv", index=False)
    print(f"daily_index.csv: {len(idx):,} days, {idx['date'].min()} -> {idx['date'].max()}")

    # --- parse instrument attributes (unique names only, then map back) ---
    uniq_names = pd.Index(df["instrument_name"].unique())
    parsed = parse_instruments(uniq_names)
    n_unparsed = parsed["expiry"].isna().sum()
    print(f"parsed {len(parsed):,} unique instruments ({n_unparsed} unparsed, dropped)")

    df = df.join(parsed, on="instrument_name")
    df = df.dropna(subset=["expiry", "strike"])

    df["dte"] = (df["expiry"] - df["trade_dt"]).dt.total_seconds() / 86400.0
    df = df[df["dte"] > 0]  # drop post-expiry/settlement prints if any
    df["log_moneyness"] = np.log(df["strike"] / df["index_price"])

    # --- ATM 30d IV series (20-40 DTE, |log-moneyness| < 7.5%) ---
    atm = df[(df["dte"].between(20, 40)) & (df["log_moneyness"].abs() < 0.075)].copy()
    atm["iv_x_amt"] = atm["iv"] * atm["amount"]
    g = atm.groupby("date").agg(
        iv_x_amt=("iv_x_amt", "sum"),
        amount=("amount", "sum"),
        n_trades=("iv", "size"),
    )
    g["atm_iv_30d"] = g["iv_x_amt"] / g["amount"]
    g = g[["atm_iv_30d", "n_trades"]].reset_index().sort_values("date")
    g.to_csv(OUT_DIR / "atm_iv_30d.csv", index=False)
    print(f"atm_iv_30d.csv: {len(g):,} days with >=1 qualifying trade")
    print(f"  coverage: {g['date'].min()} -> {g['date'].max()}, "
          f"median n_trades/day = {g['n_trades'].median():.0f}")

    # --- term structure at several DTE buckets, for context ---
    buckets = {"7d": (3, 11), "14d": (11, 21), "30d": (20, 40), "60d": (45, 75), "90d": (75, 105)}
    frames = []
    for label, (lo, hi) in buckets.items():
        sub = df[(df["dte"].between(lo, hi)) & (df["log_moneyness"].abs() < 0.075)].copy()
        sub["iv_x_amt"] = sub["iv"] * sub["amount"]
        gg = sub.groupby("date").agg(iv_x_amt=("iv_x_amt", "sum"), amount=("amount", "sum"), n_trades=("iv", "size"))
        gg["iv"] = gg["iv_x_amt"] / gg["amount"]
        gg = gg[["iv", "n_trades"]].reset_index()
        gg["dte_bucket"] = label
        frames.append(gg)
    term = pd.concat(frames, ignore_index=True).sort_values(["date", "dte_bucket"])
    term.to_csv(OUT_DIR / "term_structure.csv", index=False)
    print(f"term_structure.csv: {len(term):,} rows across {len(buckets)} DTE buckets")


if __name__ == "__main__":
    main()
