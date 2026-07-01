# Forward-Validation Ritual

**Purpose** (research plan P0.2/P0.3): the historical frozen out-of-sample window
(2025-07-01 → 2026-06-30) is fully consumed — every validated result in
`vibe_trading_research_findings.md` is retrospective as of 2026-07-02. From here, the only
source of genuinely new evidence is calendar time on **frozen** strategies. This directory
is that mechanism.

## What is frozen

`frozen/<name>/{config.json, signal_engine.py}` — exact snapshots of the five champions as
of 2026-07-02. **Never edit these files.** If a strategy design changes, that is a *new*
strategy: add a new frozen directory with a new name and track both.

| Name | Source run | Role |
|---|---|---|
| Z4 | `v_Z4_chopfreq_train` | Drawdown-focused crypto champion |
| Z8 | `v_Z8_voltarget_train` | Return/Sharpe-focused crypto champion (see §64.2 caveat) |
| ZA4 | `v_ZA4_regimeconviction_ext_train` | Max-annual-return variant (§63.6) |
| M1 | `v_M1_macro_aqrblend_full` | Macro trend sleeve (SPY+GLD) |
| CP3 | `v_CP3_sleeve_2080_full` | 20/80 crypto/macro sleeve composite |

The single most decision-relevant comparison is **Z8 vs ZA4** — §64.2 showed Z8's edge is
concentrated in the 2025-26 OOS year, so only forward data can arbitrate.

## The ritual

Quarterly (or ad hoc, but at least quarterly), from the repo root:

```bash
python3 forward_validation/run_forward.py
```

The script re-runs every frozen strategy with a uniform 13-month warmup
(start 2025-06-01, covering M1's 12-month lookback), slices the **true forward window
(2026-07-01 onward)**, and appends one row per strategy to `results.csv`
(append-only ledger; each row carries the engine's SHA-256 prefix so silent drift is
detectable).

## Non-negotiable rules

1. **Never re-tune anything against the ledger.** The ledger exists to measure, not to
   steer. If a strategy degrades, that is a finding to record, not a bug to fix in-place.
2. **Never edit `frozen/`.** New designs get new names.
3. Top-line metrics of the underlying `agent/runs/fwd_*` run dirs include the warmup —
   only the ledger's sliced true-window numbers are meaningful.
4. Ledger Sharpe on short windows (< ~90 days) is noise; the return/drawdown columns are
   still worth recording. Judge nothing before at least one full quarter.

## Paper-trading upgrade path (P0.3, optional)

The platform's `trading_*` MCP tools support paper/live broker connections, which would
capture real data-arrival timing (no hindsight bar-boundary choice). Requires account
credentials — a user decision. Until then, this ledger is the forward-tracking mechanism.
A scheduled agent (`/schedule`) can automate the quarterly run if desired.
