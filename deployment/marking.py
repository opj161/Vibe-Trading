"""Sleeve valuation from the ledger + public mark prices, and the daily
marked-equity series (CPD-1 §A3's "crypto side can be marked from public
prices automatically" -- previously a documented known gap, which left the
drawdown/single-day-loss tripwires blind between weekly manual snapshots).

Valuation model (cash-flow accounting, same as the engine's own linearity):

    sleeve equity(now) = anchor balance
                       + signed cash flows of fills after the anchor date
                       + mark value of currently open positions

where the anchor is the most recent human equity snapshot at/before the
valuation window start. This is EXACT whenever no position was open at the
anchor date (true at deployment/paper start by construction); if fills before
the anchor leave a carryover position, the valuation is flagged rather than
silently wrong -- valuing a carryover needs the anchor date's historical
marks, which this layer deliberately doesn't reconstruct.

The daily marks land in ``deployment/state/equity_marks.csv`` -- append-only
and git-tracked like the ledger CSVs (a past date's mark cannot be
regenerated from current prices, so it is a record, not a cache). Human
snapshots in ``equity_snapshots.csv`` remain the reconciliation truth;
marks are the daily risk-series between them.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from deployment._bootstrap import STATE_DIR
from deployment import ledger, venue_specs

logger = logging.getLogger(__name__)

MARKS_PATH = STATE_DIR / "equity_marks.csv"
MARKS_COLUMNS = ["date", "mode", "sleeve", "equity_usd"]


def fetch_mark_price(symbol: str, venue: str) -> Optional[float]:
    """Best-effort live mark for one (symbol, venue), from the same public
    endpoints the ticket builder already uses."""
    if venue == "binance_spot":
        return venue_specs.binance_spot_price(symbol)
    if venue == "binance_usdtm":
        return venue_specs.binance_futures_price(symbol)
    if venue == "ibkr_ucits":
        return venue_specs.macro_reference_price(symbol)
    logger.warning("marking: no mark-price source for venue %r", venue)
    return None


def fetch_mark_prices(
    positions: dict[tuple[str, str], float],
    *,
    fetch: Callable[[str, str], Optional[float]] = fetch_mark_price,
) -> dict[tuple[str, str], float]:
    """Marks for every open (symbol, venue). Pairs whose fetch fails are
    OMITTED (callers treat a missing mark as "cannot value", never as zero --
    zero would book a fake total loss into the risk series)."""
    out: dict[tuple[str, str], float] = {}
    for (symbol, venue) in positions:
        price = fetch(symbol, venue)
        if price is not None and price > 0:
            out[(symbol, venue)] = float(price)
        else:
            logger.warning("marking: no mark for %s@%s", symbol, venue)
    return out


def value_sleeve(
    sleeve: str,
    *,
    paper: bool,
    mark_prices: dict[tuple[str, str], float],
    anchor_date: str,
) -> dict:
    """Value one sleeve per the module-docstring model.

    Returns:
        {"sleeve", "anchor_date", "anchor_balance", "cash_flow",
         "position_value", "equity", "carryover": {(symbol, venue): qty},
         "unmarked": [(symbol, venue), ...]}

        ``anchor_date`` in the result is the anchor snapshot's OWN date (the
        latest snapshot at/before the requested one) -- the cash-flow window
        starts there so no fill between snapshot and request is dropped.
        ``carryover`` nonempty means fills before the anchor left an open
        position the anchor balance may not include -- equity is then
        approximate and callers must surface that. ``unmarked`` lists open
        positions with no mark available (their value is excluded).
    """
    anchor = ledger.sleeve_equity_asof(anchor_date)
    anchor_balance = anchor[f"{sleeve}_equity"]
    effective_anchor_date = anchor["anchor_date"] or anchor_date

    sleeve_venues = [v for v, s in ledger.VENUE_TO_SLEEVE.items() if s == sleeve]
    fills = ledger.confirmed_fills(paper=paper, since_date=effective_anchor_date)
    cash_flow = 0.0
    if not fills.empty:
        fills = fills[fills["venue"].isin(sleeve_venues)]
        for _, row in fills.iterrows():
            sign = -1.0 if row["side"] == "buy" else 1.0
            cash_flow += sign * float(row["qty"]) * float(row["price"]) - float(row["fee"])

    # Carryover check: positions built from fills strictly before the anchor.
    pre_window = ledger.confirmed_fills(paper=paper)
    carryover: dict[tuple[str, str], float] = {}
    if not pre_window.empty:
        recorded = pd.to_datetime(pre_window["recorded_at"], utc=True, format="ISO8601")
        pre_window = pre_window[recorded < pd.Timestamp(effective_anchor_date, tz="UTC")]
        pre_window = pre_window[pre_window["venue"].isin(sleeve_venues)]
        if not pre_window.empty:
            signed = pre_window.apply(
                lambda r: r["qty"] if r["side"] == "buy" else -r["qty"], axis=1
            )
            grouped = signed.groupby([pre_window["symbol"], pre_window["venue"]]).sum()
            carryover = {
                (str(s), str(v)): float(q)
                for (s, v), q in grouped.items()
                if abs(float(q)) > 1e-12
            }

    position_value = 0.0
    unmarked: list[tuple[str, str]] = []
    for (symbol, venue), qty in ledger.open_positions(paper=paper).items():
        if venue not in sleeve_venues:
            continue
        mark = mark_prices.get((symbol, venue))
        if mark is None:
            unmarked.append((symbol, venue))
            continue
        position_value += qty * mark

    return {
        "sleeve": sleeve,
        "anchor_date": effective_anchor_date,
        "anchor_balance": anchor_balance,
        "cash_flow": cash_flow,
        "position_value": position_value,
        "equity": anchor_balance + cash_flow + position_value,
        "carryover": carryover,
        "unmarked": unmarked,
    }


def append_marks(*, date: str, mode_paper: bool, sleeve_equities: dict[str, float]) -> None:
    """Append one row per sleeve to the marks series. Idempotence is the
    caller's concern (the daily cycle runs once per day; a rerun appends a
    second row for the same date and ``equity_series`` keeps the LAST one,
    matching the ledger's newest-row-wins correction convention)."""
    is_new = not MARKS_PATH.exists()
    with MARKS_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MARKS_COLUMNS)
        if is_new:
            writer.writeheader()
        for sleeve, equity in sleeve_equities.items():
            writer.writerow({
                "date": date,
                "mode": "paper" if mode_paper else "live",
                "sleeve": sleeve,
                "equity_usd": equity,
            })


def read_marks() -> pd.DataFrame:
    if not MARKS_PATH.exists():
        return pd.DataFrame(columns=MARKS_COLUMNS)
    return pd.read_csv(MARKS_PATH)


def equity_series(*, mode_paper: Optional[bool] = None) -> pd.Series:
    """Total (all-sleeve) marked equity per date, sorted ascending -- the
    daily risk series ``risk_rules`` runs its tripwires over. Duplicate
    (date, sleeve) rows keep the last-written value."""
    df = read_marks()
    if df.empty:
        return pd.Series(dtype=float)
    if mode_paper is not None:
        df = df[df["mode"] == ("paper" if mode_paper else "live")]
    if df.empty:
        return pd.Series(dtype=float)
    df = df.groupby(["date", "sleeve"], as_index=False).last()
    by_date = df.groupby("date")["equity_usd"].sum().sort_index()
    by_date.index = pd.to_datetime(by_date.index)
    return by_date
