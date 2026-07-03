# CPD-1 Reassessment — 2026-07-03 (post-build, fresh view)

**Mandate:** analyze the CPD-1 work as actually built, re-derive the most-profitable-path
question with an open mind, cross-check the external assessment (`assessment-cpd-1.md`)
against this repo's real state, and produce a prioritized plan. Every claim below was
verified directly in this working tree (code reads, artifact reads, full test run) —
not quoted from prior logs.

---

## 1. Verdict

The CPD-1 build is real, disciplined, and mostly excellent — the signal path
(frozen-artifact reuse, gross-exposure-clip parity, the §84 data-integrity gate) is
production-grade thinking. But **the deployment is not yet operating**: nothing is
scheduled (no crontab; the "daily" snapshotter has exactly one day of data; the ledger
is empty; paper mode has not started), and the single most important QC instrument —
`tracking_report.py` — is defective in five verified ways. The binding resource from
here is **calendar time** (the go-live gate needs 4+ paper weeks with zero missed runs
in the final 2), so the correct next move is a short hardening sprint scoped to exactly
what blocks paper start, then start the paper clock immediately and do everything else
in parallel.

The strategy layer needs no new research. The composite (crypto trend + macro trend,
forward-year Sharpe 1.80) remains the product; the two open strategy questions —
macro short expression and ZA4-vs-ZD2 — are respectively **already answered by engine
evidence** (M1LF dominates; adopt long/flat) and **correctly deferred to forward
arbitration** (but see §4.3: the ticket layer cannot currently express ZD2 at all,
which silently biases that future arbitration toward ZA4 unless fixed).

---

## 2. State of the build (verified 2026-07-03)

- `deployment/` complete per plan Phases A/B-prep/E-drill; `research/deribit_snapshot/`
  + quarterly cadence per Phase C; §83 macro-breadth negative per Phase D. All committed.
- **197/197 tests pass in this environment** — including the HL testnet drill test and
  the snapshotter parquet tests. The external assessment's dependency failures
  (`nautilus_trader`, `pyarrow` missing) were artifacts of *its* sandbox, not this repo.
  The underlying point survives in weaker form: neither package is declared in
  `pyproject.toml` (venv-only), a reproducibility gap, and the HL drill test does not
  skip gracefully where Nautilus is absent.
- `deployment/state/`: signal state + tickets exist for 2026-07-03 (demo-sized);
  **no `live_ledger.csv`, no `equity_snapshots.csv`** — paper mode has not begun.
- **No crontab.** Phase C's "build once, runs forever" automation has been built once
  and run once. Every un-scheduled day costs snapshot history and paper-track evidence
  that cannot be backfilled.

## 3. Defects and gaps (each verified in code this session)

### 3.1 `tracking_report.py` — defective; must be rewritten before paper mode (P0)

The plan calls this "the single most important quality control." As written it can
produce a wrong divergence number in either direction (false pass or false halt):

1. `realized_and_unrealized_pnl` sums **all confirmed fills ever** — no `since_date`
   window — while the paper side is computed *since* `since_date`. Any report after the
   first quarter compares mismatched windows.
2. The ledger has a `paper` column; `confirmed_fills()` never filters on it. A ledger
   containing both paper and live rows (exactly what Phase B→go-live produces) mixes them.
3. `live_return_pct` divides by the **latest** sleeve equity, not equity at
   `since_date` — divergence shrinks mechanically as the account grows.
4. `paper_return_pct` is an **unweighted mean** across strategies (line 104) instead of
   the 30/70 sleeve-weighted composite return. With macro ~8%/yr and crypto ~75%/yr
   paper rates, the unweighted mean is nowhere near the deployable book's return.
5. It compares live against **full M1** even though deployed macro (skipping short
   tickets) tracks **M1LF** — a built-in structural divergence that consumes the 1%
   paper gate / 3%/quarter live tolerance with pure model error.

Also documented but worth keeping next to this list: the frozen M1 backtest models
**zero commission** (GlobalEquityEngine default for US codes), so live-vs-paper macro
divergence has a small known-positive bias even after the rewrite.

### 3.2 The deployment layer cannot express ZD2 (nobody has flagged this)

`forward_validation/frozen/ZD2/config.json` uses `one_shot_resize` (short entries at
half size, quantity ×2 at bar 10) — an **engine-level mid-hold resize**.
`order_tickets.py` fires tickets **only on direction changes** (entry-locked, correct
for ZA4/M1). A ZD2 deployment would silently never emit the day-10 double, i.e. it
would trade a strategy that is neither ZD2 nor ZA4. Consequence: the "ZD2 vs ZA4 is
the live question" forward arbitration (§80.3) is currently rigged — if ZD2 wins the
forward ledger, it still can't be deployed faithfully. Fix is contained: derive resize
tickets from quantity changes in the audit-trail `positions.csv` (which the engine
already computes correctly), not from sign flips alone.

### 3.3 Operational gaps

- **No daily-cycle command and no `order_tickets` CLI.** `GO_LIVE_CHECKLIST.md` line 16
  literally references `python -m deployment.order_tickets`, which does not exist; the
  README's daily loop step 2 is a copy-paste Python snippet. The daily human process
  must be one command.
- **Equity-unconfigured failure is silent-ish:** with no equity snapshots,
  `ledger.latest_sleeve_equity()` returns 0.0 and `build_tickets` sizes everything off
  $0 → a wall of misleading "rounds below venue min" SKIP tickets instead of a hard
  "no equity configured" error. (`ledger.py`'s own docstring warns callers to treat 0.0
  as unconfigured; `order_tickets.py` doesn't.)
- **Risk tripwires are blind between snapshots.** Drawdown / single-day-loss checks run
  off `equity_snapshots.csv`, which is a weekly *manual* entry. A −6% crypto day
  mid-week fires nothing. The plan itself says "crypto side can be marked from public
  prices automatically" — that helper (ledger positions × `venue_specs` prices, daily
  snapshot row) is the missing piece that makes the tripwires real.
- **Sleeve-drift rule unimplemented.** The frozen spec says "rebalance monthly or when
  sleeve weights drift >5pp from 30/70". No code anywhere checks drift; the 30/70 split
  exists only in how the human funds venues. (Relatedly `SLEEVE_WEIGHTS` in
  `order_tickets.py` is dead code — defined, never read.)
- **Funding is checked only at entry.** Median holds are ~10-13 days; funding can flip
  mid-hold. A daily re-check on open perp shorts (alert above the same +15%/yr
  threshold) belongs in the daily cycle.
- **WSL2 is a scheduling hazard.** This host is WSL2: cron/systemd timers do not fire
  while the Windows host sleeps. The go-live gate requires **zero missed daily runs in
  2 weeks**. Options (user decision): Windows Task Scheduler invoking `wsl.exe`, a ~$5
  VPS, or GitHub Actions cron committing state. Deciding this is part of P0 — the gate
  is unmeetable on an ad-hoc laptop cadence.
- **Run timing matters and is undocumented in the runbook:** `latest.json` shows the
  2026-07-03 00:23 UTC run produced a ZA4 signal effective 2026-07-01 — running before
  the OKX 16:00 UTC bar close makes the crypto signal a full bar stale, and the stale
  flag only trips at >4 days. The daily cycle must be pinned to ~16:05-16:30 UTC.

### 3.4 External assessment scorecard (`assessment-cpd-1.md`)

| Claim | Verdict here |
|---|---|
| tracking_report flaws (5 items) | **Confirmed, all five** (§3.1) |
| `order_tickets` CLI missing | **Confirmed**; checklist references a nonexistent command |
| deps not installed (nautilus/pyarrow) | **Wrong for this repo** (197 tests pass) but right that they're **undeclared** |
| macro short unresolved | **Out of date** — §84.3 answered it (M1LF); what remains is formal adoption + wiring |
| risk checks not wired to scheduler | **Confirmed and understated** — *nothing* is scheduled at all |
| ZA4/ZD2/Z8/Z4 forward numbers | **Verified** against run cards (Sharpe 1.22/1.30/1.32/1.32; DD −27.4/−23.0/−22.5/−19.2) |
| "go live crypto-only (CTD) first" | **Partially disagree** — see §5 |
| Nautilus = target-executor, not strategy port | **Agree**, matches plan §E and the frozen-ledger-comparability doctrine |

---

## 4. Strategy layer: what is actually most profitable (all numbers re-read from artifacts)

### 4.1 The honest leaderboard

| Object | Basis | Ann. | Sharpe | MaxDD | Status |
|---|---|---:|---:|---:|---|
| **30/70 composite @1.5x** | fwd-year computed | +42.5% | 1.80 | −18% | pre-registered unlock after 2 clean quarters |
| **30/70 composite @1x** | fwd-year computed | +27.2% | **1.80** | −12.3% | the deployable product (CPD-1) |
| ZA4 (crypto sleeve) | fwd-year run card | +54.8% | 1.22 | −27.4% | frozen champion, deployed sleeve |
| ZD2 (ZA4 + short-side durability) | fwd-year run card | +52.8% | 1.30 | −23.1% | frozen; family's best form on all evidence (§80.3) |
| Z8 / Z4 | fwd-year run cards | +54.4% / +46.1% | 1.32 / 1.32 | −22.5% / −19.2% | frozen, lower-DD variants |
| M1LF (macro long/flat) | full / fwd | +7.7% / +8.7% | 0.92 / 1.43 | −15.0% / −4.9% | **dominates M1 on every metric** (§84.3) |
| M1 (macro long/short) | full / fwd | +6.4% / +7.4% | 0.61 / 1.16 | −19.6% / −6.8% | current frozen macro sleeve |
| H1 puts overlay | banked | — | — | — | capital-locked (SOL ≥ ~$5-10k sleeve, BTC ≥ ~$25-50k) |
| M1X breadth, VRP, semis, China-A | — | — | — | — | closed / not retail-accessible at this scale |

Per-dollar most profitable: the crypto trend family (~50-75% ann forward-basis, with a
~50% drawdown likely somewhere on the path at 1x standalone). Most profitable
*approach* for actual capital: the composite, levered to 1.5x once earned — it nearly
matches a 50/50 blend's return at materially lower tail risk, and the leverage knob is
already pre-registered in plan §E. **No configuration change is needed to chase
profit; the profit path is: start the clock → 2 clean quarters → 1.5x.**

### 4.2 Macro sleeve: adopt M1LF (user formality, evidence is one-sided)

M1's short legs lost $486k over 2005→2026 in the engine's own trades ledger; M1LF wins
full-window Sharpe 0.92 vs 0.61, maxDD −15.0% vs −19.6%, forward-year 1.43 vs 1.16,
and is operationally simplest (no margin shorts, no inverse-ETF decay). It is also
what skipping REVIEW tickets *already does de facto* — adopting it formally just makes
the deployed expression, the paper reference curve, and the forward ledger
(`fwd_M1LF`) consistent. This should stop being a REVIEW-ticket-forever.

### 4.3 ZA4 vs ZD2: keep ZA4 deployed, shadow ZD2, and fix expressibility first

ZD2 beats ZA4 on the burned bear-window on everything (Sharpe/DD/Calmar) and on
ext-window Sharpe by a hair — but its treatment was designed with knowledge of that
window's anatomy, so the burned-window edge is partially in-sample-by-design; the
forward ledger (started 2026-07-01) is the honest arbiter, exactly as §80.3 concluded.
Two practical implications: (a) shadow ZD2 signals daily — free, since
`signal_runner.py` is strategy-agnostic; (b) build resize-ticket support (§3.2) *now*,
so that if ZD2 wins the quarter, promotion is an allocation decision rather than an
engineering project. Z8/Z4 add little beyond ZD2 (same family, correlated); shadowing
more than one variant multiplies noise, not information.

### 4.4 On the external assessment's crypto-only (CTD) push

Where it's right: macro adds real fixed ops (IBKR funding, EUR→USD conversion, UCITS
verification, monthly rebalances) for tiny absolute dollars at this scale (~$150/yr on
a $1.75k macro sleeve at M1LF's forward rate). Where it's wrong: (a) at $1-5k the
absolute-profit difference between CTD and CPD is a few hundred dollars/yr — noise
against the value of the thing this account actually produces, a **composite track
record that justifies scaling**; (b) CTD at 100% allocation carries a ~50%-drawdown
expectation (bootstrap: P(maxDD>40%) ≈ 90%) that is exactly the psychological/optics
failure mode the composite exists to prevent; (c) the "paper both profiles" step is
nearly free inside this infrastructure, so the choice needn't be made today on
argument alone. The sequencing insight worth keeping from it: **macro-account
readiness must not gate crypto go-live** — see §5.

---

## 5. Recommended path (decisive)

**Profile to paper (one, not five): CPD-1-LF = 30% ZA4 + 70% M1LF-expression, 1x**,
plus free ZD2 shadow signals. Paper both sleeves regardless of IBKR status (paper
macro needs no account).

**Live sequencing (after the gate):** go live on whatever sleeves are account-ready at
composite weights. If IBKR/UCITS setup lags, start live with the crypto sleeve at its
composite size (30% of account; remainder cash) — this preserves the composite's
crypto-leg geometry exactly and lets macro switch on later without redesign. Do not
inflate crypto beyond its 30% weight to "use" idle cash; that silently converts CPD
into CTD and voids the drawdown math.

**Leverage:** 1x until the pre-registered §E trigger (2 clean quarters), then 1.5x.
That *is* the profit maximization move at this scale; nothing faster survives the
bootstrap tail math.

**Automation ambition (the "automated trading" goal):** at $1-5k the correct
automation boundary is signals/tickets/alerts automated, orders manual (10 min/day) —
per both the plan and the fresh assessment. The Nautilus **target-executor** (consume
`latest.json`, place orders; HL testnet first) is the right next automation milestone
and may be built early since the drill already passes — but it must not delay the
paper clock, and live order placement stays gated on clean paper + user sign-off +
the plan's hard constraint #2 being explicitly re-authorized by the user.

---

## 6. Prioritized backlog

**P0 — blockers to starting the paper clock (target: paper starts this week)**
1. Rewrite `tracking_report.py`: since-date + paper/live filtering on fills,
   starting-equity denominator, sleeve-weighted (30/70) composite expected return,
   macro reference = deployed expression (M1LF) — with fixture tests for each failure
   mode in §3.1. The go-live gate is meaningless until this is trustworthy.
2. Adopt M1LF formally (user says yes/no): freeze `fwd_M1LF` next to `fwd_M1` in
   `forward_validation/`, add it to `signal_runner`'s audit-trail so the paper curve
   exists, switch macro-short handling from REVIEW to flat-per-M1LF.
3. `python -m deployment.order_tickets` CLI + `python -m deployment.daily_cycle`
   (integrity → signals → tickets → funding → risk checks → alerts → state; one
   command, nonzero exit on any failure; hard error when sleeve equity unconfigured).
4. Scheduling: user picks host (WSL2-via-Task-Scheduler / VPS / GH Actions); pin the
   run to ~16:05 UTC (OKX bar close); schedule `daily_cycle` + snapshotter; verify
   Telegram delivery end-to-end.
5. Seed paper equity snapshots at the real intended capital split and start Phase B.

**P1 — during the paper weeks (parallel, no calendar cost)**
6. Auto crypto equity marking (daily snapshot from ledger positions × public prices) —
   makes drawdown/single-day-loss tripwires actually daily. Add the >5pp sleeve-drift
   alert while in there; delete or wire the dead `SLEEVE_WEIGHTS`.
7. Resize-ticket support from audit-trail `positions.csv` quantity deltas (ZD2
   expressibility, §3.2) + ZD2 shadow signals in the daily cycle.
8. Daily funding re-check on open perp shorts (alert > +15%/yr against position).
9. Declare `pyarrow` as a dependency and `nautilus_trader` as an optional extra;
   make the HL drill test skip cleanly when Nautilus is absent.
10. Profile config (cpd1_lf / ctd_za4 / ctd_zd2) as a small declarative map
    (strategy → sleeve → weight) replacing the hardcoded `STRATEGY_SLEEVE` — needed by
    the tracking rewrite anyway; keeps the CTD comparison honest during paper.

**P2 — after the paper loop is boringly reliable**
11. Nautilus target-executor spike: `latest.json` → order intents → HL testnet,
    shadowed against manual tickets (per plan §E; free to start anytime).
12. Quarterly cadence as scheduled automation (currently a script + doc, nothing runs it).

**Explicitly not on the list:** new signal research (the family is 0-for-11 on signal
tweaks and 0-for-3 on combination stacking; §83 closed macro breadth; VRP closed
twice; China-A and third-sleeve research resume at $50k+ per the scaling map).

**User decisions required (blocking, in order):** M1LF adoption; scheduling host;
paper-capital notionals; later — live capital amount, IBKR/Binance account readiness,
go-live sign-off.
