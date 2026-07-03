"""Daily signal generation for the CPD-1 deployment composite (frozen ZA4 crypto
sleeve + frozen M1 macro sleeve).

Reuses the forward-validation ritual (``forward_validation/run_forward.py``) for
the audit-trail side: copies the frozen ``{config.json, signal_engine.py}`` into
a fresh ``agent/runs/deploy_<strategy>_<date>`` dir and runs
``backtest/runner.py`` as a subprocess, exactly like the quarterly ritual does --
this produces the same ``artifacts/positions.csv``/``equity.csv`` used for the
tracking-error report later.

That alone is not enough to get "today's order," though: ``positions.csv`` is
one bar stale for this purpose. ``backtest/engines/base.py::_align`` computes
``pos[c] = raw.shift(1)...`` -- row ``dt`` is the signal from ``dt-1``'s close,
executed at ``dt``'s open. So the last row of a completed run is the position
that should *already* be held as of today's open, not tomorrow's target. To get
"what to trade after today's close," this module also calls the exact same
data-fetch + ``signal_engine.generate()`` steps ``backtest/runner.py::main()``
calls internally, and reads the RAW (pre-shift) value at the last bar -- no
strategy logic is reimplemented, only the thin fetch/dispatch glue already used
in ``runner.py``.

That fetch glue itself has a source-dependent subtlety worth being precise
about: for ``source="auto"`` (M1), ``runner.py::main()`` fetches once via
``_fetch_auto`` + ``_sanitize_data_map`` and wraps the result in ``_AutoLoader``,
so that IS the data the engine trains on. For a single source (ZA4's
``source="okx"``), ``main()``'s top-level fetch is only used for validation
checks and is discarded -- ``base.py::run_backtest`` step 1 re-fetches via
``loader.fetch()`` directly, with no ``_sanitize_data_map`` pass. This module's
``_fetch_data_map_for_signal`` branches the same way so the raw signal is
computed on provably the same data the real backtest run trains on.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from deployment._bootstrap import AGENT_DIR, FROZEN_DIR, STATE_DIR

logger = logging.getLogger(__name__)

# Same 13-month warmup convention forward_validation/run_forward.py already
# validated covers every frozen strategy's longest lookback (M1's 12-month
# TSMOM leg) with margin. Reused verbatim, not re-derived, so the deployment
# path and the quarterly ledger path are never subtly different windows.
WARMUP_START = "2025-06-01"


def _default_strategies() -> list[str]:
    """Deployed + shadow strategies from the active profile (cpd1_lf: ZA4,
    M1LF, shadow ZD2). Shadow runs cost one extra subprocess backtest per day
    and buy the forward-arbitration paper curve (findings §80.3's 'ZD2 vs ZA4
    is the live question')."""
    from deployment import profiles

    return list(profiles.active_profile().all_strategies)

# Conservative shared threshold across both crypto (trades 24/7, so any gap is
# notable) and macro (weekends/holidays routinely produce 3-4 calendar-day
# gaps) sleeves. This is a visibility flag on the raw signal only -- a
# tighter, crypto-specific "missed daily run" check belongs in risk_rules.py,
# driven by the ledger's last-confirmed-fill timestamp, not this generic gate.
STALE_THRESHOLD_DAYS = 4


@dataclasses.dataclass(frozen=True)
class SymbolTarget:
    prev_direction: int
    direction: int
    target_weight: float
    flipped: bool


@dataclasses.dataclass(frozen=True)
class SignalState:
    as_of_date: str
    generated_at: str
    # name -> {"engine_sha256", "effective_as_of", "stale", "targets": {symbol: SymbolTarget}}
    strategies: dict

    def to_json_dict(self) -> dict:
        return {
            "as_of_date": self.as_of_date,
            "generated_at": self.generated_at,
            "strategies": {
                name: {
                    "engine_sha256": info["engine_sha256"],
                    "effective_as_of": info["effective_as_of"],
                    "stale": info["stale"],
                    "targets": {
                        sym: dataclasses.asdict(t) for sym, t in info["targets"].items()
                    },
                }
                for name, info in self.strategies.items()
            },
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fetch_data_map_for_signal(config: dict) -> dict:
    """Fetch data the same way the real engine trains on it, for either
    ``source="auto"`` or a single named source. See module docstring."""
    from backtest.runner import _fetch_auto, _get_loader, _normalize_codes, _sanitize_data_map

    codes = config["codes"]
    interval = config.get("interval", "1D")
    source = config.get("source", "tushare")
    start_date = config.get("start_date", "")
    end_date = config.get("end_date", "")

    if source == "auto":
        data_map = _fetch_auto(codes, config, interval)
        return _sanitize_data_map(data_map)

    normalized = _normalize_codes(codes, source)
    LoaderCls = _get_loader(source)
    return LoaderCls().fetch(
        normalized, start_date, end_date,
        fields=config.get("extra_fields") or None, interval=interval,
    )


def _raw_targets(strategy: str, as_of: str) -> tuple[dict, dict]:
    """Return (raw signal_map[symbol] -> pd.Series, config actually used).

    Loads the frozen config/signal_engine fresh (never mutates frozen/*),
    overrides start/end date to the deployment window, fetches data, and calls
    ``SignalEngine.generate()`` -- the one and only place strategy logic runs.
    """
    frozen = FROZEN_DIR / strategy
    config = json.loads((frozen / "config.json").read_text())
    config["start_date"] = WARMUP_START
    config["end_date"] = as_of
    config.pop("validation", None)

    data_map = _fetch_data_map_for_signal(config)
    if not data_map:
        raise RuntimeError(f"{strategy}: no data fetched for signal generation")

    # Audit fix 2026-07-03: gate on data integrity BEFORE any signal is
    # generated -- an observed (not hypothetical) flaky fetch produced a
    # silently degraded draw that warped 21 years of M1 flip dates. No ticket
    # may be built from a fetch that fails these checks.
    from deployment.data_integrity import check_data_map

    check_data_map(strategy, data_map)

    # Reuse runner.py's own AST-validated loader (rejects import-time-executable
    # signal_engine.py) rather than re-implementing that safety check here.
    from backtest.runner import _load_module_from_file, _validate_signal_engine_class

    module = _load_module_from_file(frozen / "signal_engine.py", f"signal_engine_{strategy}")
    engine_cls = module.SignalEngine
    _validate_signal_engine_class(engine_cls)
    signal_map = engine_cls().generate(data_map)
    return signal_map, config


def _run_audit_trail(strategy: str, as_of: str) -> Path:
    """Reproduce forward_validation/run_forward.py's ritual for the audit trail
    (artifacts/positions.csv, equity.csv) -- same subprocess invocation, isolated
    into its own ``agent/runs/deploy_*`` dir (gitignored, regenerable)."""
    frozen = FROZEN_DIR / strategy
    config = json.loads((frozen / "config.json").read_text())
    config["start_date"] = WARMUP_START
    config["end_date"] = as_of
    config.pop("validation", None)

    run_dir = AGENT_DIR / "runs" / f"deploy_{strategy}_{as_of.replace('-', '')}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "code").mkdir(parents=True)
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))
    shutil.copy(frozen / "signal_engine.py", run_dir / "code" / "signal_engine.py")

    proc = subprocess.run(
        [sys.executable, "backtest/runner.py", str(run_dir)],
        cwd=AGENT_DIR, capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{strategy}: runner failed\n{proc.stderr[-2000:]}")
    return run_dir


def _load_prev_direction(strategy: str, symbol: str) -> int:
    latest_path = STATE_DIR / "latest.json"
    if not latest_path.exists():
        return 0
    try:
        prev = json.loads(latest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    return (
        prev.get("strategies", {})
        .get(strategy, {})
        .get("targets", {})
        .get(symbol, {})
        .get("direction", 0)
    )


def run_signal(strategy: str, as_of: Optional[str] = None, *, write_audit_trail: bool = True) -> SignalState:
    """Generate today's target for one frozen strategy.

    Args:
        strategy: Frozen strategy name under ``forward_validation/frozen/``.
        as_of: End date for the fetch window (default: today, UTC).
        write_audit_trail: Also run the full subprocess ritual so
            ``artifacts/positions.csv``/``equity.csv`` exist under
            ``agent/runs/deploy_<strategy>_<date>`` for the tracking-error report.
            Disabled by the parity test (which only needs the raw signal, run
            once per day in a 30-day loop -- the subprocess run is the slow part).

    Returns:
        A ``SignalState`` for this single strategy (callers merge across
        strategies -- see ``main()``).
    """
    as_of = as_of or dt.datetime.now(dt.timezone.utc).date().isoformat()
    frozen = FROZEN_DIR / strategy
    if not frozen.is_dir():
        raise ValueError(f"Unknown frozen strategy {strategy!r} (no {frozen})")

    signal_map, _config = _raw_targets(strategy, as_of)
    if write_audit_trail:
        _run_audit_trail(strategy, as_of)

    # The requested end_date is not necessarily the actual last available bar
    # (e.g. OKX/yfinance haven't posted today's candle yet) -- record the real
    # last-bar date per strategy so a stale signal is visible, not silently
    # relabeled as "today". direction/weight below is read from THIS bar.
    last_bar_dates = [series.index[-1] for series in signal_map.values() if not series.empty]
    if not last_bar_dates:
        raise RuntimeError(f"{strategy}: signal_engine returned only empty series")
    effective_as_of = max(last_bar_dates)
    effective_as_of_str = effective_as_of.date().isoformat()
    stale_days = (pd.Timestamp(as_of).date() - effective_as_of.date()).days
    stale = stale_days > STALE_THRESHOLD_DAYS
    if stale:
        logger.warning(
            "%s: signal is %d day(s) stale (requested %s, last bar %s)",
            strategy, stale_days, as_of, effective_as_of_str,
        )

    # backtest/engines/base.py::_align applies a row-wise gross-exposure clip
    # AFTER the shift/optimizer step -- sum(abs(weights)) is scaled down (never
    # up) to stay <= 1.0. That clip is part of what actually executes, so the
    # deployment target must apply it too (confirmed empirically: this repo's
    # own A1 parity test failed by ~0.7% on a real historical day before this
    # was added -- see deployment/tests/test_signal_runner_parity.py). Reuses
    # the exact same helper _align calls, not a re-derived formula.
    from backtest.engines.base import normalize_gross_exposure

    raw_row = pd.DataFrame(
        {sym: [float(series.iloc[-1])] for sym, series in signal_map.items() if not series.empty}
    )
    normalized_row = normalize_gross_exposure(raw_row).iloc[0]

    targets: dict[str, SymbolTarget] = {}
    for symbol, series in signal_map.items():
        if series.empty:
            continue
        raw = float(normalized_row[symbol])
        direction = 1 if raw > 1e-9 else (-1 if raw < -1e-9 else 0)
        prev_direction = _load_prev_direction(strategy, symbol)
        targets[symbol] = SymbolTarget(
            prev_direction=prev_direction,
            direction=direction,
            target_weight=raw,
            flipped=(direction != prev_direction),
        )

    return SignalState(
        as_of_date=as_of,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        strategies={
            strategy: {
                "engine_sha256": _sha256(frozen / "signal_engine.py"),
                "effective_as_of": effective_as_of_str,
                "stale": stale,
                "targets": targets,
            }
        },
    )


def merge_states(states: list[SignalState]) -> SignalState:
    """Combine multiple single-strategy SignalStates (from run_signal) into one."""
    if not states:
        raise ValueError("no states to merge")
    merged_strategies: dict[str, Any] = {}
    for s in states:
        merged_strategies.update(s.strategies)
    return SignalState(
        as_of_date=states[-1].as_of_date,
        generated_at=states[-1].generated_at,
        strategies=merged_strategies,
    )


def write_state(state: SignalState) -> Path:
    out = STATE_DIR / f"signal_state_{state.as_of_date.replace('-', '')}.json"
    out.write_text(json.dumps(state.to_json_dict(), indent=2))
    # latest.json is merge-preserving per strategy: if a strategy failed its
    # integrity gate today (absent from `state`), its previous targets must
    # survive here -- otherwise tomorrow's _load_prev_direction would see 0
    # and manufacture a spurious "flip" ticket (audit fix 2026-07-03). Each
    # strategy entry carries its own effective_as_of, so staleness stays
    # visible per strategy.
    latest_path = STATE_DIR / "latest.json"
    merged = state.to_json_dict()
    if latest_path.exists():
        try:
            prev = json.loads(latest_path.read_text())
            for name, info in prev.get("strategies", {}).items():
                merged["strategies"].setdefault(name, info)
        except (json.JSONDecodeError, OSError):
            pass  # unreadable previous state: today's state stands alone
    latest_path.write_text(json.dumps(merged, indent=2))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategies", default=",".join(_default_strategies()),
        help="Comma-separated frozen strategy names (default: the active "
             "profile's deployed + shadow strategies)",
    )
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument(
        "--no-audit-trail", action="store_true",
        help="Skip the subprocess backtest run (positions.csv/equity.csv artifacts); "
             "only compute the raw signal. Faster, used by the parity test.",
    )
    args = parser.parse_args()

    names = [n.strip() for n in args.strategies.split(",") if n.strip()]
    from deployment import alerts
    from deployment.data_integrity import DataIntegrityError

    notifier = alerts.build_notifier()
    states, failed = [], []
    for name in names:
        try:
            states.append(run_signal(name, args.as_of, write_audit_trail=not args.no_audit_trail))
        except DataIntegrityError as exc:
            # No state written for this strategy, no tickets downstream --
            # the previous day's latest.json stays authoritative for it.
            failed.append(name)
            msg = alerts.format_data_integrity_alert(name, str(exc))
            notifier.notify(msg)
            print(f"[signal_runner] DATA INTEGRITY FAILURE {name}: {exc}", file=sys.stderr)
    if states:
        merged = merge_states(states)
        out_path = write_state(merged)
        print(json.dumps(merged.to_json_dict(), indent=2))
        print(f"\n[signal_runner] wrote {out_path}", file=sys.stderr)
    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
