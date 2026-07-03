"""Driver for the automatable items in research/quarterly_cadence.md (CPD-1
Phase C2). Runs each item as a subprocess, log-and-continue (one item's
failure never blocks the rest), and appends a dated summary to
research/quarterly_cadence_log.md.

Usage::

    python3 research/quarterly_cadence.py [--skip ITEM,ITEM,...]

Item names: forward_validation, h1_btc, h1_sol, venue_funding, capacity,
quantization.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENT = REPO / "agent"
LOG_PATH = REPO / "research" / "quarterly_cadence_log.md"

# (item_name, cwd, argv) -- cwd matters: forward_validation's ritual expects
# to run from agent/ (matching run_forward.py's own convention), the
# research/ scripts expect the repo root (matching their own hardcoded R=
# path-prefix convention already used across research/assessment_20260703/*).
ITEMS: list[tuple[str, Path, list[str]]] = [
    ("forward_validation", AGENT, [sys.executable, "../forward_validation/run_forward.py"]),
    ("h1_btc", REPO, [sys.executable, "research/vrp_deribit/phase4_trend_expression_options.py"]),
    ("h1_sol", REPO, [sys.executable, "research/vrp_deribit/phase5_sol_expression.py"]),
    ("venue_funding", REPO, [sys.executable, "research/assessment_20260703/venue_funding.py"]),
    ("capacity", REPO, [sys.executable, "research/nautilus_deribit_options/capacity_study.py"]),
    ("quantization", REPO, [sys.executable, "research/assessment_20260703/quantization_study.py"]),
]


def run_item(name: str, cwd: Path, argv: list[str], timeout: int) -> dict:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {
            "name": name, "ok": proc.returncode == 0,
            "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "stdout_tail": "", "stderr_tail": "TIMEOUT"}
    except Exception as exc:  # noqa: BLE001 - one item's crash must not stop the cadence run
        return {"name": name, "ok": False, "stdout_tail": "", "stderr_tail": str(exc)}


def append_log(results: list[dict]) -> None:
    lines = [f"\n## {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"]
    for r in results:
        status = "OK" if r["ok"] else "FAILED"
        lines.append(f"- **{r['name']}**: {status}")
        if not r["ok"] and r["stderr_tail"]:
            lines.append(f"  - error: `{r['stderr_tail'].strip()[-300:]}`")
    is_new = not LOG_PATH.exists()
    with LOG_PATH.open("a") as f:
        if is_new:
            f.write("# Quarterly Cadence Run Log (append-only)\n")
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", default="", help="Comma-separated item names to skip")
    parser.add_argument("--timeout", type=int, default=1800, help="Per-item timeout (seconds)")
    args = parser.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    results = []
    for name, cwd, argv in ITEMS:
        if name in skip:
            print(f"[quarterly_cadence] skipping {name}")
            continue
        print(f"[quarterly_cadence] running {name} ...", flush=True)
        result = run_item(name, cwd, argv, args.timeout)
        results.append(result)
        print(f"  {'OK' if result['ok'] else 'FAILED'}")

    append_log(results)
    n_failed = sum(1 for r in results if not r["ok"])
    print(f"[quarterly_cadence] {len(results) - n_failed}/{len(results)} items OK; log: {LOG_PATH}")


if __name__ == "__main__":
    main()
