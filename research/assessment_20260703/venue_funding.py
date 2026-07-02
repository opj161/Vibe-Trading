"""Venue-conditional funding attribution: the champion's actual direction runs
integrated against real settlement-by-settlement funding on Binance USDT-M vs
Hyperliquid (edgeforge lake). Constant-$1-notional approximation per run
(same convention as findings §75). Positive funding = longs pay shorts on
both venues. Output: cumulative funding P&L per $ notional per side/venue,
and annualized %/yr while in position."""
import glob
import numpy as np, pandas as pd

R = "/home/j_opp/projects/Vibe-Trading"
EF = "/home/j_opp/projects/edgeforge/data/lake/funding"

# Binance: 8h settlements, wide CSV
bn = pd.read_csv(f"{R}/research/data/binance_funding_fwd_window.csv")
bn["ts"] = pd.to_datetime(bn["ts"], utc=True, format="ISO8601").dt.tz_localize(None)
bn = bn.set_index("ts")

def hl_series(sym):
    files = sorted(glob.glob(f"{EF}/{sym}/*.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in files])
    ts = pd.to_datetime(df["time_ms"], unit="ms")
    return pd.Series(df["funding_rate"].values, index=ts).sort_index()

WINDOW_START = pd.Timestamp("2023-06-01")

for asset, bn_col, hl_sym, runs_csv in [
    ("BTC", "BTCUSDT", "BTC", "btc_direction_runs.csv"),
    ("SOL", "SOLUSDT", "SOL", "sol_direction_runs.csv"),
]:
    runs = pd.read_csv(f"{R}/research/vrp_deribit/derived/{runs_csv}", parse_dates=["start", "end"])
    for c in ("start", "end"):
        if runs[c].dt.tz is not None:
            runs[c] = runs[c].dt.tz_localize(None)
    runs = runs[runs["start"] >= WINDOW_START]
    hl = hl_series(hl_sym)
    b = bn[bn_col].dropna()
    print(f"\n=== {asset} ({len(runs)} runs since {WINDOW_START.date()}; "
          f"HL settlements {len(hl):,}, Binance {len(b):,}) ===")
    for side, dirsign in [("LONG", 1), ("SHORT", -1)]:
        sub = runs[runs["dir"] == dirsign]
        days = (sub["end"] - sub["start"]).dt.days.sum()
        out = {}
        for venue, ser in [("Binance", b), ("Hyperliquid", hl)]:
            tot = 0.0
            for _, r in sub.iterrows():
                cum = ser[(ser.index >= r["start"]) & (ser.index <= r["end"])].sum()
                tot += -cum if dirsign > 0 else +cum
            ann = tot / max(days, 1) * 365
            out[venue] = (tot, ann)
        print(f"  {side:5s} ({len(sub)} runs, {days} pos-days): "
              f"Binance {out['Binance'][0]*100:+7.3f}% cum ({out['Binance'][1]*100:+6.2f}%/yr) | "
              f"Hyperliquid {out['Hyperliquid'][0]*100:+7.3f}% cum ({out['Hyperliquid'][1]*100:+6.2f}%/yr)")
