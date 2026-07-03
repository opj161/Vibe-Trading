"""CPD-1 go-live decision support: quantify deployment option (c) — "hold
flat on macro SHORT signals" — for the GO_LIVE_CHECKLIST's undecided
macro-short-expression item.

**Not a promotion study.** M1 stays the deployed reference regardless (CPD-1
§D discipline); this measures, descriptively, what the deployable long/flat
subset of the frozen M1 signal looks like, because IBKR-retail shorting of
UCITS ETFs is a real product decision the human must make with numbers in
hand. Motivation (audit 2026-07-03): M1's short legs LOST $486k over
2005→2026 in the engine's own trades ledger (GLD shorts −$333k/72 trades,
SPY shorts −$153k/68 trades; −17% of total P&L) — but shorts may still earn
their keep as crash hedges (Sharpe/DD), which only a real engine run can
show. Exactly one variant, zero tuning:

  M1LF = frozen M1 signal engine + faithful live-option-(c) transform
         (normalize the full signed book, THEN zero negatives — matching
         what deployment/order_tickets.py + normalize_gross_exposure
         actually do when short tickets are skipped; see
         M1LF/signal_engine.py's inline comment for why this order matters).

Usage::

    python3 research/macro_breadth/run_m1_longflat_study.py
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from run_m1x_study import (
    FORWARD_ONLY_START,
    FROZEN_M1,
    HERE,
    run_variant,
    window_metrics,
)

VARIANTS = {
    "M1": {"codes": ["SPY.US", "GLD.US"], "engine_src": FROZEN_M1 / "signal_engine.py"},
    "M1LF": {"codes": ["SPY.US", "GLD.US"], "engine_src": HERE / "M1LF" / "signal_engine.py"},
}


def main() -> None:
    end_date = dt.date.today().isoformat()
    results = {}
    for name, spec in VARIANTS.items():
        print(f"[m1_longflat] running {name} through {end_date} ...", flush=True)
        run_dir = run_variant(name, spec, end_date)
        equity_csv = run_dir / "artifacts" / "equity.csv"
        results[name] = {
            "run_dir": str(run_dir),
            "full": window_metrics(equity_csv),
            "forward_only": window_metrics(equity_csv, FORWARD_ONLY_START),
        }
        print(f"  full-window: {results[name]['full']}")
        print(f"  forward-only: {results[name]['forward_only']}")

    out = Path(__file__).resolve().parent / "m1_longflat_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\n[m1_longflat] saved {out}")
    d_sh = results["M1LF"]["full"]["sharpe"] - results["M1"]["full"]["sharpe"]
    d_dd = results["M1LF"]["full"]["max_dd_pct"] - results["M1"]["full"]["max_dd_pct"]
    print(f"M1LF vs M1 (full window): Sharpe {d_sh:+.3f}, maxDD {d_dd:+.1f}pp "
          f"(positive maxDD delta = shallower drawdown)")


if __name__ == "__main__":
    main()
