"""
Phase 5: the SOL expression study (findings §82) — phase 4's instrument-
expression test rerun on the leg where the prize actually lives.

§81 found the champion's BTC leg produces 26-52% more P&L when its shorts
are expressed as puts. But SOL shorts are 86-100% of recent forward P&L,
with 3x worse whipsaw churn (§79.3) and a real funding drag on perps
(§75/§79.1) — everything puts fix, at larger scale. Blocked until now by
data; unblocked by the SOL_USDC tape fetched 2026-07-02 with the new
INSTRUMENT_PREFIX filter added to the deribit-historical-data fetcher
(665,251 real trades, 2024-03-11 → 2026-07-02, 49,112 instruments).

KEY CONVENTION DIFFERENCE vs. the BTC tape: SOL_USDC options are LINEAR
(USDC-settled) — `price` is USDC per 1 SOL of underlying (not a
BTC-denominated inverse quote), so premium_usd = price × sol_units, with
NO index_price multiplication. Instrument format: SOL_USDC-{D}{MMM}{YY}-
{STRIKE}-{C|P}. All BS pricing here is plain USD-out (no inverse
conversion). The empirical half-spread is re-measured on THIS tape —
BTC's 0.61% median explicitly does not transfer to a thinner book.

Design mirrors phase 4/4b exactly otherwise (pre-registered): the
champion's REAL executed SOL direction stream (v_ZA4 ext train spliced
with fwd_ZA4; 53 runs inside the tape window, 20 long / 33 short), three
expression tracks (SPOT frozen-quantity baseline / OPT-DELTA / OPT-BUDGET),
per-direction split, mechanism-implied hybrids, 2x-spread stress,
duration-bucket decomposition. Same fee structure (0.03% of underlying
notional per side capped at 12.5% of premium; settlement 0.015%).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import norm

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "agent"))
from backtest.validation import deflated_sharpe_ratio  # noqa: E402

RAW_PATH = REPO_ROOT / "data" / "parquet" / "sol_usdc_option_trades_deribit.parquet"
DERIVED = Path(__file__).resolve().parent / "derived"

CAPITAL = 1_000_000.0
ENTRY_NOTIONAL = 500_000.0
SPOT_TAKER = 0.001
OPT_FEE_RATE = 0.0003
OPT_FEE_CAP = 0.125
SETTLE_FEE_RATE = 0.00015
PREMIUM_BUDGET_FRAC = 0.10
DTE_BAND = (20, 40)
ENTRY_FWD_DAYS = 3

_RE = re.compile(r"^SOL_USDC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])$")
_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def parse_sol_instruments(names: pd.Index) -> pd.DataFrame:
    rows = []
    for name in names:
        m = _RE.match(name)
        if not m:
            rows.append((name, pd.NaT, np.nan, None))
            continue
        day, mon, yy, strike, cp = m.groups()
        expiry = pd.Timestamp(year=2000 + int(yy), month=_MONTHS[mon], day=int(day), hour=8)
        rows.append((name, expiry, float(strike), cp))
    return pd.DataFrame(rows, columns=["instrument_name", "expiry", "strike", "opt_type"]).set_index("instrument_name")


def bs_usd(S: float, K: float, T: float, sigma: float, opt_type: str) -> tuple[float, float]:
    """Plain USD Black-Scholes (price per 1 unit of underlying, delta)."""
    if T <= 0:
        if opt_type == "C":
            return max(S - K, 0.0), (1.0 if S > K else 0.0)
        return max(K - S, 0.0), (-1.0 if S < K else 0.0)
    vst = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / vst
    d2 = d1 - vst
    if opt_type == "C":
        return max(S * norm.cdf(d1) - K * norm.cdf(d2), 0.0), float(norm.cdf(d1))
    return max(K * norm.cdf(-d2) - S * norm.cdf(-d1), 0.0), float(norm.cdf(d1) - 1.0)


def build_derived(trades: pd.DataFrame):
    """Daily index series + DTE-bucket vol surface from the SOL tape itself."""
    idx = (trades[["date", "trade_dt", "index_price"]].sort_values("trade_dt")
           .groupby("date", as_index=False).last()[["date", "index_price"]]
           .rename(columns={"index_price": "index_close"}).set_index("date")["index_close"])

    buckets = {7.0: (3, 11), 14.0: (11, 21), 30.0: (20, 40), 60.0: (45, 75), 90.0: (75, 105)}
    surf: dict[pd.Timestamp, dict[float, float]] = {}
    for dte_val, (lo, hi) in buckets.items():
        sub = trades[(trades["dte"].between(lo, hi)) & (trades["logm"].abs() < 0.075)]
        g = sub.groupby("date").apply(
            lambda x: (x["iv"] * x["amount"]).sum() / max(x["amount"].sum(), 1e-9),
            include_groups=False,
        )
        for d, iv in g.items():
            surf.setdefault(pd.Timestamp(d), {})[dte_val] = float(iv)
    return idx, surf


def interp_iv(surf_day: dict | None, dte: float, fallback: float) -> float:
    if not surf_day or dte <= 0:
        return fallback
    pts = sorted(surf_day.items())
    dtes = np.array([p[0] for p in pts])
    ivs = np.array([p[1] for p in pts])
    if dte <= dtes[0]:
        return float(ivs[0])
    if dte >= dtes[-1]:
        return float(ivs[-1])
    return float(np.interp(np.log(dte), np.log(dtes), ivs))


def nearest_surf(surf: dict, date: pd.Timestamp, max_back: int = 10):
    d = date
    for _ in range(max_back + 1):
        if d in surf:
            return surf[d]
        d = d - pd.Timedelta(days=1)
    return None


def find_option_entry(trades: pd.DataFrame, anchor: pd.Timestamp, opt_type: str):
    w = trades[
        (trades["trade_dt"] >= anchor)
        & (trades["trade_dt"] <= anchor + pd.Timedelta(days=ENTRY_FWD_DAYS))
        & (trades["opt_type"] == opt_type)
    ]
    if w.empty:
        return None
    row = w.loc[(w["trade_dt"] - anchor).abs().idxmin()]
    return {"entry_dt": row["trade_dt"].floor("D"), "expiry": row["expiry"], "strike": row["strike"],
            "price_usd": row["price"], "iv": row["iv"], "S": row["index_price"]}


def option_leg_pnl(entry, direction, units_sol, idx, surf, leg_end, half_spread):
    opt_type = "C" if direction > 0 else "P"
    expiry = entry["expiry"]
    end = min(pd.Timestamp(expiry).floor("D"), leg_end)
    dates = idx.index[(idx.index >= entry["entry_dt"]) & (idx.index <= end)]
    if len(dates) < 2:
        return pd.Series(dtype=float)

    entry_cost = entry["price_usd"] * (1 + half_spread) * units_sol
    fee = min(OPT_FEE_RATE * entry["S"] * units_sol, OPT_FEE_CAP * entry_cost)

    vals = []
    for d in dates:
        S = idx.loc[d]
        T = max((expiry - d).total_seconds(), 0) / (365 * 86400)
        sigma = max(interp_iv(nearest_surf(surf, d), max(T * 365, 0.5), entry["iv"]), 5.0) / 100.0
        v, _ = bs_usd(S, entry["strike"], T, sigma, opt_type)
        vals.append(v * units_sol)
    vals = np.array(vals)

    S_end = idx.loc[dates[-1]]
    if end >= pd.Timestamp(expiry).floor("D"):
        intrinsic = (max(S_end - entry["strike"], 0.0) if opt_type == "C"
                     else max(entry["strike"] - S_end, 0.0)) * units_sol
        exit_val = intrinsic - min(SETTLE_FEE_RATE * S_end * units_sol, OPT_FEE_CAP * max(intrinsic, 1e-9))
    else:
        exit_val = vals[-1] * (1 - half_spread)

    pnl = pd.Series(0.0, index=dates)
    pnl.iloc[0] = vals[0] - entry_cost - fee
    if len(dates) > 2:
        pnl.iloc[1:-1] = np.diff(vals)[:-1]
    pnl.iloc[-1] = exit_val - vals[-2]
    return pnl


def run_tracks(runs, trades, idx, surf, half_spread):
    spot_pnl, optd_pnl, optb_pnl = {}, {}, {}
    per_run, skipped = [], 0

    for _, r in runs.iterrows():
        start, end, direction = pd.Timestamp(r["start"]), pd.Timestamp(r["end"]), int(r["dir"])
        dates = idx.index[(idx.index >= start) & (idx.index <= end)]
        if len(dates) < 2:
            continue
        S0 = idx.loc[dates[0]]
        qty = ENTRY_NOTIONAL / S0

        s_pnl = pd.Series(direction * qty * np.diff(idx.loc[dates].values), index=dates[1:])
        s_pnl.iloc[0] -= SPOT_TAKER * ENTRY_NOTIONAL
        s_pnl.iloc[-1] -= SPOT_TAKER * qty * idx.loc[dates[-1]]
        for d, v in s_pnl.items():
            spot_pnl[d] = spot_pnl.get(d, 0.0) + v

        run_tot = {"OPT-DELTA": 0.0, "OPT-BUDGET": 0.0}
        entry_found = False
        for label, store in [("OPT-DELTA", optd_pnl), ("OPT-BUDGET", optb_pnl)]:
            leg_start, total = dates[0], 0.0
            while leg_start < dates[-1]:
                entry = find_option_entry(trades, leg_start, "C" if direction > 0 else "P")
                if entry is None or entry["entry_dt"] >= dates[-1]:
                    break
                entry_found = True
                T0 = max((entry["expiry"] - entry["entry_dt"]).total_seconds(), 1) / (365 * 86400)
                _, delta0 = bs_usd(entry["S"], entry["strike"], T0, entry["iv"] / 100.0,
                                   "C" if direction > 0 else "P")
                if label == "OPT-DELTA":
                    units = qty / max(abs(delta0), 0.05)
                else:
                    units = (PREMIUM_BUDGET_FRAC * ENTRY_NOTIONAL) / max(entry["price_usd"] * (1 + half_spread), 1e-9)
                pnl = option_leg_pnl(entry, direction, units, idx, surf, dates[-1], half_spread)
                if pnl.empty:
                    break
                for d, v in pnl.items():
                    store[d] = store.get(d, 0.0) + v
                total += pnl.sum()
                if pnl.index[-1] >= dates[-1]:
                    break
                leg_start = pnl.index[-1] + pd.Timedelta(days=1)
            run_tot[label] = total
        if not entry_found:
            skipped += 1

        per_run.append({"start": dates[0], "dir": direction, "days": int(r["days"]),
                        "spot": s_pnl.sum(), "opt_delta": run_tot["OPT-DELTA"],
                        "opt_budget": run_tot["OPT-BUDGET"]})

    return (pd.Series(spot_pnl).sort_index(), pd.Series(optd_pnl).sort_index(),
            pd.Series(optb_pnl).sort_index(), pd.DataFrame(per_run), skipped)


def metrics(pnl: pd.Series, label: str):
    if pnl.empty:
        print(f"{label:12s} (no data)")
        return
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


def main():
    print("loading SOL_USDC tape...")
    trades = pq.ParquetFile(RAW_PATH).read(
        columns=["instrument_name", "timestamp", "price", "mark_price", "iv", "index_price", "amount"]
    ).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    trades["date"] = trades["trade_dt"].dt.floor("D")
    parsed = parse_sol_instruments(pd.Index(trades["instrument_name"].unique()))
    n_unparsed = parsed["expiry"].isna().sum()
    trades = trades.join(parsed, on="instrument_name").dropna(subset=["expiry", "strike"])
    trades["dte"] = (trades["expiry"] - trades["trade_dt"]).dt.total_seconds() / 86400.0
    trades = trades[trades["dte"] > 0]
    trades["logm"] = np.log(trades["strike"] / trades["index_price"])
    print(f"{len(trades):,} trades parsed ({n_unparsed} instrument names unparsed)")

    idx, surf = build_derived(trades)
    print(f"index days: {len(idx)}, surface days: {len(surf)}")

    atm = trades[(trades["dte"].between(*DTE_BAND)) & (trades["logm"].abs() < 0.075)]
    rel = ((atm["price"] - atm["mark_price"]).abs() / atm["mark_price"].replace(0, np.nan)).dropna()
    half_spread = float(rel.median())
    print(f"SOL empirical half-spread (median |price-mark|/mark, ATM 20-40d): {half_spread*100:.2f}% "
          f"(n={len(rel):,}; BTC tape was 0.61%)")
    print(f"ATM-band entry liquidity: {atm.groupby('date').size().median():.0f} trades/day median")

    runs = pd.read_csv(DERIVED / "sol_direction_runs.csv", parse_dates=["start", "end"])
    for c in ["start", "end"]:
        if runs[c].dt.tz is not None:
            runs[c] = runs[c].dt.tz_localize(None)
    runs = runs[runs["start"] >= idx.index.min()]
    print(f"runs in tape window: {len(runs)} (long={len(runs[runs.dir > 0])}, short={len(runs[runs.dir < 0])})\n")

    entry_pool = trades[(trades["dte"].between(*DTE_BAND)) & (trades["logm"].abs() < 0.075)]

    sides = {}
    for d in (1, -1):
        sides[d] = run_tracks(runs[runs["dir"] == d], entry_pool, idx, surf, half_spread)

    def combo(lk_idx: int, sk_idx: int) -> pd.Series:
        return sides[1][lk_idx].add(sides[-1][sk_idx], fill_value=0.0).sort_index()

    print(f"option-entry-skipped runs: long={sides[1][4]}, short={sides[-1][4]}")
    print("\n=== Tracks and hybrids (0=spot, 1=opt-delta, 2=opt-budget) ===")
    metrics(combo(0, 0), "SPOT/SPOT")
    metrics(combo(1, 1), "OPTD/OPTD")
    metrics(combo(2, 2), "OPTB/OPTB")
    metrics(combo(0, 2), "H1 S/OB")
    metrics(combo(1, 2), "H2 OD/OB")
    metrics(combo(0, 1), "H3 S/OD")

    per_run = pd.concat([sides[1][3], sides[-1][3]], ignore_index=True)
    per_run["bucket"] = pd.cut(per_run["days"], [0, 8, 30, 9999], labels=["<8d", "8-30d", ">30d"])
    print("\n--- per-run P&L by duration bucket ---")
    print(per_run.groupby("bucket", observed=True)[["spot", "opt_delta", "opt_budget"]]
          .agg(["sum", "count"]).round(0).to_string())
    print("\n--- by direction ---")
    print(per_run.groupby("dir")[["spot", "opt_delta", "opt_budget"]].sum().round(0).to_string())
    per_run.to_csv(DERIVED / "phase5_sol_per_run.csv", index=False)

    # 2x-spread stress on the option tracks
    print("\n=== Stress: 2x half-spread ===")
    sides2 = {d: run_tracks(runs[runs["dir"] == d], entry_pool, idx, surf, half_spread * 2) for d in (1, -1)}

    def combo2(lk, sk):
        return sides2[1][lk].add(sides2[-1][sk], fill_value=0.0).sort_index()

    metrics(combo2(1, 1), "OPTD/OPTD*")
    metrics(combo2(2, 2), "OPTB/OPTB*")
    metrics(combo2(0, 2), "H1 S/OB*")
    metrics(combo2(0, 1), "H3 S/OD*")


if __name__ == "__main__":
    main()
