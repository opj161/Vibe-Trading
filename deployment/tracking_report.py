"""Weekly tracking-error report (CPD-1 §A3): compares the live ledger's
realized P&L against the frozen engine's own paper equity curve for the
same signals -- the single most important quality control this deployment
layer has (it catches execution slippage, missed signals, or a ledger/engine
divergence before it compounds).

Live P&L per (symbol, venue) is cash-flow accounting: every confirmed BUY
subtracts cash, every SELL adds cash, fees always subtract; any currently
open position is marked to its current price. This is exact as long as every
round trip in the ledger is fully accounted for (no external transfers) --
true for this deployment layer since nothing else touches the ledger.

Paper P&L reuses the frozen engine's own equity.csv (produced by
signal_runner.py's audit-trail run) rather than recomputing anything, per the
platform-wide "don't reimplement the ritual" discipline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from deployment._bootstrap import AGENT_DIR
from deployment import ledger


def realized_and_unrealized_pnl(symbol: str, venue: str, mark_price: float) -> float:
    """Cash-flow P&L for one (symbol, venue): sum of signed fill cash flows
    (sells add, buys subtract, fees always subtract) plus the mark-to-market
    value of any currently open position."""
    fills = ledger.confirmed_fills()
    sub = fills[(fills["symbol"] == symbol) & (fills["venue"] == venue)]
    cash_flow = 0.0
    for _, row in sub.iterrows():
        sign = -1.0 if row["side"] == "buy" else 1.0
        cash_flow += sign * float(row["qty"]) * float(row["price"]) - float(row["fee"])
    open_qty = ledger.current_position(symbol, venue)
    return cash_flow + open_qty * mark_price


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


def build_report(*, since_date: str, mark_prices: dict[tuple[str, str], float]) -> dict:
    """Compare live vs. paper cumulative return since ``since_date`` (the
    deployment start date, or the start of the current quarter).

    Args:
        since_date: Window start (YYYY-MM-DD).
        mark_prices: {(symbol, venue): current_price} for every symbol/venue
            pair that has ever had a confirmed fill (caller fetches these
            live -- see venue_specs.py -- so this module stays network-free
            and testable).

    Returns:
        {"since_date", "live_pnl_usd", "paper_return_pct", "live_return_pct",
         "divergence_pct", "by_strategy": {...}}
    """
    from deployment.order_tickets import STRATEGY_SLEEVE

    fills = ledger.confirmed_fills()
    live_pnl_total = 0.0
    by_symbol_venue = {}
    for (symbol, venue), price in mark_prices.items():
        pnl = realized_and_unrealized_pnl(symbol, venue, price)
        by_symbol_venue[f"{symbol}@{venue}"] = pnl
        live_pnl_total += pnl

    sleeve_equity = ledger.latest_sleeve_equity()
    reference_equity = sleeve_equity["crypto_equity"] + sleeve_equity["macro_equity"]
    live_return_pct = (live_pnl_total / reference_equity * 100) if reference_equity > 0 else None

    by_strategy = {}
    paper_returns = []
    for strategy in STRATEGY_SLEEVE:
        pr = paper_return_pct_since(strategy, since_date)
        by_strategy[strategy] = pr
        if pr is not None:
            paper_returns.append(pr)
    paper_return_pct = sum(paper_returns) / len(paper_returns) if paper_returns else None

    divergence_pct = (
        abs(live_return_pct - paper_return_pct)
        if live_return_pct is not None and paper_return_pct is not None
        else None
    )

    return {
        "since_date": since_date,
        "live_pnl_usd": live_pnl_total,
        "live_return_pct": live_return_pct,
        "paper_return_pct": paper_return_pct,
        "divergence_pct": divergence_pct,
        "by_symbol_venue": by_symbol_venue,
        "by_strategy_paper_return_pct": by_strategy,
    }
