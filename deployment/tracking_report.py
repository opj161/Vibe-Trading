"""Weekly tracking-error report (CPD-1 §A3): compares the ledger's realized
P&L against the frozen engines' own paper equity curves for the same signals
-- the single most important quality control this deployment layer has (it
catches execution slippage, missed signals, or a ledger/engine divergence
before it compounds).

Rewritten 2026-07-03 (reassessment §3.1) -- the original implementation had
five defects that could produce a wrong divergence in either direction:

1. it summed ALL confirmed fills ever while the paper side was windowed to
   ``since_date`` (mismatched windows after the first quarter);
2. it ignored the ledger's ``paper`` column (paper and live rows mixed);
3. it divided by the LATEST sleeve equity, not the anchor-date equity
   (divergence shrank mechanically as the account grew);
4. it averaged strategy paper returns unweighted instead of using the
   profile's sleeve weights (30/70);
5. it compared against full-M1 even though deployed macro (long/flat) tracks
   the frozen M1LF expression.

The live side now reuses ``marking.value_sleeve`` (anchor snapshot at the
window start + windowed signed cash flows + current marks -- exact whenever
no position predates the anchor, flagged when one does), and both sides are
composited with the active profile's weights so like is compared with like.

Known, documented residual bias: the frozen M1-family backtests model zero
commission for US-equity codes (see deployment/README.md), so live macro
should run slightly behind paper by real IBKR costs -- a few bps, not the
3%/quarter tolerance's scale.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import pandas as pd

from deployment._bootstrap import AGENT_DIR
from deployment import marking, profiles


def latest_paper_equity_curve(strategy: str) -> Optional[pd.Series]:
    """Most recent ``agent/runs/deploy_<strategy>_*/artifacts/equity.csv``
    (signal_runner.py's own audit-trail runs), as an equity Series indexed by
    date. None if no audit-trail run exists yet for this strategy."""
    candidates = sorted((AGENT_DIR / "runs").glob(f"deploy_{strategy}_*"), reverse=True)
    for run_dir in candidates:
        equity_path = run_dir / "artifacts" / "equity.csv"
        if equity_path.exists():
            df = pd.read_csv(equity_path, index_col=0, parse_dates=True)
            return df["equity"]
    return None


def paper_return_pct_since(strategy: str, since_date: str) -> Optional[float]:
    """Cumulative % return of the paper equity curve from ``since_date`` to
    its last available bar."""
    equity = latest_paper_equity_curve(strategy)
    if equity is None or equity.empty:
        return None
    window = equity[equity.index >= since_date]
    if len(window) < 2:
        return None
    return float(window.iloc[-1] / window.iloc[0] - 1.0) * 100


def build_report(
    *,
    since_date: str,
    mark_prices: dict[tuple[str, str], float],
    paper: bool,
    profile: Optional[profiles.Profile] = None,
) -> dict:
    """Compare live vs. paper cumulative return since ``since_date`` (the
    deployment start date, or the start of the current quarter -- there must
    be an equity snapshot at/before it, which the go-live checklist's seeding
    step guarantees).

    Args:
        since_date: Window start (YYYY-MM-DD).
        mark_prices: {(symbol, venue): current_price} for every open
            position (callers fetch these live -- ``marking.fetch_mark_prices``
            -- so this module stays network-free and testable).
        paper: Which ledger mode to report on. Always explicit -- the paper
            gate (<1%) and the live tolerance (3%/quarter) are different
            questions and must never see each other's rows.
        profile: Deployment profile; defaults to the active one.

    Returns:
        {"since_date", "mode", "profile",
         "by_sleeve": {sleeve: {"anchor_equity", "current_equity",
                                "pnl_usd", "return_pct"}},
         "by_strategy_paper_return_pct": {strategy: pct | None},
         "live_return_pct", "paper_return_pct", "divergence_pct",
         "warnings": [str, ...]}

        ``live_return_pct``/``paper_return_pct`` are profile-weighted
        composites; ``divergence_pct`` is their absolute difference and is
        None when either side has no data yet.

    Raises:
        ValueError: If no equity snapshot exists at/before ``since_date``
            for a sleeve the profile deploys -- without an anchor the report
            is meaningless, and a silent zero would masquerade as infinite
            divergence.
    """
    profile = profile or profiles.active_profile()
    warnings: list[str] = []

    # -- Live side: per-sleeve valuation anchored at the window start.
    by_sleeve: dict[str, dict] = {}
    live_weighted = 0.0
    live_weight_total = 0.0
    sleeves = {a.sleeve for a in profile.allocations.values()}
    for sleeve in sorted(sleeves):
        valuation = marking.value_sleeve(
            sleeve, paper=paper, mark_prices=mark_prices, anchor_date=since_date
        )
        anchor = valuation["anchor_balance"]
        if anchor <= 0:
            raise ValueError(
                f"no equity snapshot at/before {since_date} for sleeve {sleeve!r} -- "
                f"seed deployment/state/equity_snapshots.csv before running the report"
            )
        if valuation["anchor_date"] != since_date:
            warnings.append(
                f"{sleeve}: anchor snapshot is dated {valuation['anchor_date']}, "
                f"not {since_date} -- live window starts at the snapshot date"
            )
        if valuation["carryover"]:
            warnings.append(
                f"{sleeve}: fills before {since_date} leave open positions "
                f"{sorted(valuation['carryover'])} unvalued at the anchor -- "
                f"return_pct is approximate"
            )
        if valuation["unmarked"]:
            warnings.append(
                f"{sleeve}: no mark price for open positions "
                f"{sorted(valuation['unmarked'])} -- their value is excluded"
            )
        pnl = valuation["cash_flow"] + valuation["position_value"]
        return_pct = pnl / anchor * 100
        by_sleeve[sleeve] = {
            "anchor_equity": anchor,
            "current_equity": valuation["equity"],
            "pnl_usd": pnl,
            "return_pct": return_pct,
        }
        weight = profile.sleeve_weight(sleeve)
        live_weighted += weight * return_pct
        live_weight_total += weight
    live_return_pct = live_weighted / live_weight_total if live_weight_total > 0 else None

    # -- Paper side: profile-weighted composite of each deployed strategy's
    # own frozen-engine curve (M1LF for the long/flat macro book, per §84.3).
    by_strategy: dict[str, Optional[float]] = {}
    paper_weighted = 0.0
    paper_weight_total = 0.0
    for strategy, alloc in profile.allocations.items():
        pr = paper_return_pct_since(strategy, since_date)
        by_strategy[strategy] = pr
        if pr is None:
            warnings.append(
                f"{strategy}: no deploy_{strategy}_* audit-trail curve covering "
                f"{since_date} -- excluded from the paper composite"
            )
            continue
        paper_weighted += alloc.weight * pr
        paper_weight_total += alloc.weight
    paper_return_pct = (
        paper_weighted / paper_weight_total if paper_weight_total > 0 else None
    )

    divergence_pct = (
        abs(live_return_pct - paper_return_pct)
        if live_return_pct is not None and paper_return_pct is not None
        else None
    )

    return {
        "since_date": since_date,
        "mode": "paper" if paper else "live",
        "profile": profile.name,
        "by_sleeve": by_sleeve,
        "by_strategy_paper_return_pct": by_strategy,
        "live_return_pct": live_return_pct,
        "paper_return_pct": paper_return_pct,
        "divergence_pct": divergence_pct,
        "warnings": warnings,
    }


def main() -> None:
    """``python -m deployment.tracking_report`` -- the weekly cron entry point.
    Fetches live marks for every open position in the chosen mode, builds the
    report, pushes the Telegram summary, and prints the full JSON."""
    from deployment import alerts, ledger, risk_rules

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=None, help="Window start YYYY-MM-DD "
                        "(default: the earliest equity snapshot date -- deployment start)")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    profile = profiles.PROFILES[args.profile] if args.profile else profiles.active_profile()
    paper = args.mode == "paper"
    if args.since is None:
        snapshots = ledger.read_equity_snapshots()
        if snapshots.empty:
            print("error: no equity snapshots -- pass --since or seed the ledger first",
                  file=sys.stderr)
            sys.exit(3)
        args.since = str(snapshots["date"].min())
    marks = marking.fetch_mark_prices(ledger.open_positions(paper=paper))
    try:
        report = build_report(since_date=args.since, mark_prices=marks,
                              paper=paper, profile=profile)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(3)

    notifier = alerts.build_notifier()
    if report["divergence_pct"] is not None:
        notifier.notify(alerts.format_tracking_error_summary(
            report["divergence_pct"], risk_rules.QUARTER_TRACKING_ERROR_TOLERANCE_PCT,
        ))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
