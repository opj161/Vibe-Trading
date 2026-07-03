"""Live venue quantization/price/funding lookups, all public no-key endpoints,
with hardcoded fallback constants when a live call fails (network unavailable,
API change, etc.) -- self-correcting instead of shipping stale "verified at
build time" snapshots that silently drift from what the venue actually
enforces (CPD-1 §A2's own caveat).

Only Binance spot + USDT-M futures are implemented -- CPD-1's crypto sleeve
(ZA4: BTC-USDT, SOL-USDT) is the only venue this deployment layer sizes
orders for; IBKR has no public unauthenticated quote API, so macro tickets
use the same SPY/GLD reference price the signal itself was computed from
(passed in by the caller) with a hardcoded fractional-share minimum -- see
``order_tickets.py``.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"

# Fallback snapshot values (CPD-1 §A2 / §2), used only if the live fetch
# fails. Live-verified 2026-07-03: spot min notional $5, spot step 1e-5 BTC/
# 1e-2 SOL, futures LOT_SIZE minQty 0.001 BTC/0.01 SOL, futures min notional
# $50 BTC/$5 SOL (the plan's own "~$5/0.001 BTC/1 SOL" text was an
# approximation -- this fetches live and only falls back to it).
_FALLBACK_SPOT = {
    "BTCUSDT": {"step_size": 0.00001, "min_notional": 5.0},
    "SOLUSDT": {"step_size": 0.01, "min_notional": 5.0},
}
_FALLBACK_FUTURES = {
    "BTCUSDT": {"step_size": 0.001, "min_notional": 50.0},
    "SOLUSDT": {"step_size": 0.01, "min_notional": 5.0},
}

# CPD-1's default annual-funding review threshold (§A2): proceed if projected
# funding cost against the position is below this; else the ticket is
# flagged REVIEW, never silently skipped.
FUNDING_REVIEW_THRESHOLD_ANNUAL = 0.15


def to_binance_symbol(code: str) -> str:
    """"BTC-USDT" -> "BTCUSDT" (Binance's REST API takes no separator)."""
    return code.replace("-", "").upper()


def _get_json(url: str, params: Optional[dict] = None) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("venue_specs: live fetch failed for %s: %s", url, exc)
        return None


def binance_spot_filters(code: str) -> dict:
    """{"step_size": float, "min_notional": float} for a Binance spot symbol."""
    symbol = to_binance_symbol(code)
    data = _get_json(f"{SPOT_BASE}/api/v3/exchangeInfo", {"symbol": symbol})
    if data and data.get("symbols"):
        filters = {f["filterType"]: f for f in data["symbols"][0]["filters"]}
        lot = filters.get("LOT_SIZE")
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
        if lot and notional:
            return {
                "step_size": float(lot["stepSize"]),
                "min_notional": float(notional.get("minNotional") or notional.get("notional")),
            }
    fallback = _FALLBACK_SPOT.get(symbol)
    if fallback is None:
        raise ValueError(f"no spot filters (live or fallback) for {symbol!r}")
    logger.warning("venue_specs: using fallback spot filters for %s", symbol)
    return dict(fallback)


def binance_futures_filters(code: str) -> dict:
    """{"step_size": float, "min_notional": float} for a Binance USDT-M symbol."""
    symbol = to_binance_symbol(code)
    data = _get_json(f"{FUTURES_BASE}/fapi/v1/exchangeInfo")
    if data:
        for s in data.get("symbols", []):
            if s["symbol"] != symbol:
                continue
            filters = {f["filterType"]: f for f in s["filters"]}
            lot = filters.get("LOT_SIZE")
            notional = filters.get("MIN_NOTIONAL")
            if lot and notional:
                return {
                    "step_size": float(lot["stepSize"]),
                    "min_notional": float(notional["notional"]),
                }
    fallback = _FALLBACK_FUTURES.get(symbol)
    if fallback is None:
        raise ValueError(f"no futures filters (live or fallback) for {symbol!r}")
    logger.warning("venue_specs: using fallback futures filters for %s", symbol)
    return dict(fallback)


def binance_spot_price(code: str) -> Optional[float]:
    data = _get_json(f"{SPOT_BASE}/api/v3/ticker/price", {"symbol": to_binance_symbol(code)})
    return float(data["price"]) if data and "price" in data else None


def binance_futures_price(code: str) -> Optional[float]:
    data = _get_json(f"{FUTURES_BASE}/fapi/v1/premiumIndex", {"symbol": to_binance_symbol(code)})
    return float(data["markPrice"]) if data and "markPrice" in data else None


def binance_futures_funding_annualized(code: str) -> Optional[float]:
    """Annualized funding rate a position pays (positive) or receives
    (negative) while held, from Binance's 8h settlement rate (3x/day)."""
    data = _get_json(f"{FUTURES_BASE}/fapi/v1/premiumIndex", {"symbol": to_binance_symbol(code)})
    if not data or "lastFundingRate" not in data:
        return None
    return float(data["lastFundingRate"]) * 3 * 365


def macro_reference_price(yf_symbol: str) -> Optional[float]:
    """Best-effort reference price for a macro-sleeve symbol (e.g. "SPY.US")
    via yfinance -- IBKR has no public unauthenticated quote API, so this is
    the same data source the M1 signal itself is computed from, used only to
    size a ticket's approximate notional; the human confirms the real UCITS
    fill price via ``confirm.py`` regardless."""
    try:
        import yfinance as yf

        ticker = yf_symbol.split(".")[0]
        price = yf.Ticker(ticker).fast_info.get("lastPrice")
        return float(price) if price else None
    except Exception as exc:  # noqa: BLE001 - best-effort sizing hint, never fatal
        logger.warning("venue_specs: macro reference price failed for %s: %s", yf_symbol, exc)
        return None


def round_down_to_step(qty: float, step: float) -> float:
    """Floor ``qty`` to the nearest multiple of ``step`` -- never rounds up,
    matching CLAUDE.md §8.3's lesson that forcing a minimum silently changes
    the risk profile. Callers decide separately whether a floored-to-zero
    result means SKIP."""
    if step <= 0:
        return qty
    steps = math.floor(qty / step + 1e-9)
    return round(steps * step, 12)
