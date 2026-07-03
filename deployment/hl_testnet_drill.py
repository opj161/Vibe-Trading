"""Hyperliquid TESTNET order-lifecycle smoke drill (CPD-1 Phase E, §E table's
"HL testnet drill" row -- explicitly pre-authorized to run "any time", free,
validates the future automated-shorts-leg path per
venue_data_assessment_20260703.md §2/§4).

**This is the ONE exception to CPD-1's hard constraint #2 ("no live order
placement, no mainnet keys")** -- and only because the testnet environment is
hardcoded below (``HyperliquidEnvironment.TESTNET``, never a config flag), so
it cannot reach mainnet by mistake.

Started from edgeforge's `scripts/spike_engine_order_drill.py` (prior art per
CPD-1 §E) as a reference for *what* to validate, but that script's API
(`TradingNode`/`Strategy`) does not exist in this repo's installed
`nautilus_trader` (2.0.0rc1 here exposes a lower-level `LiveNode`/
`LiveNodeBuilder` surface instead -- a genuinely different generation of the
adapter). Rebuilt on the adapter's `HyperliquidHttpClient` -- a direct,
synchronous-per-call REST client that needs no node/actor/strategy
orchestration at all, which is the right level for a one-shot smoke drill
(the full live-trading-node machinery is what Phase E's later "automation via
Nautilus" unlock, not this drill, is for). Every step below was interactively
verified against the real testnet before being written here.

Validates: connect (real account balance query) -> place a resting limit
order far enough from market to never fill -> confirm ACCEPTED with a real
venue_order_id -> cancel -> confirm no open orders remain.

Reads `HYPERLIQUID_TESTNET_PK` / `HYPERLIQUID_ACCOUNT_ADDRESS` from `.env`.

Usage::

    python3 deployment/hl_testnet_drill.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from typing import Optional

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from nautilus_trader import model
from nautilus_trader.adapters.hyperliquid import HyperliquidEnvironment, HyperliquidHttpClient

# Hardcoded testnet-only -- never make this a config flag (CPD-1 hard
# constraint #2's one exception is conditioned on exactly this).
TESTNET_INFO_URL = "https://api.hyperliquid-testnet.xyz/info"
INSTRUMENT_ID_STR = "BTC-USD-PERP.HYPERLIQUID"
COIN = "BTC"
DISCOUNT = 0.70  # rest 30% below mid -- never fills under normal conditions
ORDER_QTY = 0.001
SETTLE_WAIT_S = 3


def testnet_mid_price(coin: str) -> float:
    resp = httpx.post(TESTNET_INFO_URL, json={"type": "allMids"}, timeout=15)
    resp.raise_for_status()
    mid = resp.json().get(coin)
    if mid is None:
        raise RuntimeError(f"no mid price returned for {coin}")
    return float(mid)


async def run_drill() -> dict:
    result = {
        "connected": False, "account_address": None, "balance_usdc": None,
        "submitted": False, "venue_order_id": None, "accepted": False,
        "canceled": False, "confirmed_closed": None,
    }

    client = HyperliquidHttpClient.from_env(environment=HyperliquidEnvironment.TESTNET)
    address = client.get_user_address()
    client.set_account_id(f"HYPERLIQUID-{address}")
    result["account_address"] = address

    account_state = await client.request_account_state()
    result["connected"] = True
    # AccountBalance's .pyi declares total/locked/free as __init__ params but
    # they aren't exposed as readable attributes on this build (verified
    # interactively) -- the object's own repr already renders them, which is
    # all this diagnostic needs.
    result["balance_usdc"] = str(account_state.balances[0]) if account_state.balances else None

    instruments = await client.load_instrument_definitions(include_spot=False, include_perps=True)
    instrument = next((i for i in instruments if str(i.id) == INSTRUMENT_ID_STR), None)
    if instrument is None:
        raise RuntimeError(f"{INSTRUMENT_ID_STR} not found in testnet instrument universe")
    client.cache_instrument(instrument)

    mid = testnet_mid_price(COIN)
    limit_price = round(mid * DISCOUNT, instrument.price_precision)
    price = model.Price(limit_price, instrument.price_precision)
    qty = model.Quantity(ORDER_QTY, instrument.size_precision)
    client_order_id = model.ClientOrderId(f"CPD1DRILL-{uuid.uuid4().hex[:16]}")

    report = await client.submit_order(
        instrument_id=instrument.id, client_order_id=client_order_id, order_side=model.OrderSide.BUY,
        order_type=model.OrderType.LIMIT, quantity=qty, time_in_force=model.TimeInForce.GTC,
        price=price, post_only=False, reduce_only=False,
    )
    result["submitted"] = True
    result["venue_order_id"] = str(report.venue_order_id)
    result["accepted"] = str(report.order_status) == "ACCEPTED"

    await asyncio.sleep(SETTLE_WAIT_S)

    await client.cancel_order(instrument_id=instrument.id, client_order_id=client_order_id)
    result["canceled"] = True

    await asyncio.sleep(SETTLE_WAIT_S)

    reports = await client.request_order_status_reports(instrument_id=INSTRUMENT_ID_STR)
    still_open = [
        r for r in reports
        if str(r.client_order_id) == str(client_order_id) and str(r.order_status) not in ("CANCELED", "FILLED", "REJECTED")
    ]
    result["confirmed_closed"] = len(still_open) == 0

    return result


def drill_passed(result: dict) -> bool:
    return all([
        result.get("connected"), result.get("submitted"), result.get("accepted"),
        result.get("canceled"), result.get("confirmed_closed"),
    ])


def main() -> None:
    result = asyncio.run(run_drill())
    print(f"DRILL RESULT: {result}")
    passed = drill_passed(result)
    print(f"DRILL {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
