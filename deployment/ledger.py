"""Append-only live ledger for the CPD-1 deployment composite.

Two CSVs under ``deployment/state/``, both tracked in git (unlike the
regenerable ``signal_state_*.json``/``agent/runs/deploy_*`` artifacts) --
these are the non-regenerable, human-confirmed record of what actually
happened, mirroring how ``forward_validation/results.csv`` is the repo's
other tracked append-only ledger.

Nothing is ever edited in place. A correction to a wrong entry is a NEW row
whose ``supersedes`` column names the ``row_id`` (not ``ticket_id`` -- a
ticket_id is deterministic per strategy/symbol/day and a correction shares
the SAME ticket_id as the row it fixes, so only the per-append ``row_id`` can
unambiguously identify "this specific prior entry") of the row it corrects;
readers exclude any row named in another row's ``supersedes`` when computing
current state.
"""

from __future__ import annotations

import csv
import datetime as dt
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd

from deployment._bootstrap import STATE_DIR

LEDGER_PATH = STATE_DIR / "live_ledger.csv"
EQUITY_PATH = STATE_DIR / "equity_snapshots.csv"

LEDGER_COLUMNS = [
    "row_id", "ticket_id", "recorded_at", "symbol", "venue", "side", "status",
    "qty", "price", "fee", "reason", "paper", "supersedes",
]
EQUITY_COLUMNS = ["date", "venue", "symbol_or_cash", "balance_usd"]

# Which sleeve each venue's balance counts toward, for order_tickets.py's
# account_split. binance_usdtm is crypto's short leg; ibkr_ucits is the
# entire macro sleeve (CPD-1 §2 venue map).
VENUE_TO_SLEEVE = {
    "binance_spot": "crypto",
    "binance_usdtm": "crypto",
    "ibkr_ucits": "macro",
}


def _append_row(path: Path, columns: list[str], row: dict) -> None:
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if is_new:
            writer.writeheader()
        writer.writerow({c: row.get(c, "") for c in columns})


def append_ledger_row(
    *,
    ticket_id: str,
    symbol: str,
    venue: str,
    side: str,
    status: str,
    qty: float = 0.0,
    price: float = 0.0,
    fee: float = 0.0,
    reason: str = "",
    paper: bool = False,
    supersedes: Optional[str] = None,
) -> str:
    """Append one confirmation/skip/correction row. ``status`` is
    ``"confirmed"`` or ``"skipped"``; a correction re-confirms with
    ``supersedes`` set to the wrong row's ``row_id`` (printed when that row
    was originally recorded -- see ``confirm.py``).

    Returns the newly generated ``row_id``.
    """
    if status not in ("confirmed", "skipped"):
        raise ValueError(f"status must be 'confirmed' or 'skipped', got {status!r}")
    row_id = uuid.uuid4().hex[:12]
    _append_row(LEDGER_PATH, LEDGER_COLUMNS, {
        "row_id": row_id,
        "ticket_id": ticket_id,
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "symbol": symbol,
        "venue": venue,
        "side": side,
        "status": status,
        "qty": qty,
        "price": price,
        "fee": fee,
        "reason": reason,
        "paper": paper,
        "supersedes": supersedes or "",
    })
    return row_id


def append_equity_snapshot(*, date: str, venue: str, symbol_or_cash: str, balance_usd: float) -> None:
    _append_row(EQUITY_PATH, EQUITY_COLUMNS, {
        "date": date, "venue": venue, "symbol_or_cash": symbol_or_cash, "balance_usd": balance_usd,
    })


def read_ledger() -> pd.DataFrame:
    if not LEDGER_PATH.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    return pd.read_csv(LEDGER_PATH, dtype={"row_id": str, "ticket_id": str, "supersedes": str})


def read_equity_snapshots() -> pd.DataFrame:
    if not EQUITY_PATH.exists():
        return pd.DataFrame(columns=EQUITY_COLUMNS)
    return pd.read_csv(EQUITY_PATH)


def confirmed_fills() -> pd.DataFrame:
    """Confirmed ledger rows, with any row named in another row's
    ``supersedes`` excluded (the correction row itself is always kept, since
    ``supersedes`` never references its own freshly-generated ``row_id``).
    Public (not just an internal helper) -- tracking_report.py needs the same
    "what really happened" view current_position() uses."""
    df = read_ledger()
    if df.empty:
        return df
    confirmed = df[df["status"] == "confirmed"].copy()
    superseded_row_ids = set(confirmed["supersedes"].dropna()) - {""}
    return confirmed[~confirmed["row_id"].isin(superseded_row_ids)]


def current_position(symbol: str, venue: str) -> float:
    """Net signed quantity currently believed held for ``(symbol, venue)``,
    from confirmed (non-superseded) ledger rows. Positive = long, negative =
    short.

    Scoped by venue, not just symbol: CPD-1's venue-split rule (longs on
    ``binance_spot``, shorts on ``binance_usdtm``) means the SAME symbol can
    have independent positions on two venues simultaneously mid-flip (the old
    leg not yet closed) -- summing across venues would incorrectly net a spot
    long against a perp short as if they were one instrument.
    """
    confirmed = confirmed_fills()
    if confirmed.empty:
        return 0.0
    sub = confirmed[(confirmed["symbol"] == symbol) & (confirmed["venue"] == venue)]
    if sub.empty:
        return 0.0
    signed = sub.apply(lambda r: r["qty"] if r["side"] == "buy" else -r["qty"], axis=1)
    return float(signed.sum())


def current_position_any_venue(symbol: str, venues: list[str]) -> tuple[str, float]:
    """Return (venue, signed_qty) for whichever of ``venues`` currently holds
    a nonzero position in ``symbol`` (there should be at most one, by
    construction of the venue-split rule -- a symbol is never held long-spot
    and short-perp at the same time). Returns ("", 0.0) if none do."""
    for venue in venues:
        qty = current_position(symbol, venue)
        if abs(qty) > 1e-12:
            return venue, qty
    return "", 0.0


def latest_sleeve_equity() -> dict:
    """{"crypto_equity": float, "macro_equity": float} from the most recent
    equity_snapshots.csv date, summed by sleeve. Returns 0.0 for a sleeve with
    no snapshots yet (caller/order_tickets.py must treat that as
    "no equity configured", not "target is zero")."""
    df = read_equity_snapshots()
    if df.empty:
        return {"crypto_equity": 0.0, "macro_equity": 0.0}
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date]
    out = {"crypto_equity": 0.0, "macro_equity": 0.0}
    for _, row in latest.iterrows():
        sleeve = VENUE_TO_SLEEVE.get(row["venue"])
        if sleeve is None:
            continue
        out[f"{sleeve}_equity"] += float(row["balance_usd"])
    return out
