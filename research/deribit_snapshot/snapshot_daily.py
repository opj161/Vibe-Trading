"""Daily Deribit option chain snapshotter (CPD-1 Phase C1).

Deribit's history API only returns EXPIRED options, so the most recent weeks
of chain data are always invisible to any later analysis unless captured as
it happens (venue_data_assessment_20260703.md §5). This closes that gap: one
public, no-key ``get_book_summary_by_currency`` call per underlying, appended
to a per-day parquet file. Feeds H1 forward-tracking and the future SOL/BTC
options unlock (quarterly capacity re-measurement).

Usage (cron-friendly, log-and-continue -- one underlying's API hiccup never
blocks the others or crashes the whole run)::

    python3 research/deribit_snapshot/snapshot_daily.py
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DERIBIT_BASE = "https://www.deribit.com/api/v2/public"
DATA_DIR = Path(__file__).resolve().parent / "data"
TIMEOUT_S = 20

COLUMNS = [
    "date", "underlying", "instrument_name", "option_type", "strike",
    "expiration_timestamp", "bid_price", "ask_price", "mark_price",
    "mark_iv", "open_interest", "underlying_price", "volume",
]

# BTC/ETH options are coin-settled (query by their own currency code); SOL
# options are USDC-settled/linear (query currency=USDC, then filter by
# base_currency -- confirmed live 2026-07-03: currency="SOL" returns zero
# option instruments, the SOL book only exists under the USDC query).
UNDERLYINGS = {
    "BTC": {"query_currency": "BTC", "base_currency_filter": None},
    "SOL": {"query_currency": "USDC", "base_currency_filter": "SOL"},
    "ETH": {"query_currency": "ETH", "base_currency_filter": None},
}


def _fetch_book_summary(query_currency: str) -> Optional[list[dict]]:
    try:
        resp = requests.get(
            f"{DERIBIT_BASE}/get_book_summary_by_currency",
            params={"currency": query_currency, "kind": "option"},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            logger.warning("Deribit API error for currency=%s: %s", query_currency, payload["error"])
            return None
        return payload.get("result", [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Deribit fetch failed for currency=%s: %s", query_currency, exc)
        return None


def snapshot_underlying(underlying: str, spec: dict, date: str) -> pd.DataFrame:
    """One underlying's chain summary as a DataFrame, or empty on failure
    (never raises -- callers log-and-continue to the next underlying)."""
    rows = _fetch_book_summary(spec["query_currency"])
    if rows is None:
        return pd.DataFrame(columns=COLUMNS)

    base_filter = spec["base_currency_filter"]
    if base_filter is not None:
        rows = [r for r in rows if r.get("base_currency") == base_filter]

    records = []
    for r in rows:
        name = r["instrument_name"]
        option_type = "call" if name.endswith("-C") else ("put" if name.endswith("-P") else "")
        strike, expiry_ts = _parse_instrument_name(name)
        records.append({
            "date": date,
            "underlying": underlying,
            "instrument_name": name,
            "option_type": option_type,
            "strike": strike,
            "expiration_timestamp": expiry_ts,
            "bid_price": r.get("bid_price"),
            "ask_price": r.get("ask_price"),
            "mark_price": r.get("mark_price"),
            "mark_iv": r.get("mark_iv"),
            "open_interest": r.get("open_interest"),
            "underlying_price": r.get("underlying_price"),
            "volume": r.get("volume"),
        })
    return pd.DataFrame(records, columns=COLUMNS)


def _parse_instrument_name(instrument_name: str) -> tuple[Optional[float], Optional[int]]:
    """Deribit encodes strike and expiry in the instrument name itself
    (e.g. "BTC-31JUL26-81000-C" / "SOL_USDC-3JUL26-45-C") -- parsed directly
    rather than issuing a second per-underlying API call for the same data."""
    parts = instrument_name.split("-")
    if len(parts) < 4:
        return None, None
    try:
        strike = float(parts[-2])
    except ValueError:
        strike = None
    try:
        expiry = pd.to_datetime(parts[-3], format="%d%b%y")
        expiry_ts = int(expiry.timestamp() * 1000)
    except ValueError:
        expiry_ts = None
    return strike, expiry_ts


def run_snapshot(date: Optional[str] = None) -> Path:
    date = date or dt.date.today().isoformat()
    frames = []
    for underlying, spec in UNDERLYINGS.items():
        df = snapshot_underlying(underlying, spec, date)
        if df.empty:
            logger.warning("snapshot_daily: no rows captured for %s on %s", underlying, date)
        else:
            logger.info("snapshot_daily: %d rows for %s", len(df), underlying)
        frames.append(df)

    non_empty = [f for f in frames if not f.empty]
    combined = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame(columns=COLUMNS)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{date}.parquet"
    combined.to_parquet(out_path, index=False)
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    path = run_snapshot()
    print(f"[snapshot_daily] wrote {path}")
