# CPD-1 Deployment Layer

Operational runbook for the frozen 30/70 ZA4/M1 composite
(`vibe_trading_deployment_plan_CPD1.md`). This directory is signal/
bookkeeping/notification tooling only — **no order-placing code against any
real venue** exists here except `hl_testnet_drill.py`, which is
testnet-hardcoded and cannot reach a real venue (see that file's own
docstring for why it's the one authorized exception).

## What's deployed

```
CPD-1 = 30% crypto sleeve (frozen ZA4: BTC-USDT + SOL-USDT, daily)
      + 70% macro sleeve  (frozen M1: SPY+GLD AQR blend, monthly)
      @ 1.0x leverage
```

Frozen source: `forward_validation/frozen/{ZA4,M1}/`. **Never edited by
anything in `deployment/`** — `signal_runner.py` only *reads* those files.

## Module map

| Module | Purpose |
|---|---|
| `signal_runner.py` | Daily: fetch data, run the frozen engines, extract today's raw (pre-shift) target per symbol. Writes `state/signal_state_<date>.json` + `state/latest.json`. |
| `order_tickets.py` | Turn a SignalState into human-readable BUY/SELL/SKIP/REVIEW tickets, sized against sleeve equity, quantized against live venue minimums. |
| `ledger.py` / `confirm.py` | Append-only fill/skip record (`state/live_ledger.csv`) + the `python -m deployment.confirm` CLI that writes to it. |
| `tracking_report.py` | Weekly: live ledger P&L vs. the frozen engine's own paper equity curve — the single most important QC check this layer has. |
| `risk_rules.py` | Pre-registered drawdown/single-day-loss/missed-run/reconciliation tripwires, pure functions over ledger state. |
| `alerts.py` | Telegram push (edgeforge's bot, reused with permission) for everything `risk_rules.py`/`order_tickets.py` flags. |
| `venue_specs.py` | Live Binance quantization/price/funding lookups with hardcoded fallback constants. |
| `tickets.py` | Shared `Ticket` schema so `order_tickets.py` (writer) and `confirm.py` (reader) never drift on format. |
| `hl_testnet_drill.py` | Phase E: Hyperliquid testnet order-lifecycle smoke drill (see its own docstring). |

## Daily loop

1. **After the crypto daily bar close** (OKX-style 16:00 UTC boundary — the
   frozen ZA4 config's actual source; verify this hasn't drifted if the
   config ever changes), run:
   ```bash
   python -m deployment.signal_runner
   ```
   This runs both ZA4 (daily) and M1 (monthly signal, run daily anyway —
   cheap, no scheduling special case) and writes `state/signal_state_<date>.json`.
   Check the `stale`/`effective_as_of` fields per strategy — a stale signal
   (>4 calendar days behind the request date) means the loader didn't get
   fresh data; investigate before trusting the tickets built from it.
2. Build tickets:
   ```python
   import json
   from deployment.order_tickets import build_tickets
   from deployment.tickets import write_tickets
   state = json.loads(open("deployment/state/latest.json").read())
   tickets = build_tickets(state)  # sleeve equity defaults to the ledger's latest snapshot
   write_tickets(state["as_of_date"], tickets)
   for t in tickets:
       print(t.human_text)
   ```
3. For each ticket, place the real order (or the paper-mode equivalent —
   see `GO_LIVE_CHECKLIST.md`), then:
   ```bash
   python -m deployment.confirm <ticket-id> --px <fill price> --qty <filled qty> --fee <fee>
   # or, if the ticket said SKIP / you chose not to act on a REVIEW ticket:
   python -m deployment.confirm <ticket-id> --skip --reason "..."
   ```
   `confirm.py` prints a `row_id` — note it if you ever need to correct this
   specific entry later (`--supersedes <that-row-id>` on a future call;
   nothing is ever edited in place).
4. `risk_rules.run_risk_checks(state)` runs automatically as part of a
   complete daily cycle (wire it into whatever cron/`/schedule` invocation
   you set up — not yet wired into `signal_runner.py`'s own `main()`,
   deliberately: keeps signal generation and risk alerting independently
   testable/callable). Alerts push to Telegram; everything also stays in the
   ledger regardless of whether Telegram is reachable.

## Weekly

- Record an equity snapshot per venue:
  ```python
  from deployment.ledger import append_equity_snapshot
  append_equity_snapshot(date="2026-07-10", venue="binance_spot", symbol_or_cash="cash", balance_usd=...)
  append_equity_snapshot(date="2026-07-10", venue="binance_usdtm", symbol_or_cash="cash", balance_usd=...)
  append_equity_snapshot(date="2026-07-10", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=...)
  ```
  (Crypto side is markable from public prices; this isn't automated yet —
  see "Known gaps" below.)
- Run the tracking report and act on it (>3% cumulative divergence in a
  quarter → halt new entries, investigate, document before resuming — the
  pre-registered tolerance):
  ```python
  from deployment.tracking_report import build_report
  build_report(since_date="<deployment start date>", mark_prices={("BTC-USDT","binance_spot"): <live price>, ...})
  ```
- Reconcile: confirm venue balances match the ledger within fees.
  `risk_rules.check_reconciliation_due()` reminds you when >=7 days have
  passed since the last equity snapshot — the actual balance comparison is
  a human step (no live venue-balance API is wired in).

## Quarterly

See `research/quarterly_cadence.md` — forward-validation ledger rerun, H1
forward-track, venue funding re-attribution, SOL options capacity
re-measurement, lot-quantization feasibility. `research/quarterly_cadence.py`
automates the runnable items.

## Venue map (why each leg lives where it does)

| Leg | Venue | Why |
|---|---|---|
| Crypto longs (any symbol, either strategy) | Binance spot | Finest granularity; **never perps** — funding-attribution confirmed perp longs pay 10-30%/yr on both Binance and Hyperliquid (`venue_data_assessment_20260703.md` §1) |
| Crypto shorts | Binance USDT-M perps | Positive carry (BTC +4.1%/yr, SOL small drag) |
| Macro longs | IBKR, UCITS proxies | PRIIPs blocks US ETFs for EEA retail — see below |
| Macro shorts | **undecided** | M1 does sometimes signal short (e.g. GLD) — CPD-1 never specified a short-expression venue for macro. `order_tickets.py` surfaces these as REVIEW tickets rather than guessing; see `GO_LIVE_CHECKLIST.md` Phase 2. |

**UCITS proxy mapping** (`order_tickets.py::MACRO_UCITS_CANDIDATES`): the M1
signal is computed on SPY/GLD data (yfinance) but executed via UCITS
equivalents — SPYL (SPDR) or VUAA (Vanguard) for S&P 500 exposure, 4GLD
(Xetra-Gold) or EGLN (iShares physical) for gold. Both candidates are listed
on every ticket; pick one per leg for your specific IBKR entity before going
live (see `GO_LIVE_CHECKLIST.md`) — the choice doesn't change after that,
it's a one-time decision, not a per-ticket one.

## Known cost-modeling gap: M1's backtest assumed zero commission

Traced during this build: `forward_validation/frozen/M1/config.json` sets no
`commission`/`hk_commission` key, and `GlobalEquityEngine` defaults to
**zero** commission for non-HK US-equity codes (CLAUDE.md's documented
engine-cost-key gotcha). So M1's own historical backtest — and the forward-
validation ledger's ongoing M1 row — never modeled any trading cost for the
macro sleeve. Live IBKR costs are small (~0.05% tiered per CPD-1's venue
assessment) but real, and are **not** in the modeled numbers the way crypto's
0.1% taker assumption already conservatively covers live Binance costs. Not
a bug to fix in the frozen strategy (that would require re-running/re-
validating the frozen ledger, out of scope for a deployment-tooling
session) — just a real, previously-undocumented gap worth knowing before
comparing live macro P&L too literally against the paper curve in
`tracking_report.py`.

## Risk-rule thresholds (`risk_rules.py`) — review tripwires, not strategy stops

The composite's own drawdowns are expected and survivable (bootstrap median
maxDD −18% per the fresh assessment) — crossing a threshold means "a human
looks at this," not "the strategy is broken":

| Trigger | Action |
|---|---|
| Account drawdown from high-water mark ≤ −15% | Alert; reduce new-entry size 50% |
| Account drawdown from high-water mark ≤ −20% | Alert; close-only mode until human review is logged |
| Single-day loss ≥ 6% (~6σ) | Alert; verify data/fills before any new order |
| Crypto sleeve signal >1 day stale | Alert (crypto trades 24/7, so any gap is notable) |
| Macro sleeve signal >4 days stale | Alert (tolerates a long weekend/holiday) |
| No equity snapshot in ≥7 days | Reconciliation-due reminder |
| Tracking-error cumulative divergence >3% of equity in a quarter | Halt-new-entries flag |

## Known gaps (deliberately out of scope this session)

- **No automated crypto-side equity marking.** The plan allows "crypto side
  can be marked from public prices automatically" — not built; every equity
  snapshot is currently a manual `append_equity_snapshot` call.
- **No automated venue-balance reconciliation.** `check_reconciliation_due`
  only reminds on a timer; the actual balance-vs-ledger comparison needs
  live venue APIs this layer doesn't poll (out of scope — no order-placing
  infrastructure beyond the testnet drill, per the plan's hard constraints).
- **Macro short expression is undecided** (see venue map above) — a real
  product/regulatory decision for the user, not something to assume.
- **`risk_rules.run_risk_checks` isn't wired into a scheduler.** Building the
  actual cron/`/schedule` invocation that runs the daily loop for real is a
  separate decision — see `GO_LIVE_CHECKLIST.md`; this session built and
  tested the tooling, not the always-on automation.

## Testing

`deployment/tests/` (wired into `pyproject.toml`'s `testpaths`, runs under
plain `pytest`). Network-touching tests are `@pytest.mark.integration`
(the signal-parity gate against real OKX/yfinance data); everything else is
fixture-driven. `pytest deployment/tests -m "not integration"` for the fast
subset.

## See also

- `GO_LIVE_CHECKLIST.md` — the paper→live transition, literally.
- `vibe_trading_deployment_plan_CPD1.md` — the approved spec this
  implements.
- `forward_validation/README.md` — the ritual `signal_runner.py` reuses for
  the audit-trail side.
- `research/quarterly_cadence.md` — the standing research cadence.
