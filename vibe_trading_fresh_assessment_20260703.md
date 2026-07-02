# Fresh-Eyes Assessment — 2026-07-03

**Mandate:** deliberately set aside the accumulated research log, plans, and momentum;
re-derive the goal from first principles; assess the champions, the framework, and the
paths forward; execute whatever analyses can be run on data already on disk. Four new
analyses were executed for this report (portfolio orthogonality, benchmark honesty,
leverage/Kelly bootstrap, and an option **capacity study** — the last one produces the
single most consequential new fact). Scripts in the session scratchpad; every number
below is freshly computed from artifacts in this repo, not quoted from the log.

---

## 1. The goal, restated from first principles

"Find the most profitable trading strategies" decomposes into three multiplicative
factors, and only their **product** is realized P&L:

```
realized P&L  =  edge (per-unit economics)
              ×  capacity (dollars the edge supports)
              ×  risk-efficiency (portfolio construction / sizing that survives the path)
```

The research arc to date has optimized factor 1 almost exclusively — with real success —
while factor 2 had never been measured at all, and factor 3 exists (CP3) but has never
been treated as *the product*. This assessment's core conclusion: **the marginal unit of
effort now pays 5-10x more in factors 2 and 3 than in factor 1.**

---

## 2. The champion, stress-tested with fresh eyes

All computed from `agent/runs/v_ZA4_regimeconviction_ext_train` + `fwd_ZA4_20260702`
equity artifacts, spliced at 2025-07-01 (returns, not equity, so no splice artifact);
BTC benchmark from the option tape's own index series; calendar-daily basis.

### 2.1 Benchmark honesty (common window 2020-11 → 2026-06)

| Series | Ann. return | Sharpe | MaxDD |
|---|---:|---:|---:|
| ZA4 (train+forward spliced) | +111.5% | 1.54 | −43.5% |
| BTC buy & hold | +29.1% | 0.73 | −76.7% |
| BTC 200dma timing (0.1%/flip) | +32.3% | 0.86 | −64.2% |

The champion clears both naive benchmarks decisively on every axis. It is not a
disguised beta clone or a trivial-timing clone.

### 2.2 The virgin evidence (forward year 2025-07 → 2026-06, never used for selection)

| Series | Ann. return | Sharpe | MaxDD |
|---|---:|---:|---:|
| ZA4 forward | **+75.6%** | **1.49** | −27.4% |
| BTC B&H forward | −45.3% | −1.19 | −53.0% |
| BTC 200dma forward | −6.6% | −0.25 | −19.7% |

Forward Sharpe 1.49 vs in-sample 1.54 — essentially zero degradation, in a year where
the underlying *halved*. This is the strongest fact the platform owns. Honest caveat: a
short-capable trend strategy in a monster bear year is close to its best-case regime;
the regime that would genuinely stress it (multi-year chop) has not yet occurred on
virgin data. One good year is one draw, not a law.

### 2.3 Selection-bias check

`agent/runs/` contains ~160 named design variants (~100 excluding shuffle-seed nulls) —
the honest trial count behind the champion is on the order of 100, far above the small
`n_trials` used in the log's per-comparison DSR calls. Recomputing DSR on the train
window at n_trials ∈ {10, 50, 100, 200} still gives 99.97% — 4.6 years of daily data at
SR 1.5 is long enough that even harsh deflation doesn't dent it. (Implementation caveat:
the library's default cross-trial Sharpe dispersion is generous; the sturdier fact
remains §2.2's virgin-year confirmation, which no deflation argument touches.)

### 2.4 The raw sleeve is too hot to be "the strategy"

Bootstrap (400 resamples of the spliced daily returns): at 1.0x, **P(maxDD worse than
−40%) ≈ 90%**, median bootstrap maxDD −52%. Full-Kelly is nominally 2.55x, but the
realized path already sits far above any drawdown-constrained sizing. **Leverage is not
the profit lever here — de-risking is** (which is exactly what the composite and the
puts expression do). Anyone deploying the crypto sleeve alone at 1.0x should expect a
~50% drawdown at some point and should size capital accordingly.

---

## 3. The portfolio is the product — and it is better than any component

Daily-return correlations on the common window (2020-11 → 2026-06):

| | ZA4 | M1 | VRP(hedged-cond) | BTC |
|---|---:|---:|---:|---:|
| ZA4 | 1.000 | 0.008 | −0.009 | 0.004 |
| M1 | | 1.000 | −0.029 | 0.076 |
| VRP | | | 1.000 | −0.039 |

The sleeves are **literally orthogonal** — correlation 0.008 between the two real return
engines is as close to zero as live data gets. Consequently:

| Portfolio (daily-rebal, gross) | Window | Ann. | Sharpe | MaxDD |
|---|---|---:|---:|---:|
| 30/70 ZA4/M1 composite | full common | +38.6% | **1.79** | −16.4% |
| 30/70 ZA4/M1 composite | **forward year only** | +27.2% | **1.80** | −12.3% |
| 30/55/15 + VRP sleeve | forward year | +25.9% | 1.75 | −11.4% |

The composite's Sharpe **reproduces identically on the virgin forward year** (1.80 vs
1.79) — it is not an in-sample artifact. At ~27% forward return with a −12% drawdown, it
is the deployable object; the raw crypto sleeve is a component, not a product.

**VRP is now definitively closed, including as a sleeve.** Freshly computed on its own
delta-hedged equity curves: Sharpe 0.22 (best variant) at near-zero vol; adding it at
15-20% *lowers* blend Sharpe (1.80 → 1.75) while shaving only ~1pt of drawdown. The
prior "not promotable standalone" verdict extends to portfolio context. Stop revisiting.

The structural observation: **the platform owns exactly two real return engines**
(crypto trend, macro trend — both trend). Everything else in the frozen ledger is a
variant of engine #1. The highest-value *research* target is a third orthogonal engine
with real capacity — see §6.

---

## 4. The capacity study — the most consequential new fact

Never previously measured: for every historical H1 put entry (premium-budget puts on the
champion's short runs, median $50k premium per entry at the studied 500k-notional
sizing), what fraction of that day's *printed volume* would the order have been?
(Printed volume proxies book depth; >100% of a day's prints is unambiguously
capacity-constrained even granting resting liquidity and block/RFQ channels.)

| | BTC (62 entries) | SOL_USDC (22 entries) |
|---|---|---|
| vs same-instrument same-day volume, median | 77.9% | **4,977%** |
| — entries exceeding 100% | 43.5% | **100%** |
| vs whole ATM-band same-day volume, median | 5.2% | **258%** |
| — entries exceeding 100% | 11.3% | **77%** |
| Supportable strategy notional @10% band participation | **~$950k** | **~$18.5k** |

Conclusions:

- **BTC H1 is deployable** at roughly the studied size ($0.5M notional ≈ half the
  estimated $0.95M capacity), with entries spread across the 3-day window and across
  strikes rather than one print.
- **SOL H1 — the celebrated "leg where the prize lives" — is untradeable at the studied
  size by a factor of ~25-30x.** Deribit's SOL_USDC book (open only since 2024-03)
  supports ~$18k of this strategy's notional at sane participation. The §82 result is
  per-unit-economics-valid and dollar-capacity-void. No amount of RFQ generosity closes
  a 25x gap.
- Consequences for the SOL short leg, in order of preference: (a) keep SOL shorts in
  spot/flat form (the linear strategy is unaffected — SOL spot/perp depth is ample);
  (b) trade SOL-H1 at whatever trivial size the book allows and let it grow with the
  venue — SOL options volume is young and rising, so **re-measure capacity quarterly**;
  (c) do not proxy SOL shorts with BTC puts — basis risk in exactly the crash scenarios
  the puts exist for.
- Meta-lesson worth institutionalizing: **every future strategy result must carry a
  capacity number next to its Sharpe.** A per-unit edge without a dollar capacity is a
  research finding, not a strategy.

---

## 5. Framework assessment: what the platform actually is

Fresh-eyes inventory of what earns its keep:

1. **The discipline layer is the moat** — frozen strategies, append-only forward ledger,
   pre-registration norms, DSR/PBO library, the research log's kill-record. This is what
   most retail-grade and many professional setups lack, and it transfers to any engine.
2. **The homegrown engine** is a known-safe niche tool: daily-bar, linear instruments,
   entry-locked sizing, with its trap-list documented (funding-on-spot default,
   commission keys, loader truncations — each found the hard way). Its irreplaceable
   role now is **comparability of the frozen ledger** — the seven frozen strategies'
   forward numbers are only meaningful against the same engine semantics.
   *Do not port the ledger anywhere.*
3. **Nautilus** is now a validated second engine with a specific mandate: everything the
   homegrown engine can't do — options (validated to ≤$1.15 across 326 run-pairs), and
   eventually live/paper execution via its Deribit adapter. The correct integration
   depth is exactly what exists: catalog + strategy harness in `research/`, not a
   platform rewrite. **Do not build options into the homegrown engine** (the
   `options_portfolio.py` synthetic-IV path should be considered deprecated for
   research), and do not migrate linear backtests to Nautilus (cost without benefit;
   would break ledger comparability).
4. **The gap in the stack is operational, not analytical**: no live/paper execution, no
   daily data snapshotting (Deribit history API returns only expired options, so the
   most recent weeks are always invisible), no monitoring. For a program whose stated
   goal is *profit*, the missing components are all in the boring layer.

---

## 6. Paths forward, ranked by expected value per unit effort

**Tier 1 — harvest what is already validated (highest certainty, lowest effort):**

1. **Stand up the composite as the deployable product.** Define and freeze a
   `CPD` (deployment composite): 30/70 crypto/macro sleeve split, crypto sleeve with
   BTC shorts expressed as budget puts (capacity-cleared) and SOL shorts linear
   (capacity-forced), sized so the bootstrap P(maxDD < −20%) is acceptable. Paper-trade
   it: macro sleeve needs only an equity broker; crypto linear needs spot/perp venue;
   BTC puts via Deribit (Nautilus live adapter, testnet first). Everything analytical
   for this exists today.
2. **Forward-track H1-BTC in the ledger** (frozen rule + quarterly rerun on the accruing
   tape) and **re-measure SOL options capacity quarterly** — the SOL prize re-opens if
   the venue deepens 25x (it is young; monitor, don't assume).
3. **Daily Deribit chain snapshotter** (public API, no keys): closes the
   expired-options-only recency gap, feeds both forward tracking and any future live
   step. Hours of work, permanent payoff.

**Tier 2 — the one research direction that matters: a third orthogonal engine.**
The composite math (§3) says a genuinely uncorrelated third sleeve with real capacity is
worth more than any improvement to the existing two. Ranked candidates by
(orthogonality × capacity × prior evidence):

4. **China-A cross-sectional momentum sleeve** — the strongest already-validated
   non-trend, non-crypto signal in the platform's history (robust at all 20 tested
   bar-offsets), never built into a frozen sleeve; A-share depth makes capacity a
   non-issue; correlation to both existing engines plausibly near zero. Build it with
   full discipline (point-in-time universe, harsh net costs), freeze, forward-track.
5. **Macro sleeve breadth** — M1 is only SPY+GLD; extending the same validated AQR-blend
   machinery to TLT/UUP/commodity proxies (loaders exist, dividend-adjustment already
   fixed) is cheap and attacks the composite's single-sleeve concentration on the macro
   side. Small, pre-registered, one shot.
6. **ETH options tape** (fetcher works, free) — only *after* 4-5: it broadens the
   expression finding but ETH correlates with the existing crypto engine, so it
   diversifies less than it appears.

**Tier 3 — explicitly not worth new effort:**
more signal variants on the champion family (0-for-11 record stands under fresh eyes),
VRP in any form (closed twice over, §3), SOL-H1 at size (physics, not research),
homegrown-engine options, full Nautilus migration, and new exotic data sources without a
specific orthogonal-sleeve hypothesis attached.

---

## 7. What was executed for this report

| Analysis | Result | Where |
|---|---|---|
| Benchmark honesty (champion vs BTC B&H vs 200dma) | champion clears both decisively; forward year Sharpe 1.49 vs −1.19 B&H | §2.1-2.2 |
| Honest-trial-count DSR | 99.97% @ n_trials=200 (with stated caveat) | §2.3 |
| Leverage/Kelly bootstrap | raw sleeve at 1.0x: ~90% chance of >40% DD; leverage is not the lever | §2.4 |
| Sleeve orthogonality + composite | corr ≈ 0.00 across sleeves; composite forward Sharpe 1.80, DD −12.3%; VRP adds nothing | §3 |
| **Option capacity study** | **BTC H1 ~$950k capacity (deployable); SOL H1 ~$18.5k (untradeable at size, 25-30x over)** | §4 |

Analysis scripts committed: `research/assessment_20260703/{portfolio_analysis,forward_only}.py`
and `research/nautilus_deribit_options/capacity_study.py` (the latter is the quarterly
SOL-capacity re-measurement tool); all inputs are repo artifacts (`agent/runs/*/artifacts/equity.csv`,
`research/vrp_deribit/derived/*`, the two option tapes). The capacity study is the one
result that should graduate into the research log and drive an immediate decision
(§6 items 1-2).
