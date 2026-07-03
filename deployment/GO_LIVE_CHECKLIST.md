# CPD-1 Go-Live Checklist

This is the literal checklist for moving the CPD-1 deployment layer
(`deployment/`) from paper mode to real orders, per
`vibe_trading_deployment_plan_CPD1.md` §B. **Nothing in `deployment/` places
real orders** — every step below that says "you" is a human action outside
this codebase; the tooling only produces tickets and records what you did.

## Phase 1 — Paper mode (minimum 4 weeks, target ≥1 full crypto entry/exit cycle)

Run the daily loop for real (real signals, real timestamps, no simulated
data) — this exercises the *process*, not the strategy (already validated in
`vibe_trading_research_findings.md`/`forward_validation/`).

- [ ] One-time: seed the paper equity snapshots at the intended capital
      split (e.g. $2,500 at 30/70 → crypto $750, macro $1,750) via
      `ledger.append_equity_snapshot(...)` — the daily cycle hard-errors
      (exit 3) until this is done, by design.
- [ ] Daily (scheduled on the Ubuntu-VM, 16:10 UTC — see `deploy/README.md`):
      `python -m deployment.daily_cycle --auto-paper`. This runs signals for
      ZA4+M1LF (+ZD2 shadow), builds tickets, records hypothetical paper
      fills at observed prices + modeled taker fees, re-checks funding on
      open shorts, marks both sleeves, runs risk checks, and pushes the
      Telegram summary. REVIEW tickets are auto-skipped and alerted — decide
      them manually with `python -m deployment.confirm` if you disagree.
- [ ] Weekly: run `tracking_report.build_report(since_date=<paper start>,
      mark_prices=..., paper=True)` (see `deployment/README.md` "Weekly")
      and confirm divergence stays near zero (paper fills should track the
      engine closely by construction — a real divergence during paper mode
      means a ticket/confirm bug, not execution slippage; investigate before
      continuing).
- [ ] Confirm at least one full ZA4 entry→exit cycle occurred during the
      window (median hold ~9-10 days per the fresh assessment — 4 weeks
      should comfortably contain one, but don't shortcut this check).

## Phase 2 — Account setup (do this in parallel with Phase 1's calendar wait, not after)

- [ ] **IBKR**: fund the account; note the EUR→USD conversion happens once
      (IBKR spot FX ~$2 min commission, per CPD-1 §B2) — don't convert
      piecemeal per trade.
- [ ] **IBKR**: verify the chosen UCITS tickers are tradable and fractional
      at your specific IBKR entity/jurisdiction — candidates named in
      `deployment/order_tickets.py::MACRO_UCITS_CANDIDATES` (SPYL/VUAA for
      S&P 500, 4GLD/EGLN for gold). Pick one candidate per leg before going
      live (the tickets currently list both candidates — you decide which
      one your IBKR entity can actually trade, then that choice is fixed).
- [x] **Macro SHORT expression: DECIDED — option (c), hold flat/cash**
      (2026-07-03, findings §84.3/§85). The engine evidence was one-sided:
      M1's short legs LOST $486k over 2005→2026 (GLD −$333k/72 trades, SPY
      −$153k/68), and the faithful long/flat expression beat full M1 on
      every metric (full-window Sharpe 0.92 vs 0.61, maxDD −15.0% vs −19.6%,
      forward-year 1.43 vs 1.16) while being operationally simplest (no
      margin/borrow costs, no inverse-ETF daily-reset decay). Implemented as
      the frozen `M1LF` expression (`forward_validation/frozen/M1LF/`,
      forward-tracked as `fwd_M1LF` since 2026-07-03) inside the `cpd1_lf`
      profile — no macro short ticket is ever generated. Full M1 remains the
      frozen research reference with its own quarterly ledger row.
- [ ] **Binance**: enable USDT-M futures; set isolated margin, 1x leverage,
      on BTCUSDT and SOLUSDT specifically (CPD-1 §B2).
- [ ] **Binance**: confirm spot trading is enabled for BTCUSDT/SOLUSDT (longs
      always execute here, never on futures — CPD-1's funding-attribution
      rule).
- [ ] **Jurisdiction**: one-line reminder per CPD-1 — check tax treatment for
      your jurisdiction before the first real trade. Out of scope for this
      codebase; a real, first-order consideration at this account size
      (`vibe_trading_fresh_assessment_20260703.md` §8.6 item 6).
- [ ] **Telegram**: confirm alerts are actually arriving (they were smoke-
      tested during the build session) — `python -c "from deployment import alerts; alerts.build_notifier().notify('test')"`.

## Phase 3 — Go-live gate (pre-registered, binding)

All three must hold before flipping to real orders:

- [ ] Paper cycle completed with **zero missed daily runs in the final 2
      weeks** (check `deployment/state/signal_state_*.json` dates for gaps).
- [ ] Tracking error of the paper ledger vs. the engine's own paper equity
      curve **< 1%** (tighter than the ongoing 3%/quarter live tolerance —
      paper fills have no real slippage, so anything above ~1% here means a
      process bug, not market noise).
- [ ] **User sign-off** — explicit, not implied by the above two boxes being
      checked.

Then deploy at the target allocation, **starting at the low end of your
capital range** (per CPD-1: this is an ops de-risk, not a strategy change).

## Phase 4 — First two live weeks

- [ ] Size every real entry at **50% of the computed target notional**
      (execution shakedown — confirms fills, fees, and the confirm/ledger
      loop work correctly with real money before trusting it at full size).
      `order_tickets.build_tickets(..., leverage=0.5)` achieves this
      directly (leverage is a pure multiplier on target notional, so 0.5x
      here is exactly "half the computed size", not a change to the 1.0x
      strategy leverage itself).
- [ ] After two clean weeks (no missed runs, no reconciliation mismatches,
      no risk-rule tripwires fired), switch to full size
      (`leverage=1.0`, CPD-1's frozen default).

## After go-live: standing discipline (not a one-time checklist item)

- Weekly reconciliation: confirm venue balances match the ledger within fees
  (`deployment/risk_rules.py::check_reconciliation_due` reminds you when one
  is overdue; the actual balance-vs-ledger comparison is a human step this
  layer doesn't automate — no live venue-balance API is wired in).
- Risk tripwires (`deployment/risk_rules.py`) are review triggers, not
  strategy stops — see `deployment/README.md` for the exact thresholds and
  what each one means operationally.
- Phase E's scale-up unlocks (`vibe_trading_deployment_plan_CPD1.md` §E) are
  capital-triggered, not calendar-triggered — check them against
  `deployment/state/equity_snapshots.csv` periodically, not on a fixed
  schedule.
