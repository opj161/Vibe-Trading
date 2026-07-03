# CPD-1 Deployment Layer

Operational runbook for the frozen 30/70 ZA4/M1 composite
(`vibe_trading_deployment_plan_CPD1.md`). This directory is signal/
bookkeeping/notification tooling only — **no order-placing code against any
real venue** exists here except `hl_testnet_drill.py`, which is
testnet-hardcoded and cannot reach a real venue (see that file's own
docstring for why it's the one authorized exception).

## What's deployed

```
cpd1_lf (deployment/profiles.py, the active profile — findings §85):
    30% crypto sleeve (frozen ZA4: BTC-USDT + SOL-USDT, daily)
  + 70% macro sleeve  (frozen M1LF: SPY+GLD AQR blend, LONG/FLAT expression)
    @ 1.0x leverage
  + ZD2 shadow (daily signals + paper curve only, never tickets — feeds the
    ZA4-vs-ZD2 forward arbitration, findings §80.3)
```

**Macro short expression is DECIDED (2026-07-03, findings §84.3/§85):
option (c), hold flat.** M1LF is the frozen long/flat expression of the M1
signal (byte-frozen at `forward_validation/frozen/M1LF/`, forward-tracked as
`fwd_M1LF`); full M1 stays the frozen research reference and keeps its own
quarterly ledger row. The engine evidence was one-sided: M1's short legs lost
$486k over 2005→2026, and M1LF beats M1 on every metric (Sharpe 0.92 vs 0.61,
maxDD −15.0% vs −19.6%, forward-year 1.43 vs 1.16).

Frozen source: `forward_validation/frozen/{ZA4,M1LF,ZD2,M1}/`. **Never edited
by anything in `deployment/`** — `signal_runner.py` only *reads* those files.

## Module map

| Module | Purpose |
|---|---|
| `profiles.py` | THE single statement of what is deployed: strategy → sleeve/weight map + shadow list. Active profile: `cpd1_lf`. |
| `daily_cycle.py` | **The one command per day**: signals → tickets → (auto-paper fills) → funding re-check on open shorts → sleeve marking → risk checks → Telegram summary. |
| `signal_runner.py` | Fetch data, run the frozen engines behind the data-integrity gate, extract today's raw (pre-shift) target per symbol. Writes `state/signal_state_<date>.json` + `state/latest.json`. |
| `order_tickets.py` | SignalState → BUY/SELL/SKIP/REVIEW tickets (CLI: `python -m deployment.order_tickets`), sized against sleeve equity (hard error when unconfigured), quantized against live venue minimums; also `one_shot_resize` tickets so ZD2 is expressible. |
| `ledger.py` / `confirm.py` | Append-only fill/skip record (`state/live_ledger.csv`, paper/live rows tagged) + the `python -m deployment.confirm` CLI that writes to it. |
| `marking.py` | Sleeve valuation (anchor snapshot + windowed cash flows + public marks) and the daily `state/equity_marks.csv` risk series. |
| `tracking_report.py` | Weekly: mode-filtered, window-anchored, profile-weighted live-vs-paper divergence — the single most important QC check this layer has (rewritten 2026-07-03; see its docstring for the five defects fixed). |
| `risk_rules.py` | Pre-registered drawdown/single-day-loss/missed-run/reconciliation/sleeve-drift tripwires over the marked equity series. |
| `alerts.py` | Telegram push (edgeforge's bot, reused with permission) for everything the cycle flags. |
| `venue_specs.py` | Live Binance quantization/price/funding lookups with hardcoded fallback constants + modeled paper fee rates. |
| `tickets.py` | Shared `Ticket` schema so writers and readers never drift on format. |
| `hl_testnet_drill.py` | Phase E: Hyperliquid testnet order-lifecycle smoke drill (needs the optional `[nautilus]` extra). |

## Daily loop

One command, scheduled shortly **after the crypto daily bar close** (OKX-style
16:00 UTC boundary — the frozen ZA4 config's actual source; `daily_cycle`
warns if run earlier):

```bash
python -m deployment.daily_cycle --auto-paper        # paper mode (Phase B)
python -m deployment.daily_cycle --mode live         # after go-live: tickets only, human places orders
```

Paper mode with `--auto-paper` records every pending ticket as a hypothetical
fill at the observed reference price + the modeled taker fee
(`venue_specs.PAPER_FEE_RATES`), idempotently (a rerun cannot double-fill).
REVIEW tickets are auto-SKIPPED with a Telegram alert — never auto-executed.
In live mode the human places each order and confirms it:

```bash
python -m deployment.confirm <ticket-id> --px <fill price> --qty <filled qty> --fee <fee>
# or, for a SKIP / a REVIEW ticket you chose not to act on:
python -m deployment.confirm <ticket-id> --skip --reason "..."
```

`confirm.py` prints a `row_id` — note it if you ever need to correct this
specific entry later (`--supersedes <that-row-id>` on a future call; nothing
is ever edited in place). Tickets can also be (re)built standalone:
`python -m deployment.order_tickets [--crypto-equity N --macro-equity N]`.

## Weekly

- Daily sleeve marking is automatic (`daily_cycle` step 5 →
  `state/equity_marks.csv`); the weekly HUMAN snapshot remains the
  reconciliation truth (in live mode, from real venue balances; in paper
  mode the seed row is enough):
  ```python
  from deployment.ledger import append_equity_snapshot
  append_equity_snapshot(date="2026-07-10", venue="binance_spot", symbol_or_cash="cash", balance_usd=...)
  append_equity_snapshot(date="2026-07-10", venue="binance_usdtm", symbol_or_cash="cash", balance_usd=...)
  append_equity_snapshot(date="2026-07-10", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=...)
  ```
- Run the tracking report and act on it (>3% cumulative divergence in a
  quarter → halt new entries, investigate, document before resuming — the
  pre-registered tolerance; paper gate is <1%):
  ```python
  from deployment import ledger, marking
  from deployment.tracking_report import build_report
  marks = marking.fetch_mark_prices(ledger.open_positions(paper=True))
  build_report(since_date="<deployment start date>", mark_prices=marks, paper=True)
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
| Macro shorts | **held flat (decided)** | Option (c) adopted 2026-07-03 (findings §84.3/§85): the deployed M1LF expression zeroes short legs after the gross clip, so no macro short ticket is ever generated under `cpd1_lf`. The REVIEW-ticket path remains in `order_tickets.py` for the legacy `cpd1` (full M1) profile. |

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

## Scheduling (Ubuntu-VM)

The daily cycle runs on the always-on Ubuntu-VM (`~/.ssh/config` host
`Ubuntu-VM`, repo at `/home/opj/projects/Vibe-Trading`), NOT on the WSL2 dev
machine — WSL2 cron does not fire while the Windows host sleeps, and the
go-live gate demands zero missed daily runs. See `deploy/README.md` for the
rsync-based deploy/bootstrap/cron scripts and the state pull-back flow.
Cron times (UTC): daily cycle 16:10 (just after the OKX bar close), Deribit
snapshotter 16:40, weekly tracking report Monday 17:00.

## Known gaps (deliberate)

- **No automated venue-balance reconciliation.** `check_reconciliation_due`
  only reminds on a timer; the actual balance-vs-ledger comparison needs
  live venue APIs this layer doesn't poll (out of scope — no order-placing
  infrastructure beyond the testnet drill, per the plan's hard constraints).
- **Live order placement stays manual** until the Phase E Nautilus
  target-executor milestone (account ≥ ~$10-25k), and any change to that
  boundary is a user decision, never an agent default.

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
