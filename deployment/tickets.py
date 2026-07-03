"""Shared ``Ticket`` schema + persistence, used by ``order_tickets.py`` (writer)
and ``confirm.py``/``ledger.py`` (readers) so the two never drift on format.
"""

from __future__ import annotations

import dataclasses
import glob
import json
from pathlib import Path
from typing import Optional

from deployment._bootstrap import STATE_DIR


@dataclasses.dataclass(frozen=True)
class Ticket:
    """One order instruction (or a documented SKIP/REVIEW).

    ``ticket_id`` is deterministic (``<strategy>_<symbol>_<as_of_date>``) so a
    given day's signal always produces the same id -- re-running
    ``signal_runner``/``order_tickets`` the same day is idempotent, and
    ``confirm.py`` can look a ticket up by id without a separate index.
    """

    ticket_id: str
    strategy: str
    symbol: str
    venue: str  # "binance_spot" | "binance_usdtm" | "ibkr_ucits"
    side: str  # "buy" | "sell" | "skip"
    qty: float
    notional_usd: float
    reason: str
    status: str = "pending"  # "pending" | "review"  (ledger.py tracks confirmed/skipped)
    human_text: str = ""

    @property
    def as_of_date(self) -> str:
        # ticket_id = f"{strategy}_{symbol}_{YYYYMMDD}"
        return self.ticket_id.rsplit("_", 1)[-1]


def make_ticket_id(strategy: str, symbol: str, as_of_date: str) -> str:
    return f"{strategy}_{symbol}_{as_of_date.replace('-', '')}"


def write_tickets(as_of_date: str, tickets: list[Ticket]) -> Path:
    out = STATE_DIR / f"tickets_{as_of_date.replace('-', '')}.json"
    out.write_text(json.dumps([dataclasses.asdict(t) for t in tickets], indent=2))
    return out


def read_tickets(as_of_date: str) -> list[Ticket]:
    path = STATE_DIR / f"tickets_{as_of_date.replace('-', '')}.json"
    if not path.exists():
        return []
    return [Ticket(**row) for row in json.loads(path.read_text())]


def find_ticket(ticket_id: str) -> Optional[Ticket]:
    """Look up a ticket by id, scanning ticket files newest-first (a ticket_id
    encodes its own date, but scanning stays robust to callers that only have
    the id)."""
    for path in sorted(glob.glob(str(STATE_DIR / "tickets_*.json")), reverse=True):
        for row in json.loads(Path(path).read_text()):
            if row["ticket_id"] == ticket_id:
                return Ticket(**row)
    return None
