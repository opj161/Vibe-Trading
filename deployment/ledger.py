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


def _paper_mask(df: pd.DataFrame, paper: bool) -> pd.Series:
    """Row mask for the ``paper`` column, robust to CSV round-tripping (the
    column is written as Python bools but may read back as bool dtype or as
    "True"/"False" strings depending on surrounding rows)."""
    return df["paper"].astype(str).str.lower().eq("true") == paper


def confirmed_fills(
    *, paper: Optional[bool] = None, since_date: Optional[str] = None
) -> pd.DataFrame:
    """Confirmed ledger rows, with any row named in another row's
    ``supersedes`` excluded (the correction row itself is always kept, since
    ``supersedes`` never references its own freshly-generated ``row_id``).
    Public (not just an internal helper) -- tracking_report.py needs the same
    "what really happened" view current_position() uses.

    Args:
        paper: None returns all rows (legacy behavior); True/False returns
            only paper/live rows. The tracking report and daily cycle must
            always pass this explicitly -- mixing modes was one of the
            2026-07-03 reassessment's tracking-report defects.
        since_date: If given (YYYY-MM-DD), only rows recorded at/after that
            UTC date. Supersedes-exclusion is computed on the FULL ledger
            first (a correction row inside the window must still knock out
            its wrong row from before the window).
    """
    df = read_ledger()
    if df.empty:
        return df
    confirmed = df[df["status"] == "confirmed"].copy()
    superseded_row_ids = set(confirmed["supersedes"].dropna()) - {""}
    confirmed = confirmed[~confirmed["row_id"].isin(superseded_row_ids)]
    if paper is not None and not confirmed.empty:
        confirmed = confirmed[_paper_mask(confirmed, paper)]
    if since_date is not None and not confirmed.empty:
        recorded = pd.to_datetime(confirmed["recorded_at"], utc=True, format="ISO8601")
        confirmed = confirmed[recorded >= pd.Timestamp(since_date, tz="UTC")]
    return confirmed


def has_confirmation(ticket_id: str, *, paper: Optional[bool] = None) -> bool:
    """Whether a (non-superseded) confirmed OR skipped row already exists for
    this ticket_id -- the daily cycle's idempotence guard (ticket_ids are
    deterministic per day, so a rerun must not double-record a fill)."""
    df = read_ledger()
    if df.empty:
        return False
    superseded = set(df["supersedes"].dropna()) - {""}
    rows = df[(df["ticket_id"] == ticket_id) & (~df["row_id"].isin(superseded))]
    if paper is not None and not rows.empty:
        rows = rows[_paper_mask(rows, paper)]
    return not rows.empty


def current_position(symbol: str, venue: str, *, paper: Optional[bool] = None) -> float:
    """Net signed quantity currently believed held for ``(symbol, venue)``,
    from confirmed (non-superseded) ledger rows. Positive = long, negative =
    short.

    Scoped by venue, not just symbol: CPD-1's venue-split rule (longs on
    ``binance_spot``, shorts on ``binance_usdtm``) means the SAME symbol can
    have independent positions on two venues simultaneously mid-flip (the old
    leg not yet closed) -- summing across venues would incorrectly net a spot
    long against a perp short as if they were one instrument.
    """
    confirmed = confirmed_fills(paper=paper)
    if confirmed.empty:
        return 0.0
    sub = confirmed[(confirmed["symbol"] == symbol) & (confirmed["venue"] == venue)]
    if sub.empty:
        return 0.0
    signed = sub.apply(lambda r: r["qty"] if r["side"] == "buy" else -r["qty"], axis=1)
    return float(signed.sum())


def current_position_any_venue(
    symbol: str, venues: list[str], *, paper: Optional[bool] = None
) -> tuple[str, float]:
    """Return (venue, signed_qty) for whichever of ``venues`` currently holds
    a nonzero position in ``symbol`` (there should be at most one, by
    construction of the venue-split rule -- a symbol is never held long-spot
    and short-perp at the same time). Returns ("", 0.0) if none do."""
    for venue in venues:
        qty = current_position(symbol, venue, paper=paper)
        if abs(qty) > 1e-12:
            return venue, qty
    return "", 0.0


def open_positions(*, paper: Optional[bool] = None) -> dict[tuple[str, str], float]:
    """{(symbol, venue): signed_qty} for every pair with a nonzero net
    position -- the marking/funding-check iteration surface."""
    confirmed = confirmed_fills(paper=paper)
    if confirmed.empty:
        return {}
    out: dict[tuple[str, str], float] = {}
    signed = confirmed.apply(lambda r: r["qty"] if r["side"] == "buy" else -r["qty"], axis=1)
    grouped = signed.groupby([confirmed["symbol"], confirmed["venue"]]).sum()
    for (symbol, venue), qty in grouped.items():
        if abs(float(qty)) > 1e-12:
            out[(str(symbol), str(venue))] = float(qty)
    return out


def position_entry_info(
    symbol: str, venue: str, *, paper: Optional[bool] = None
) -> Optional[dict]:
    """Entry metadata for the CURRENT open position streak of (symbol, venue):
    the fill that last took the running quantity away from zero, plus whether
    a one-shot resize row was already recorded during this streak (ticket_id
    containing ``_resize``). None if flat.

    Needed by the ZD2-style ``one_shot_resize`` ticket support -- the engine
    fires its resize off ``entry_bar_idx`` + ``resize_applied``
    (``base.py::_maybe_one_shot_resize``); this is the ledger-side analogue
    of those two fields.
    """
    confirmed = confirmed_fills(paper=paper)
    if confirmed.empty:
        return None
    sub = confirmed[(confirmed["symbol"] == symbol) & (confirmed["venue"] == venue)].copy()
    if sub.empty:
        return None
    sub["_ts"] = pd.to_datetime(sub["recorded_at"], utc=True, format="ISO8601")
    sub = sub.sort_values("_ts")
    running = 0.0
    entry_ts = None
    resize_recorded = False
    for _, row in sub.iterrows():
        signed = float(row["qty"]) if row["side"] == "buy" else -float(row["qty"])
        was_flat = abs(running) <= 1e-12
        running += signed
        if was_flat and abs(running) > 1e-12:
            entry_ts = row["_ts"]
            resize_recorded = False
        if entry_ts is not None and "_resize" in str(row["ticket_id"]):
            resize_recorded = True
    if abs(running) <= 1e-12 or entry_ts is None:
        return None
    return {
        "entry_date": entry_ts.date().isoformat(),
        "qty": running,
        "resize_recorded": resize_recorded,
    }


def sleeve_equity_asof(date: str) -> dict:
    """{"crypto_equity", "macro_equity", "anchor_date"} from the most recent
    snapshot date at or before ``date`` -- the tracking report's
    starting-equity anchor (the 2026-07-03 reassessment: using the LATEST
    snapshot as denominator shrinks measured divergence as the account
    grows). ``anchor_date`` is the snapshot's OWN date (may be earlier than
    the requested one); cash-flow windows must start there, or fills between
    the snapshot and the requested date would be silently dropped. Zeros and
    ``anchor_date=None`` if no snapshot exists at/before ``date``."""
    df = read_equity_snapshots()
    out: dict = {"crypto_equity": 0.0, "macro_equity": 0.0, "anchor_date": None}
    if df.empty:
        return out
    eligible = df[df["date"] <= date]
    if eligible.empty:
        return out
    anchor_date = eligible["date"].max()
    out["anchor_date"] = str(anchor_date)
    latest = eligible[eligible["date"] == anchor_date]
    for _, row in latest.iterrows():
        sleeve = VENUE_TO_SLEEVE.get(row["venue"])
        if sleeve is None:
            continue
        out[f"{sleeve}_equity"] += float(row["balance_usd"])
    return out


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
