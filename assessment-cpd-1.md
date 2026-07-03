## Updated conclusion

Now that CPD-1 is already implemented, I would **not throw it away**. The best move is to treat CPD-1 as the **operational chassis** and then simplify the actual live deployment decision inside it.

My updated recommendation is:

> **Keep CPD-1’s infrastructure, but do not automatically go live with the full 30/70 CPD-1 composite. First harden the implementation, then paper-run two profiles:**
>
> 1. **CPD profile:** ZA4 + macro long/flat, risk-efficient.
> 2. **CTD profile:** one crypto trend strategy only, preferably ZA4 or ZD2, profit-focused.
>
> Then choose **one** live profile.

The most important shift from our earlier discussion is this:

```text id="0pe72e"
Before implementation:
    I would have built a simpler crypto-only deployment first.

Now:
    CPD-1 is already built, so use it.
    But use it to test and deploy the best single profile,
    not to multiply live complexity.
```

---

# 1. What I found in the implemented codebase

The CPD-1 implementation is real and substantial. The uploaded archive now contains a complete `deployment/` layer with:

```text id="mcy2ae"
deployment/signal_runner.py
deployment/order_tickets.py
deployment/ledger.py
deployment/confirm.py
deployment/tracking_report.py
deployment/risk_rules.py
deployment/alerts.py
deployment/venue_specs.py
deployment/data_integrity.py
deployment/hl_testnet_drill.py
deployment/tickets.py
deployment/README.md
deployment/GO_LIVE_CHECKLIST.md
deployment/tests/
```

It also has Phase C pieces, including the Deribit snapshotter:

```text id="ptx74r"
research/deribit_snapshot/
```

The current state file exists:

```text id="2eejqf"
deployment/state/latest.json
```

and the current tickets file exists:

```text id="n9l51p"
deployment/state/tickets_20260703.json
```

The latest generated CPD signal was:

```text id="88zu4d"
ZA4:
    BTC-USDT short, weight about -0.2625
    SOL-USDT long, weight about +0.1102

M1:
    SPY.US long, weight about +0.4017
    GLD.US short, weight about -0.1341
```

The corresponding tickets showed the implementation working conceptually:

```text id="9ucmnw"
BTC short:
    Binance USDT-M, 0.003 BTC, about $184 notional,
    funding about +10.95% annualized, favorable.

SOL long:
    Binance spot, about 1.024 SOL, about $83 notional.

SPY macro:
    buy about $703 of UCITS proxy candidate.

GLD macro short:
    REVIEW / not executed because macro short expression is undecided.
```

That last point is important. The implementation has already surfaced a strategic issue: **the macro short leg is not actually deployment-ready.**

---

# 2. What is good about the implemented CPD-1

The implementation did many things right.

## 2.1 It preserved the most important discipline rule

The signal runner uses the frozen strategy artifacts rather than reimplementing the alpha casually. That is the right architecture.

The correct principle is:

```text id="n6ocwz"
Research engine remains the signal source of truth.
Deployment layer consumes targets.
```

That avoids the biggest failure mode: subtle drift between backtest and live signal.

## 2.2 It implemented human-readable tickets

The current ticket file demonstrates that abstract targets can be converted into practical instructions:

```text id="m9vwgg"
venue
symbol
side
quantity
estimated notional
reason
funding check
review/skip status
```

That is useful even if the eventual system becomes Nautilus-executed, because the ticket layer is also an audit layer.

## 2.3 It implemented ledger and confirmation primitives

`deployment/ledger.py` and `deployment/confirm.py` are the right primitives for a live track record:

```text id="3uui5d"
append-only rows
confirmed fills
skipped tickets
fees
equity snapshots
```

That is valuable regardless of whether the execution is manual or automated.

## 2.4 It implemented risk and data-integrity modules

There are now modules for:

```text id="1khi7l"
drawdown checks
single-day loss checks
stale signal checks
missing signal checks
data-integrity checks
```

That is exactly the infrastructure you want before live trading.

## 2.5 It already has the Hyperliquid testnet direction

`deployment/hl_testnet_drill.py` exists, and the Nautilus archive contains adapters for the relevant venues: Binance, Hyperliquid, Interactive Brokers, and Deribit. So the long-term Nautilus path is technically aligned with the implementation.

---

# 3. What is not ready yet

The main conclusion from the code scan is:

> **CPD-1 is implemented, but it is not yet live-ready.**

It is close enough to be useful, but not close enough to trust real capital without a hardening pass.

## 3.1 The full deployment test suite does not pass as-is

Running the deployment tests failed initially because `deployment/tests/test_hl_testnet_drill.py` imports Nautilus, but `nautilus_trader` is not installed in the environment.

When I excluded that file, the non-integration deployment tests passed:

```text id="mqxpvo"
112 passed, 4 deselected
```

Running research and deployment tests together, excluding the Nautilus test, also passed:

```text id="1g00go"
119 passed, 4 deselected
```

So the core non-Nautilus code is in decent shape.

But the current dependency story is incomplete:

```text id="p0sxyc"
nautilus_trader is needed by the HL drill test
but is not installed or declared as a dependency.

pyarrow or fastparquet is needed by the Deribit snapshotter test
but is not installed or declared as a dependency.
```

The Deribit snapshotter tests failed because pandas could not write/read parquet without `pyarrow` or `fastparquet`.

That matters because the plan says the Deribit snapshotter is a Phase C standing automation. If parquet is the chosen storage format, `pyarrow` should be a declared dependency.

## 3.2 `deployment.order_tickets` lacks a proper CLI

The checklist refers to running something like:

```bash id="d0mfuk"
python -m deployment.order_tickets
```

but `deployment/order_tickets.py` exposes `build_tickets()` and does not have a proper `main()` CLI entry point.

The README currently uses Python snippets to build tickets. That is fine for development, but it is too brittle for a daily live process.

This should be fixed before paper mode.

Recommended command:

```bash id="p4jo0y"
python -m deployment.order_tickets \
  --state deployment/state/latest.json \
  --crypto-equity 300 \
  --macro-equity 700 \
  --write deployment/state/tickets_YYYYMMDD.json
```

The daily loop should not require copy-pasting Python snippets.

## 3.3 The tracking report is not reliable enough yet

This is the biggest implementation issue.

CPD-1 says tracking error is the most important live quality-control mechanism. But the current tracking report logic can mismeasure divergence.

Problems I found:

```text id="m7knxc"
deployment/ledger.py:
    confirmed_fills() returns all confirmed fills.
    It does not filter by date window or paper/live mode.

deployment/tracking_report.py:
    uses all confirmed fills in the ledger, not just the report period.
    uses latest sleeve equity as denominator, not starting equity at since_date.
    averages paper returns across strategies instead of weighting them 30/70.
    can mix paper/live rows if the ledger contains both.
    does not correctly model a macro long/flat deployment if M1 shorts are skipped.
```

This is not a minor issue. If the tracking report is wrong, then the system can falsely conclude:

```text id="tp7pn2"
live is tracking paper
```

or falsely halt a good process.

Before paper or live deployment, this should be fixed.

The tracking report should compute:

```text id="dg0cbp"
actual realized/live return over period
vs
target theoretical CPD profile return over same period
```

with:

```text id="3t3m3g"
date filtering
paper/live filtering
starting equity denominator
strategy weights
actual skipped/flat expressions
fees
funding
cash
unfilled tickets
```

For the crypto-only fast lane, it should also support:

```text id="64lbfp"
CTD profile:
    100% ZA4 or ZD2 crypto sleeve
```

not only the 30/70 CPD profile.

## 3.4 Macro short expression is unresolved

The current ticket output already has a GLD short review. That means live CPD-1 is not fully specified.

This matters because the macro research found that M1 short legs are weak, and the macro-breadth work appears to support a **long/flat macro deployment** rather than full long/short M1.

The macro-breadth results show:

```text id="0ct3l7"
M1:
    full ann about 6.39%
    Sharpe about 0.609
    maxDD about -19.6%

M1LF:
    full ann about 7.67%
    Sharpe about 0.916
    maxDD about -15.0%

Forward:
    M1 Sharpe about 1.16
    M1LF Sharpe about 1.43
```

So from here, I would not trade macro shorts until explicitly re-frozen and tested.

The simplest rule:

```text id="79rd5s"
Macro sleeve = long/flat only.
If M1 says short, hold cash for that instrument.
```

That should become a first-class deployment profile, not a REVIEW ticket forever.

## 3.5 Risk checks are not fully wired into the daily scheduler

The README documents that `risk_rules.run_risk_checks` exists but is not wired into a scheduler/daily cycle.

That is acceptable during development, but not for paper/live.

You want one daily command:

```bash id="mux80p"
python -m deployment.daily_cycle
```

that runs:

```text id="7koyvu"
data integrity
signal runner
ticket generation
funding checks
risk checks
alerting
state write
```

Right now, the pieces exist, but the operational loop is still partly manual at the script level.

---

# 4. Strategy reassessment after seeing the implemented state

The prior strategic critique still mostly stands, but now the action changes.

Earlier, I would have said:

```text id="h37ykf"
Do not build CPD-1 first.
Build crypto-only first.
```

But CPD-1 is now already built. So the new answer is:

```text id="u0efso"
Do not discard CPD-1.
Use it as the deployment framework.
But simplify the first live strategy choice.
```

## 4.1 The crypto trend system is still the best single high-profit candidate

The codebase still points to the BTC/SOL daily crypto trend family as the best deployable edge.

The strongest candidates remain:

```text id="jcgsq3"
ZA4
Z8
ZD2
Z4
```

From the parsed run cards:

| Run                | Annual return | Sharpe |   MaxDD | Assessment                           |
| ------------------ | ------------: | -----: | ------: | ------------------------------------ |
| `fwd_ZA4_20260702` |        ~54.8% |  ~1.22 | ~−27.4% | Official champion lineage            |
| `fwd_Z8_20260702`  |        ~54.4% |  ~1.32 | ~−22.5% | Better forward Sharpe/DD             |
| `fwd_ZD2_20260702` |        ~52.8% |  ~1.30 | ~−23.1% | Strong short-side durability variant |
| `fwd_Z4_20260702`  |        ~46.1% |  ~1.32 | ~−19.2% | Lower drawdown                       |

My current view:

```text id="v6agks"
Most defensible live baseline:
    ZA4

Best profit-focused candidate:
    ZD2 or Z8

Best lower-drawdown crypto candidate:
    Z4
```

Because the deployment plan is already centered around ZA4, I would not abruptly replace it in production without a shadow period.

But I would absolutely add support for ZD2 and Z8 as **shadow profiles**.

## 4.2 CPD-1 remains best if you want a smoother record

The 30/70 composite still has the best risk-adjusted logic:

```text id="ae3oo9"
lower drawdown
better Sharpe
more psychologically survivable
better live track record optics
```

But it is not the best answer to:

```text id="525e6z"
What single system gets profitable fastest?
```

For that, crypto-only is still better.

The tradeoff is unchanged:

| Approach               | Best for                           | Main problem                      |
| ---------------------- | ---------------------------------- | --------------------------------- |
| CPD-1 30/70            | Smooth, risk-efficient live record | Lower profit, more venues         |
| Crypto-only CTD        | Simpler, higher expected profit    | Much larger drawdowns             |
| Semiconductor intraday | Headline annualization             | Too short/fragile                 |
| Options/H1             | Future convexity                   | Not feasible at current capital   |
| Macro breadth          | Research neatness                  | Already failed promotion criteria |

## 4.3 The semiconductor strategy should still not be first

The top annualized semiconductor strategy is still too short-window and fragile.

It had the flashiest annualized number, but it was roughly a one-month sample. It is not a better first live system than the multi-year BTC/SOL crypto trend family.

I would keep it in research only.

## 4.4 Options should still not be traded now

The Deribit snapshotter is worth fixing because it builds future evidence. But the options overlay remains capital-locked.

At $1k–$5k, minimum-lot distortion is still the issue. The deployment should stay linear-only.

## 4.5 Macro breadth is done for now

The macro-breadth study appears to have done its job:

```text id="hmyq3n"
M1X variants did not promote.
M1 long/flat looks better than M1 long/short.
```

So the next macro decision is not “more research.” It is:

```text id="f8vk7w"
Do we deploy macro long/flat, or skip macro initially?
```

---

# 5. Venue reassessment

The implemented venue logic is mostly correct:

```text id="oqppld"
spot longs
perp shorts
no perp longs
no options yet
```

That remains the right expression.

Current public fee assumptions are still broadly supportive. Hyperliquid publishes base perp fees of **0.015% maker / 0.045% taker**. ([Hyperliquid Docs][1]) Binance’s futures fee example for regular users is around **0.02% maker / 0.05% taker**. ([Binance][2]) IBKR’s European stock/ETF commissions show tiered pricing around **0.05% of trade value**, but with minimum commissions such as EUR 1.25 depending on market/currency. ([Interactive Brokers][3])

The live caveat remains venue availability.

Binance has announced EEA restrictions/delistings for non-MiCA-compliant stablecoin pairs such as USDT, and recent reporting has raised broader Binance EU/MiCA service-availability concerns. ([Binance][4]) ([Reuters][5])

That does not automatically mean the user cannot use Binance USDT-M, especially if the account is Swiss or otherwise outside the affected EEA scope. But it means the deployment must have an account-level venue check before live.

Required verification:

```text id="0z3njd"
Binance:
    Is BTCUSDT spot tradable?
    Is SOLUSDT spot tradable?
    Is USDT-M futures enabled?
    Are BTCUSDT and SOLUSDT perps tradable?
    Are USDT balances/pairs restricted?

Hyperliquid:
    Can it serve as fallback for shorts?
    Is self-custody/bridging acceptable?
    Are BTC/SOL perp minimums and fees acceptable?

IBKR:
    Are chosen UCITS ETFs/ETCs tradable?
    Are fractional shares available for them?
    Are US ETFs actually blocked or available for this account?
    What are effective minimum commissions?
```

---

# 6. Best approach from here

I would use a **three-stage plan**.

## Stage 1 — Hardening sprint

Before any paper/live, fix the implementation issues.

Priority list:

```text id="0tvrb1"
P0:
    Fix tracking_report.py.
    Add date filtering, paper/live filtering, correct weighted profile returns,
    and correct starting-equity denominator.

P0:
    Decide macro short expression.
    My recommendation: macro long/flat only.

P0:
    Add order_tickets CLI.
    The daily process should not require Python snippets.

P0:
    Fix dependency handling.
    Add pyarrow or change snapshot format.
    Skip Nautilus tests gracefully if Nautilus is not installed,
    or declare Nautilus as an optional dependency.

P1:
    Add deployment.daily_cycle.
    One command should run integrity → signals → tickets → risk → alerts.

P1:
    Add crypto marking/equity snapshot helper.
    Tracking error needs reliable daily marks.

P1:
    Add profile support:
        cpd1
        cpd1_longflat
        ctd_za4
        ctd_zd2
        ctd_z8

P2:
    Install Nautilus and make Hyperliquid testnet drill actually runnable.
```

The most important fix is tracking. Without correct tracking, paper mode is less meaningful.

## Stage 2 — Paper-run profiles, not strategies

Do not run five live systems.

Run two or three profiles in paper/shadow mode:

```text id="fu5fvz"
Profile A — CPD-1 long/flat:
    30% ZA4 crypto
    70% M1 long/flat macro

Profile B — CTD-ZA4:
    100% ZA4 crypto trend, or chosen account allocation

Profile C — CTD-ZD2:
    100% ZD2 crypto trend, or chosen account allocation
```

Only one profile should eventually go live first.

This gives you useful comparison without operational explosion.

Metrics to compare during paper/shadow:

```text id="imnq17"
number of tickets
skipped tickets
funding-review flags
tracking error
actual effective fees
macro short/flat impact
venue minimum impact
human time per day
signal differences ZA4 vs ZD2/Z8
drawdown behavior
```

This will answer the real question:

```text id="msomqu"
Is CPD’s extra smoothness worth the extra complexity,
or should the first live account be crypto-only?
```

## Stage 3 — Choose one live profile

After the hardening sprint and short paper/shadow run, choose one.

My default decision tree:

```text id="w5ukpt"
If the priority is highest expected profit and simplicity:
    go live with CTD-ZA4 or CTD-ZD2.

If the priority is smoother live record and lower drawdown:
    go live with CPD-1 long/flat.

If venue access blocks Binance futures:
    use Hyperliquid for short perps, but keep spot longs elsewhere.

If macro execution remains awkward:
    skip macro initially and run CTD.
```

My personal choice, given your stated preference for one highly profitable approach:

```text id="8xkqya"
Go live first with CTD-ZA4 or CTD-ZD2,
using the CPD-1 infrastructure,
at reduced allocation.

Keep CPD-1 running in shadow.
```

That uses the implementation you already paid for, but avoids making the first live deployment unnecessarily multi-venue and multi-sleeve.

---

# 7. How to integrate Nautilus from here

I would not rewrite ZA4/M1/ZD2 as Nautilus strategies yet.

Instead:

```text id="62f5fw"
Vibe engine:
    continues producing target weights.

Nautilus:
    consumes target state and handles paper/testnet/live execution.

Deployment ledger:
    remains the realized-truth and reconciliation layer.
```

That is the best of both worlds.

The next Nautilus milestone should be:

```text id="5etmbw"
Nautilus target executor, not Nautilus strategy port.
```

Sequence:

```text id="yllr17"
1. Install Nautilus dependency or mount local Nautilus in dev environment.
2. Make hl_testnet_drill.py test pass.
3. Create a generic TargetState → OrderIntent translator.
4. Run Hyperliquid testnet drill from actual CPD/CTD target state.
5. Keep manual live execution until the executor has shadowed cleanly.
6. Automate one venue first, probably perp shorts.
```

That avoids revalidation drift while still moving toward stable automated deployment.

---

# 8. Brainstormed alternatives

## Alternative 1 — Full CPD-1 as planned

```text id="eedslh"
ZA4 + M1
IBKR + Binance
manual execution
paper for 4 weeks
```

Good if you want a clean, smooth, conservative track record.

I would modify it to:

```text id="6uuico"
ZA4 + M1 long/flat
```

not full macro long/short.

Verdict:

```text id="keb1a7"
Good baseline, but not the fastest high-profit path.
```

## Alternative 2 — Crypto-only CTD using CPD infrastructure

```text id="b4lqtm"
ZA4 or ZD2 only
BTC/SOL
spot longs
perp shorts
deployment ledger/tickets/alerts
```

This is the best fit for your stated preference.

Verdict:

```text id="3rul2j"
Best first live candidate if you accept drawdown.
```

## Alternative 3 — Crypto-only plus cash reserve

```text id="ptvf6l"
60–70% account allocated to CTD
30–40% cash
```

This is cleaner than adding macro if the goal is one system.

Verdict:

```text id="l5a5n5"
Probably the best compromise.
```

## Alternative 4 — ZD2 instead of ZA4

ZD2 appears to be a better short-side durability variant in some forward/burned-window checks, but the evidence is not overwhelmingly superior on every dimension.

Verdict:

```text id="uyurf0"
Shadow it now.
Promote only after target-level comparison and paper evidence.
```

## Alternative 5 — Z8 instead of ZA4

Z8 has attractive forward Sharpe/drawdown.

Verdict:

```text id="v52vkf"
Also worth shadowing.
Do not live-switch blindly.
```

## Alternative 6 — Semiconductor intraday system

Too short-window, too fragile, too execution-sensitive.

Verdict:

```text id="gegu4d"
Do not deploy now.
```

## Alternative 7 — Nautilus-first rewrite

Tempting, but wrong next step.

Verdict:

```text id="d4cyzq"
Use Nautilus for execution, not strategy rewrite.
```

## Alternative 8 — Options overlay

Not at current capital.

Verdict:

```text id="g59lvf"
Fix snapshotter, collect data, do not trade.
```

---

# 9. Concrete next backlog

## Immediate fixes

```text id="no4yir"
1. Fix tracking_report.py.
2. Add CLI to order_tickets.py.
3. Add deployment.daily_cycle.
4. Add pyarrow or change snapshotter storage format.
5. Skip Nautilus tests cleanly unless Nautilus is installed.
6. Decide macro long/flat expression.
7. Add strategy-sleeve mappings for ZD2 and Z8.
8. Add deployment profiles.
```

## Paper/shadow setup

```text id="c84hda"
1. Run CPD-1 long/flat daily.
2. Run CTD-ZA4 daily.
3. Run CTD-ZD2 daily.
4. Compare tickets, skips, funding, and theoretical P&L.
5. Do not live trade all three.
```

## Live decision

```text id="jfhdkp"
If profit-first:
    CTD-ZA4 or CTD-ZD2 at reduced allocation.

If smooth-track-record-first:
    CPD-1 long/flat.

If uncertain:
    CTD-ZA4 at 50–70% allocation,
    CPD-1 shadow only.
```

## Automation path

```text id="e74tuf"
1. Make Nautilus testnet drill pass.
2. Build TargetState → Nautilus paper executor.
3. Shadow Nautilus executor against manual tickets.
4. Automate one leg only after clean shadow operation.
```

---

# 10. Final recommendation

My best reassessment is:

> **Do not abandon CPD-1. It is useful infrastructure. But do not let the fact that CPD-1 is implemented force you into a slower, lower-profit, multi-sleeve first live deployment.**

From here, the best path is:

```text id="dbgncs"
1. Harden CPD-1 implementation.
2. Convert macro to long/flat or keep macro shadow-only.
3. Add CTD crypto-only profiles inside the same deployment framework.
4. Paper-run CPD and CTD side by side.
5. Choose one live profile.
6. If your preference remains “one highly profitable approach,” go live with crypto-only CTD first.
7. Use Nautilus as execution harness later, not as a strategy rewrite.
```

My specific preferred next live candidate:

```text id="abvr7h"
CTD-ZA4 or CTD-ZD2:
    BTC/SOL daily crypto trend
    spot longs
    perp shorts
    no macro initially
    no options
    reduced starting allocation
    CPD infrastructure for tickets, ledger, risk, alerts
```

My specific preferred conservative fallback:

```text id="w7xhqf"
CPD-1 long/flat:
    30% ZA4 crypto
    70% M1 long/flat macro
    no macro shorts
```

So the best approach from here is not “more research” and not “five deployments.” It is:

> **Stabilize the implemented deployment chassis, add one crypto-only fast lane, shadow both CPD and CTD briefly, then deploy exactly one profile live.**

[1]: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees?utm_source=chatgpt.com "Fees | Hyperliquid Docs - GitBook"
[2]: https://www.binance.com/en-KZ/support/faq/detail/360033544231?utm_source=chatgpt.com "Binance Futures Fee Structure & Fee Calculations"
[3]: https://www.interactivebrokers.com/en/pricing/commissions-stocks-europe.php?utm_source=chatgpt.com "Commissions Stock Europe | Interactive Brokers LLC"
[4]: https://www.binance.com/en/support/announcement/detail/bcaa1f68d6a6450099056ff694ad6c46?utm_source=chatgpt.com "Binance Will Delist Non-MiCA Compliant Stablecoin ..."
[5]: https://www.reuters.com/business/finance/binance-set-lose-eu-licence-bid-permission-offer-services-bloc-sources-say-2026-06-16/?utm_source=chatgpt.com "Binance set to lose permission to operate in EU, sources say"
