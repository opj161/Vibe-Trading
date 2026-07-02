# Vibe-Trading Strategy Research: Conclusive Synthesis

**Written:** 2026-07-02.
**Scope:** systematic analysis of the full research arc — `vibe_trading_research_findings.md` §1-62,
`HANDOFF.md`, `vibe_trading_next_directions.md`, the six external deep-research reports in
`research/`, and all 177 backtest runs with metrics under `agent/runs/` — synthesized into one
conclusive picture of what is profitable, what the identified edges are, and how much of each
result should be trusted.
**Companion document:** `vibe_trading_research_plan_2026H2.md` (forward-looking, prioritized
next-steps plan).

---

## 1. Executive summary

After ~62 documented research rounds spanning crypto trend-following, macro trend-following,
equity factor research, funding-rate carry, cross-sectional momentum, volatility risk premia,
and composite portfolios, the platform has produced:

- **One dominant, multiply-validated champion strategy family** — Z4 / Z4+Z8, a BTC+SOL
  long/short EMA-crossover trend system with vol-targeting, risk-parity allocation, and a
  portfolio-level chop-frequency exposure scalar. **OOS (2025-07→2026-06): +48.4% to +69.7%
  return, Sharpe 1.36-1.47, max DD -19.2% to -23.7% — in a year when BTC buy-and-hold lost
  46.3%.**
- **One validated diversifying sleeve** — M1/M2 macro trend on SPY+GLD (21-year Sharpe
  0.43-0.54, OOS Sharpe ~1.1, near-zero correlation to the crypto sleeve).
- **One composite portfolio candidate** — CP3 (20% crypto / 80% macro sleeve-level blend,
  Sharpe 1.34, max DD -18.1%) as a drawdown-focused point on the frontier.
- **One large, statistically overwhelming but not-yet-tradable edge** — the crypto
  variance risk premium via Deribit DVOL (BTC short-variance Sharpe 2.11, t-stat 28.3,
  robust across all 30 rebalance offsets).
- **A dense, unusually disciplined ledger of negative results** — arguably as valuable as the
  champion itself, because it maps precisely where the alpha *isn't*.

The single most load-bearing meta-finding across the whole arc:
**capital-allocation and universe changes worked (roughly 5-for-5); signal-timing and
signal-representation changes failed (11-plus-for-11-plus).** Every future hour spent on this
platform should be biased by that prior.

---

## 2. Leaderboard: most profitable strategies, ranked by annual return

### 2.1 How to read the numbers honestly

Raw `annual_return` across all 177 runs is a misleading ranking on its own — the top raw
entries are either short-window annualization artifacts (e.g. `20260630_044631` annualizes an
8% four-month semiconductor-ETF gain to "155%/yr"), un-validated train-window runs, or
buy-and-hold benchmarks captured during a bull window (`v_Rung1_naivebh_train` at 149%/yr,
which then did **-40.8%/yr OOS**). The table below therefore separates *train-window*
annualized return from the *frozen, single-shot out-of-sample* result (2025-07-01→2026-06-30,
never re-tuned), and ranks only strategies that have both.

### 2.2 Validated strategies, ranked by OOS annual return

| Rank | Strategy | Run dirs | Train ann. return / Sharpe / MaxDD | **OOS return / Sharpe / MaxDD** | Status |
|---|---|---|---|---|---|
| 1 | **Z4+Z8** — Z4 + portfolio vol-target overlay | `v_Z8_voltarget_train` / `_OOS_TEST` | 96.6% / 1.62 / -37.2% | **+69.7% / 1.47 / -23.7%** | **Champion (return/Sharpe focus)** |
| 2 | **Z4** — chop-frequency exposure scalar | `v_Z4_chopfreq_train` / `_OOS_TEST` | 84.7% / 1.64 / -33.0% | **+48.4% / 1.36 / -19.2%** | **Champion (drawdown focus)** |
| 3 | L — BTC+SOL, drop-ETH baseline | `v_L_dropeth_train` / `_OOS_TEST` | 102.2% / 1.48 / -46.7% | +47.8% / 1.06 / -31.4% | Valid fallback |
| 4 | Z0 — corrected control (no scalar) | `v_Z0_control_train` / `_OOS_TEST` | 90.0% / 1.44 / -44.4% | +53.8% / 1.18 / -29.1% | Control |
| 5 | K — 3-asset long-bias tilt | `v_K_longbias_fixedhook_train` / `_OOS_TEST` | 74.7% / 1.39 / -30% | +45.2% / 1.10 / -30.8% | Superseded by L/Z4 |
| 6 | M2 — macro barbell (SPY+GLD) | `v_M2_macro_barbell_full` | 97.0%/21y / **0.47** / -17.9% (§67-corrected) | +14.5% / 1.10 / (small) | Validated sleeve |
| 7 | M1 — macro AQR blend (SPY+GLD) | `v_M1_macro_aqrblend_full` | 284.5%/21y / **0.62** / -19.6% (§67-corrected) | +7.1% / 1.13 / (small) | Validated sleeve |

Composite portfolio (full-window 2023-01→2026-06, includes the OOS year; no separate frozen OOS):

| Strategy | Run dir | Ann. return / Sharpe / MaxDD | Role |
|---|---|---|---|
| CP3 — 20% Z4 / 80% M1, sleeve-level ERC | `v_CP3_sleeve_2080_full` | 23.7% / 1.34 / **-18.1%** | Drawdown-focused frontier point |
| CP2 — 50/50 sleeve blend | `v_CP2_sleeve_5050_full` | 45.5% / 1.33 / -28.8% | Middle point, dominated by neither |
| CP1 — naive per-asset ERC (anti-pattern) | `v_CP1_composite_crypto_macro_full` | 57.1% / 1.29 / -41.4% | **Worse than Z4 alone on every metric** — see §4.4 |

### 2.3 Highest raw annual returns on record (context, not recommendations)

- `v_V_btcsol_extended_train` — **150%/yr, Sharpe 1.66, -47% DD** over 2020-11→2025-06
  (+7,133% total). This is the L-family mechanics on the longest available BTC+SOL window; it
  is a train-window figure with no independent OOS and includes the 2021 mega-bull. It is the
  best evidence of the strategy family's raw return ceiling across a full cycle, not a
  validated expectation.
- `v_Z4_extended_train` — 94.8%/yr, Sharpe 1.59, -41% DD over the same extended window
  (+2,143% total), with Z4 improving within-year drawdown vs. control **in every single year
  without exception**, on both OKX and Binance (§33.6, §41.3). The 2024 Binance year is the
  standout risk datapoint of the whole log: control -43.6%, Z4 -11.7%.
- `v_Rung1_naivebh_train` — 149%/yr buy-and-hold on the 2023-2025 bull train window, which
  collapsed to **-40.8%/yr OOS**. Included as the permanent reminder of why train-window
  annual return is not the ranking criterion.

### 2.4 The champion, precisely specified

**Z4** (`v_Z4_chopfreq_train/code/signal_engine.py`, config `optimizer: null`):
BTC-USDT + SOL-USDT daily bars (OKX spot), EMA(10,30) crossover direction, 10-day
realized-vol-targeted sizing, 0.43x short-side conviction tilt, hand-rolled ERC (equal risk
contribution) capital allocation across the two assets, and the discovery that made it
champion: a **portfolio-level chop-frequency exposure scalar** that scales *total gross
exposure* down when recent signal-flip frequency across both assets is elevated (attacking
the §23 finding that a third to half of BTC/SOL signal flips are same-day, i.e. shared
market-wide noise). **Z8** adds a portfolio-level vol-target overlay (target 35% annualized,
scale clipped [0.5, 1.5]) — more return and Sharpe OOS, at some drawdown cost.

Statistical support, in one place: 4-trial DSR 99.35% (§33.4); champion-lineage 13-variant
DSR 91.7% (§28.5); EMA(10,30) confirmed as a genuine parameter-grid peak, not a spike
(DSR 98.77%, §42); 60-seed real-engine permutation test p=0.033 (§42); walk-forward 4/4
profitable windows; profitable through the 2018 and 2022 bear markets (§26, §33.6); venue-robust
(OKX + Binance, §37, §41.3); funding-rate-insensitive on genuine perpetuals (§41.2).
Honest counterweight: CSCV-PBO found **80% probability of backtest overfitting among the
near-identical Z1-Z4 variant family** (§38) — reconciled as "the edge is real; the claim that
Z4's *exact* variant is reliably the best of its siblings is weak." The Z2+Z4 ensemble test
(§39) came back a genuine tie, so Z4 stands, but expect its edge over Z2/Z12 to be noise.

---

## 3. The identified edges (alpha), ranked by evidence strength

### Edge 1 — Crypto time-series trend (the traded champion edge)

The EMA(10,30) timing signal on BTC+SOL is **genuine alpha, not repackaged beta or risk
engineering**. This was settled empirically by §42's benchmark-decomposition ladder: buy-and-hold
with the identical vol-targeting/risk-parity stack still *loses* money in the true OOS window
(Sharpe ≈ -1.0); only adding the timing signal turns it positive, and a 60-seed
block-shuffled-direction permutation through the real engine put p=0.033 on that claim.
Economics: retail-dominated flow, momentum-chasing, slower institutional arbitrage — trend
continuation is a structurally more plausible inefficiency in crypto than in equities, and the
external literature (31.96% annualized crypto TSMOM; SG Trend corroboration) agrees.
Character: low win rate (26-36%), payoff asymmetry 3-5x — a classic few-big-wins profile; SOL
contributed ~68% of gross training profit, much of it in one 91-day +320% trade.

### Edge 2 — Portfolio construction as the dominant lever (meta-edge)

The single largest single-change improvement in the entire arc was adding risk-parity
allocation (Sharpe 1.17→1.43, §2-3) — bigger than any signal change ever tested. The Z4 chop
scalar and Z8 vol overlay are both *allocation-space* mechanisms. The full scorecard across
both sessions: **every winning change operated in capital-allocation or universe space
(risk parity, long-bias tilt, dropping ETH, chop scalar, vol-target overlay); every one of
11+ signal-timing/representation changes lost** (Donchian, ATR stops, trend-strength gates,
KAMA, variance-ratio, Carver/Campbell continuous forecasts, CUSUM bars, multi-speed EMA
ensembles, universe rotation…). This is the platform's most reusable prior.

### Edge 3 — Crypto variance risk premium (strongest untraded edge)

Deribit's free DVOL index vs. subsequent realized vol (§56): BTC VRP mean **10.26 vol-points,
t-stat 28.3**, positive on 77.7% of days; non-overlapping 30-day short-variance payoff
**Sharpe 2.11 (BTC) / 0.98 (ETH)**; robust at **all 30 rebalance offsets with zero sign
flips** — materially more offset-robust than the platform's own trend signal. Not yet
backtestable as a net-of-cost strategy (no historical option bid/ask data acquired; DVOL
futures delisted, §61). Known left tail: May-2021-style crashes where realized vol overshoots
implied (VRP hit -52.8 vol-points intraminimum). This is the highest-Sharpe genuine edge the
research has measured; converting it to a tradable strategy is a data-acquisition problem,
not a signal-discovery problem.

### Edge 4 — Macro trend at the correct signal speed

The crypto-tuned EMA(10,30) is ~6x too fast for macro assets — recalibrating to institutional
speeds (AQR 1/3/12-month blend, or a fast/slow barbell) turned a -13.3%/20-yr loss into
Sharpe 0.43-0.54 full-window and **Sharpe >1.0 in the true OOS year**, matching the live SG
Trend index's +9% YTD over the same window (§44). Correlation to the crypto sleeve: -0.03,
genuinely near zero. Lesson: signal speed is an asset-class property; the fast-crypto edge
does not port, but the architecture (vol-target + ERC) ports perfectly.

### Edge 5 — Chop-frequency dampening, with a known boundary condition

Z4's core innovation is real and multiply confirmed, but conditional: it helps assets with
sustained, low-reversal trends (SOL, AVAX) and **actively hurts** reversal-prone assets
(DOGE -16% relative Sharpe; 3-asset with ETH; §36, §41.1). Never assume it transfers to a new
pair without checking.

### Edge 6 — Real-but-unmonetizable signals (a recurring class)

Four independent, statistically genuine signals failed to improve Z4 when converted to
overlays: funding-rate trend-confirmation (§53), multi-speed EMA ensembling (§52), on-chain
address-growth froth (§60), and DVOL-adjacent regime ideas remain untested. Plus
cross-sectional crypto momentum: real daily IC, three independent tests (16-asset, 66-asset,
real-engine) all negative as a strategy — root cause **rebalance-timing luck** (§57), the
cross-sectional cousin of bar-boundary sensitivity. Meta-finding worth naming: **Z4 appears
close to a local optimum for overlay-style refinements** — a real IC is necessary but nowhere
near sufficient.

### Edge 7 — Regime-conditionality of equity factors (China A)

China A value's IC genuinely flips sign between calm (+0.068) and crowded/high-turnover
(-0.049) regimes (§45.4); regime-conditioning improves composites +16-21% relative IR, but
**momentum alone is the most offset-robust standalone China A signal** (positive at all 20
tested offsets, §59). Blocked from full exploitation by the fundamental-data gap (no
`TUSHARE_TOKEN`).

---

## 4. The negative-results ledger (where the alpha is not)

Each of these was well-motivated, tested with train/OOS discipline, and closed:

1. **All signal-timing/representation sophistication** (11+ attempts, §25.4, §35, §52) —
   the whipsaw isn't a bug next to the edge; it *is* the edge's cost of early trend entry.
2. **Universe expansion** — broad crypto universes lose (§31, G, Y1); ETH is a confirmed
   laggard even with chop-dampening (§36); AVAX/DOGE baselines too weak (§33.8, §41.1);
   4-asset macro (adding TLT+UUP) underperforms clean 2-asset SPY+GLD (§44.4).
3. **Cross-sectional crypto momentum as a strategy** — closed with three independent tests
   (§51, §57, §62). Real IC, not tradable at any tested basket size/frequency/offset.
4. **Naive per-asset ERC across mixed asset classes** (CP1, §50.2) — allocates by vol alone,
   drags capital toward the lower-alpha sleeve; worse than the best sleeve on every metric.
   Sleeve-level allocation is the correct pattern.
5. **CEX↔DEX funding-rate carry** — decisively negative net of costs for majors (§47) and
   even more so for mid-cap alts (11 of 12 negative, §54).
6. **US→China cross-session lead-lag** — real gap prediction (corr 0.345) but the open is
   already efficient; no tradable continuation (§48).
7. **Mid-hold continuous position resizing** (`rebalance_threshold`) — collapses this
   strategy family (Z4 train Sharpe 1.64→0.55); entry-locked sizing is an accidental feature
   that lets winners run (§43). Do not enable it here.
8. **Leverage** — 1.5x on perpetuals scales return and drawdown proportionally; Sharpe
   unchanged; no free lunch (§43). Also: >100% notional is structurally impossible through
   signal weights alone (`base.py` clips the divisor at 1.0, §34.1).
9. **US price-proxy value/quality factors** — the platform's `[PRICE PROXY]` academic factors
   were decisively *inverted* in-sample for US large caps (§46); a proxy-quality finding, and
   a hard block on US QVM until real fundamental data exists.
10. **Options/dispersion/skew strategies on the current engine** — structurally untestable:
    the options engine's "implied vol" is *defined as* trailing realized vol
    (`options_portfolio.py:276`); dispersion/skew premia cannot exist in its world model.

---

## 5. Robustness, trust calibration, and known traps

- **Bar-boundary / rebalance-timing luck is the platform's signature confound.** A daily-bar
  cutoff offset alone swings the EMA signal's Sharpe from -0.06 to +1.19 on identical data
  (§15); it also explains the apparent OKX-vs-Hyperliquid venue gap, the OKX-vs-Binance
  absolute gap, and the cross-sectional momentum failure. Never cite a single-offset Sharpe;
  offset-sweeps are mandatory for any new result. (The VRP edge is notable precisely for
  surviving all 30 offsets.)
- **Honest going-forward expectation for the champion** is below its OOS point estimate:
  DSR-corrected lineage plus offset realism argues for expecting Sharpe ~0.8-1.3, not 1.5+,
  on a genuinely fresh window.
- **The backtest's cost model is now realistic and conservative**: spot fees 0.08%/0.10%
  maker/taker (researched, §18/§28), `funding_rate: 0.0` mandatory for spot configs, zero
  yield on idle capital (real returns modestly *better* than reported, §42).
- **Every reported number sits on top of eight+ real platform bugs found and fixed during the
  arc** (funding-fee-on-spot, commission key, two lookahead leaks, annualization mismatch,
  ERC solver divergence, `bars_per_year=None` crash, digit-leading-ticker misrouting,
  Hyperliquid pagination cap). The recurring lesson: **verify platform capability against the
  actual code before trusting any framing — external reports' and this platform's own.**

---

## 6. Conclusive assessment

The research program found one real, well-understood, multiply-validated source of tradable
alpha (crypto TSMOM on BTC+SOL, harvested through allocation-space engineering), one
validated low-correlation diversifier (macro trend at institutional speed), and one
larger-but-unharvested edge (crypto VRP). It also demonstrated — with unusual statistical
discipline — that the surrounding space of "obvious improvements" is almost entirely barren,
and that the platform's most dangerous failure modes are implementation-level (timing-luck
confounds, silent config traps, allocation mechanics) rather than statistical.

**Recommended deployment posture as of July 2026** (see the companion plan for the market-
conditions argument): Z4 for drawdown-focused use, Z4+Z8 for return/Sharpe-focused use, CP3
(20/80 crypto/macro sleeve blend) where a sub--20% max drawdown mandate matters. The
champion's long/short design — specifically its ability to be short — is the load-bearing
feature in the current bear regime: it is what turned BTC's -46.3% OOS year into +48.4%.

---

## 7. Addendum (2026-07-02, same day): §63 forensics round — two mechanical discoveries and a new max-annual-return variant

A trade-level forensic round run immediately after this synthesis
(`vibe_trading_research_findings.md` §63) found: (1) **the 0.43x short tilt is dead code**
in the 2-asset ERC implementation (it cancels inside the `weights × mag_share` ratio;
empirically confirmed by ZA2 — removing it changes nothing); (2) **the champion deploys only
~47% of capital on an average day** (the `ERC-weight × magnitude-share` product construction
structurally caps full-conviction gross near 0.5). Recovering that idle capital with a ×2
final scale under the existing 1.0 gross cap (**ZA1**) lifted the extended-window annual
return from 94.8% to **125.5%** at flat Sharpe and only -44.7% DD (Calmar 2.33→2.81); adding
counter-regime conviction dampening (**ZA4**: halve positions whose sign disagrees with the
asset's own SMA200 regime) kept ~120%/yr train while dominating ZA1 in the burned bear-year
check (+57.2% / Sharpe 1.29 / DD -27.4%). **Champions unchanged for Sharpe/DD mandates; ZA4
(`v_ZA4_regimeconviction_ext_train`/`_OOS_TEST`) is the new maximum-annual-return spot
variant.** Z8 vs ZA4 must be arbitrated on fresh forward data from 2026-07-01 — the old OOS
window is burned. Also: gross-recovery cannot be stacked under Z8's vol overlay (ZA3,
degenerate self-cancellation).

---

## 8. Addendum (2026-07-02, same day): a platform-limitations audit found and fixed a real, corroborating data bug

A methodical audit of the codebase (findings log §67) found that both US-equity loader paths
(`yfinance_loader.py`, `yahoo_client.py`) served split/dividend-unadjusted prices — quantified
on real data as a ~300-percentage-point total-return understatement for SPY over 2005-2026.
Fixed and re-validated against the affected champions: **M1's Sharpe improved 0.535→0.616 and
M2's improved 0.434→0.470, both with better drawdown too** — every metric moved the same,
positive direction, confirming this was a second conservative (never favorable) bias in the
platform's reported numbers, joining the already-documented zero-cash-yield gap. The table in
§2.2 above reflects the corrected values. CPA3 (the crypto+macro composite) moved by less than
a rounding error, since its 30%-crypto/70%-macro blend dilutes a macro-only correction into
noise. Also fixed in the same round: a structural data-sufficiency tripwire (defends against a
third silent loader-truncation bug, after two already found this session), a consolidated
DSR/PBO utility (validated by exact reproduction of §33.4's hand-computed 99.35%/99.66%
figures), an opt-in equity short-borrow fee, and an opt-in volume-scaled-slippage utility. See
`vibe_trading_research_findings.md` §67 for full detail.
