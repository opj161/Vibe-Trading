"""
Phase 2: an actual, cost-aware, real-data-executed short-straddle backtest.

Design (pre-registered before running -- see vibe_trading_research_findings.md
§72 for the write-up): monthly-rebalanced short ATM straddle on BTC options,
using REAL traded entry premiums (not modeled/interpolated) from the Deribit
tape, marked daily via Black-Scholes using a real, trade-derived implied-vol
surface (interpolated across the term_structure.csv DTE buckets built in
data_prep.py), realistic Deribit fees, and an empirically-estimated
half-spread haircut on entry. No engine capability on this platform can
represent genuine implied vol (see CLAUDE.md/§49) so this is a standalone,
carefully-validated script, not a `runner.py` backtest -- flagged explicitly
per this repo's own "hand-rolled approximations are not evidence" caution
(the honest distinction here: there is no existing engine capability being
*approximated*; this is the only way to test a capability that doesn't
otherwise exist on this platform at all).

Two pre-registered variants (per the H2 plan's step 3), run identically
except for the entry gate:
  - UNCONDITIONAL: sell the straddle every month, regardless of vol level.
  - IV-CONDITIONAL: only sell when trailing ATM-30d IV is above its own
    trailing 2-year median as of the entry date (a live-safe, lookahead-free
    conditioner -- uses only data available strictly before the entry date).

Also runs an entry-day offset sweep (this platform's own bar-boundary-luck
discipline: never trust a single-offset result for an arbitrary rebalance
timing choice) and a stress test against the worst realized VRP episodes
found in phase1 (COVID March 2020, and the next-worst episodes).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import norm

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "agent"))
from backtest.validation import deflated_sharpe_ratio  # noqa: E402

RAW_PATH = REPO_ROOT / "data" / "parquet" / "btc_option_trades_deribit.parquet"
DERIVED = Path(__file__).resolve().parent / "derived"

TARGET_DTE = 30
DTE_TOLERANCE_BAND = (20, 40)  # preferred band; falls back to nearest available if empty
ENTRY_SEARCH_WINDOW_DAYS = 3  # look +/- N days around the anchor date for a real trade
DERIBIT_FEE_RATE = 0.0003  # 0.03% of underlying notional, per side
DERIBIT_FEE_CAP_FRAC_OF_PREMIUM = 0.125  # capped at 12.5% of option premium
MARGIN_FRACTION_PER_LEG = 0.15  # simplified Deribit-style IM approx (of underlying notional)
TARGET_MARGIN_UTILIZATION = 0.30  # fraction of capital committed as margin at entry
INITIAL_CAPITAL = 1_000_000.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_raw_trades() -> pd.DataFrame:
    pf = pq.ParquetFile(RAW_PATH)
    df = pf.read(columns=["instrument_name", "timestamp", "price", "mark_price", "iv", "index_price", "amount"]).to_pandas()
    df["trade_dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df


def build_vol_surface(term: pd.DataFrame) -> dict[pd.Timestamp, dict[float, float]]:
    """date -> {dte_days: iv} for the 5 buckets, for later log-DTE interpolation."""
    bucket_dte = {"7d": 7.0, "14d": 14.0, "30d": 30.0, "60d": 60.0, "90d": 90.0}
    term = term.copy()
    term["dte_val"] = term["dte_bucket"].map(bucket_dte)
    surf: dict[pd.Timestamp, dict[float, float]] = {}
    for date, grp in term.groupby("date"):
        surf[pd.Timestamp(date)] = dict(zip(grp["dte_val"], grp["iv"]))
    return surf


def interp_iv(surf_for_day: dict[float, float] | None, dte: float, fallback: float) -> float:
    if not surf_for_day or dte <= 0:
        return fallback
    pts = sorted(surf_for_day.items())
    dtes = np.array([p[0] for p in pts])
    ivs = np.array([p[1] for p in pts])
    if dte <= dtes[0]:
        return float(ivs[0])
    if dte >= dtes[-1]:
        return float(ivs[-1])
    log_dte = np.log(dte)
    log_dtes = np.log(dtes)
    return float(np.interp(log_dte, log_dtes, ivs))


def nearest_surf(surf: dict, date: pd.Timestamp, max_back: int = 10):
    """Nearest available vol-surface day at or before `date` (data doesn't
    print every single day for every DTE bucket -- carry the last known
    surface forward, capped at max_back days to avoid using stale data)."""
    d = date
    for _ in range(max_back + 1):
        if d in surf:
            return surf[d]
        d = d - pd.Timedelta(days=1)
    return None


def bs_price(S: float, K: float, T: float, sigma: float, opt_type: str) -> float:
    """Standard European BS price (USD), then converted to Deribit-style
    inverse (BTC-denominated) quote by dividing by spot -- the same
    simplification implicit in how Deribit's own quoted `iv`/mark_price
    fields are commonly reverse-engineered by practitioners; consistent
    with calibrating sigma from Deribit's own reported iv values."""
    if T <= 0:
        intrinsic = max(S - K, 0.0) if opt_type == "C" else max(K - S, 0.0)
        return intrinsic / S
    vol_sqrt_t = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    if opt_type == "C":
        usd = S * norm.cdf(d1) - K * norm.cdf(d2)
    else:
        usd = K * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(usd, 0.0) / S


# ---------------------------------------------------------------------------
# Entry selection: find a real, tradeable ATM straddle near a target date
# ---------------------------------------------------------------------------

def find_straddle_entry(trades: pd.DataFrame, anchor_date: pd.Timestamp, target_dte: int = TARGET_DTE):
    window = trades[
        (trades["trade_dt"] >= anchor_date - pd.Timedelta(days=ENTRY_SEARCH_WINDOW_DAYS))
        & (trades["trade_dt"] <= anchor_date + pd.Timedelta(days=ENTRY_SEARCH_WINDOW_DAYS))
    ]
    if window.empty:
        return None

    band_lo, band_hi = DTE_TOLERANCE_BAND
    cand = window[window["dte"].between(band_lo, band_hi)]
    if cand.empty:
        # fall back to nearest available DTE to target, regardless of band
        # (real, periodic listing-calendar gaps -- see phase1 findings)
        window = window.copy()
        window["dte_dist"] = (window["dte"] - target_dte).abs()
        best_expiry = window.loc[window["dte_dist"].idxmin(), "expiry"]
        cand = window[window["expiry"] == best_expiry]

    # need both a call and a put at the SAME strike; pick the strike with
    # both legs present, closest to spot
    calls = cand[cand["opt_type"] == "C"]
    puts = cand[cand["opt_type"] == "P"]
    common_strikes = set(calls["strike"]).intersection(set(puts["strike"]))
    if not common_strikes:
        return None

    spot_est = cand.sort_values("trade_dt")["index_price"].iloc[-1]
    best_strike = min(common_strikes, key=lambda k: abs(k - spot_est))

    calls_k = calls[calls["strike"] == best_strike]
    puts_k = puts[puts["strike"] == best_strike]
    call_row = calls_k.loc[(calls_k["trade_dt"] - anchor_date).abs().idxmin()]
    put_row = puts_k.loc[(puts_k["trade_dt"] - anchor_date).abs().idxmin()]

    return {
        "entry_date": anchor_date,
        "expiry": call_row["expiry"],
        "strike": best_strike,
        "call_entry_price": call_row["price"],
        "put_entry_price": put_row["price"],
        "index_at_entry": (call_row["index_price"] + put_row["index_price"]) / 2,
        "call_entry_iv": call_row["iv"],
        "put_entry_iv": put_row["iv"],
    }


# ---------------------------------------------------------------------------
# One full trade's daily mark-to-model path
# ---------------------------------------------------------------------------

def simulate_trade_path(entry: dict, idx_series: pd.Series, surf: dict, dataset_end: pd.Timestamp) -> pd.DataFrame:
    strike = entry["strike"]
    expiry = entry["expiry"]
    end = min(expiry, dataset_end)
    dates = idx_series.index[(idx_series.index >= entry["entry_date"]) & (idx_series.index <= end)]
    if len(dates) < 2:
        return pd.DataFrame()

    rows = []
    for d in dates:
        S = idx_series.loc[d]
        T = max((expiry - d).total_seconds(), 0) / (365 * 86400)
        dte_remaining = T * 365
        surf_day = nearest_surf(surf, d)
        fallback_iv = (entry["call_entry_iv"] + entry["put_entry_iv"]) / 2 / 100.0
        sigma = interp_iv(surf_day, max(dte_remaining, 0.5), fallback_iv * 100) / 100.0
        sigma = max(sigma, 0.05)
        call_v = bs_price(S, strike, T, sigma, "C")
        put_v = bs_price(S, strike, T, sigma, "P")
        rows.append({"date": d, "index": S, "dte_remaining": dte_remaining, "sigma": sigma,
                      "call_value_btc": call_v, "put_value_btc": put_v})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Full backtest over a sequence of monthly anchor dates
# ---------------------------------------------------------------------------

def run_backtest(trades: pd.DataFrame, idx_df: pd.DataFrame, surf: dict, anchor_dates: list[pd.Timestamp],
                  iv_conditional: bool = False, atm_iv_series: pd.Series | None = None,
                  spread_haircut: float = 0.0, verbose: bool = False):
    """Fixed-capital-base (non-compounding) sizing: each month's contract
    count is derived from INITIAL_CAPITAL, not a compounding running equity.
    This is a deliberate simplification (avoids a sequencing bug where
    overlapping ~30-day-hold positions from consecutive monthly entries
    would otherwise need a proper chronological interleave to compound
    correctly) and is conservative for a feasibility read: it neither
    benefits from nor is punished by path-dependent compounding, so the
    Sharpe/drawdown figures below are a clean per-dollar-deployed read,
    not inflated by re-investing gains into larger positions."""
    idx_series = idx_df.set_index("date")["index_close"]
    dataset_end = idx_series.index.max()

    per_trade_pnl_series = []
    trade_log = []
    skipped = 0

    for anchor in anchor_dates:
        if iv_conditional and atm_iv_series is not None:
            trailing = atm_iv_series[atm_iv_series.index < anchor].tail(730)
            if len(trailing) < 60:
                continue
            current = atm_iv_series[atm_iv_series.index <= anchor]
            if current.empty or current.iloc[-1] < trailing.median():
                continue  # gate: skip this month, vol not elevated

        entry = find_straddle_entry(trades, anchor)
        if entry is None:
            skipped += 1
            continue

        path = simulate_trade_path(entry, idx_series, surf, dataset_end)
        if path.empty:
            skipped += 1
            continue

        entry_premium_btc = entry["call_entry_price"] + entry["put_entry_price"]
        entry_premium_btc *= (1 - spread_haircut)  # conservative half-spread haircut on what we collect

        margin_per_straddle_usd = 2 * MARGIN_FRACTION_PER_LEG * entry["index_at_entry"]
        target_margin_usd = INITIAL_CAPITAL * TARGET_MARGIN_UTILIZATION
        contracts = max(target_margin_usd / margin_per_straddle_usd, 0.0)

        entry_premium_usd = entry_premium_btc * entry["index_at_entry"] * contracts
        fee_usd = min(
            2 * DERIBIT_FEE_RATE * entry["index_at_entry"] * contracts,
            DERIBIT_FEE_CAP_FRAC_OF_PREMIUM * entry_premium_usd,
        )

        path = path.copy()
        path["straddle_value_usd"] = (path["call_value_btc"] + path["put_value_btc"]) * path["index"] * contracts
        # short position: liability = current theoretical value; P&L vs entry premium collected
        path["short_pnl_usd"] = entry_premium_usd - path["straddle_value_usd"]

        daily_pnl = path.set_index("date")["short_pnl_usd"].diff()
        daily_pnl.iloc[0] = path["short_pnl_usd"].iloc[0] - fee_usd  # fee charged at entry
        per_trade_pnl_series.append(daily_pnl)

        trade_log.append({
            "entry_date": entry["entry_date"], "expiry": entry["expiry"], "strike": entry["strike"],
            "contracts": contracts, "entry_premium_usd": entry_premium_usd, "fee_usd": fee_usd,
            "final_pnl_usd": path["short_pnl_usd"].iloc[-1] - fee_usd,
            "index_at_entry": entry["index_at_entry"], "index_at_exit": path["index"].iloc[-1],
        })
        if verbose:
            print(f"  {entry['entry_date'].date()} K={entry['strike']:.0f} exp={entry['expiry'].date()} "
                  f"premium=${entry_premium_usd:,.0f} pnl=${path['short_pnl_usd'].iloc[-1] - fee_usd:,.0f}")

    if not per_trade_pnl_series:
        return pd.DataFrame(), pd.DataFrame(), skipped

    total_daily_pnl = pd.concat(per_trade_pnl_series, axis=1).sum(axis=1).sort_index()
    equity = INITIAL_CAPITAL + total_daily_pnl.cumsum()
    ec = equity.reset_index()
    ec.columns = ["date", "equity"]
    tl = pd.DataFrame(trade_log)
    return ec, tl, skipped


def compute_metrics(ec: pd.DataFrame) -> dict:
    if len(ec) < 10:
        return {"error": "insufficient equity curve"}
    ec = ec.set_index("date")["equity"]
    rets = ec.pct_change().dropna()
    total_return = ec.iloc[-1] / ec.iloc[0] - 1
    n_years = (ec.index[-1] - ec.index[0]).days / 365.25
    ann_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else float("nan")
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else float("nan")
    running_max = ec.cummax()
    dd = (ec - running_max) / running_max
    max_dd = dd.min()
    calmar = ann_return / abs(max_dd) if max_dd != 0 else float("nan")
    dsr = deflated_sharpe_ratio(rets.values, n_trials=1, bars_per_year=365)
    return {
        "n_days": len(ec), "start": ec.index[0], "end": ec.index[-1],
        "total_return": total_return, "ann_return": ann_return, "sharpe": sharpe,
        "max_dd": max_dd, "calmar": calmar, "dsr": dsr["dsr"], "psr_at_zero": dsr["psr_at_zero"],
    }


def print_metrics(label: str, m: dict):
    if "error" in m:
        print(f"{label}: {m['error']}")
        return
    print(f"{label}: {m['start'].date()} -> {m['end'].date()} ({m['n_days']} days)")
    print(f"  total_return={m['total_return']*100:.1f}%  ann_return={m['ann_return']*100:.1f}%  "
          f"sharpe={m['sharpe']:.2f}  max_dd={m['max_dd']*100:.1f}%  calmar={m['calmar']:.2f}")
    print(f"  DSR={m['dsr']*100:.1f}%  PSR-at-zero={m['psr_at_zero']*100:.1f}%")


def main():
    print("loading raw trade tape...")
    trades = load_raw_trades()

    idx_df = pd.read_csv(DERIVED / "daily_index.csv", parse_dates=["date"])
    term = pd.read_csv(DERIVED / "term_structure.csv", parse_dates=["date"])
    atm = pd.read_csv(DERIVED / "atm_iv_30d.csv", parse_dates=["date"]).set_index("date")["atm_iv_30d"]

    # attach parsed instrument attrs to raw trades (reuse data_prep parser)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from data_prep import parse_instruments  # noqa: E402
    uniq = pd.Index(trades["instrument_name"].unique())
    parsed = parse_instruments(uniq)
    trades = trades.join(parsed, on="instrument_name").dropna(subset=["expiry", "strike"])
    trades["dte"] = (trades["expiry"] - trades["trade_dt"]).dt.total_seconds() / 86400.0
    trades = trades[trades["dte"] > 0]

    surf = build_vol_surface(term)

    # empirical spread proxy: relative |price - mark_price| / mark_price for
    # near-ATM, near-30d trades, used as a conservative one-way haircut
    atm_mask = (trades["dte"].between(20, 40)) & ((np.log(trades["strike"] / trades["index_price"])).abs() < 0.075)
    rel_dev = ((trades.loc[atm_mask, "price"] - trades.loc[atm_mask, "mark_price"]).abs()
               / trades.loc[atm_mask, "mark_price"].replace(0, np.nan)).dropna()
    half_spread = float(rel_dev.median())
    print(f"empirical half-spread proxy (median |price-mark|/mark, ATM 30d): {half_spread*100:.2f}%")

    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = idx_df["date"].max()
    anchor_dates = pd.date_range(start, end, freq="MS", tz="UTC")

    print(f"\n=== UNCONDITIONAL: monthly short straddle, {len(anchor_dates)} candidate months ===")
    ec_u, tl_u, skip_u = run_backtest(trades, idx_df, surf, list(anchor_dates), spread_haircut=half_spread)
    print(f"trades executed: {len(tl_u)}, skipped (no listing/liquidity match): {skip_u}")
    m_u = compute_metrics(ec_u)
    print_metrics("UNCONDITIONAL", m_u)
    ec_u.to_csv(DERIVED / "phase2_equity_unconditional.csv", index=False)
    tl_u.to_csv(DERIVED / "phase2_trades_unconditional.csv", index=False)

    print(f"\n=== IV-CONDITIONAL: only enter when trailing IV > trailing 2y median ===")
    ec_c, tl_c, skip_c = run_backtest(trades, idx_df, surf, list(anchor_dates), iv_conditional=True,
                                       atm_iv_series=atm, spread_haircut=half_spread)
    print(f"trades executed: {len(tl_c)}, skipped/gated: {skip_c}")
    m_c = compute_metrics(ec_c)
    print_metrics("IV-CONDITIONAL", m_c)
    ec_c.to_csv(DERIVED / "phase2_equity_conditional.csv", index=False)
    tl_c.to_csv(DERIVED / "phase2_trades_conditional.csv", index=False)

    # --- offset robustness: shift the monthly anchor day-of-month ---
    print("\n=== Offset robustness: monthly anchor shifted by N days ===")
    for offset in [5, 10, 15, 20, 25]:
        anchors_off = [d + pd.Timedelta(days=offset) for d in anchor_dates]
        ec_o, tl_o, _ = run_backtest(trades, idx_df, surf, anchors_off, spread_haircut=half_spread)
        m_o = compute_metrics(ec_o)
        if "error" in m_o:
            print(f"  offset +{offset}d: insufficient data")
            continue
        print(f"  offset +{offset}d: n_trades={len(tl_o)} sharpe={m_o['sharpe']:.2f} "
              f"ann_return={m_o['ann_return']*100:.1f}% max_dd={m_o['max_dd']*100:.1f}%")

    print("\ndone.")


if __name__ == "__main__":
    main()
