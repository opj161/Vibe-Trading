"""CPD-1 Phase D: macro-sleeve breadth study (pre-registered,
vibe_trading_deployment_plan_CPD1.md §D).

Binding pre-registration, quoted verbatim from the plan: "exactly two
variants against the M1 control -- M1X-a (SPY+GLD+TLT) and M1X-b
(SPY+GLD+TLT+commodity proxy). Same engine, same frozen M1 hyperparameters
(no re-tuning), full 2005->present window, DSR with n_trials=3. Decision
rule: promote to a forward-track freeze only if Sharpe improves >=0.1 AND
maxDD does not worsen >=2pp on the full window; otherwise record the
negative and keep M1. The 2025-07->2026-06 window is burned for M1
selection -- treat it as a consistency check only."

M1X-a/M1X-b's signal_engine.py are byte-identical copies of the frozen M1
engine (verified via diff at build time, same discipline as ZA4B's own
"universe-agnostic, confirmed via diff" freeze) -- only the ``codes`` list
in config.json changes. Commodity proxy: DBC (Invesco DB Commodity Index
Tracking Fund, UCITS-deployable, live since 2006-02).

Usage::

    python3 research/macro_breadth/run_m1x_study.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
AGENT = REPO / "agent"
FROZEN_M1 = REPO / "forward_validation" / "frozen" / "M1"

START_DATE = "2005-01-01"
FORWARD_ONLY_START = "2025-07-01"  # consistency check only, per pre-registration
SHARPE_IMPROVEMENT_THRESHOLD = 0.10
MAXDD_WORSENING_THRESHOLD = 0.02  # 2 percentage points
BARS_PER_YEAR = 252
N_TRIALS = 3

VARIANTS = {
    "M1": {"codes": ["SPY.US", "GLD.US"], "engine_src": FROZEN_M1 / "signal_engine.py"},
    "M1X_a": {"codes": ["SPY.US", "GLD.US", "TLT.US"], "engine_src": HERE / "M1X_a" / "signal_engine.py"},
    "M1X_b": {
        "codes": ["SPY.US", "GLD.US", "TLT.US", "DBC.US"],
        "engine_src": HERE / "M1X_b" / "signal_engine.py",
    },
}


def _build_config(codes: list[str], end_date: str) -> dict:
    return {
        "source": "auto",
        "codes": codes,
        "start_date": START_DATE,
        "end_date": end_date,
        "interval": "1D",
        "engine": "daily",
        "initial_cash": 1000000,
        "benchmark": "SPY.US",
        "optimizer": None,
        "optimizer_params": {},
    }


def run_variant(name: str, spec: dict, end_date: str) -> Path:
    run_dir = AGENT / "runs" / f"v_M1X_study_{name}_full"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "code").mkdir(parents=True)
    (run_dir / "config.json").write_text(json.dumps(_build_config(spec["codes"], end_date), indent=2))
    shutil.copy(spec["engine_src"], run_dir / "code" / "signal_engine.py")

    proc = subprocess.run(
        [sys.executable, "backtest/runner.py", str(run_dir)],
        cwd=AGENT, capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name}: runner failed\n{proc.stderr[-2000:]}")
    # Data-integrity guard (audit 2026-07-03): a flaky auto-source fetch was
    # observed to silently degrade one run's data (same-day M1 draws gave
    # Sharpe 0.61/0.44/0.61) -- refuse to report metrics from a bad draw.
    for f in (run_dir / "artifacts").glob("ohlcv_*.csv"):
        d = pd.read_csv(f)
        n_nan = int(d["close"].isna().sum())
        if n_nan:
            raise RuntimeError(f"{name}: {f.name} has {n_nan} NaN close(s) -- bad fetch draw, rerun")
    return run_dir


def window_metrics(equity_csv: Path, window_start: str | None = None) -> dict:
    e = pd.read_csv(equity_csv, parse_dates=["timestamp"])
    if window_start:
        e = e[e.timestamp >= window_start].reset_index(drop=True)
    if len(e) < 5:
        return {"n_days": len(e), "ann_return_pct": float("nan"), "sharpe": float("nan"), "max_dd_pct": float("nan")}
    eq = e.equity / e.equity.iloc[0]
    ret = eq.pct_change().dropna()
    years = max((e.timestamp.iloc[-1] - e.timestamp.iloc[0]).days, 1) / 365.25
    ann_return = (eq.iloc[-1] ** (1 / years) - 1) * 100
    sharpe = float(ret.mean() / ret.std() * np.sqrt(BARS_PER_YEAR)) if ret.std() > 0 else float("nan")
    max_dd = float((eq / eq.cummax() - 1).min() * 100)
    return {"n_days": len(e), "ann_return_pct": round(ann_return, 2), "sharpe": round(sharpe, 4), "max_dd_pct": round(max_dd, 2)}


def daily_returns(equity_csv: Path) -> np.ndarray:
    e = pd.read_csv(equity_csv, parse_dates=["timestamp"])
    return e["equity"].pct_change().dropna().to_numpy()


def decide_promotion(sharpe_delta: float, maxdd_worsening_pp: float) -> bool:
    """The pre-registered binding decision rule: promote only if Sharpe
    improves >=0.1 AND maxDD does not worsen >=2pp. A small epsilon guards
    against float noise at an exact-threshold boundary (both sharpe values
    are independently rounded to 4dp before this subtraction, e.g.
    0.70-0.60 can land at 0.09999999999999998, not exactly 0.10)."""
    eps = 1e-9
    return (
        sharpe_delta >= SHARPE_IMPROVEMENT_THRESHOLD - eps
        and maxdd_worsening_pp <= MAXDD_WORSENING_THRESHOLD * 100 + eps
    )


def main() -> None:
    import datetime as dt
    end_date = dt.date.today().isoformat()

    results = {}
    for name, spec in VARIANTS.items():
        print(f"[m1x_study] running {name} through {end_date} ...", flush=True)
        run_dir = run_variant(name, spec, end_date)
        equity_csv = run_dir / "artifacts" / "equity.csv"
        results[name] = {
            "run_dir": str(run_dir),
            "full": window_metrics(equity_csv),
            "forward_only": window_metrics(equity_csv, FORWARD_ONLY_START),
            "returns": daily_returns(equity_csv),
        }
        print(f"  full-window: {results[name]['full']}")
        print(f"  forward-only (consistency check, not for selection): {results[name]['forward_only']}")

    full_sharpes = np.array([results[n]["full"]["sharpe"] for n in VARIANTS])
    sharpe_std_across_trials = float(full_sharpes.std(ddof=1))
    print(f"\n[m1x_study] cross-trial Sharpe dispersion (n_trials={N_TRIALS}): {sharpe_std_across_trials:.4f}")

    control = results["M1"]["full"]
    decisions = {}
    for name in ("M1X_a", "M1X_b"):
        variant = results[name]["full"]
        sharpe_delta = variant["sharpe"] - control["sharpe"]
        maxdd_worsening = (control["max_dd_pct"] - variant["max_dd_pct"])  # positive = worse (more negative dd)
        from backtest.validation import deflated_sharpe_ratio  # noqa: PLC0415 -- agent/ on sys.path only after subprocess step

        dsr = deflated_sharpe_ratio(
            results[name]["returns"], n_trials=N_TRIALS,
            sharpe_std_across_trials=sharpe_std_across_trials, bars_per_year=BARS_PER_YEAR,
        )
        promote = decide_promotion(sharpe_delta, maxdd_worsening)
        decisions[name] = {
            "sharpe_delta": round(sharpe_delta, 4),
            "maxdd_worsening_pp": round(maxdd_worsening, 2),
            "dsr": dsr,
            "promote": promote,
        }
        print(f"\n[m1x_study] {name}: Sharpe {control['sharpe']:.3f} -> {variant['sharpe']:.3f} "
              f"(delta {sharpe_delta:+.3f}); maxDD {control['max_dd_pct']:.1f}% -> {variant['max_dd_pct']:.1f}% "
              f"(worsening {maxdd_worsening:+.1f}pp); DSR={dsr.get('dsr')}; PROMOTE={promote}")

    out = {"variants": {n: {"full": r["full"], "forward_only": r["forward_only"]} for n, r in results.items()},
           "sharpe_std_across_trials": sharpe_std_across_trials, "decisions": decisions}
    (HERE / "m1x_study_results.json").write_text(json.dumps(out, indent=2))
    print(f"\n[m1x_study] wrote {HERE / 'm1x_study_results.json'}")


if __name__ == "__main__":
    sys.path.insert(0, str(AGENT))  # for the deflated_sharpe_ratio import inside main()
    main()
