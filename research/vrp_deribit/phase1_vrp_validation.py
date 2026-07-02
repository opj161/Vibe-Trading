"""
Phase 1: does the real Deribit trade tape corroborate §56's DVOL-based VRP
finding (BTC implied vol > subsequent realized vol), using genuinely traded
option prices instead of the DVOL index, and over a much longer real
history (2017-02 -> 2026-06 vs. DVOL's 2021-03 -> present)?

This is a pure measurement/validation step -- no strategy, no positions, no
costs. Two checks:
  1. Cross-validate our own trade-derived ATM-30d IV against the existing
     free DVOL series (research/data/dvol_btc.csv) on their overlapping
     window -- if they disagree substantially, something is wrong with the
     parsing/aggregation before any VRP number can be trusted.
  2. VRP = trade-derived ATM-30d IV(t) - realized vol of BTC over the
     *forward* 30 calendar days from t (computed from the option tape's own
     index_price series). Report mean/t-stat/hit-rate, by sub-period, and
     the worst historical episodes (tail-risk check, per the H2 plan's own
     "does a survivable-tail check exist" requirement).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DERIVED = Path(__file__).resolve().parent / "derived"
DVOL_PATH = Path(__file__).resolve().parents[1] / "data" / "dvol_btc.csv"


def realized_vol_forward(index_df: pd.DataFrame, window_days: int = 30) -> pd.Series:
    """Annualized realized vol of log returns over the *forward* window_days
    calendar days from each date, indexed by date. Uses only future data
    relative to `date` -- appropriate for a backward-looking VRP
    *measurement*, not for a live trading signal (a live signal must use
    trailing realized vol only; see phase2 for the live-safe version)."""
    s = index_df.set_index("date")["log_return"]
    # forward realized vol: at date t, std of returns over (t, t+window]
    rev = s[::-1]
    fwd_std = rev.rolling(window_days, min_periods=int(window_days * 0.6)).std()[::-1].shift(-1)
    return fwd_std * np.sqrt(365) * 100  # annualized, in vol POINTS (same units as iv, which is %)


def main() -> None:
    idx = pd.read_csv(DERIVED / "daily_index.csv", parse_dates=["date"])
    atm = pd.read_csv(DERIVED / "atm_iv_30d.csv", parse_dates=["date"])

    # --- Check 1: cross-validate against the free DVOL series ---
    dvol = pd.read_csv(DVOL_PATH, parse_dates=["date"])
    dvol["date"] = dvol["date"].dt.tz_localize("UTC")
    merged = atm.merge(dvol, on="date", how="inner")
    corr = merged["atm_iv_30d"].corr(merged["dvol"])
    diff = merged["atm_iv_30d"] - merged["dvol"]
    print("=== Check 1: trade-derived ATM-30d IV vs. free DVOL series ===")
    print(f"overlap: {len(merged):,} days ({merged['date'].min().date()} -> {merged['date'].max().date()})")
    print(f"correlation: {corr:.4f}")
    print(f"mean diff (ours - DVOL): {diff.mean():.2f} vol-pts, median {diff.median():.2f}, "
          f"std {diff.std():.2f}")
    print(f"mean abs diff: {diff.abs().mean():.2f} vol-pts")
    print()

    # --- Check 2: VRP using our own trade-derived series over its full history ---
    fwd_rv = realized_vol_forward(idx, 30)
    vrp_df = atm.set_index("date").join(fwd_rv.rename("fwd_rv_30d"), how="inner")
    vrp_df = vrp_df.dropna(subset=["fwd_rv_30d"])
    vrp_df["vrp"] = vrp_df["atm_iv_30d"] - vrp_df["fwd_rv_30d"]

    print("=== Check 2: VRP = trade-derived ATM-30d IV - forward-30d realized vol ===")
    print(f"n days: {len(vrp_df):,}  ({vrp_df.index.min().date()} -> {vrp_df.index.max().date()})")
    t_stat, p_val = stats.ttest_1samp(vrp_df["vrp"], 0)
    print(f"mean VRP: {vrp_df['vrp'].mean():.2f} vol-pts, median {vrp_df['vrp'].median():.2f}, "
          f"std {vrp_df['vrp'].std():.2f}")
    print(f"t-stat vs 0: {t_stat:.2f}, p-value: {p_val:.2e}")
    print(f"% of days VRP > 0: {(vrp_df['vrp'] > 0).mean() * 100:.1f}%")
    print()

    print("--- by year ---")
    vrp_df["year"] = vrp_df.index.year
    print(vrp_df.groupby("year")["vrp"].agg(["mean", "std", "count", lambda s: (s > 0).mean()]).rename(
        columns={"<lambda_0>": "pct_positive"}
    ).round(2))
    print()

    print("--- worst 10 VRP days (left-tail / short-vol blowup risk) ---")
    worst = vrp_df.nsmallest(10, "vrp")[["atm_iv_30d", "fwd_rv_30d", "vrp"]]
    print(worst.round(2))
    print()

    print("--- non-overlapping (every 30th trading day) sanity check ---")
    non_overlap = vrp_df.iloc[::30]
    t2, p2 = stats.ttest_1samp(non_overlap["vrp"], 0)
    print(f"n={len(non_overlap)}, mean VRP={non_overlap['vrp'].mean():.2f}, t-stat={t2:.2f}, p={p2:.2e}")

    vrp_df.reset_index().to_csv(DERIVED / "vrp_daily.csv", index=False)
    print(f"\nsaved: {DERIVED / 'vrp_daily.csv'}")


if __name__ == "__main__":
    main()
