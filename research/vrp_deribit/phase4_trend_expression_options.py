"""
Phase 4: instrument-expression study -- the champion's OWN validated BTC trend
signal, expressed three ways over the identical direction stream (findings
§81). Not a new signal, not a new allocation: the never-explored third axis.

Motivation (the P&L anatomy across §70/§74/§79/§80 is an option profile):
  - <8d whipsaw trades lose with ~0-14% win rate on BOTH sides (the premium),
  - >30d trades win 92-100% (the payoff), profits front-loaded in explosive
    rallies (which is why ZC1's discrete day-10 pyramiding failed -- an
    option's gamma pyramids continuously at locally fair prices),
  - shorts additionally carry funding drag (§75/§79.1) and squeeze risk,
  - and phase 1 measured the BTC VRP on this very tape as SMALL (2-4 vol
    pts, p=0.07-0.15) -- i.e. options are near-fairly priced, so the theta
    paid to bound the whipsaw is not obviously a losing trade a priori.
    (Classic negative prior: with a fat positive VRP, options-based trend
    underperforms; this tape says the VRP is thin. Empirical question.)

Direction stream: the REAL executed BTC positions of the champion lineage
(v_ZA4_regimeconviction_ext_train spliced with fwd_ZA4_20260702 at
2025-07-01), reduced to sign -- 110 direction runs, 2020-11 -> 2026-07,
median hold 9-10.5d, 43% of runs <8d. Saved by the §81 pre-analysis to
derived/btc_direction_runs.csv. Using the realized stream (not re-deriving
the signal) keeps the comparison pinned to exactly what the champion did.

Pre-registered tracks (declared before running):
  1. SPOT      -- frozen-quantity linear position (the engine's own
                  entry-locked semantics: pnl = dir * qty * dS), taker fee
                  0.10% per side. The baseline.
  2. OPT-DELTA -- 20-40 DTE ATM call (long) / put (short), REAL entry trade
                  prints from the tape, contracts delta-matched to the spot
                  baseline's entry notional. Rolls at expiry if the run
                  persists; sold at surface mark on signal flip.
  3. OPT-BUDGET-- same instrument selection, contracts sized so entry
                  premium = 10% of the spot notional (bounded-loss,
                  convex-leverage mode).

Costs (same fee model as phases 2-3): Deribit option fee 0.03% of underlying
notional per side capped at 12.5% of premium; empirically-measured 0.61%
half-spread applied against us on entry (real print * (1+hs)) and on every
model-marked exit (mark * (1-hs)); settlement fee 0.015% capped likewise on
expiry settlements. Spot: 0.10% taker per side (champion's own config).

Metrics: full-calendar Sharpe/DD/return on a fixed 1M base with 500k
per-entry notional (sizing held constant across tracks so differences are
expression, not sizing), per-duration-bucket and per-direction decomposition
-- the specific claim under test is "options cut the <8d bucket's cost and
keep the >30d bucket's capture".
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

from backtest.validation import deflated_sharpe_ratio  # noqa: E402
from data_prep import parse_instruments  # noqa: E402
from phase3_delta_hedged_backtest import (  # noqa: E402
    bs_price_and_delta,
    build_vol_surface,
    interp_iv,
    nearest_surf,
)

RAW_PATH = REPO_ROOT / "data" / "parquet" / "btc_option_trades_deribit.parquet"
DERIVED = Path(__file__).resolve().parent / "derived"

CAPITAL = 1_000_000.0
ENTRY_NOTIONAL = 500_000.0
SPOT_TAKER = 0.001            # 0.10% per side, champion config
OPT_FEE_RATE = 0.0003         # 0.03% of underlying notional per side
OPT_FEE_CAP = 0.125           # capped at 12.5% of premium
SETTLE_FEE_RATE = 0.00015     # delivery fee 0.015%
HALF_SPREAD = 0.0061          # phase-2/3 empirical measure
PREMIUM_BUDGET_FRAC = 0.10    # OPT-BUDGET: premium = 10% of spot notional
DTE_BAND = (20, 40)
ENTRY_FWD_DAYS = 3


def find_option_entry(trades: pd.DataFrame, anchor: pd.Timestamp, opt_type: str):
    """Nearest real ATM 20-40DTE trade of opt_type in [anchor, anchor+3d]."""
    w = trades[
        (trades["trade_dt"] >= anchor)
        & (trades["trade_dt"] <= anchor + pd.Timedelta(days=ENTRY_FWD_DAYS))
        & (trades["opt_type"] == opt_type)
        & (trades["dte"].between(*DTE_BAND))
        & (trades["logm"].abs() < 0.075)
    ]
    if w.empty:
        return None
    row = w.loc[(w["trade_dt"] - anchor).abs().idxmin()]
    return {
        "entry_dt": row["trade_dt"].floor("D"),
        "expiry": row["expiry"],
        "strike": row["strike"],
        "price_btc": row["price"],
        "iv": row["iv"],
        "S": row["index_price"],
    }


def option_leg_pnl(entry: dict, direction: int, contracts: float,
                   idx: pd.Series, surf: dict, leg_end: pd.Timestamp) -> tuple[pd.Series, float]:
    """Daily USD P&L of a long option leg from entry to min(flip, expiry).

    Returns (daily pnl series, settlement/exit cash-flow already included on
    the final day). Marks with the trade-derived surface; exit at
    mark*(1-HALF_SPREAD) on flip, intrinsic minus settlement fee at expiry.
    """
    opt_type = "C" if direction > 0 else "P"
    expiry = entry["expiry"]
    end = min(pd.Timestamp(expiry).floor("D"), leg_end)
    dates = idx.index[(idx.index >= entry["entry_dt"]) & (idx.index <= end)]
    if len(dates) < 2:
        return pd.Series(dtype=float), 0.0

    entry_cost = entry["price_btc"] * (1 + HALF_SPREAD) * entry["S"] * contracts
    fee = min(OPT_FEE_RATE * entry["S"] * contracts, OPT_FEE_CAP * entry_cost)

    vals = []
    for d in dates:
        S = idx.loc[d]
        T = max((expiry - d).total_seconds(), 0) / (365 * 86400)
        fallback = entry["iv"]
        sigma = max(interp_iv(nearest_surf(surf, d), max(T * 365, 0.5), fallback), 5.0) / 100.0
        v, _ = bs_price_and_delta(S, entry["strike"], T, sigma, opt_type)
        vals.append(v * S * contracts)
    vals = np.array(vals)

    is_expiry_exit = end >= pd.Timestamp(expiry).floor("D")
    S_end = idx.loc[dates[-1]]
    if is_expiry_exit:
        intrinsic = max(S_end - entry["strike"], 0.0) if opt_type == "C" else max(entry["strike"] - S_end, 0.0)
        exit_val = intrinsic * contracts
        exit_val -= min(SETTLE_FEE_RATE * S_end * contracts, OPT_FEE_CAP * max(exit_val, 1e-9))
    else:
        exit_val = vals[-1] * (1 - HALF_SPREAD)

    pnl = pd.Series(0.0, index=dates)
    pnl.iloc[0] = vals[0] - entry_cost - fee
    if len(dates) > 2:
        pnl.iloc[1:-1] = np.diff(vals)[:-1]
    pnl.iloc[-1] = exit_val - vals[-2]
    return pnl, exit_val


def run_tracks(runs: pd.DataFrame, trades: pd.DataFrame, idx: pd.Series, surf: dict):
    spot_pnl, optd_pnl, optb_pnl = {}, {}, {}
    per_run = []
    skipped = 0

    for _, r in runs.iterrows():
        start, end, direction = pd.Timestamp(r["start"]), pd.Timestamp(r["end"]), int(r["dir"])
        days = int(r["days"])
        dates = idx.index[(idx.index >= start) & (idx.index <= end)]
        if len(dates) < 2:
            continue
        S0 = idx.loc[dates[0]]
        qty = ENTRY_NOTIONAL / S0

        # --- SPOT (frozen quantity, engine semantics) ---
        s_pnl = pd.Series(direction * qty * np.diff(idx.loc[dates].values), index=dates[1:])
        s_pnl.iloc[0] -= SPOT_TAKER * ENTRY_NOTIONAL
        s_pnl.iloc[-1] -= SPOT_TAKER * qty * idx.loc[dates[-1]]
        for d, v in s_pnl.items():
            spot_pnl[d] = spot_pnl.get(d, 0.0) + v
        spot_total = s_pnl.sum()

        # --- OPTIONS (roll chain until run ends) ---
        run_opt = {"OPT-DELTA": 0.0, "OPT-BUDGET": 0.0}
        found_any = False
        for label, store in [("OPT-DELTA", optd_pnl), ("OPT-BUDGET", optb_pnl)]:
            leg_start = dates[0]
            total = 0.0
            while leg_start < dates[-1]:
                entry = find_option_entry(trades, leg_start, "C" if direction > 0 else "P")
                if entry is None or entry["entry_dt"] >= dates[-1]:
                    break
                T0 = max((entry["expiry"] - entry["entry_dt"]).total_seconds(), 1) / (365 * 86400)
                _, delta0 = bs_price_and_delta(entry["S"], entry["strike"], T0, entry["iv"] / 100.0,
                                               "C" if direction > 0 else "P")
                if label == "OPT-DELTA":
                    contracts = qty / max(abs(delta0), 0.05)
                else:
                    prem_per = entry["price_btc"] * (1 + HALF_SPREAD) * entry["S"]
                    contracts = (PREMIUM_BUDGET_FRAC * ENTRY_NOTIONAL) / max(prem_per, 1e-9)
                pnl, _ = option_leg_pnl(entry, direction, contracts, idx, surf, dates[-1])
                if pnl.empty:
                    break
                for d, v in pnl.items():
                    store[d] = store.get(d, 0.0) + v
                total += pnl.sum()
                leg_end = pnl.index[-1]
                if leg_end >= dates[-1]:
                    break
                leg_start = leg_end + pd.Timedelta(days=1)  # roll: expiry hit mid-run
                found_any = True
            run_opt[label] = total
            if total != 0.0:
                found_any = True
        if not found_any:
            skipped += 1

        per_run.append({
            "start": dates[0], "dir": direction, "days": days,
            "spot": spot_total, "opt_delta": run_opt["OPT-DELTA"], "opt_budget": run_opt["OPT-BUDGET"],
        })

    return (pd.Series(spot_pnl).sort_index(), pd.Series(optd_pnl).sort_index(),
            pd.Series(optb_pnl).sort_index(), pd.DataFrame(per_run), skipped)


def metrics(pnl: pd.Series, label: str):
    cal = pd.date_range(pnl.index.min(), pnl.index.max(), freq="D")
    daily = pnl.reindex(cal, fill_value=0.0)
    eq = CAPITAL + daily.cumsum()
    rets = eq.pct_change().dropna()
    n_years = len(cal) / 365.25
    ann = (eq.iloc[-1] / CAPITAL) ** (1 / n_years) - 1
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else float("nan")
    dd = ((eq - eq.cummax()) / eq.cummax()).min()
    dsr = deflated_sharpe_ratio(rets.values, n_trials=2, bars_per_year=365)
    print(f"{label:12s} total={pnl.sum():+12,.0f}  ann={ann*100:+6.1f}%  sharpe={sharpe:6.2f}  "
          f"maxDD={dd*100:6.1f}%  DSR={dsr['dsr']*100:5.1f}%")
    return eq


def main():
    runs = pd.read_csv(DERIVED / "btc_direction_runs.csv", parse_dates=["start", "end"])
    idx_df = pd.read_csv(DERIVED / "daily_index.csv", parse_dates=["date"])
    idx = idx_df.set_index("date")["index_close"]
    idx.index = idx.index.tz_localize(None)
    runs["start"] = runs["start"].dt.tz_localize(None) if runs["start"].dt.tz is not None else runs["start"]
    runs["end"] = runs["end"].dt.tz_localize(None) if runs["end"].dt.tz is not None else runs["end"]

    term = pd.read_csv(DERIVED / "term_structure.csv", parse_dates=["date"])
    term["date"] = term["date"].dt.tz_localize(None)
    surf = build_vol_surface(term)

    print("loading tape...")
    pf = pq.ParquetFile(RAW_PATH)
    trades = pf.read(columns=["instrument_name", "timestamp", "price", "iv", "index_price"]).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    parsed = parse_instruments(pd.Index(trades["instrument_name"].unique()))
    parsed = parsed.copy()
    parsed["expiry"] = parsed["expiry"].dt.tz_localize(None)
    trades = trades.join(parsed, on="instrument_name").dropna(subset=["expiry", "strike"])
    trades["dte"] = (trades["expiry"] - trades["trade_dt"]).dt.total_seconds() / 86400.0
    trades = trades[trades["dte"] > 0]
    trades["logm"] = np.log(trades["strike"] / trades["index_price"])
    # pre-filter once to the entry-eligible subset (ATM band, 20-40 DTE) --
    # find_option_entry re-applies the same conditions, so this is purely a
    # performance reduction, not a behavior change
    trades = trades[(trades["dte"].between(*DTE_BAND)) & (trades["logm"].abs() < 0.075)]

    spot, optd, optb, per_run, skipped = run_tracks(runs, trades, idx, surf)
    print(f"\nruns={len(per_run)} option-entry-skipped={skipped}\n")
    metrics(spot, "SPOT")
    metrics(optd, "OPT-DELTA")
    metrics(optb, "OPT-BUDGET")

    per_run["bucket"] = pd.cut(per_run["days"], [0, 8, 30, 9999], labels=["<8d", "8-30d", ">30d"])
    print("\n--- per-run mean P&L by duration bucket (the core claim) ---")
    g = per_run.groupby("bucket", observed=True)[["spot", "opt_delta", "opt_budget"]].agg(["mean", "sum", "count"])
    print(g.round(0).to_string())
    print("\n--- by direction ---")
    g2 = per_run.groupby("dir")[["spot", "opt_delta", "opt_budget"]].sum()
    print(g2.round(0).to_string())
    per_run.to_csv(DERIVED / "phase4_per_run.csv", index=False)
    print(f"\nsaved {DERIVED / 'phase4_per_run.csv'}")


if __name__ == "__main__":
    main()
