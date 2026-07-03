"""``python -m deployment.confirm`` -- the human's one command to record what
actually happened for a ticket. Nothing is ever edited in place: re-running
this for a ticket_id that already has a confirmed row appends a NEW row; to
fix a mistake, note the ``row_id`` printed when the wrong row was recorded
and pass ``--supersedes <that-row-id>`` on the correcting call (see ledger.py).
"""

from __future__ import annotations

import argparse
import sys

from deployment.ledger import append_ledger_row
from deployment.tickets import find_ticket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket_id")
    parser.add_argument("--px", type=float, help="Fill price")
    parser.add_argument("--qty", type=float, help="Filled quantity")
    parser.add_argument("--fee", type=float, default=0.0, help="Commission paid")
    parser.add_argument("--skip", action="store_true", help="Record this ticket as not executed")
    parser.add_argument("--reason", default="", help="Required with --skip; optional otherwise")
    parser.add_argument(
        "--paper", action="store_true",
        help="Paper-mode: record a hypothetical fill (Phase B paper cycle), not a real trade",
    )
    parser.add_argument(
        "--supersedes", default=None,
        help="row_id (not ticket_id -- printed by a prior confirm.py call) of a previously-"
             "confirmed row this corrects; that row is excluded from current_position() "
             "from now on, but is never deleted",
    )
    args = parser.parse_args()

    ticket = find_ticket(args.ticket_id)
    if ticket is None:
        print(f"error: no ticket found with id {args.ticket_id!r} under deployment/state/tickets_*.json",
              file=sys.stderr)
        sys.exit(1)

    if args.skip:
        if args.px is not None or args.qty is not None:
            print("error: --skip is exclusive with --px/--qty", file=sys.stderr)
            sys.exit(1)
        if not args.reason:
            print("error: --skip requires --reason", file=sys.stderr)
            sys.exit(1)
        row_id = append_ledger_row(
            ticket_id=ticket.ticket_id, symbol=ticket.symbol, venue=ticket.venue,
            side=ticket.side, status="skipped", reason=args.reason, paper=args.paper,
        )
        print(f"recorded SKIP for {ticket.ticket_id}: {args.reason} (row_id={row_id})")
        return

    if args.px is None or args.qty is None:
        print("error: confirming a fill requires --px and --qty (or use --skip)", file=sys.stderr)
        sys.exit(1)

    row_id = append_ledger_row(
        ticket_id=ticket.ticket_id, symbol=ticket.symbol, venue=ticket.venue,
        side=ticket.side, status="confirmed", qty=args.qty, price=args.px, fee=args.fee,
        reason=args.reason or ticket.reason, paper=args.paper, supersedes=args.supersedes,
    )
    mode = "PAPER" if args.paper else "LIVE"
    print(
        f"recorded {mode} fill for {ticket.ticket_id}: {ticket.side} {args.qty} {ticket.symbol} "
        f"@ {args.px} (row_id={row_id})"
    )


if __name__ == "__main__":
    main()
