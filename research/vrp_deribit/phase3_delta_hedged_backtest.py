"""
Phase 3: delta-hedged short straddle -- the follow-on §72.4 left open, plus
corrections for two methodology defects found auditing phase 2.

Pre-registered design (before running):

  Variants (2, mirroring phase 2's pre-registration exactly):
    - UNCONDITIONAL: short one ~30-DTE ATM straddle every month.
    - IV-CONDITIONAL: same, gated on trailing ATM-30d IV > trailing 2y median
      (live-safe, strictly-before-entry data only).
  Both run WITH a daily delta hedge (BS delta, hedged with a linear BTC
  position, e.g. a perp), and the same run WITHOUT the hedge as the control,
  so the hedging effect is isolated under identical, corrected mechanics.

  Corrections vs. phase 2 (both verified defects, findings §73):
    1. No-lookahead entry: candidate trades are drawn only from
       [anchor, anchor+3d] (you cannot transact a print from 3 days ago),
       the strike is chosen against the FIRST index print at/after anchor,
       and marking starts at the actual entry-trade date, not the anchor.
    2. Full-calendar Sharpe: equity is reindexed to every calendar day
       (flat days = zero P&L) before computing Sharpe/DSR, so a gated
       variant that sits out 70% of the time cannot inflate its Sharpe by
       having its idle days dropped (phase 2's conditional 0.59 was 0.32
       on this basis).

  Hedge mechanics: at each daily mark, portfolio delta of the short straddle
  = -(N(d1)_call + (N(d1)-1)_put) * contracts (standard USD BS deltas, using
  the same trade-derived ATM term-structure sigma as the marks); the hedge
  holds the offsetting linear BTC position. Costs: taker fee 0.05% on
  |change in hedge notional| each rebalance (Deribit perp taker rate, per
  §41.2), plus perp funding at the platform's standard 0.0001/8h on the
  signed hedge notional (long pays / short receives -- the repo's standard
  perp funding model).

  Sizing/fees otherwise identical to phase 2 (same margin model, same real
  entry premiums, same empirical half-spread haircut, same Deribit option
  fee cap), so phase-2 vs phase-3 differences are attributable to the listed
  changes only. Headline at 10% margin utilization; 20%/30% reported as
  sensitivity. Offset sweep {0,5,10,15,20,25} days on the monthly anchor,
  per the platform's standing rebalance-timing-luck discipline.

  Promotion bar (unchanged from the H2 plan): net Sharpe ~>= 1.0 with a
  survivable COVID-scale tail. DSR reported with n_trials=4 (2 variants x
  {hedged, unhedged}).
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest.validation import deflated_sharpe_ratio  # noqa: E402
from data_prep import parse_instruments  # noqa: E402

RAW_PATH = REPO_ROOT / "data" / "parquet" / "btc_option_trades_deribit.parquet"
DERIVED = Path(__file__).resolve().parent / "derived"

TARGET_DTE = 30
DTE_TOLERANCE_BAND = (20, 40)
ENTRY_SEARCH_FORWARD_DAYS = 3  # [anchor, anchor+3d] only -- no backward look
DERIBIT_FEE_RATE = 0.0003
DERIBIT_FEE_CAP_FRAC_OF_PREMIUM = 0.125
MARGIN_FRACTION_PER_LEG = 0.15
INITIAL_CAPITAL = 1_000_000.0
PERP_TAKER_RATE = 0.0005      # 0.05% on hedge notional traded (§41.2)
PERP_FUNDING_8H = 0.0001      # long pays, short receives; 3x/day
N_TRIALS_PREREGISTERED = 4    # 2 variants x {hedged, unhedged}


def build_vol_surface(term: pd.DataFrame) -> dict:
    bucket_dte = {"7d": 7.0, "14d": 14.0, "30d": 30.0, "60d": 60.0, "90d": 90.0}
    term = term.copy()
    term["dte_val"] = term["dte_bucket"].map(bucket_dte)
    return {pd.Timestamp(d): dict(zip(g["dte_val"], g["iv"])) for d, g in term.groupby("date")}


def interp_iv(surf_for_day: dict | None, dte: float, fallback: float) -> float:
    if not surf_for_day or dte <= 0:
        return fallback
    pts = sorted(surf_for_day.items())
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


def bs_price_and_delta(S: float, K: float, T: float, sigma: float, opt_type: str) -> tuple[float, float]:
    """Returns (BTC-denominated price, USD BS delta) -- same pricing
    convention as phase 2, plus the delta needed for hedging."""
    if T <= 0:
        if opt_type == "C":
            return max(S - K, 0.0) / S, (1.0 if S > K else 0.0)
        return max(K - S, 0.0) / S, (-1.0 if S < K else 0.0)
    vol_sqrt_t = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    if opt_type == "C":
        usd = S * norm.cdf(d1) - K * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        usd = K * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1.0
    return max(usd, 0.0) / S, float(delta)


def find_straddle_entry(trades: pd.DataFrame, anchor_date: pd.Timestamp, target_dte: int = TARGET_DTE):
    """Corrected entry: forward-only window, strike chosen against the first
    index print at/after anchor, entry stamped at the actual trade time."""
    window = trades[
        (trades["trade_dt"] >= anchor_date)
        & (trades["trade_dt"] <= anchor_date + pd.Timedelta(days=ENTRY_SEARCH_FORWARD_DAYS))
    ]
    if window.empty:
        return None

    band_lo, band_hi = DTE_TOLERANCE_BAND
    cand = window[window["dte"].between(band_lo, band_hi)]
    if cand.empty:
        window = window.copy()
        window["dte_dist"] = (window["dte"] - target_dte).abs()
        best_expiry = window.loc[window["dte_dist"].idxmin(), "expiry"]
        cand = window[window["expiry"] == best_expiry]

    calls = cand[cand["opt_type"] == "C"]
    puts = cand[cand["opt_type"] == "P"]
    common_strikes = set(calls["strike"]).intersection(set(puts["strike"]))
    if not common_strikes:
        return None

    spot_est = cand.sort_values("trade_dt")["index_price"].iloc[0]  # FIRST print, not last
    best_strike = min(common_strikes, key=lambda k: abs(k - spot_est))

    calls_k = calls[calls["strike"] == best_strike]
    puts_k = puts[puts["strike"] == best_strike]
    call_row = calls_k.loc[(calls_k["trade_dt"] - anchor_date).abs().idxmin()]
    put_row = puts_k.loc[(puts_k["trade_dt"] - anchor_date).abs().idxmin()]
    entry_dt = max(call_row["trade_dt"], put_row["trade_dt"]).floor("D")

    return {
        "entry_date": entry_dt,
        "expiry": call_row["expiry"],
        "strike": best_strike,
        "call_entry_price": call_row["price"],
        "put_entry_price": put_row["price"],
        "index_at_entry": (call_row["index_price"] + put_row["index_price"]) / 2,
        "call_entry_iv": call_row["iv"],
        "put_entry_iv": put_row["iv"],
    }


def simulate_trade(entry: dict, idx_series: pd.Series, surf: dict, dataset_end: pd.Timestamp,
                   contracts: float, hedged: bool) -> pd.Series | None:
    """Daily USD P&L series for one short straddle (optionally delta-hedged)."""
    strike, expiry = entry["strike"], entry["expiry"]
    end = min(expiry, dataset_end)
    dates = idx_series.index[(idx_series.index >= entry["entry_date"]) & (idx_series.index <= end)]
    if len(dates) < 2:
        return None

    fallback_iv = (entry["call_entry_iv"] + entry["put_entry_iv"]) / 2
    straddle_vals, deltas, spots = [], [], []
    for d in dates:
        S = idx_series.loc[d]
        T = max((expiry - d).total_seconds(), 0) / (365 * 86400)
        sigma = interp_iv(nearest_surf(surf, d), max(T * 365, 0.5), fallback_iv) / 100.0
        sigma = max(sigma, 0.05)
        cv, cd = bs_price_and_delta(S, strike, T, sigma, "C")
        pv, pdlt = bs_price_and_delta(S, strike, T, sigma, "P")
        straddle_vals.append((cv + pv) * S * contracts)
        deltas.append((cd + pdlt) * contracts)  # straddle delta in BTC units (long-straddle sign)
        spots.append(S)

    straddle_vals = np.array(straddle_vals)
    deltas = np.array(deltas)
    spots = np.array(spots)

    # short-option P&L: change in (premium - liability) day over day
    option_pnl = -np.diff(straddle_vals)

    hedge_pnl = np.zeros(len(dates) - 1)
    hedge_costs = np.zeros(len(dates) - 1)
    if hedged:
        # short straddle position delta = -deltas; hedge holds +deltas BTC
        hedge_pos = deltas
        hedge_pnl = hedge_pos[:-1] * np.diff(spots)
        # fee on initial hedge + each daily adjustment (aligned to pnl days)
        adj = np.abs(np.diff(hedge_pos)) * spots[1:]
        hedge_costs = adj * PERP_TAKER_RATE
        hedge_costs[0] += abs(hedge_pos[0]) * spots[0] * PERP_TAKER_RATE
        # funding: signed, long pays, 3 settlements/day on held notional
        funding = hedge_pos[:-1] * spots[:-1] * PERP_FUNDING_8H * 3
        hedge_costs += funding
        # close-out fee at final day
        hedge_costs[-1] += abs(hedge_pos[-1]) * spots[-1] * PERP_TAKER_RATE

    daily = option_pnl + hedge_pnl - hedge_costs

    entry_premium_btc = (entry["call_entry_price"] + entry["put_entry_price"])
    pnl = pd.Series(daily, index=dates[1:])
    # day-0 economics: premium actually collected (post-haircut, applied by
    # caller) vs. day-0 model mark, plus option entry fee -- handled by caller
    return pnl, straddle_vals[0], len(dates)


def run_backtest(trades, idx_df, surf, anchor_dates, util, hedged,
                 iv_conditional=False, atm_iv_series=None, spread_haircut=0.0):
    idx_series = idx_df.set_index("date")["index_close"]
    dataset_end = idx_series.index.max()
    per_trade, trade_log, skipped = [], [], 0

    for anchor in anchor_dates:
        if iv_conditional and atm_iv_series is not None:
            trailing = atm_iv_series[atm_iv_series.index < anchor].tail(730)
            if len(trailing) < 60:
                continue
            current = atm_iv_series[atm_iv_series.index < anchor]  # strictly before anchor
            if current.empty or current.iloc[-1] < trailing.median():
                continue

        entry = find_straddle_entry(trades, anchor)
        if entry is None:
            skipped += 1
            continue

        margin_per_straddle_usd = 2 * MARGIN_FRACTION_PER_LEG * entry["index_at_entry"]
        contracts = INITIAL_CAPITAL * util / margin_per_straddle_usd

        sim = simulate_trade(entry, idx_series, surf, dataset_end, contracts, hedged)
        if sim is None:
            skipped += 1
            continue
        pnl, day0_liability, n_days = sim

        entry_premium_btc = (entry["call_entry_price"] + entry["put_entry_price"]) * (1 - spread_haircut)
        entry_premium_usd = entry_premium_btc * entry["index_at_entry"] * contracts
        fee_usd = min(
            2 * DERIBIT_FEE_RATE * entry["index_at_entry"] * contracts,
            DERIBIT_FEE_CAP_FRAC_OF_PREMIUM * entry_premium_usd,
        )
        # book the entry-day economics on the first P&L day
        pnl.iloc[0] += entry_premium_usd - day0_liability - fee_usd
        per_trade.append(pnl)
        trade_log.append({
            "entry_date": entry["entry_date"], "expiry": entry["expiry"], "strike": entry["strike"],
            "contracts": contracts, "entry_premium_usd": entry_premium_usd,
            "final_pnl_usd": pnl.sum(), "index_at_entry": entry["index_at_entry"],
        })

    if not per_trade:
        return None, None, skipped
    total = pd.concat(per_trade, axis=1).sum(axis=1).sort_index()
    # FULL-CALENDAR equity: reindex to every day in the overall span
    cal = pd.date_range(total.index.min(), total.index.max(), freq="D", tz="UTC")
    total = total.reindex(cal, fill_value=0.0)
    equity = INITIAL_CAPITAL + total.cumsum()
    return equity, pd.DataFrame(trade_log), skipped


def compute_metrics(equity: pd.Series, n_trials: int = N_TRIALS_PREREGISTERED) -> dict:
    rets = equity.pct_change().dropna()
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    n_years = (equity.index[-1] - equity.index[0]).days / 365.25
    ann = (1 + total_return) ** (1 / n_years) - 1
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else float("nan")
    dd = (equity - equity.cummax()) / equity.cummax()
    dsr = deflated_sharpe_ratio(rets.values, n_trials=n_trials, bars_per_year=365)
    return {"ann": ann, "sharpe": sharpe, "max_dd": dd.min(), "total": total_return,
            "dsr": dsr["dsr"], "psr": dsr["psr_at_zero"]}


def fmt(m):
    return (f"ann={m['ann']*100:6.1f}%  sharpe={m['sharpe']:5.2f}  maxDD={m['max_dd']*100:6.1f}%  "
            f"DSR={m['dsr']*100:5.1f}%  PSR={m['psr']*100:5.1f}%")


def main():
    print("loading raw trade tape...")
    pf = pq.ParquetFile(RAW_PATH)
    trades = pf.read(columns=["instrument_name", "timestamp", "price", "mark_price", "iv",
                              "index_price", "amount"]).to_pandas()
    trades["trade_dt"] = pd.to_datetime(trades["timestamp"], unit="ms", utc=True)
    uniq = pd.Index(trades["instrument_name"].unique())
    parsed = parse_instruments(uniq)
    trades = trades.join(parsed, on="instrument_name").dropna(subset=["expiry", "strike"])
    trades["dte"] = (trades["expiry"] - trades["trade_dt"]).dt.total_seconds() / 86400.0
    trades = trades[trades["dte"] > 0]

    idx_df = pd.read_csv(DERIVED / "daily_index.csv", parse_dates=["date"])
    term = pd.read_csv(DERIVED / "term_structure.csv", parse_dates=["date"])
    atm = pd.read_csv(DERIVED / "atm_iv_30d.csv", parse_dates=["date"]).set_index("date")["atm_iv_30d"]
    surf = build_vol_surface(term)

    atm_mask = (trades["dte"].between(20, 40)) & ((np.log(trades["strike"] / trades["index_price"])).abs() < 0.075)
    rel_dev = ((trades.loc[atm_mask, "price"] - trades.loc[atm_mask, "mark_price"]).abs()
               / trades.loc[atm_mask, "mark_price"].replace(0, np.nan)).dropna()
    half_spread = float(rel_dev.median())
    print(f"empirical half-spread: {half_spread*100:.2f}%")

    anchor_dates = list(pd.date_range(pd.Timestamp("2020-01-01", tz="UTC"), idx_df["date"].max(), freq="MS"))

    results = {}
    for hedged in [False, True]:
        for cond in [False, True]:
            label = f"{'HEDGED' if hedged else 'UNHEDGED'}-{'COND' if cond else 'UNCOND'}"
            eq, tl, skip = run_backtest(trades, idx_df, surf, anchor_dates, util=0.10, hedged=hedged,
                                        iv_conditional=cond, atm_iv_series=atm, spread_haircut=half_spread)
            m = compute_metrics(eq)
            results[label] = (eq, tl, m)
            print(f"{label:16s} n_trades={len(tl):3d} skipped={skip:2d}  {fmt(m)}")
            eq.rename("equity").to_csv(DERIVED / f"phase3_equity_{label}.csv")
            tl.to_csv(DERIVED / f"phase3_trades_{label}.csv", index=False)

    # sizing sensitivity for the hedged variants
    print("\n--- sizing sensitivity (hedged) ---")
    for util in [0.20, 0.30]:
        for cond in [False, True]:
            eq, tl, _ = run_backtest(trades, idx_df, surf, anchor_dates, util=util, hedged=True,
                                     iv_conditional=cond, atm_iv_series=atm, spread_haircut=half_spread)
            m = compute_metrics(eq)
            print(f"util={util:.0%} {'COND' if cond else 'UNCOND':6s}  {fmt(m)}")

    # offset sweep (hedged, both variants)
    print("\n--- offset sweep (hedged, util=10%) ---")
    for cond in [False, True]:
        row = []
        for off in [0, 5, 10, 15, 20, 25]:
            anchors = [a + pd.Timedelta(days=off) for a in anchor_dates]
            eq, tl, _ = run_backtest(trades, idx_df, surf, anchors, util=0.10, hedged=True,
                                     iv_conditional=cond, atm_iv_series=atm, spread_haircut=half_spread)
            m = compute_metrics(eq)
            row.append(f"+{off}d:{m['sharpe']:.2f}")
        print(f"{'COND' if cond else 'UNCOND':6s}  " + "  ".join(row))

    # worst trades / tail check for the hedged unconditional
    _, tl, _ = results["HEDGED-UNCOND"][0], results["HEDGED-UNCOND"][1], None
    print("\n--- worst 5 hedged-unconditional trades ---")
    print(tl.nsmallest(5, "final_pnl_usd")[["entry_date", "strike", "entry_premium_usd", "final_pnl_usd"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
