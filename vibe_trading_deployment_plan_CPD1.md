# CPD-1: Deployment & Growth Plan — 2026-07-03

**For the executing agent.** This plan is self-contained but grounded in four session
documents you should read first, in this order:

1. `vibe_trading_fresh_assessment_20260703.md` — why the composite is the product; §8
   scale correction (real capital **$1,000-5,000**); the scaling map.
2. `vibe_trading_venue_data_assessment_20260703.md` — venue mapping, funding rules,
   free-data map, external-project assets.
3. `winning_strategy_technical_overview.md` + `forward_validation/README.md` — the
   frozen champion (ZA4) and the forward-validation ritual you will reuse.
4. `CLAUDE.md` — platform gotchas; **standing discipline rules apply to every step
   here** (pre-registration, append-only ledgers, no re-tuning against results).

**The goal, restated:** highest *realized* profit = edge × capacity × risk-efficiency.
At $1-5k every validated edge fits capacity; risk-efficiency says deploy the
max-Sharpe composite (forward-year Sharpe 1.80, maxDD −12.3%), not the raw crypto
sleeve; and the account's most valuable output at this scale is a **verified live track
record + a debugged one-person process** that justifies scaling capital later. Optimize
for process fidelity and information, not absolute dollars.

**What is being deployed (frozen, do not redesign):**

```
CPD-1 = 30% crypto sleeve + 70% macro sleeve, 1.0x leverage
  crypto sleeve = frozen ZA4 signal (BTC-USDT + SOL-USDT, daily bars,
                  forward_validation/frozen/ZA4/ — byte-frozen)
  macro sleeve  = frozen M1 signal (SPY+GLD AQR blend, monthly,
                  forward_validation/frozen/M1/ — byte-frozen)
  venue map     = IBKR (macro, via UCITS equivalents — PRIIPs blocks US ETFs
                  for EEA retail), Binance spot (crypto longs), Binance USDT-M
                  perps (crypto shorts; Hyperliquid later per Phase E)
  expression    = linear only. LONGS ARE NEVER PERPS (funding attribution:
                  −10.7 to −29.7%/yr while long, two venues). Options are
                  locked until the Phase E capital thresholds.
  sleeve rebalance = monthly, or when sleeve weights drift >5pp from 30/70
```

---

## Phase A — Build the operations layer (`deployment/`)

New top-level directory. Everything here is signal/bookkeeping/notification tooling —
**no order-placing code against real venues anywhere in this plan.** The human places
orders; the tooling makes that a 10-minute, error-resistant daily task.

### A1. `deployment/signal_runner.py` — the daily/monthly signal step

- **Reuse the forward-validation ritual, do not reimplement signals.** The runner
  invokes the platform engine (`agent/backtest/runner.py`) on the *frozen* ZA4
  config/signal_engine over data through today (with the standard 60-day warmup
  buffer), exactly as the `fwd_ZA4_*` runs do, then reads the final row of
  `positions.csv`/target state to obtain today's target direction and weight per asset.
  Same pattern for M1 on its monthly cadence (run it daily anyway; it only changes at
  month boundaries — cheap and removes a scheduling special case).
- Timing convention (must match the engine's validated semantics — signal on bar close,
  execute next open): run after the crypto daily bar close used by the frozen config
  (OKX-style 16:00 UTC boundary — verify against the frozen config's source at build
  time); execution guidance to the human is "as soon as practical after the signal".
  For M1, signal after US close, execute next US open.
- Output: a single `SignalState` JSON (date, per-asset target direction/weight, signal
  changes vs yesterday, funding-check inputs) written to `deployment/state/`.
- **Signal-parity gate (A1 acceptance):** for the last 30 days of history, the runner's
  daily emitted targets must be byte-consistent with a single full historical run of
  the same frozen config over the same window. Add a pytest that does this on a short
  fixture window.

### A2. `deployment/order_tickets.py` — human-readable order instructions

- Input: `SignalState` + the live ledger's current positions + account equity split.
- Output: explicit tickets, e.g.
  `BINANCE SPOT: BUY 0.0041 BTCUSDT (~$250) — reason: ZA4 BTC flip flat→long` /
  `BINANCE USDT-M: SELL 3 SOLUSDT perp (~$240, isolated, 1x) — reason: ZA4 SOL
  flip long→short; funding check: −0.004%/8h (favorable)`.
- Must respect venue minimums and quantization (verify live at build time; snapshot
  values: Binance spot min ~$5 notional; USDT-M min 0.001 BTC / 1 SOL; IBKR fractional
  from ~$1). If a target rounds below a venue minimum, the ticket says SKIP with the
  reason — never force a minimum (the §8.3 lesson: forced minimums silently change the
  risk profile).
- **Funding-sign check** (SHORT tickets only): fetch current funding
  (Binance `premiumIndex`, HL info API — both free, no keys) and stamp it on the
  ticket. Rule (pre-registered here): proceed if projected funding cost <
  +15%/yr annualized against the position; flag "REVIEW" above that. Do not silently
  skip — the human decides on flagged tickets.
- **Macro tickets** name the UCITS instruments. Candidates to verify at build time
  (price-per-share matters for quantization at $1-4k): S&P 500 — SPYL (SPDR, ~€13/sh)
  or VUAA (Vanguard, ~$90); gold — 4GLD (Xetra-Gold) or EGLN (iShares physical).
  Prefer the lowest unit price with adequate spread. Signals stay computed on SPY/GLD
  data (yfinance); document the proxy mapping once in `deployment/README.md`.

### A3. `deployment/ledger.py` + `deployment/state/live_ledger.csv` — append-only live ledger

- The human confirms each executed ticket (fill price/qty/fee) via a tiny CLI
  (`python -m deployment.confirm <ticket-id> --px ... --qty ... --fee ...`); skipped
  tickets are recorded as skipped with reason. Nothing is ever edited in place.
- Daily equity snapshot row (per-venue balances entered weekly by the human is
  acceptable; crypto side can be marked from public prices automatically).
- **Tracking-error report**: weekly, compare live ledger P&L vs the frozen-engine
  paper P&L for the same signals (the A1 runs produce it for free). Pre-registered
  tolerance: cumulative divergence >3% of equity in a quarter → halt new entries,
  investigate, document in the research log before resuming. This is the live
  analogue of the parity gates and the single most important quality control.

### A4. `deployment/alerts.py` — Telegram notifications

- Reuse edgeforge's alerting pattern (`~/projects/edgeforge`, Telegram bot). **Ask the
  user** whether to reuse the existing bot credentials from `edgeforge/.env` or create
  a new bot; do not copy them unprompted (only the HYPERLIQUID_TESTNET* keys were
  pre-authorized and are already in `Vibe-Trading/.env`).
- Alert on: signal flip (with the ticket), funding REVIEW flags, missed daily run,
  drawdown thresholds (below), weekly tracking-error summary.

### A5. Risk rules (pre-registered; implement as checks in A1/A3, alert via A4)

- Account drawdown −15% from high-water mark → alert + reduce new-entry size 50%.
- Account drawdown −20% → close-only mode until human review is logged.
  (Composite bootstrap median maxDD is −18%; these are review tripwires, not
  strategy stops — the strategy's own drawdowns are expected and survivable.)
- Single-day loss >6% (≈6σ) → alert + verify data/fills before any new order.
- Reconciliation: weekly human confirmation that venue balances match the ledger
  within fees; mismatch → halt new entries until explained.

**Phase A acceptance gate:** all modules unit-tested (AAA style, repo conventions);
signal-parity test green; one full simulated day (fixture data → signal → tickets →
confirm → ledger → tracking report) runs end-to-end in CI/pytest.

---

## Phase B — Paper cycle, then go-live

1. **Paper mode (minimum 4 weeks, target ≥1 full crypto entry/exit cycle):** run the
   daily loop for real (real signals, real timestamps), record hypothetical fills at
   observed prices ± the modeled costs. This exercises the *process* — cron reliability,
   ticket clarity, ledger hygiene — not the strategy (already validated).
2. **Go-live checklist (user actions, agent prepares the checklist doc):**
   fund IBKR (EUR→USD conversion note: IBKR spot FX ~$2 min commission — do it once);
   enable Binance USDT-M futures, set isolated margin / 1x on BTCUSDT+SOLUSDT;
   verify chosen UCITS tickers tradable + fractional at the user's IBKR entity;
   jurisdiction tax check (one-line reminder; out of scope otherwise).
3. **Go-live gate (pre-registered):** paper cycle completed with zero missed daily
   runs in the final 2 weeks; tracking error of paper ledger vs engine <1%; user
   signs off. Then deploy at target allocation, starting at the *low* end of the
   user's range.
4. First two live weeks: entries at 50% of computed size (execution shakedown), then
   full size. This is an ops de-risk, not a strategy change; pre-registered here.

---

## Phase C — Standing automation (build once, runs forever)

1. **Daily Deribit chain snapshotter** (`research/deribit_snapshot/snapshot_daily.py` +
   cron): public API, no keys; per BTC + SOL_USDC (+ETH if cheap to include): full
   option chain summary (instrument, bid/ask/mark, mark_iv, delta, OI, underlying) once
   daily → parquet append. Closes the "history API only returns expired options" gap;
   feeds H1 forward-tracking and the future options unlock. Keep it under ~100 lines +
   tests; log-and-continue on API hiccups (never crash the cron).
2. **Quarterly cadence script** (`research/quarterly_cadence.md` checklist + one
   driver where automatable):
   - forward-validation reruns of all frozen strategies (existing ritual);
   - H1 forward-track: rerun the phase4/phase5 expression evaluation on the accrued
     tape (`research/vrp_deribit/`, tape refresh via the documented fetcher command);
   - `research/assessment_20260703/venue_funding.py` (funding regimes drift);
   - `research/nautilus_deribit_options/capacity_study.py` (SOL options book growth —
     the SOL-H1 unlock trigger);
   - `research/assessment_20260703/quantization_study.py` thresholds vs current
     account size (the lot-feasibility unlock trigger).
3. **H1 frozen rule doc** (`forward_validation/frozen/H1_overlay/RULE.md`): the exact
   put-expression rule (earliest-eligible ATM 20-40 DTE, 10% budget, roll at expiry,
   fee/spread constants) written once, referenced by the quarterly rerun — so the
   overlay's forward evidence accrues with zero drift while it waits for capital.

---

## Phase D — The one research item: macro-sleeve breadth (pre-registered)

The only research direction that deploys at $1-5k (China-A is not retail-accessible at
this scale; third-sleeve search pays at $50k+). Bounded, one shot:

- **Hypothesis:** extending M1's validated AQR-blend machinery from SPY+GLD to a
  modestly broader ETF set (add TLT and one diversified-commodity proxy; optionally
  UUP) improves composite Sharpe/DD via more macro breadth. All instruments have UCITS
  equivalents (deployable) and yfinance data (free, adjustment bug already fixed).
- **Pre-registration (binding):** exactly two variants against the M1 control —
  M1X-a (SPY+GLD+TLT) and M1X-b (SPY+GLD+TLT+commodity). Same engine, same frozen
  M1 hyperparameters (no re-tuning), full 2005→present window, DSR with n_trials=3.
  Decision rule: promote to a forward-track freeze only if Sharpe improves ≥0.1 AND
  maxDD does not worsen ≥2pp on the *full* window; otherwise record the negative and
  keep M1. **The 2025-07→2026-06 window is burned for M1 selection — treat it as a
  consistency check only.** Watch the risk-parity/ERC N>2 lessons (CLAUDE.md §44) and
  the TLT dividend-adjustment fix (already platform-wide).
- Whatever the outcome: the deployed sleeve stays M1 until a promoted variant has
  ≥1 quarter of forward-ledger evidence. No exceptions.

---

## Phase E — Scale-up unlocks (entry criteria, not dates)

| Trigger | Unlock | Prepared by |
|---|---|---|
| 2 clean live quarters (tracking error <3%/q, no halts) | raise leverage to **1.5x** (perp margin crypto side; 2x-ETF blend or IBKR margin macro side) — §8.4: dominates weight-shifting | Phase A ledger evidence |
| crypto sleeve ≥ ~$5-10k | **SOL-H1 puts** (Deribit, 1-lot granularity becomes faithful) — re-verify with quantization_study at current prices | Phase C H1 rule + snapshotter |
| account ≥ ~$10-25k | **automation via Nautilus** (adapters exist for all four venues). First leg: shorts on **Hyperliquid** (0.045% taker, +1.7%/yr better BTC short carry, testnet keys already in `.env`) — run the testnet drill first (edgeforge's drill logs are prior art) | HL testnet drill (optional early: agent may build/run the drill any time — it is free and validates the future path) |
| crypto sleeve ≥ ~$25-50k | **BTC-H1 puts** | same |
| account ≥ ~$50k+ | third-sleeve research resumes (China-A momentum first) | Phase D discipline as template |
| account ≥ ~$500k | §4 capacity analysis becomes operative again | capacity_study quarterly |

---

## Hard constraints for the executing agent

1. **Never modify** `forward_validation/frozen/*`, the frozen research oracles
   (`research/vrp_deribit/`), or any validated constant. New code lives in
   `deployment/`, `research/deribit_snapshot/`, and the named research files only.
2. **No live order placement, no mainnet keys, no withdrawal-capable API scopes** —
   this plan's automation ends at tickets + notifications. (The HL *testnet* drill is
   the sole permitted order-transmitting code, testnet endpoint hardcoded.)
3. Every artifact must be regenerable from a committed script (the audit lesson —
   an artifact whose generator isn't committed is not a result).
4. Every result reported with its capacity/feasibility number next to its Sharpe.
5. Follow repo TDD/test conventions; the full existing suite must stay green.
6. Anything requiring a user decision (broker specifics, credentials, real funds,
   going live) → prepare, document, and **ask; do not assume.**
7. Report honestly per the research-log conventions: negatives are results;
   pre-registrations are binding; the ledger is append-only.

## Suggested execution order

A1 → A3 → A2 → A4/A5 → (Phase A gate) → C1 snapshotter → B paper start (runs in
background from here) → C2/C3 → D (while paper accrues) → B go-live gate → E as
triggered. Rough effort: Phase A ~2-3 sessions, C ~1, D ~1-2, B mostly calendar time.
