"""Direction 2 (vibe_trading_forensics_new_directions.md): post-hoc real-
funding-rate attribution over the champion's actual forward-year positions.

Re-attributes fwd_Z8_20260702 / fwd_ZA4_20260702's realized daily positions
(artifacts/positions.csv, weight fraction of equity) against two funding
models, both applied at Binance's real 3x/day settlement cadence
({00,08,16} UTC), matching the crypto engine's own fee formula
(`_market_hooks.py::calc_crypto_funding_fee`: fee = notional * rate *
direction; positive = longs pay):

  1. STATIC  -- the engine's own default constant rate (0.0001/settlement,
     the same assumption CLAUDE.md's crypto-engine section documents as
     "~11%/year notional" when applied 3x/day), i.e. what the champion's own
     validated numbers implicitly assumed whenever prior research reasoned
     about perp funding.
  2. REAL    -- actual observed Binance BTCUSDT/SOLUSDT settlement rates for
     the same dates (research/data/binance_funding_fwd_window.csv, fetched
     this session; extended to full history back to each symbol's perp
     listing by fetch_binance_funding_history.py for historical context).

No engine change needed: positions.csv already records the exact daily
target weight the real backtest executed; funding is a pure post-hoc
notional-times-rate sum, entirely decoupled from the entry/exit trade
mechanics already validated by the run itself.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FUNDING_CSV = REPO_ROOT / "research" / "data" / "binance_funding_fwd_window.csv"
STATIC_RATE = 0.0001  # engine default (config.get("funding_rate", 0.0001))
SYMBOL_MAP = {"BTC-USDT": "BTCUSDT", "SOL-USDT": "SOLUSDT"}

RUNS = {
    "fwd_Z8_20260702": REPO_ROOT / "agent" / "runs" / "fwd_Z8_20260702",
    "fwd_ZA4_20260702": REPO_ROOT / "agent" / "runs" / "fwd_ZA4_20260702",
}

# The true (non-warmup) forward window, matching forward_validation's own
# slicing convention (13-month warmup starting 2025-06-01, true window
# starts 2026-07-01) is NOT used here deliberately -- the forensics doc's
# original +$25.2k/+$50.7k static-model figures were computed over the full
# fwd_* run span (2025-06-01 -> 2026-07-02, the "forward year" it names).
# Reproduced at that same span first (to calibrate/validate this script
# against the doc's cited numbers), then also reported for the true-window
# slice for forward-validation-ledger consistency.
TRUE_WINDOW_START = pd.Timestamp("2026-07-01")


def load_funding() -> pd.DataFrame:
    df = pd.read_csv(FUNDING_CSV)
    df["ts"] = pd.to_datetime(df["ts"], format="mixed", utc=True).dt.tz_localize(None)
    return df.set_index("ts").sort_index()


def attribute_run(run_dir: Path, funding: pd.DataFrame) -> pd.DataFrame:
    """Return a per-settlement funding cash-flow table for one run.

    Columns: ts, symbol, static_fee, real_fee (positive = paid by the
    strategy, i.e. a P&L cost; negative = received).
    """
    positions = pd.read_csv(run_dir / "artifacts" / "positions.csv", parse_dates=["timestamp"])
    positions = positions.set_index("timestamp")
    equity = pd.read_csv(run_dir / "artifacts" / "equity.csv", parse_dates=["timestamp"])
    equity = equity.set_index("timestamp")["equity"]

    rows = []
    for day, day_weights in positions.iterrows():
        day_equity = equity.get(day)
        if day_equity is None or pd.isna(day_equity):
            continue
        # 3 real settlements per calendar day this position was held,
        # matching FUNDING_HOURS = {0, 8, 16} in _market_hooks.py.
        settlement_ts = [day.normalize() + pd.Timedelta(hours=h) for h in (0, 8, 16)]
        for code, weight in day_weights.items():
            if code not in SYMBOL_MAP or abs(weight) < 1e-9:
                continue
            direction = 1 if weight > 0 else -1
            notional = abs(weight) * day_equity
            fsym = SYMBOL_MAP[code]
            for sts in settlement_ts:
                static_fee = notional * STATIC_RATE * direction
                real_rate = funding[fsym].get(sts, None)
                real_fee = notional * real_rate * direction if real_rate is not None and not pd.isna(real_rate) else None
                rows.append({
                    "ts": sts, "symbol": code, "weight": weight,
                    "static_fee": static_fee, "real_fee": real_fee,
                })
    return pd.DataFrame(rows)


def summarize(name: str, run_dir: Path, funding: pd.DataFrame) -> None:
    attr = attribute_run(run_dir, funding)
    n_missing = attr["real_fee"].isna().sum()
    attr = attr.dropna(subset=["real_fee"])

    initial_cash = 1_000_000.0

    def _report(df: pd.DataFrame, label: str) -> None:
        static_pnl = -df["static_fee"].sum()
        real_pnl = -df["real_fee"].sum()
        print(f"  [{label}] static funding P&L: {static_pnl:+,.0f} ({static_pnl/initial_cash*100:+.2f}%)")
        print(f"  [{label}] real   funding P&L: {real_pnl:+,.0f} ({real_pnl/initial_cash*100:+.2f}%)")
        by_sym_static = -df.groupby("symbol")["static_fee"].sum()
        by_sym_real = -df.groupby("symbol")["real_fee"].sum()
        for sym in by_sym_static.index:
            print(f"    {sym}: static {by_sym_static[sym]:+,.0f}  real {by_sym_real[sym]:+,.0f}")
        # split by long/short
        for sub_label, mask in [("LONG", df["weight"] > 0), ("SHORT", df["weight"] < 0)]:
            sub = df[mask]
            if sub.empty:
                continue
            s_static = -sub["static_fee"].sum()
            s_real = -sub["real_fee"].sum()
            print(f"    {sub_label}: static {s_static:+,.0f}  real {s_real:+,.0f}")
        # split by (symbol, direction) -- the actual grain a wrapper decision needs
        df = df.copy()
        df["side"] = df["weight"].apply(lambda w: "LONG" if w > 0 else "SHORT")
        grp = df.groupby(["symbol", "side"])
        for (sym, side), sub in grp:
            s_static = -sub["static_fee"].sum()
            s_real = -sub["real_fee"].sum()
            print(f"    {sym} {side}: static {s_static:+,.0f}  real {s_real:+,.0f}  (n={len(sub)})")

    print(f"\n=== {name} (full fwd-run span, {n_missing} settlements with no funding data dropped) ===")
    _report(attr, "full span")

    true_window = attr[attr["ts"] >= TRUE_WINDOW_START]
    if not true_window.empty:
        print(f"\n=== {name} (true forward window only, >= {TRUE_WINDOW_START.date()}) ===")
        _report(true_window, "true window")


def historical_context(funding: pd.DataFrame) -> None:
    print("\n=== Full-history real funding-rate context (per symbol) ===")
    for sym in ["BTCUSDT", "SOLUSDT"]:
        s = funding[sym].dropna()
        ann_pct = s.mean() * 3 * 365 * 100
        neg_frac = (s < 0).mean() * 100
        print(f"  {sym}: n={len(s)} span={s.index.min().date()}->{s.index.max().date()} "
              f"mean_ann={ann_pct:+.2f}%  frac_negative={neg_frac:.1f}%")
        # Also break into 1yr trailing buckets for regime context
        yearly = s.groupby(s.index.year).agg(["mean", "count"])
        yearly["ann_pct"] = yearly["mean"] * 3 * 365 * 100
        print(f"    by year (ann. %): " + ", ".join(
            f"{yr}:{row.ann_pct:+.1f}%" for yr, row in yearly.iterrows()
        ))


def main() -> None:
    funding = load_funding()
    historical_context(funding)
    for name, run_dir in RUNS.items():
        summarize(name, run_dir, funding)


if __name__ == "__main__":
    main()
