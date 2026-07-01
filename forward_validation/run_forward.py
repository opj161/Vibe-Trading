#!/usr/bin/env python3
"""Forward-validation ritual runner (research plan P0.2/P0.3).

Re-runs the frozen champion strategies on the accruing post-2026-06-30 window
and appends true-window metrics to an append-only ledger. The frozen
snapshots under ``frozen/<name>/`` must never be edited — that is the whole
point. See README.md in this directory for the ritual rules.

Usage (from the repo root)::

    python3 forward_validation/run_forward.py [--end YYYY-MM-DD] [--only Z4,Z8]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
AGENT = REPO / "agent"
RUNS = AGENT / "runs"
LEDGER = HERE / "results.csv"

# All frozen engines' longest lookback is M1's 12-month TSMOM leg; a uniform
# ~13-month warmup covers every strategy with margin.
WARMUP_START = "2025-06-01"
# First day of the genuine forward window (the historical frozen OOS window
# ended 2026-06-30; everything after it is virgin data).
TRUE_START = "2026-07-01"

LEDGER_COLUMNS = [
    "run_timestamp", "strategy", "engine_sha256", "window_start", "window_end",
    "true_days", "true_return_pct", "true_sharpe", "true_max_dd_pct",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def true_window_metrics(equity_csv: Path) -> tuple[int, float, float, float]:
    e = pd.read_csv(equity_csv, parse_dates=["timestamp"])
    e = e[e.timestamp >= TRUE_START].reset_index(drop=True)
    if len(e) < 2:
        return len(e), float("nan"), float("nan"), float("nan")
    eq = e.equity / e.equity.iloc[0]
    ret = eq.pct_change().dropna()
    years = max((e.timestamp.iloc[-1] - e.timestamp.iloc[0]).days, 1) / 365.25
    bars_per_year = len(ret) / years
    sharpe = float("nan")
    if ret.std() > 0:
        sharpe = ret.mean() / ret.std() * np.sqrt(bars_per_year)
    total = (eq.iloc[-1] - 1) * 100
    max_dd = (eq / eq.cummax() - 1).min() * 100
    return len(e), round(total, 2), round(sharpe, 3), round(max_dd, 2)


def run_strategy(name: str, end_date: str) -> dict:
    frozen = HERE / "frozen" / name
    cfg = json.loads((frozen / "config.json").read_text())
    cfg["start_date"] = WARMUP_START
    cfg["end_date"] = end_date
    # Validation suites are for full research backtests; the ledger only
    # needs the sliced equity curve.
    cfg.pop("validation", None)

    run_dir = RUNS / f"fwd_{name}_{end_date.replace('-', '')}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "code").mkdir(parents=True)
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=2))
    shutil.copy(frozen / "signal_engine.py", run_dir / "code" / "signal_engine.py")

    proc = subprocess.run(
        [sys.executable, "backtest/runner.py", str(run_dir)],
        cwd=AGENT, capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name}: runner failed\n{proc.stderr[-2000:]}")

    days, total, sharpe, max_dd = true_window_metrics(run_dir / "artifacts" / "equity.csv")
    return {
        "run_timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "strategy": name,
        "engine_sha256": sha256(frozen / "signal_engine.py")[:16],
        "window_start": TRUE_START,
        "window_end": end_date,
        "true_days": days,
        "true_return_pct": total,
        "true_sharpe": sharpe,
        "true_max_dd_pct": max_dd,
    }


def append_ledger(rows: list[dict]) -> None:
    is_new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--only", default="", help="Comma-separated subset of strategy names")
    args = parser.parse_args()

    names = sorted(p.name for p in (HERE / "frozen").iterdir() if p.is_dir())
    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        unknown = wanted - set(names)
        if unknown:
            raise SystemExit(f"Unknown strategies: {sorted(unknown)} (have {names})")
        names = [n for n in names if n in wanted]

    rows = []
    for name in names:
        print(f"[forward-validation] running {name} through {args.end} ...", flush=True)
        try:
            row = run_strategy(name, args.end)
        except Exception as exc:  # noqa: BLE001 - ledger run must report per-strategy failures
            print(f"  FAILED: {exc}", file=sys.stderr)
            continue
        rows.append(row)
        print(f"  {row['true_days']} true-window bars | ret {row['true_return_pct']}% "
              f"| sharpe {row['true_sharpe']} | maxDD {row['true_max_dd_pct']}%")

    if rows:
        append_ledger(rows)
        print(f"[forward-validation] appended {len(rows)} rows to {LEDGER}")
    else:
        raise SystemExit("No strategies completed — nothing appended.")


if __name__ == "__main__":
    main()
