# Vibe-Trading: Next-Direction Synthesis (Post Deep-Research Reports)

**STATUS: fully executed the same day it was written.** Every ranked item
below (§3.1-3.5) was implemented and tested; results are in
`vibe_trading_research_findings.md` §44-49 (§49 is the cross-workstream
synthesis — read that first). The options/volatility item (§3.6/§4's table)
was correctly left untouched, exactly per this document's own recommendation
— no real options-market data source was acquired. This file is kept as-is
below for the original reasoning/methodology; it is no longer a pending plan.

**Written:** 2026-07-01. Synthesizes the six external deep-research reports in
`research/` (two per prompt in `vibe_trading_deep_research_prompts.md`)
against this platform's actual, verified capabilities and the standing
brainstormed-but-unexecuted directions from `HANDOFF.md` /
`vibe_trading_research_findings.md` §40.3 / §43.7 (Alpha Zoo factor scan,
macro-trend signal recalibration, Z4 optimizer replumbing, perp-vs-spot
bar-boundary isolation).

**How to use this document:** it is a decision document, not a task list to
execute blindly. Section 1 is the methodology carried over from the existing
research log (read this first — it's the lens everything else is filtered
through). Section 2 is the single most consequential finding of this
synthesis pass: three of the external reports' most-touted candidate
strategies are **not empirically testable on this platform as built**, for a
specific, verified, structural reason — this reshapes the priority order
more than any individual report's own ranking did. Section 3 is the ranked
recommendation. Section 4 is explicit rejections with reasons. Section 5 is
the sequencing plan.

---

## 1. Methodology carried over from the existing research log

Every candidate below is filtered through discipline this codebase's own
research arc already validated the hard way (`vibe_trading_research_findings.md`
§18-40):

- **Credibility tiering**, mirrored from the reports themselves and from
  `vibe_trading_bar_boundary_deep_dive.md` §1: Tier A (multiple independent,
  recent, verifiable sources) > Tier B (single credible source or dated) >
  Tier C (speculative/single-source/infra-heavy). A report's own Tier
  labeling is treated as a starting point, not gospel — verified against
  this platform's actual data/engine capabilities in Section 2.
- **DSR / PBO discipline is non-negotiable for any factor-search or
  parameter-search work**, exactly as already applied to the crypto
  strategy (§19, §28.5, §38, §42.4). Every one of these reports
  independently re-derives the same warning; that convergence itself is a
  signal worth taking seriously, not just a repeated caveat to skim past.
- **Point-in-time data and net-of-cost returns are mandatory**, not optional
  — this is the same lesson as this repo's own commission-key bug
  (`CLAUDE.md`) and funding-fee bug (§27-28), now independently confirmed by
  the factor-research reports as *the* standard failure mode for naive
  factor-zoo usage.
- **Freeze parameters after a design phase; one single-shot OOS
  confirmation; no re-tuning against the OOS result** — the same discipline
  used throughout the crypto arc, applied here to every new thread below.
- **A report surfacing a mechanism is not the same as this platform being
  able to test it.** This is the organizing principle of Section 2 and the
  main reason this document's priority order differs from what a naive
  reading of the six reports alone would suggest.

---

## 2. Platform-capability reality check (verified directly against code, not assumed)

Before ranking anything, three claims from the reports were checked directly
against `agent/backtest/engines/*.py` and `agent/backtest/loaders/*.py`. All
three change what's actually worth pursuing next.

### 2.1 The options engine's "implied volatility" is historical realized volatility — not real market-implied vol

`agent/backtest/engines/options_portfolio.py:276`: `iv_map[code] =
historical_volatility(df["close"])`. Every option price this engine produces
is priced off trailing realized volatility of the underlying, full stop —
there is no options-chain, no real quoted implied vol, no real skew, no real
term structure anywhere in this codebase. An `iv_smile_adjustment` helper
exists but it is a *shape applied on top of* this synthetic base IV, not a
recovered real-market skew.

**Consequence, verified by re-reading the mechanism each report proposes:**

- **Active dispersion trading (IC-RC spread)** — `Systematic-Quant-Trading-Ideas-1.md`'s
  #2 candidate — is structurally untestable here. The entire trade exists
  *because* real index/single-stock implied correlation diverges from
  realized correlation. On this platform, "implied vol" for every
  constituent is *defined as* trailing realized vol, so "implied
  correlation" backed out from it would be realized correlation by
  construction. The IC-RC spread this strategy monetizes cannot exist in
  this engine's model of the world. Not a backtest that would show a
  negative result — a backtest that cannot represent the phenomenon at all.
- **Systematic volatility skew arbitrage** (selling structurally overpriced
  OTM puts against OTM calls) — same report's #4 candidate — has the
  identical problem. The strategy's entire edge is that real-world
  inelastic put demand creates a *persistent, empirically observable* skew
  richer than realized-vol-justified pricing. This platform has no
  mechanism to observe or price that richness; any skew tested here would
  have to be hand-assumed, at which point the "backtest" is testing
  arithmetic, not evidence of a live premium.
- **0DTE dealer-gamma / EOD forced-liquidation squeeze** (`Systematic-Quant-Trading-Ideas-1.md`'s
  own top pick) needs real options open interest by strike and minute-level
  flow data. This platform has neither an options chain nor open-interest
  data of any kind — only a synthesized single-underlying theoretical
  engine. Not reachable without an entirely new, paid data source.

**None of the options/volatility candidates from either Systematic-Quant-Trading-Ideas
report are executable as genuine research on this platform today.** They
require a real options-market data provider (CBOE DataShop, ORATS,
OptionMetrics, or similar) as a prerequisite — that's a deliberate,
standalone infrastructure/budget decision, not a research task to start
opportunistically. Parked in Section 4, not the ranked list.

### 2.2 Crypto funding rate is a fixed config scalar, not a fetched historical time series

`agent/backtest/engines/crypto.py:47`: `self.funding_rate: float =
config.get("funding_rate", 0.0001)` — a single constant applied uniformly
for the whole backtest window (this is exactly the mechanism `CLAUDE.md`'s
funding-fee bug writeup already describes). Grepping every loader
(`agent/backtest/loaders/*.py`) for `fetchFundingRate`/`funding` confirms:
**no loader fetches real historical per-timestamp funding-rate data from
any exchange.** The `ccxt` loader only calls OHLCV-equivalent methods.

**Consequence:** `Systematic-Quant-Trading-Ideas-1.md`'s #3 candidate
(CEX/DEX altcoin funding-rate arbitrage) and `Systematic-Quant-Trading-Ideas-2.md`'s
single most-recommended idea (dynamic CEX→DEX funding-rate differential
carry) are **not blocked by a fundamental platform limitation** the way the
options strategies are — `ccxt`'s unified `fetchFundingRateHistory` method
is available on most of the exchanges already confirmed reachable
credential-free in this repo (Binance, OKX, Bybit, Hyperliquid per
`CLAUDE.md`'s existing venue survey) — but it **is** blocked by a missing,
buildable, bounded piece of data-loader infrastructure that doesn't exist
yet. This is real, scoped engineering work (a new fetch utility, not a
platform redesign), not a research task you can start today by writing a
`signal_engine.py`. Scoped correctly in Section 3.4 below.

### 2.3 The Alpha Zoo factor library exactly matches what the factor-research reports assume

`agent/src/factors/zoo/{qlib158,gtja191,alpha101,academic}/` — four families,
matching both factor reports' framing precisely (GTJA191 for China A,
Qlib158 as a broad technical feature set, Alpha101 as short-horizon
price-volume, academic set for value/quality/profitability anchors).
`factor_analysis_tool.py::run_factor_analysis` computes IC/IR and
quantile-group equity curves out of the box — but **does not** bake in
DSR/PBO, net transaction costs, or point-in-time universe handling; those
layers must be added manually, exactly as they were for the crypto research
(§18-19, §38). This is the **best-aligned, most shovel-ready surface of any
candidate in any of the six reports** — the infrastructure gap here is
zero, unlike 2.1 and 2.2.

---

## 3. Ranked recommendation

### 3.1 Rank 1 — Macro trend-following signal recalibration (SPY/GLD/+bonds/+FX)

**Why first:** directly closes the specific open question this research
thread itself surfaced (§43.5's SPY+GLD failure), reuses architecture
already built and validated (vol-targeting, hand-rolled ERC allocation — the
exact code pattern in `v_Z4_chopfreq_train/code/signal_engine.py`
generalizes almost directly), needs **zero new data infrastructure**
(`GlobalEquityEngine`/`ForexEngine` + `yfinance` loader already cover
SPY/GLD/TLT/UUP-style tickers), and is the cheapest test to run of anything
in this document.

**What the two reports agree on, treated as Tier A anchors:**
- The crypto-tuned EMA(10,30) is roughly **6x too fast** for this asset
  class. SG Trend Indicator's own disclosed methodology uses a 20/120-day
  crossover; AQR's century-scale replication uses an equal 1/3/12-month
  (~21/63/252 trading day) TSMOM blend. Both are anchoring, disclosed,
  Tier-A-sourced numbers, not guesses.
- Volatility-scale every asset by its own realized vol *before* applying the
  trend signal, using one universal signal-speed parameterization across
  asset classes (not a per-asset-tuned lookback) — the same anti-overfitting
  argument this repo's own log already makes about not tuning Z4's exact
  thresholds further (§38, §40.3).
- Realistic priors to evaluate against, not to beat by miles: net Sharpe
  0.3–0.6, max drawdown 15–25%, win rate 35–45%. **Treat any 20-year backtest
  Sharpe above ~1.0-1.2 as a red flag demanding scrutiny before celebrating
  it** — both reports state this explicitly and independently.

**Where the two reports genuinely disagree — test both, don't pick one on
faith:**
- `Macro-Trend-Calibration-Strategy-2.md` recommends keeping a 4-way
  equal-weighted blend (1mo + 3mo + 12mo TSMOM + 20/120-day MA), i.e.
  medium-term is retained.
- `Macro-Trend-Calibration-Strategy-1.md` cites a late-2025/2026 Bayesian
  paper ("Revisiting the Structure of Trend Premia") arguing the medium-term
  (~125-day) leg is *mathematically redundant* once a fast (20-60d) and slow
  (250-500d) leg are both present, and that a pure barbell strictly
  dominates on Sharpe and drawdown once the redundant middle is removed.
- **This is directly, cheaply testable with this platform's existing tools**
  rather than deferred to secondary literature trust. Run both
  parameterizations side by side on the identical extended window and let
  the platform's own DSR-corrected comparison settle it, the same way this
  log settled its own internal design disagreements throughout §29-39.

**Concrete phased plan:**
1. Universe: start with SPY+GLD (already tested, gives a clean before/after),
   then extend to SPY+GLD+TLT+UUP (equities/gold/bonds/FX, one instrument
   each) once the signal-speed fix alone is confirmed to help.
2. Signal candidates to test head-to-head, same window (2005-01-01 to
   2025-06-30 train, sliced OOS as always): (a) original fast EMA(10,30) —
   control, already have this; (b) AQR-style 1/3/12-month equal blend +
   20/120-day MA; (c) barbell-only (e.g. 40-day breakout + 250-day breakout,
   equal risk-weighted, no medium leg).
3. Vol-target each asset's own signal (reuse the exact `vol_scalar_df`
   pattern from Z4's `signal_engine.py`), then combine via the same
   hand-rolled ERC weighting code already validated and battle-tested for
   Z4/Z8 — this is a near-direct port, not new design work.
4. Portfolio vol target 10% (research-comparable per both reports) as the
   default, not the crypto work's more aggressive settings.
5. Apply this log's own DSR correction across the 3 signal variants tested
   (§19/§42.4 methodology) before declaring a winner — a 3-point search is
   cheap to correct for and this discipline is exactly what separates this
   platform's research from the reports' own more casual treatment of the
   question.
6. If a genuinely positive, DSR-robust result emerges: compute **event-conditional**
   correlation (not full-sample) between this macro sleeve's returns and the
   existing crypto Z4 sleeve's returns during (a) SPY drawdown windows, (b)
   BTC drawdown windows, (c) joint risk-off windows — this is
   `Macro-Trend-Calibration-Strategy-2.md`'s own explicitly recommended test
   and the right way to evaluate whether combining the two sleeves is a real
   diversification benefit or just two uncorrelated coin flips.

**Expected outcome, stated honestly in advance per this log's own
discipline:** the credible prior from both reports is Sharpe 0.3-0.6, not a
crypto-strategy-beating result — success here means "a legitimately
positive, non-overfit macro sleeve that plausibly diversifies the crypto
book," not "a second Z4."

### 3.2 Rank 2 — China A-share cross-sectional factor research (Alpha Zoo, first real use)

**Why second:** highest-evidence-tier candidate of any equity idea in either
factor report, zero infrastructure gap (Section 2.3), and the single
largest genuinely untouched capability on this whole platform (456 factors,
never used in any research to date per `HANDOFF.md`).

**What both factor reports agree on, treated as the starting hypothesis
set, not the final answer:**
- China A is structurally the best-fit universe for this specific factor
  library — GTJA191 was built for it, and both reports independently rank
  **low-volatility + dividend/value + profitability-quality** as the
  strongest current China A combination (MSCI's own China A factor research:
  low-vol and high-dividend-yield persistently outperform; classic global
  momentum is comparatively weak/fragile there).
- A 2026 paper revisiting 191 short-term China A-share signals (double-selection
  LASSO against 151 fundamental factors, isolating 17 non-redundant
  price-volume signals) is close enough to this platform's own GTJA191
  family in name and construction to be worth a direct, literal test — this
  is the single most concrete, actionable pointer in either report.
- **China A factor behavior is regime-conditional on retail-participation
  bursts** (Acadian's 2026 research: value loses ~25% of its historical edge
  during retail-surge episodes, roughly twice a year on average) — this is
  `Systematic-Trading-Factor-Research-2.md`'s own flagged "most important
  thing you didn't ask about," and it reframes the right research question
  from "does factor X work in China A" to "does factor X work in China A,
  conditional on retail-surge/policy/liquidity regime."

**Concrete phased plan:**
1. Universe: CSI 300 + CSI 500 (or a Stock Connect large/mid proxy), point-in-time
   membership — **do not backtest on today's constituent list**, both
   reports flag this as the single most common survivorship-bias mistake.
2. Build a low-vol + dividend/value + profitability-quality composite
   z-score from the academic/Qlib158 families first (these map most cleanly
   to "quality/value/low-vol" as commonly defined) — monthly rebalance,
   1-3 month holding, sector-neutral if sector data is available via
   `get_sector_info`.
3. Separately, test the GTJA191 family's short-horizon price-volume signals
   as a **residual reversal / liquidity-pressure** sleeve — 5-20 day
   holding, and require this sleeve in particular to survive harsh net-cost
   modeling (bid-ask spread + market impact) before trusting any gross IC,
   per both reports' explicit warning that short-horizon reversal has a
   documented >90% premium collapse once implementation costs are honestly
   modeled.
4. Add a simple retail-crowding/regime proxy (e.g. rolling turnover z-score,
   already computable from existing OHLCV volume data — no new data source
   needed) and re-test factor #2/#3 conditional on that regime, directly
   answering the Acadian-flagged question rather than reporting an
   unconditional average.
5. Apply full DSR/PBO discipline across whatever factor variants get tested,
   exactly as done for the crypto arc — this is the platform's own existing
   competitive advantage over ad hoc factor research and should not be
   skipped just because the asset class changed.
6. Explicitly treat every raw Alpha101/GTJA191/Qlib158 factor as a
   **feature candidate**, not a standalone premium, until it clears
   point-in-time + net-cost + DSR bars — both reports independently insist
   on this framing.

### 3.3 Rank 3 — US large-cap Quality+Value+Momentum (QVM) composite

**Why third, not first among the equity work:** slightly lower evidence
tier than the China A angle for *this specific factor library* (both
reports note Alpha101/Qlib158 raw ICs are close to zero out-of-sample in
the hyper-efficient US large-cap space — the value here is in the
**composite**, not raw factor mining), but still Tier A on the combination
itself (S&P's own QVM index research: +9% relative to S&P 500 in
Q1/YTD 2026; J.P. Morgan's 2Q 2026 factor outlook explicitly recommends
this combination).

**Concrete plan:** S&P 500 or Russell 1000 proxy, monthly rebalance,
sector-neutral z-score composite of value (book/earnings/cash-flow yield),
profitability-quality, and **risk-adjusted, skip-month (12-1) momentum**
— both reports are emphatic that naked top-decile price momentum is
currently live but historically crowded (widest internal momentum
dispersion since 1990 per J.P. Morgan) and must be volatility-scaled and
skip-month-adjusted to avoid a momentum-crash left tail, not run raw.

### 3.4 Rank 4 — Crypto CEX→DEX funding-rate differential carry (infra task first, then research)

**Why fourth, not higher:** genuinely the most interesting *mechanism*
surfaced in either quant-ideas report — it is a real diversifier from the
validated trend-following strategy (different return driver entirely), and
this platform already has credential-free reach to exactly the venues
needed (Binance/OKX/Bybit as CEX, Hyperliquid as DEX-perp, per `CLAUDE.md`'s
existing venue survey). It ranks below the two equity threads only because
of the verified Section 2.2 gap: **there is no historical funding-rate data
loader yet.**

**Concrete plan, explicitly two phases:**
1. **Infra phase (bounded, scoped)**: write a standalone fetch utility using
   `ccxt`'s unified `fetchFundingRateHistory` for a handful of liquid pairs
   across 2-3 CEXs plus Hyperliquid. This does not need to become a full
   `LOADER_REGISTRY` citizen yet — a research-script-level fetch is enough
   to run the one-week test both reports converge on recommending.
2. **Research phase**, using `Systematic-Quant-Trading-Ideas-2.md`'s own
   explicit pass/fail framing (this is unusually concrete for one of these
   reports and should be followed close to verbatim): collect funding, mark
   price, index price, open interest, and fees for the top liquid perps;
   test whether CEX funding/spread changes predict DEX funding/spread
   changes; compare static carry vs. high-spread-threshold carry vs.
   high-spread-plus-persistence-filter carry, net of realistic costs.
   **Pass/fail criterion, stated by the report and worth keeping
   verbatim:** does it produce a low-correlation, market-neutral return
   stream after realistic costs that survives the 2024-2026 compression the
   Tier A/B evidence itself documents? If the naive full-time version has
   plausibly gone negative in 2025 (per `Systematic-Quant-Trading-Ideas-2.md`'s
   own citation), do not be surprised if the answer is "no" — this is a
   genuine open question, not a rubber-stamp exercise.

### 3.5 Rank 5 (opportunistic, low-cost) — Cross-session US→China/HK lead-lag

**Why include it at all:** buildable *today* with existing daily OHLCV
across markets the platform already loads (no new infra), and it's a
genuinely different mechanism (information diffusion across trading
sessions) from anything in the crypto or macro-trend work. Tier B evidence
(the underlying academic paper itself cautions the effect is pre-cost, not
automatically deployable alpha) — this belongs in a spare-cycle slot
alongside Rank 2/3's equity work, not as a dedicated research push.

**Concrete plan:** predict China A/HK open-to-close or open-gap returns
from the prior US session's close-to-close moves in matched sector ETFs,
ADRs, China-exposed ETFs, and relevant commodities/FX — start with a simple
regression/IC test before building anything resembling a strategy, and
report net of realistic costs immediately given the paper's own caveat.

---

## 4. Explicitly deprioritized or rejected, with reasons

| Candidate | Report | Why not now |
|---|---|---|
| Active dispersion trading (IC-RC spread) | Quant-Ideas-1 | Structurally untestable — this platform's "implied vol" is defined as historical realized vol (§2.1); no IC-RC divergence can exist in this engine's model of the world. |
| Systematic volatility skew arbitrage | Quant-Ideas-1 | Same root cause as above — no real skew data exists on this platform to test whether a skew premium is genuinely mispriced. |
| 0DTE dealer-gamma / EOD forced-liquidation squeeze | Quant-Ideas-1 (report's own top pick) | Needs real options open-interest-by-strike and minute-level flow data; this platform has no options-chain data source at all, only a synthetic single-underlying theoretical engine. |
| Retail algorithmic clock-based liquidity provision | Quant-Ideas-1 | Same data gap — needs real minute-level options/quote data this platform doesn't have. |
| LLM "Hidden Beta" / LLM allocation-flow fading | Quant-Ideas-1 | Needs live multi-LLM response-surface simulation infrastructure; report's own credibility tier is "Medium," single-preprint sourced. |
| Systematic merger arbitrage | Quant-Ideas-1 | Needs a deal-terms/completion-probability database this platform has no loader for. |
| Chinese futures diversification (jujube, PTA, etc.) | Quant-Ideas-1 | Plausible mechanism, but unverified whether the platform's futures loaders (tushare/akshare) actually cover these specific exotic contracts — verify data availability before any commitment; not assumed feasible. |
| Bitcoin ETF options vs. crypto-native options relative value | Quant-Ideas-2 | Needs both US-listed options data and Deribit-style crypto options surfaces — same category of missing data as §2.1, doubled. |
| On-chain BTC/ETH signals as regime filters | Quant-Ideas-2 | Report's own tier is B-/C+; high-quality historical point-in-time on-chain data is usually paid. Revisit only after higher-tier candidates are exhausted. |
| LLM-refined economic-linkage graph mean reversion | Quant-Ideas-2 | Buildable in principle (SEC filings + prices are available) but NLP-heavy with no existing infra; report's own tier is B-/C+. Lower priority than the equity factor work, which has zero infra gap. |
| AI-agent alpha-mining-as-infrastructure | Quant-Ideas-2 | Not a strategy, a meta-tool. Worth revisiting once the factor-research thread (Rank 2/3) produces a stable enough pipeline to be worth automating — premature before that. |
| AI-sentiment-fused long/short (MDPI paper) | Factor-Research-1 | Needs a quantified, historical, cross-sectional sentiment score feed; this platform has `get_stock_news` (article-level text) but no quantified sentiment factor pipeline. Possible future extension, not a near-term item. |

---

## 5. Recommended sequencing

1. **Macro trend-following recalibration (§3.1)** — start here. Cheapest to
   run, zero new infra, most directly answers an already-open question from
   this exact research thread.
2. **China A-share factor research (§3.2)** in parallel or immediately
   after — different codebase area (equities, not crypto), no resource
   conflict with #1, highest evidence tier of any equity candidate, and the
   single biggest genuinely unexplored capability on the platform.
3. **US large-cap QVM composite (§3.3)** as a natural follow-on to #2,
   reusing the same `factor_analysis_tool` + DSR/PBO harness.
4. **Crypto CEX→DEX funding-rate carry (§3.4)** — start the bounded infra
   phase (funding-rate history fetch) once #1-#3 are underway; this is a
   distinct, genuinely new mechanism worth the scoped engineering cost, but
   shouldn't block the zero-infra-gap equity/macro work above it.
5. **Cross-session lead-lag (§3.5)** — slot in opportunistically alongside
   #2/#3; cheap, no dedicated push needed.
6. **Options/volatility strategies** — do not start without first deciding,
   as a deliberate scope/budget call, whether to acquire a real
   options-market data source (CBOE DataShop, ORATS, OptionMetrics, or
   similar). Nothing in §4's options-related rejections is a "no forever" —
   it's "no until that specific prerequisite decision is made."
7. **Housekeeping (optional, low priority, do opportunistically):**
   re-plumb Z4 from its hand-rolled ERC replica into the platform's real
   `risk_parity` optimizer (implementation-quality task, not a research
   question — only matters before any live/production consideration); a
   rigorous perpetual-vs-spot bar-boundary isolation (needs a new Hyperliquid
   spot loader path — only worth it if the perpetuals research thread
   specifically resumes).
