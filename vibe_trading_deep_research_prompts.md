# Deep Research Prompts: Next-Direction Investigation for Vibe-Trading

**Purpose:** three standalone, copy-paste-ready prompts for external deep-research
agents (Perplexity Deep Research, OpenAI/ChatGPT Deep Research, Gemini Deep
Research, etc.), each scoped to one of the open directions surfaced by
`vibe_trading_research_findings.md` §40-43, plus one deliberately open-ended
scan for edges nobody has hypothesized yet. Run them independently — each is
self-contained and does not depend on the others' output.

**How to use:** paste one "PROMPT" block (everything between the `---PROMPT
START---` / `---PROMPT END---` markers) into a research agent as-is. Do not
paste the surrounding explanatory text. Save each resulting report back into
this repo (e.g. `research_reports/<topic>.md`) for the next Vibe-Trading
session to read alongside this file.

**Common instruction embedded in all three prompts, stated once here for
context:** every prompt asks the agent to (a) prioritize the most recent
12-18 months of available sources over older ones and explicitly flag when
the best available evidence is stale, (b) tier every citation by
verifiability (independently-checkable/well-established vs. single-source/
illustrative-only — mirroring the credibility framework already used in this
project's `vibe_trading_bar_boundary_deep_dive.md`), and (c) end with an
explicit open-ended question inviting the agent to surface anything
important that the specific sub-questions didn't ask about.

---

## Prompt 1 of 3: Cross-sectional equity factor investing — is there a live, exploitable edge right now?

---PROMPT START---

I am extending a systematic trading research platform (Python-based
backtester) that has an existing library of ~456 pre-built cross-sectional
equity factors (three families: GTJA191 — China A-share-oriented, Qlib158,
and Alpha101 from WorldQuant, plus a small academic set) spanning momentum,
reversal, volatility, volume/microstructure, and a few quality/value/
liquidity/sentiment factors. This factor library has never been used in any
research so far — all prior work was a single crypto trend-following
strategy. I want to know which of these factor families (or combinations)
currently have credible, *live* premia worth actually backtesting, on which
universe, and how to avoid the standard traps.

Research and report on:

1. **Current live-vs-decayed status of major factor categories** (momentum,
   value, quality, low-volatility, size, profitability/quality composites,
   short-term reversal, volume/liquidity factors) as of the most recent
   available evidence. Distinguish factors with credible *recent* (last
   12-18 months) evidence of continued premia from ones widely reported as
   crowded, arbitraged away, or structurally weakened. Cite specific
   studies, practitioner white papers, or credible fintech research —
   prefer 2024-2026 publications; flag anything older presented as current.
2. **Regional differences**: is there credible recent evidence that factor
   performance differs meaningfully between China A-shares, US large-caps,
   and Hong Kong equities specifically? (These are exactly the three
   universes the existing factor library targets.)
3. **Momentum crowding / momentum-crash risk** in the current market
   regime specifically — is now a good or bad time to be running momentum
   strategies, and why, per the most recent credible sources you can find?
4. **Factor combinations** with stronger recent evidence than single
   factors alone (e.g., quality+momentum, low-vol+value) — which
   combinations, and what's the current evidentiary basis?
5. **Implementation pitfalls specific to right now**: current best
   practice (2024-2026) for avoiding look-ahead bias, survivorship bias in
   universe construction, reporting net-of-realistic-transaction-cost
   premia (not just gross IC), turnover/capacity limits, and correcting for
   multiple-factor-search overfitting (Deflated Sharpe Ratio / Probability
   of Backtest Overfitting style methods — this platform already applies
   this rigor and any recommendation should be compatible with it).
6. **AI-era market structure**: is there credible evidence that classic
   factor premia behave differently in the post-2023 environment of
   widespread AI-driven/LLM-assisted trading and retail options flow, versus
   pre-2023 baselines? Any documented *new* anomalies specific to this
   period worth investigating?

**Deliverable**: a ranked list of factor families/combinations by current
evidence strength (with credibility tier per citation), a recommended
starting universe + rebalance horizon + holding period for each top
candidate, and explicit caveats on what would still need independent
in-platform validation before trusting any number.

**Before finishing**, answer one more question in your own judgment: what is
the single most interesting or important thing you found in this research
that the questions above didn't directly ask about?

---PROMPT END---

---

## Prompt 2 of 3: Recalibrating trend-following for macro assets (equities, gold, bonds, FX)

---PROMPT START---

I have a validated systematic trend-following strategy for crypto (BTC +
SOL, daily bars, EMA(10,30) crossover direction + volatility-targeted
position sizing + risk-parity capital allocation + a portfolio-level
exposure dampener during choppy/high-noise periods). I directly tested this
exact recipe, completely unmodified except for rescaling the volatility
target to the new asset class's own typical daily volatility, on SPY (US
equities) + GLD (gold) over a 20-year window (2005-2025) that includes the
2008 financial crisis, the 2020 COVID crash, and the 2022 rate-hike bear
market. **It lost money outright** (-13.3% total return vs. SPY
buy-and-hold's +413.6% over the same period), while the identical mechanics
worked well on crypto. I need to understand how to correctly recalibrate
trend-following signal *speed* (not just position sizing) for macro asset
classes, since a fast crypto-tuned signal is evidently the wrong tool for
slower-moving macro trends.

Research and report on:

1. **What signal speeds/constructions real, currently-operating trend-
   following / managed-futures funds actually use** for equity index, gold,
   government bond, and FX trend signals. Cite specific, credible, recent
   sources: fund methodology disclosures, index documentation (e.g. SG
   Trend Index, BTOP50-style benchmarks), or recent academic replications
   of live CTA behavior. I need concrete, implementable numbers (typical
   moving-average pairs, breakout lookback windows, or multi-timeframe
   blend weights), not vague guidance.
2. **Current regime for trend-following (roughly 2022 through the present)**
   — has it been a favorable or unfavorable multi-year stretch for
   trend-following broadly, and specifically for each of equities/gold/
   bonds/FX, per the most recent credible research and industry
   performance reporting you can find?
3. **Multi-speed ensemble evidence**: credible recent research on
   combining multiple lookback speeds (fast+medium+slow) specifically for
   macro trend-following, distinct from single-speed systems — does this
   generalize the way it's expected to, per recent studies?
4. **Cross-asset diversification**: current, credible evidence on
   correlation between crypto trend-following returns and macro (equity/
   gold/bond/FX) trend-following returns — especially during risk-off/
   drawdown events specifically (a genuine diversification benefit only
   exists if these decouple exactly when it matters).
5. **Realistic performance benchmarks**: what Sharpe ratio, max drawdown,
   and win-rate range should be considered "credible" (not overfit) for a
   properly-built macro trend system, per recent, reputable sources — I
   want an honest prior before backtesting anything.
6. **Current macro backdrop**: as of when you conduct this research, what
   is the prevailing rate environment, equity valuation regime, and gold
   market context, and does any of it argue for or against expecting
   trend-following to work well in a specific macro asset class right now?
7. Beyond simple slower moving-average pairs — any credible, currently-
   discussed alternative signal designs for macro trend (volatility-scaled
   breakouts, carry-augmented trend, regime/risk-on-risk-off filters) worth
   considering?

**Deliverable**: a credibility-tiered recommended starting parameterization
(specific lookback pairs or breakout windows) per asset class, realistic
Sharpe/drawdown expectations to calibrate against, and explicit sourcing
for every specific number (real fund practice vs. replicated academic study
vs. single-source speculation).

**Before finishing**, answer one more question in your own judgment: what is
the single most interesting or important thing you found in this research
that the questions above didn't directly ask about?

---PROMPT END---

---

## Prompt 3 of 3: Open scan for currently-live, under-explored systematic trading edges

---PROMPT START---

I am looking for genuinely new, currently-relevant (not historical-only)
systematic/quantitative trading ideas — deliberately not constrained to any
one asset class or strategy family, because the goal of this research is
to surface things I have not thought to ask about directly. Context on what
I already have access to, so you can calibrate feasibility: a backtesting
platform supporting China A-share, US, and Hong Kong equities; crypto (spot
and perpetual futures, across 100+ exchanges); futures, forex, and a
theoretical (Black-Scholes-based) options engine; a large pre-built
cross-sectional equity factor library; and mixed-asset composite
portfolios. Data access is broad but mostly free/public-tier providers.
Already deeply explored: crypto trend-following (validated, working) and a
first attempt at macro trend-following (found not to transfer naively from
crypto, needs its own signal-speed calibration). Not yet explored at all:
cross-sectional equity factors, options-based strategies, and anything
crypto-specific beyond simple spot trend-following (e.g. funding-rate carry,
cross-exchange basis, on-chain signals).

Research and report on:

1. **What are institutional quant desks, credible fintech research
   publications, and reputable independent quant researchers currently
   (most recent 12-18 months) discussing as live, underexploited systematic
   opportunities** — across any asset class?
2. **Recent market-structure shifts** (new regulation, new venues/products,
   documented changes in AI-driven trading flow, ETF/derivatives
   proliferation, etc.) that may have created genuinely new, currently-
   exploitable inefficiencies not present a few years ago.
3. **Options/volatility strategies**: is there current, credible evidence
   for simple, systematic volatility-selling, volatility-buying, or
   options-overlay strategies with a real edge in the current volatility
   regime — something implementable with a standard options-pricing engine
   (not requiring exotic real-market microstructure data)?
4. **Crypto angles beyond spot trend-following**: current, credible
   evidence on funding-rate carry strategies, cross-exchange basis/
   arbitrage, or on-chain-data-driven signals — anything representing a
   genuinely different mechanism from directional trend-following, not just
   a parameter variation of it.
5. **Genuinely novel recent research**: any 2024-2026 academic papers or
   credible preprints proposing systematic strategies that are not minor
   variations of momentum/value/carry/trend — flag anything that looks
   like a real departure from the well-known canon.
6. For each candidate surfaced above, note whether it looks implementable
   with commonly-available free/low-cost data sources, or would require
   specialized/paid data infrastructure not typically available by default.

**Deliverable**: a prioritized list of candidate ideas, each with a
credibility tier, a short plain-language mechanism explanation, and an
explicit feasibility flag (buildable with standard data access today vs.
needs specialized infrastructure).

**Before finishing**, answer this directly and specifically: of everything
you found, what is the single most interesting, currently-relevant
systematic trading idea — the one you'd bet is most worth a busy
researcher's next week of attention?

---PROMPT END---
