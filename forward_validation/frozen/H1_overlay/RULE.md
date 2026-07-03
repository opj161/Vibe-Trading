# H1 Overlay — Frozen Put-Expression Rule (CPD-1 Phase C3)

**Purpose**: write the exact H1 (put-expression) rule once, referenced by the
quarterly cadence's forward-track rerun (`research/quarterly_cadence.md` item
2), so the overlay's forward evidence accrues with zero drift while it waits
for the capital thresholds in `vibe_trading_fresh_assessment_20260703.md`
§8.3/§8.6 to unlock it. **This directory holds no `signal_engine.py`** — H1
is not a homegrown-engine strategy (options aren't supported there, per
CLAUDE.md's framework-assessment note); it is evaluated directly against the
Deribit option tape by the scripts named below. This file is the frozen
parameter record those scripts must keep matching, not new logic.

## The rule, as implemented (source of truth: the code, quoted exactly)

Source scripts (unchanged since the phase4/phase5 research; **never edit
either script's constants without renaming this rule** — the same
new-name-for-new-design discipline `forward_validation/README.md` applies to
`frozen/*` applies here):

- BTC: `research/vrp_deribit/phase4_trend_expression_options.py`
- SOL: `research/vrp_deribit/phase5_sol_expression.py`

| Parameter | Value | Constant name |
|---|---|---|
| Entry window | 20–40 days to expiry | `DTE_BAND = (20, 40)` |
| Moneyness filter | \|log-moneyness\| < 0.075 (near-ATM band) | inline filter on `trades["logm"]` |
| Entry selection | **earliest eligible** real ATM 20-40DTE trade within `[anchor, anchor+3d]` of the direction-run's start — NOT nearest-ATM: the code's `.abs().idxmin()` runs on an already-post-anchor window, so it reduces to earliest-in-window (verified in the Nautilus parity project; `research/nautilus_deribit_options/selector.py` carries a regression test for exactly this distinction) | `find_option_entry` (phase4/phase5) |
| Sizing (OPT-BUDGET variant — the one CPD-1 deploys) | premium = 10% of spot notional at entry | `PREMIUM_BUDGET_FRAC = 0.10` |
| Roll | at expiry, chain continues until the underlying direction-run itself ends (`leg_start = leg_end + 1 day`) | roll loop in `run_tracks`/`main` |
| Option fee | 0.03% of underlying notional per side, capped at 12.5% of premium | `OPT_FEE_RATE = 0.0003`, `OPT_FEE_CAP = 0.125` |
| Settlement/delivery fee | 0.015%, same 12.5%-of-premium cap | `SETTLE_FEE_RATE = 0.00015` |
| Spread — BTC | fixed 0.61% half-spread (phase-2/3 empirical measure) | `HALF_SPREAD = 0.0061` |
| Spread — SOL | **not fixed** — median \|price−mark\|/mark over the ATM 20-40DTE entry pool, measured fresh from whatever tape is loaded each run | `half_spread` (local var, phase5 `main()`) |

The two underlyings share every constant except the spread measurement
method — SOL's book is thinner/younger, so phase5 deliberately measures its
own empirical spread each run rather than reusing BTC's fixed constant. This
is a real, intentional asymmetry, not an oversight; preserve it in any future
refactor.

## Direction source (what triggers a put entry)

Both scripts consume the **same direction-run files** the venue-funding
attribution and quantization studies use —
`research/vrp_deribit/derived/{btc,sol}_direction_runs.csv` — i.e. the
champion strategy's (ZA4/Z8, per which run produced the file) own long/short
run boundaries. H1 does not have an independent entry signal; it is an
*expression* of the existing crypto-sleeve direction onto an options
instrument, put-side only (short-direction runs), per the "H1" naming
(hedge-1 / short-expression-1 in the research log's own convention).

## Capacity thresholds unlocking this rule (do not deploy before these)

Per `vibe_trading_fresh_assessment_20260703.md` §8.3/§8.6's scaling map,
re-verified quarterly by `research/assessment_20260703/quantization_study.py`:

| Underlying | Faithful (floor-policy, not overspending) at | Account size |
|---|---:|---:|
| SOL-H1 | crypto sleeve ≥ ~$5-10k | ~$16-33k (30/70 weights) |
| BTC-H1 | crypto sleeve ≥ ~$25-50k | ~$50-160k |

At CPD-1's actual deployment scale ($1-5k), **the options expression is off
the table** — this rule exists purely so forward evidence keeps accruing
without drift while it waits (§6 item 2 of the fresh assessment: "forward-
track H1 ... quarterly ... unlocks on schedule as capital grows").

## What the quarterly rerun should do

1. Confirm the option tape covers the run window (refresh via the fetcher
   documented in `vibe_trading_research_findings.md` §61 if not).
2. Run both scripts unchanged; record OPT-BUDGET's per-run and aggregate P&L.
3. Re-run `quantization_study.py` against current Deribit lot sizes/prices
   and the account's current size — has either underlying crossed into
   "faithful" territory (table above)?
4. Log the result (win, loss, or "still not faithful") — this is a forward-
   track measurement, not a re-tune; a negative quarter is a result, not a
   reason to change the rule.
