# Quarterly Cadence Checklist (CPD-1 Phase C2)

Run at least quarterly (calendar reminder, not automated scheduling -- a
human or a `/schedule`d agent triggers this). Each item's script is
independently runnable; `quarterly_cadence.py` runs the automatable ones in
sequence and logs a dated summary to `research/quarterly_cadence_log.md`.

## 1. Forward-validation ledger rerun

```bash
python3 forward_validation/run_forward.py
```

Reruns every frozen strategy (Z4, Z8, ZA4, ZA4B, ZD2, M1, CP3, and any newly
promoted `M1X_*`) and appends true-window metrics to
`forward_validation/results.csv`. See `forward_validation/README.md` for the
ritual's own non-negotiable rules (never re-tune against the ledger, never
edit `frozen/`).

## 2. H1 forward-track (BTC + SOL puts expression)

Rerun the phase4/phase5 expression evaluation on the accrued option tape:

```bash
python3 research/vrp_deribit/phase4_trend_expression_options.py   # BTC H1
python3 research/vrp_deribit/phase5_sol_expression.py             # SOL H1
```

Both need the historical option tape refreshed first if it hasn't been
pulled recently -- see `research/vrp_deribit/data_prep.py` and the fetcher
command documented in `vibe_trading_research_findings.md` (the deribit-
historical-data fetcher, §61). The daily snapshotter
(`research/deribit_snapshot/snapshot_daily.py`) closes the "expired-only"
gap going forward, but a full historical refresh is still a separate step.

Record the result against `forward_validation/frozen/H1_overlay/RULE.md`'s
frozen rule -- this is a forward-track measurement, not a re-tune.

## 3. Venue funding re-attribution

```bash
python3 research/assessment_20260703/venue_funding.py
```

Funding regimes drift; re-verify the BTC-short-positive-carry /
SOL-short-small-drag / never-perp-longs rules still hold on the accrued
tape (`venue_data_assessment_20260703.md` §1).

## 4. SOL options capacity re-measurement

```bash
python3 research/nautilus_deribit_options/capacity_study.py
```

The SOL-H1 unlock trigger (`vibe_trading_fresh_assessment_20260703.md` §4/§6
item 2): re-measure whether Deribit's SOL_USDC book has deepened toward the
~25-30x gap closing. Needs the option tape refreshed (see item 2).

## 5. Lot-quantization feasibility vs current account size

```bash
python3 research/assessment_20260703/quantization_study.py
```

The options-expression unlock trigger (`vibe_trading_fresh_assessment_20260703.md`
§8.3/§8.6's scaling map) -- re-run against current Deribit lot sizes/prices
and the account's current size to see whether SOL-H1 (then BTC-H1) has
crossed into "faithful" territory.

## 6. Deployment-layer health (not a research item, but worth checking same cadence)

- `forward_validation/results.csv` vs `deployment/state/live_ledger.csv`
  tracking error still within the pre-registered 3%/quarter tolerance
  (`deployment/tracking_report.py`, `deployment/risk_rules.py`).
- Venue fee schedules / minimums re-verified (spot-checked automatically by
  `deployment/venue_specs.py`'s live-fetch-with-fallback on every ticket run,
  but a manual glance at the fallback constants' staleness is still worth it).

## Non-negotiable rules (same as forward_validation/README.md)

1. Never re-tune anything against these results -- they measure, they don't steer.
2. Never edit `forward_validation/frozen/*`.
3. A negative/no-change result is still a result -- log it in
   `research/quarterly_cadence_log.md`, don't just re-run until something changes.
