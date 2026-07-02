# Vibe-Trading Research Plan — H2 2026

**Written:** 2026-07-02. **Updated same day** after (a) the §63 forensics round and (b) a
full audit + execution pass against the external
`vibe_trading_missed_edges_next_research_report.md` (assessment and results in
`vibe_trading_research_findings.md` §64). See §6 below for the live task-list status.
**Companion to:** `vibe_trading_strategy_synthesis.md` (conclusive analysis of the research
arc to date — read that first for the evidence behind every prior cited here).
**Purpose:** a critical evaluation of the repository for overlooked research vectors and
unpursued edges, grounded in (a) what the codebase can actually test today (verified against
code and the MCP tool surface, per the arc's own standing discipline), (b) fresh external
research on market conditions as of June/July 2026, and (c) the arc's validated priors about
where alpha does and does not live on this platform.

---

## 1. Market conditions, June/July 2026 (externally researched, 2026-07-02)

The facts that should shape the next six months of research:

1. **Crypto is in a confirmed, deep bear market.** BTC opened July 2026 at ~$57,950 — its
   lowest level in 652 days (21+ months). June 2026 saw the worst-ever monthly US spot-ETF
   outflow (~$4.51B). Total crypto market cap has fallen from ~$4.2T (Oct 2025) to ~$2.18T.
2. **Altcoins are substantially weaker than BTC.** SOL ≈ $72.75 (-47% YTD), trading below
   every meaningful moving average in a structural downtrend; BTC dominance ~55.75%
   (historically alt-suppressing above 55%); altcoin-season index in the bearish 30-40 band.
3. **Consensus cycle-bottom expectations cluster around Q4 2026** (multiple on-chain
   analytics firms and cycle analysts), i.e. a *bottoming process* — historically a choppy,
   reversal-prone regime — is the base case for H2 2026, with the July 28-29 Fed meeting the
   nearest macro catalyst.
4. **Crypto implied volatility is moderate-to-low** (DVOL spiked ~37→44 in the January 2026
   selloff; IV rank ~36, IV percentile ~50) and BTC realized volatility sits near levels that
   historically preceded volatility expansions.
5. **Macro trend-following is in a healthy stretch**: SG Trend +9.09% / SG CTA +9.58% YTD as
   of late June 2026 (already corroborated in-repo: M1/M2's OOS Sharpe >1.0 over the same
   window), while equity quant *momentum* suffered a crowded unwind in June 2026.

**Implications for this platform's strategies:**

- **The champion's short capability is currently the load-bearing feature.** Z4's +48.4% OOS
  year against BTC's -46.3% came substantially from being able to be short. A regime where
  SOL grinds down and BTC bleeds is a *tradable* trend regime, not a dead one.
- **But the 0.43x short-conviction tilt systematically undersizes shorts** — it was
  calibrated as a bet on crypto's dominant upward drift, in a training window that was
  net-bullish. In a multi-quarter bear this is a live, evidence-based question (see P1.2),
  and it sits in allocation space, the one category with an unbroken winning record.
- **A Q4-2026 bottoming process is exactly the chop regime Z4's exposure scalar exists for.**
  Expect the scalar to earn its keep; expect naive controls (Z0/L) to look worse than Z4 in
  relative terms while this lasts.
- **Selling volatility at IV-rank ~36 is worse risk/reward than the 2021-2026 average** the
  VRP finding was measured over — any VRP harvesting build (P1.3) should condition entries on
  DVOL level from day one rather than harvesting unconditionally into a potential
  vol-expansion.
- **The macro sleeve and the CP3 composite deserve more weight now**, both because the
  external CTA regime is favorable and because crypto's absolute-return engine (SOL's
  outsized rallies) is dormant until a new bull leg.

---

## 2. Critical evaluation: overlooked vectors found in this pass

A systematic scan of the codebase, the MCP tool surface, and the research log's own "open"
flags surfaced the following genuinely unpursued or under-pursued items, ordered by how
concretely actionable they are:

1. **A likely unblock for the VRP edge, verified externally this session.**
   The log closed §56/§61 with "historical Deribit option prices not available free; DVOL
   futures delisted; paid data is a standalone budget decision." **Verified 2026-07-02:
   CryptoDataDownload publishes historical Deribit option chains — every strike, puts and
   calls, OHLC+volume, organized by expiry, spanning September 2022 → present — behind a
   low-cost "Plus+" subscription** (far below the OptionMetrics/ORATS/CBOE-DataShop tier the
   log assumed was the only path), with the BTC/ETH volatility-index history free. OHLC by
   strike is sufficient to build a variance-swap replication-strip backtest marked daily at
   close, with spreads modeled from Deribit's published fee schedule (0.03%/side, capped at
   12.5% of premium) plus a conservative assumed half-spread. This converts the single
   strongest measured edge in the whole arc (BTC short-variance Sharpe 2.11 gross, t=28.3,
   offset-robust 30/30) from "structurally blocked" to "one small budget decision away."
2. **DVOL-as-regime-signal for Z4** — explicitly flagged open in §56.6(b), data already
   free and fetched once. The cheapest untested, well-motivated item on the board.
3. **The short-tilt regime question** (see §1 above) — never tested because the entire
   design phase happened inside a net-bullish sample. Allocation-space category prior: 5-for-5.
4. **A cheap same-venue perp-vs-spot bar-boundary isolation nobody noticed.** §41.4 parked
   this as "needs new loader infrastructure" (Hyperliquid spot path or an OKX perp loader).
   But Binance offers *both* spot (`BTC-USDT`) and USDT-margined perpetuals
   (`BTC-USDT:USDT`) through the already-working ccxt loader at the same UTC-midnight bar
   alignment — same venue, same offset, only the instrument differs. If the perp symbol
   resolves through the existing `code.replace("-", "/")` mapping (verify first; may need
   `CCXT_EXCHANGE=binanceusdm`), the last flagged confound in the crypto arc closes for the
   cost of two backtests, not a loader project.
5. **An entire unused China-A event/flow data surface.** The MCP server exposes
   `get_dragon_tiger`, `get_northbound_flow`, `get_lockup_expiry`, `get_block_trades`,
   `get_margin_trading`, `get_fund_flow`, `get_shareholder_count` — none of which appear
   anywhere in the research log. The validated §59 finding (China A momentum positive at all
   20 offsets, the most robust equity signal found) has never been combined with any
   event/flow conditioning, and lockup-expiry / margin-balance / dragon-tiger data are
   exactly the retail-crowding proxies §45.4's regime-flip finding calls for. Caveat to
   verify first, per standing discipline: real-time northbound flow disclosure was curtailed
   by exchanges in 2024 — check what these endpoints actually return, point-in-time, before
   designing anything.
6. **No strategy has ever been forward-tracked.** The platform has `trading_*` (paper/live
   account, orders, positions) and `scan_shadow_signals`/`run_shadow_backtest` tooling —
   never used. Every validated result is retrospective; the frozen OOS window ended
   2026-06-30, i.e. **the OOS runway is fully consumed as of this week**. The cheapest
   possible source of genuinely new evidence from here is calendar time on a frozen,
   forward-tracked signal.
7. **The fundamental-data gap is a budget decision being treated as a wall.** China A
   value/quality (§45) and US QVM (§46) are both blocked on real fundamentals; a
   `TUSHARE_TOKEN` is a low-cost subscription, and §45.4's regime-conditional value flip is
   the single most interesting *equity* finding of the arc, currently unexploitable.

Vectors considered and *not* recommended: more crypto pairs/venues/parameters (closed by
§40-41 with statistical backing), signal-timing redesigns (0-for-11+), cross-sectional
crypto momentum (closed three ways), funding carry (closed twice), intraday/faster bars
(the signal-speed and §20 continuous-EMA evidence argues against; no new hypothesis exists),
LLM/sentiment/on-chain-paid data (Tier B-/C evidence, infra-heavy, deferred).

---

## 3. The prioritized plan

Each item lists: motivation → concrete action → prerequisite/cost → expected value →
discipline requirements. Effort grades: S (hours), M (1-2 sessions), L (multi-session).

### P0 — Operational hygiene (do first, this week)

**P0.1 — Commit the in-flight work.** (S)
The branch `fix-channel-settings` carries uncommitted platform fixes and modified tests
(market-detection regex, metrics helper, risk-parity solver work, research docs). Get the
4,629-test suite green, commit, and stop carrying research-critical fixes uncommitted.
*Confirm commit strategy with the user — the handoff explicitly marks this a user decision.*

**P0.2 — Institute the forward-validation ritual.** (S, recurring)
The frozen OOS window (2025-07→2026-06) is now exhausted. Freeze Z4, Z4+Z8, M1, M2, CP3
exactly as they stand; re-run them quarterly on the accruing window (with the standard 60-day
warmup buffer, slicing the true window manually); record results append-only. **No re-tuning
against these results, ever** — this is the only mechanism that generates genuinely new
evidence for free.

**P0.3 — Start forward signal tracking (paper/shadow).** (M, then recurring)
Wire Z4+Z8 and CP3 into the unused shadow/paper tooling so that live-forward daily signals
are recorded from now on. This is strictly more informative than quarterly backtest
extension (no hindsight bar-boundary choice, real data-arrival timing) and costs nothing.

### P1 — Highest expected value research (next 2-4 sessions)

**P1.1 — DVOL-level regime overlay on Z4.** (S-M)
*Motivation:* the last explicitly-flagged open item (§56.6b); free data; already fetched once.
*Action:* test DVOL level/percentile as an exposure conditioner on Z4 (train window first,
extended window second), one small pre-registered grid, DSR-corrected.
*Expected value:* honestly, likely neutral — three prior real-signal overlays all failed to
monetize (§52/§53/§60), and "Z4 is near a local optimum for overlays" is the standing
meta-finding. Worth doing because it is cheap, closes the flag, and a *negative* result
further sharpens the local-optimum claim.

**P1.2 — Short-tilt regime recalibration (allocation space).** (M)
*Motivation:* §1's regime argument; the 0.43x tilt is the one championed parameter calibrated
purely inside a bull sample; tilt changes are allocation-space (5-for-5 category record).
*Action:* pre-register a 3-point comparison — 0.43x (control), 1.0x symmetric, and one
regime-conditional variant (e.g. tilt toward symmetric when price < SMA(200), a slow, dumb,
hard-to-overfit conditioner) — on the extended 2020-2025 window *including* the 2022 bear,
plus the Binance extended window as the second venue check. DSR across the 3 trials; freeze
the winner; single-shot confirmation on the 2025-07→2026-06 window *last* (it is no longer
virgin OOS for the control, so treat it as a consistency check, not proof).
*Risk:* this is regime-chasing if done sloppily. The guardrails: the conditioning variable
must be slow and generic, the grid must stay at 3, and a null result (0.43x survives) is a
perfectly good outcome — record it and stop.

**P1.3 — VRP monetization feasibility (the biggest prize).** (L, small budget)
*Motivation:* Sharpe 2.11 gross, t=28.3, 30/30 offset-robust — the strongest edge measured in
the entire arc, currently unharvested; §2.1 above found a concrete low-cost data path.
*Action, phased with explicit go/no-go gates:*
  1. Subscribe to CryptoDataDownload Plus+ (bounded cost); pull BTC option chains
     (Sept 2022→present) and validate coverage/quality (strikes per expiry, gaps, sanity
     against the free DVOL series).
  2. Build a short-volatility replication backtest: monthly short ATM-straddle or short
     variance-strip, held to expiry, marked daily; Deribit fees (0.03%/side, 12.5%-of-premium
     cap) plus a conservative assumed half-spread; margin per Deribit's rules so the May-2021
     left tail is realistically survivable (position sizing such that a -50-vol-point VRP
     month does not breach margin).
  3. Condition on DVOL: given IV-rank ~36 today (§1.4), test unconditional harvesting vs.
     harvest-only-above-DVOL-median. Pre-register both; DSR across the pair.
  4. If net Sharpe survives above ~1.0 with a survivable tail: promote to a third sleeve in
     the composite (P2.3) — its return driver is mechanically distinct from both trend
     sleeves, which is exactly what the portfolio lacks.
*Go/no-go:* if data quality at step 1 is poor (sparse strikes, big gaps pre-2024), stop and
record; do not hand-wave the replication with interpolated data.

**P1.4 — Same-venue perp-vs-spot isolation on Binance.** (S)
*Motivation:* closes the last flagged confound (§41.4) at ~1% of the assumed cost (§2.4 above).
*Action:* verify `BTC-USDT:USDT`/`SOL-USDT:USDT` resolve through the ccxt loader
(`CCXT_EXCHANGE=binance` or `binanceusdm`, scoped env var via direct `runner.py` invocation,
per the standing CLAUDE.md pattern); run Z4 on Binance spot vs. Binance perp, identical
window; the residual difference is the true instrument effect, offset held constant.
*Expected value:* a clean robustness datapoint ahead of any real perp deployment (perp fees
are cheaper, 0.02%/0.05%, per §41.2 — if mechanics are also neutral, perps become the
preferred execution wrapper).

### P2 — New mechanisms (after P1; bounded infra or small budget)

**P2.1 — China A momentum sleeve + event/flow conditioning.** (L)
The §59 momentum finding (robust at all 20 offsets) is the arc's most durable equity signal
and has never been built as an actual frozen strategy sleeve. Build it with the platform's
full discipline (point-in-time universe, harsh net costs, DSR), then — only after the plain
sleeve is validated — test *one* event/flow conditioner from the unused MCP surface
(lockup-expiry avoidance is the most mechanically direct: supply events are scheduled,
public, and point-in-time by construction). **Prerequisite:** verify what
`get_lockup_expiry`/`get_margin_trading`/`get_dragon_tiger` actually return and whether it
is point-in-time safe; northbound-flow granularity changed in 2024.

**P2.2 — Fundamental data decision (TUSHARE_TOKEN).** (decision + S to integrate)
A deliberate, small budget decision that unblocks the §45.4 regime-conditional value finding
(China A) — the most interesting equity result of the arc. Without it, all value/quality
work stays proxy-degraded and should not be attempted (§46's inverted-proxy lesson).

**P2.3 — Composite portfolio refresh.** (M)
Re-run the sleeve-level composite (CP3 pattern — sleeve-level allocation only; CP1's
per-asset ERC is a documented anti-pattern) with: updated window through the present, M1 vs.
M2 as the macro sleeve, crypto sleeve weight {15%, 20%, 25%} as one small pre-registered
grid, and — if P1.3 succeeds — the VRP sleeve as a third leg. Given §1's regime read
(macro CTA healthy, crypto bear), CP3-style blends are the most deployment-relevant artifact
this platform has; treat this as productization, not exploration.

### P3 — Deliberately deferred (revisit conditions stated)

- **Equity options / dispersion / skew:** revisit only if P1.3 succeeds *and* a real
  equity-options data budget is approved. The engine's synthetic IV remains a hard block.
- **US large-cap QVM:** revisit only after P2.2-class fundamental data exists for US names.
- **Intraday/faster-bar strategies:** revisit only with a specific new hypothesis that
  survives the §20/§25.4 signal-speed evidence; Binance deep intraday history is available
  when that day comes.
- **AI/LLM/sentiment alpha, alpha-mining automation:** defer until the factor pipeline is
  producing stable validated sleeves worth automating.
- **More crypto pairs, venues, Z4 parameter tuning, signal-timing redesigns,
  cross-sectional crypto momentum, funding carry:** closed by evidence; do not reopen
  without genuinely new information (see the synthesis §4).

---

## 4. Standing guardrails (non-negotiable, from the arc's own validated discipline)

1. Pre-register every grid; DSR/PBO-correct every comparison; freeze before OOS; never
   re-tune against an OOS result.
2. Never cite a single-offset Sharpe — offset-sweep any result whose rebalance/bar boundary
   is arbitrary.
3. Spot crypto configs: `"funding_rate": 0.0`, `"maker_rate": 0.0008, "taker_rate": 0.0010`.
   Never enable `rebalance_threshold` for this strategy family.
4. Manual return-series blends and hand-rolled engine approximations are not evidence —
   three documented failures (§42.3, §45.2, §50.3). Run the real engine.
5. Verify platform capability against the actual code before trusting any external framing
   — the arc's single most reusable meta-lesson (§49).
6. Sleeve-level allocation when combining strategies of different alpha quality; per-asset
   ERC across heterogeneous sleeves is a documented anti-pattern (§50.2).

---

## 6. Live task-list status (updated 2026-07-02, post-§63/§64 execution)

Assessment of the external missed-edges report: its headline Z8 gross-cap claim was
**refuted by measurement** (78% upside expression; findings §64.1), its top new-edge
recommendation (liquidity-regime overlay) was **built, tested, and rejected** (ZB2, §64.5),
its funding thread was **already closed** by §47/§53/§54, and its genuinely valid items are
folded in below. Its proposed `gross_exposure_cap` engine change was **deliberately
rejected** (cost-free-leverage trap, §64.3).

| Item | Status | Result / next step |
|---|---|---|
| P0.1 commit in-flight work | **Done** | Suite green (4,629 passed); three conventional commits on `fix-channel-settings` (§65.1) |
| P0.2 forward-validation ritual | **Done — operational** | `forward_validation/` harness: frozen Z4/Z8/ZA4/M1/CP3/CPA3 + `run_forward.py` + append-only ledger; run quarterly |
| P0.3 forward signal tracking (paper/shadow) | **Done (ledger form)** | Shadow tools are journal-mining, `trading_*` needs credentials (user decision); the ledger is the mechanism until then |
| P1.1 DVOL regime overlay | **Done — negative** | No stable attribution split (§64.4); closed without burning a backtest trial |
| P1.2 short-tilt recalibration | **Done — reframed** | Tilt is dead code in 2-asset ERC (§63.2, ZA2); ZA4's post-allocation regime dampener is the working replacement |
| NEW: §74 forensics directions 1-4 (Round 60) + full audit (Round 61) | **Done — audited, 2 fixes, net state in §79.5** | §75-78 executed by agent; §79 audit found and fixed a real ZE3 bug (fixed rerun reverses §76 on the ext window, then loses the bear-year consistency check — static BTC-cap closed as a regime bet), corrected §75's funding magnitudes (~halved; SOL-short wrapper advice stands), amended ZA4B's frozen deployment (`GROSS_RECOVERY_SCALE=len(symbols)`, 0.44→0.72 gross, zero forward bars accrued), and added the missing burned-window check for ZD2 (**beats ZA4 on every axis in the bear regime** — outlook upgraded, still forward-arbitrated). `one_shot_resize` primitive verified correct; suite 4,679 green. |
| P1.3 follow-on: delta-hedged VRP (was "open, larger follow-on") | **Done — built, run, not promotable yet; forward-track** | §73: §72's phase 2 audited first (two flattering defects found: ±3d entry lookahead; flat-day-excluded Sharpe — conditional 0.59 was really 0.32). Then the delta-hedged implementation was actually built with corrected mechanics (`research/vrp_deribit/phase3_delta_hedged_backtest.py`). Hedging fixes the tail decisively (max DD -40%→-9.6% uncond; COVID entry contained at -$71k; -13.7% DD even at 30% util) but net Sharpe stays small: hedged IV-conditional 0.31-0.34 point estimate, offset-mean 0.78 with the first 6/6-positive offset sweep of any VRP variant, corr to Z4 ≈ 0. Not promotable on 25 trades; re-run quarterly as the tape accrues, reconsider at offset-mean ≥~0.7 on materially more data. |
| P1.3 VRP monetization (real Deribit trade tape, user-supplied) | **Done — closed, no-go on naive form** | §72: user supplied the full real 2016-2026 Deribit BTC option trade tape (23.8M trades) — a better unblock than the planned paid CryptoDataDownload path. Built both the VRP-validation and the actual net-of-cost tradeable short-straddle backtest. Result: non-overlapping VRP is real-direction but only marginally significant (p=0.07-0.15, not the originally-reported t=28.3 — that used an overlapping-window design); actual executed P&L (real entry prices, real fees, empirical spread) never clears Sharpe~1.0 at any tested size, and is severely offset-sensitive (Sharpe swings -0.39 to +3.64 across just 6 rebalance-day choices) — the same rebalance-timing-luck signature already distrusted elsewhere on this platform. Do not promote to composite in this naive (naked, hold-to-expiry) form. Open, larger follow-on if resumed: delta-hedged or defined-risk (iron condor/butterfly) implementation — not attempted this round. |
| P1.4 spot-vs-perp isolation | **Done — closed** | Zero instrument effect (ZB3, §64.6); perps are the preferred live wrapper (cheaper fees) |
| NEW: exogenous data bridge | **Done** | `research/data/`: stablecoin mcap, BTC ETF flows, DVOL, macro ETFs — refresh scripts trivial to re-run |
| NEW: liquidity/macro/ETF-flow overlays on Z4 | **Done — closed negative** | ZB2 + attribution (§64.4-64.5); do not revisit slower-than-trend conditioning variables as Z4 overlays |
| P2.1 China A momentum sleeve + event/flow conditioning | **Pilot done — negative; found a platform bug** | Naive 40-name top-8 12-1 momentum LOST to an equal-weight-all-40 control (Sharpe 0.13 vs 0.38, DD -29.9% vs -21.6%, §66.2). Not a refutation of §59's IC finding — a cruder test. If resumed: needs the full factor-analysis-tool pipeline + point-in-time broader universe, not another top-N variant. Side effect: found + fixed a 4th loader-truncation bug (Tencent 500-bar cap, §66.1) |
| P2.2 TUSHARE_TOKEN decision | Open (user budget call) | Unblocks China A value/quality |
| P2.3 composite refresh | **Done** | CPA3 (full-deploy ×2 + crypto-leg regime damp + 30/70): ann 45.7%, Sharpe 1.402, Calmar 1.55 — best composite yet; frozen for forward validation (§65.2) |
| P2.5 (new) US AI/semi rotation study | Open — hypothesis-generation only | From the report's P5; treat archive short-window runs as hypotheses, never evidence |
| P3 additions | Open, deferred | OI/crowding data (report P2 residue), event/unlock calendars (report P6) |
| NEW: platform-limitations audit + fixes | **Done** | §67: yfinance/yahoo_client split-dividend adjustment fixed (M1 Sharpe 0.535→0.616, M2 0.434→0.470, both metrics improved across the board — CPA3 essentially unchanged, dilution effect); data-sufficiency tripwire added (structural defense against a 3rd truncation bug); DSR/PBO consolidated into `validation.py` (exact-reproduction-validated against §33.4); equity short-borrow fee + volume-scaled-slippage utility added (both opt-in, zero behavior change by default) |
| NEW: external data audit (microforge/edgeforge) + re-validation | **Done** | §68: edgeforge's Hyperliquid OI/asset-ctx data (2024-03+, ~20 assets) is genuinely new — worth one attribution+overlay test on Z4 (low prior, per the 4-for-4 real-signal-no-monetization pattern). edgeforge's 9-asset ensemble momentum candidate independently re-validated on this platform's own engine after fixing 2 real implementation bugs — confirmed NO edge (DSR 52%, bootstrap CI straddles zero, walk-forward 1/4 windows, MC p=0.94), corroborating its own rejection with more rigor. microforge has no strategy worth porting (simpler than Z4, own DSR reports ≤0.67). Neither project unblocks options/IV data. |
| NEW: OI-crowding overlay on Z4 | **Done — negative (6th instance)** | §69.1: attribution was unusually stable across subperiods, but the overlay still underperforms Z4 on both ext-window and OOS. Local-optimum meta-finding now overwhelming (6 independent exogenous signals tested, 6 failed to monetize). |
| NEW: US AI/semiconductor rotation (was P2.5, hypothesis-only) | **Done — decisive negative** | §69.2: M1's proven recipe ported to SOXX+SPY; Sharpe 0.21 vs. SOXX buy-and-hold's +2,787% (2001-2026) — timing captured barely 2% of available return. Confirms the missed-edges report's own caution about treating archive runs as evidence. Closed. |
| NEW: China A value+momentum composite | **Closed — did not survive broadening** | §69.3 found a promising 40-stock result (Sharpe 0.50 vs 0.38 control, DSR 79.7%); §70.3's follow-through on an 85-stock universe REVERSED it (composite 0.21 vs control's 0.52) — a small-N artifact, not a real edge, per the same discipline that already closed crypto cross-sectional momentum (§57). Do not pursue further without point-in-time universe construction (gated behind TUSHARE_TOKEN). |
| NEW: deep trade forensics (MAE/MFE, holding-period signature) | **Done — new, precise, OOS-confirmed finding** | §70.1: every Z4 trade held <8 days lost money; every trade held >30 days won (train AND OOS independently confirm this). Winners give back a mean 56% of peak unrealized profit before exit. Entry EMA-gap is a real but weak predictor (OOS r=0.04-0.12). Motivated a durability-based sizing test (ZD1). |
| NEW: ZD1 durability-confirmation add-on | **Confounded — inconclusive on the idea itself** | §70.2: mixed result (ext window worse, OOS better), but traced to a genuine platform-mechanics discovery — `rebalance_threshold` compares against price-dependent implied weight, not frozen quantity, so ANY mid-hold change (even a nominally one-time step) reintroduces diluted continuous weight-maintenance rebalancing (§43's failure mode). The durability idea itself is not refuted; a clean test needs a new engine primitive (quantity-based, not weight-based, resize) — a real, scoped future task, not attempted this round. |
| NEW: genuine-tick-data bar-boundary re-test | **Done — nuanced finding** | §69.4: 31.5M real Hyperliquid ticks, all 24 hourly offsets, ~10.5-month window (not the same window as §15). BTC robustly positive-leaning (2/24 negative offsets), SOL robustly negative-leaning (19/24) — offset is NOT the dominant driver of sign in this recent window, a different character from §15's own sign-flipping finding. SOL's raw-signal struggle during almost exactly Z4's own strong OOS period is itself a clean confirmation that allocation-space engineering, not raw signal quality, is what keeps the full strategy working. |
| NEW: raw-leaderboard "abandoned strategy" audit (90164a SOXL/SOXS mean-reversion) | **Done — closed negative** | §71: the one undocumented top-leaderboard entry (155%/yr, 20-day window, own MC p=0.452) extended to max real data (15m ~60d, 1H 2 real years, unmodified + hold-rescaled variants) — decisively negative on every extension (Sharpe -2.63 on new data; -15 to -30pp underperformance vs. buy-and-hold OOS; every bootstrap CI straddles zero). Confirms no abandoned/pre-fix strategy on this leaderboard has unrealized profit; only P1.3/P2.2 remain as budget-gated open items. |

## 7. Sources (external research, retrieved 2026-07-02)

- [BeInCrypto — Bitcoin Price Prediction July 2026: worst-ever ETF month, $42,000 risk](https://beincrypto.com/bitcoin-price-prediction-july-2026/) (BTC $57,950 July open, 652-day low; June ETF outflow $4.51B; Fed July 28-29)
- [Mudrex — When Will Bitcoin Bottom? (updated July 2026)](https://mudrex.com/learn/when-will-bitcoin-bottom-prediction/) (Q4 2026 bottom consensus)
- [CryptoTimes — Bitcoin Price Prediction July 2026](https://www.cryptotimes.io/2026/07/02/bitcoin-price-prediction-july-2026-will-btc-go-up-or-crash/) (base case $65.6k, bull $70k)
- [Ziro Market — Crypto Market Crash 2026: What Caused It](https://www.ziromarket.com/blog/crypto-market-crash-2026-altcoins-solana-xrp) (market cap $4.2T→$2.18T; SOL -47% YTD; BTC dominance 55.75%)
- [Cryptonomist — Solana Price Analysis, June 26 2026](https://en.cryptonomist.ch/2026/06/26/solana-price-today-analysis-mixed-signals/) (SOL ≈$72.75, below all major MAs)
- [Bitget — Altcoin Season Index](https://www.bitget.com/price/altcoin-season-index) (index 30-40, BTC-led regime)
- [CoinDesk — Bitcoin options flash troubling signs as DVOL spikes (Jan 2026)](https://www.coindesk.com/markets/2026/01/30/bitcoin-options-flash-troubling-signs-as-dvol-spikes-most-since-november) (DVOL 37→44; IV rank ~36)
- [CryptoDataDownload — Deribit Historical Data](https://www.cryptodatadownload.com/data/deribit/) (free BTC/ETH vol-index history; full option chains by strike/expiry, Sept 2022→present, via low-cost Plus+ subscription — the P1.3 unblock)
- [HedgeNordic — Managed Futures ETFs (Apr 2026)](https://hedgenordic.com/2026/04/muddling-through-the-mess-managed-futures-etfs/) and [CFA Institute — Decoding CTA Allocations by Trend Horizon (2026)](https://rpc.cfainstitute.org/blogs/enterprising-investor/2026/decoding-cta-allocations-by-trend-horizon) (macro CTA context)
- SG Trend +9.09% / SG CTA +9.58% YTD (late June 2026): cited within `research/Macro-Trend-Calibration-Strategy-1.md` and corroborated in-repo by M1/M2's OOS window.
