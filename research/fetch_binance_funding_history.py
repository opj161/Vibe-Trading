"""Fetch full Binance USDⓈ-M perpetual funding-rate history for BTC/SOL.

Direction 2 of vibe_trading_forensics_new_directions.md: the champion's
"perps are the preferred live wrapper" decision (CLAUDE.md / §64.6 ZB3) was
made under the engine's static funding model (fixed rate, longs-pay/
shorts-receive); the forward year's real Binance rates turned that
assumption's sign around for SOL. This script pulls Binance's public,
no-key `/fapi/v1/fundingRate` endpoint back to each symbol's perp-listing
date (BTCUSDT ~2019-09-11, SOLUSDT ~2020-09-13) and writes a single wide
CSV: one row per real settlement timestamp (3/day, {00,08,16} UTC), one
column per symbol, matching the exact schema of the pre-existing
`research/data/binance_funding_fwd_window.csv` (2025-06-01 -> 2026-07-02)
this session already fetched for the forward window alone -- so the output
here is the superset, used to (a) re-run the forward-window attribution
with the same file used elsewhere, and (b) give the forward year's
observed funding sign/magnitude a multi-year base rate to compare against.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

OUT_PATH = Path(__file__).resolve().parent / "data" / "binance_funding_fwd_window.csv"
SYMBOLS = ["BTCUSDT", "SOLUSDT"]
START_MS = {
    "BTCUSDT": int(pd.Timestamp("2019-09-01", tz="UTC").timestamp() * 1000),
    "SOLUSDT": int(pd.Timestamp("2020-09-01", tz="UTC").timestamp() * 1000),
}
END_MS = int(pd.Timestamp("2025-06-01", tz="UTC").timestamp() * 1000)  # existing file starts here
URL = "https://fapi.binance.com/fapi/v1/fundingRate"
PAGE_LIMIT = 1000


def fetch_symbol(symbol: str) -> pd.Series:
    """Page through Binance funding history for one symbol, oldest-first."""
    start = START_MS[symbol]
    rows: list[tuple[int, float]] = []
    while start < END_MS:
        resp = requests.get(
            URL,
            params={"symbol": symbol, "startTime": start, "limit": PAGE_LIMIT},
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for row in batch:
            rows.append((int(row["fundingTime"]), float(row["fundingRate"])))
        last_time = int(batch[-1]["fundingTime"])
        if last_time <= start or len(batch) < PAGE_LIMIT:
            # No more pages (either exhausted or hit END_MS boundary next loop)
            if len(batch) < PAGE_LIMIT:
                break
            start = last_time + 1
        else:
            start = last_time + 1
        time.sleep(0.2)  # be polite to the public endpoint
        print(f"{symbol}: {len(rows)} settlements fetched, last={pd.Timestamp(last_time, unit='ms', tz='UTC')}")

    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    ser = pd.Series([r[1] for r in rows], index=idx, name=symbol)
    ser = ser[~ser.index.duplicated(keep="first")].sort_index()
    return ser[ser.index < pd.Timestamp(END_MS, unit="ms", tz="UTC")]


def main() -> None:
    series = {sym: fetch_symbol(sym) for sym in SYMBOLS}
    history_df = pd.concat(series, axis=1).sort_index()

    existing = pd.read_csv(OUT_PATH)
    existing["ts"] = pd.to_datetime(existing["ts"], format="mixed", utc=True)
    existing = existing.set_index("ts")

    combined = pd.concat([history_df, existing]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.index.name = "ts"
    combined.to_csv(OUT_PATH)
    print(f"wrote {len(combined)} rows ({combined.index.min()} -> {combined.index.max()}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
