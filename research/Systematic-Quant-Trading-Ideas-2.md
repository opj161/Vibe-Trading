I found the most promising current ideas less in “new factor names” and more in **new market-structure seams**: crypto derivatives fragmentation, 0DTE/options proliferation, retail/leveraged ETF flow, cross-market information propagation, and AI-assisted alpha discovery. A useful credibility scale here:

**Tier A** = multiple credible sources, clear mechanism, feasible to test.
**Tier B** = credible and timely, but sample/data/execution caveats.
**Tier C** = novel and potentially valuable, but early, infrastructure-heavy, or likely crowded.

## Prioritized candidate ideas

### 1. Dynamic crypto funding-rate differential carry, especially CEX → DEX lead-lag

**Credibility:** Tier A-/B+
**Feasibility:** **Buildable with public/low-cost data; execution needs serious exchange/risk infrastructure.**

The naive trade is “long spot, short perp, collect funding.” That still matters, but recent evidence says the broad crypto carry premium has compressed sharply since 2024 and was negative in 2025 in one large study, despite a strong 2020–2025 full-sample Sharpe. ([arXiv][1])

The more interesting current version is **cross-venue funding dispersion**: funding markets are fragmented, especially between centralized exchanges and decentralized perp venues. A 2025 study using 1-minute data across 26 exchanges found CEX venues lead DEX venues in funding/price-discovery relationships, while many apparent arbitrages disappear after fees, reversals, and spread instability. ([mdpi.com][2])

**Mechanism:** funding premia reflect leverage demand, crowding, and venue segmentation. Instead of static carry, model when funding spreads are likely to persist long enough to pay fees and when they mean-revert too fast.

**Research angle:** long low-funding leg / short high-funding leg, or spot-perp hedged carry, but only when spread magnitude, duration, liquidity, open interest, and CEX-leading signals pass filters.

**Why it is current:** perp markets remain structurally dominant in crypto derivatives, DEX perps are growing, and regulated US crypto perps are emerging, potentially changing participant mix and funding dynamics. Reuters reported that Coinbase and Kalshi moved toward the first CFTC-regulated US crypto perpetual futures offerings in 2026. ([Reuters][3])

---

### 2. Short-horizon cross-sectional equity factors from retail-heavy markets, especially China A-share

**Credibility:** Tier A-/B+
**Feasibility:** **Buildable now with your A-share/US/HK equity platform and factor library.**

A 2026 paper revisits 191 short-term China A-share trading signals and uses double-selection LASSO to control for 151 fundamental factors, isolating 17 price-volume/microstructural signals with non-redundant premia. ([arXiv][4])

**Mechanism:** retail-heavy, constrained, or segmented markets can exhibit short-horizon behavioral and liquidity effects that are not fully captured by standard value, quality, momentum, or carry factors.

**Research angle:** do not test generic “momentum/value again.” Test **interaction models**: short-horizon price-volume signals conditional on turnover, retail intensity proxies, volatility regime, limit-up/limit-down proximity, liquidity, and recent news/attention.

**Why it is attractive for you:** you already have the platform and factor library. This is probably the fastest non-crypto research branch to launch.

---

### 3. Cross-session US ↔ China/HK lead-lag equity signals

**Credibility:** Tier B+
**Feasibility:** **Buildable now with daily/intraday OHLCV; better with sector/ADR/supply-chain mappings.**

Recent academic work uses non-overlapping US and China trading sessions to test whether US market information predicts Chinese stocks before the next China open, finding US information more informative for Chinese stocks than the reverse, though the authors caution that the result is pre-cost and not automatically deployable alpha. ([arXiv][5])

**Mechanism:** information diffuses across time zones, ADRs, sector ETFs, suppliers/customers, commodities, and macro proxies before local markets open.

**Research angle:** predict China/HK open-to-close or open-gap returns from US close-to-close moves in matched sectors, ADRs, China ETFs, commodities, rates, FX, semiconductors, luxury, internet, EVs, and geopolitical proxies.

**Feasibility:** public prices are enough for a first test. Specialized mapping data improves it, but you can start with sector/industry and manually curated ADR/ETF baskets.

---

### 4. 0DTE index option premium harvesting with dynamic sizing, not naive short-vol

**Credibility:** Tier B
**Feasibility:** **Prototype with standard options engine; robust historical testing likely needs paid options data.**

0DTE is no longer niche. Cboe reported that SPX 0DTE options averaged about 2.3 million contracts daily in 2025 and represented 59% of SPX options volume. ([cboe.com][6]) A recent paper on systematic S&P 500 put-writing finds that ultra-short-dated far-OTM options can deliver strong risk-adjusted results, with hybrid Kelly/VIX sizing improving the return/drawdown balance, especially in low-volatility regimes. ([arXiv][7])

**Mechanism:** harvest intraday crash insurance premia, but scale exposure down when volatility, skew, or gap risk rises.

**Research angle:** compare fixed-size short puts, short put spreads, VIX-scaled sizing, realized-vol-scaled sizing, skew-filtered sizing, and stop-loss/roll rules. Use capped-risk structures first.

**Important caveat:** this is not “free edge.” Tail risk, slippage, early-day gap risk, and execution assumptions dominate. A theoretical Black-Scholes engine is useful for controlled experiments, but live credibility requires real implied vol surfaces and quote/transaction-cost modeling.

---

### 5. Volatility-surface signals as a portfolio overlay

**Credibility:** Tier B+
**Feasibility:** **Needs options surface data; can prototype with VIX/VVIX/skew/term-structure proxies.**

Man Group argues that option-implied volatility surfaces contain richer forward risk information than a single VIX-like index, especially through term structure and skew; they present examples where surfaces reacted quickly to stress and then normalized. ([man.com][8])

**Mechanism:** option markets price crash, event, and normalization risk before realized returns fully show it.

**Research angle:** use implied-vol term structure, skew, and surface curvature to risk-scale existing trend/factor portfolios. For example: reduce equity beta when downside skew steepens and short-dated vol rises; increase exposure when vol term structure normalizes.

**Why it matters:** this may be more robust than trying to monetize options directly. It can improve your mixed-asset composite portfolios even if the overlay itself is not a standalone alpha.

---

### 6. Retail call-flow / leveraged ETF feedback around AI, semiconductors, and mega-cap tech

**Credibility:** Tier B
**Feasibility:** **Partly buildable; best version needs options-flow and ETF-flow data.**

Citadel Securities’ 1H 2026 market-structure report says retail dip-buying, record options premium, leveraged ETFs, and systematic strategies have amplified market moves; it also notes that about one-third of listed US options are now 0DTE and nearly half of retail options activity on its platform is 0DTE. ([Citadel Securities][9]) Reuters reported that leveraged single-stock ETFs grew rapidly, with nearly 90% of their trading by retail investors and all but 80 of 355 such ETFs launched since January 2025. ([Reuters][10])

**Mechanism:** retail call demand, dealer hedging, daily leveraged ETF rebalancing, and concentration in AI/semiconductor names can create predictable intraday or next-day flow pressure.

**Research angle:** focus on “spot-up / vol-up” regimes, semiconductor baskets, single-stock leveraged ETF underlyings, and dispersion trades: long/short relative vol or relative return among AI-linked names.

**Feasibility:** price/volume-only proxies are buildable. The strongest version likely needs options volume by strike/expiry, dealer gamma estimates, and ETF creation/redemption or flow data.

---

### 7. Long-dated rates volatility as convex hedge / relative-value overlay

**Credibility:** Tier B
**Feasibility:** **Needs rates futures/options or swaption data; theoretical engine can prototype.**

SocGen’s 2026 quant outlook highlights long-dated rates volatility as attractive after rates vol fell in 2025, arguing that long-end rates remain reactive to labor, fiscal, inflation, and Fed repricing shocks. ([advisoranalyst.com][11])

**Mechanism:** buy convexity where implied vol is no longer expensive relative to macro uncertainty; use it as a diversifier against equity/factor drawdowns.

**Research angle:** delta-hedged long-dated Treasury futures options, conditional long-vol only when term premium / inflation surprise / fiscal stress proxies rise, possibly funded by short nearer-dated vol.

**Feasibility:** not ideal with only a Black-Scholes equity-style engine, but you can approximate with futures options. More precise testing needs proper rates vol data.

---

### 8. Bitcoin ETF options vs crypto-native options volatility relative value

**Credibility:** Tier B-/C+
**Feasibility:** **Needs specialized options data and access to both US-listed options and crypto options venues.**

US spot Bitcoin ETF options are a genuinely new market-structure layer: Nasdaq’s IBIT options approval in 2024 opened listed options on a spot Bitcoin ETF, while Cboe has also been expanding Bitcoin ETF index option products. ([nasdaq.com][12])

**Mechanism:** US-listed ETF options and crypto-native options can price different client bases, margin regimes, tax constraints, trading hours, and crash-skew demand.

**Research angle:** compare ETF-option implied vol/skew/term structure against Deribit-style BTC options and BTC perp/futures basis. Look for persistent skew gaps or event-vol mispricings.

**Feasibility:** interesting but less accessible. Historical ETF option data and Deribit options surfaces are not usually “free-tier complete.”

---

### 9. On-chain BTC/ETH signals as state filters, not standalone magic alpha

**Credibility:** Tier B-/C+
**Feasibility:** **Prototype with public/free-tier on-chain metrics; serious version probably paid.**

A 2025 SSRN paper tests hourly BTC/ETH strategies using on-chain indicators from 2021–2025 and reports that filtered combinations of indicators produced smoother out-of-sample returns than single-strategy baselines, especially for ETH. ([SSRN][13])

**Mechanism:** on-chain activity, flows, exchange balances, transaction behavior, and holder cohorts proxy investor positioning and network usage.

**Research angle:** do not use on-chain indicators as raw buy/sell signals. Use them as **regime filters** for trend-following, funding carry, or volatility exposure: for example, trend signal only when exchange inflows/outflows and realized-cap metrics agree.

**Feasibility:** likely workable for a first pass with public APIs, but high-quality historical point-in-time on-chain data is often paid.

---

### 10. LLM-refined economic-linkage pairs / graph mean reversion

**Credibility:** Tier B-/C+
**Feasibility:** **Buildable, but NLP-heavy; CRSP-level data not required for a rough version.**

A 2026 paper uses LLMs to refine semantic relationships from 10-K embeddings, then applies relation-aware mean-reversion signals; the authors report improved Sharpe and lower drawdown versus baseline semantic-network approaches. ([arXiv][14])

**Mechanism:** companies linked by supply chains, substitutes, competitors, or shared exposures may temporarily diverge after idiosyncratic moves. LLMs help filter false relationships.

**Research angle:** build a graph from SEC filings, industry descriptions, product overlap, and news co-mentions; trade residual mean reversion among economically linked stocks, sector-neutral and beta-neutral.

**Feasibility:** SEC filings and prices are available, but robust entity mapping and text processing take work. This is more novel than another factor backtest, but less immediately tradable than crypto funding or A-share factors.

---

### 11. AI-agent alpha mining as research infrastructure, not as the alpha

**Credibility:** Tier C+
**Feasibility:** **Buildable internally.**

Alpha-GPT-style research systems use agents and genetic programming to generate candidate alphas, backtest them, summarize results, and iterate autonomously. ([arXiv][15])

**Mechanism:** not a market inefficiency by itself; it is a way to systematically search the hypothesis space.

**Research angle:** point an alpha-generation loop at underexplored domains: A-share microstructure factors, crypto funding/basis features, cross-session lead-lag, and options-surface overlays. Penalize turnover, crowding, fragility, and similarity to existing factors.

**Feasibility:** very buildable. The danger is overfitting at industrial scale.

---

## Market-structure shifts that look genuinely relevant

The biggest shift is **options becoming shorter-dated, more retail-driven, and more embedded in daily market flow**. Cboe’s 2025 data shows record options activity and dominant SPX 0DTE share, while Citadel’s 2026 report points to retail 0DTE, leveraged ETFs, and systematic strategies amplifying moves. ([cboe.com][6])

The second is **leveraged single-stock ETF proliferation**, especially around mega-cap technology and AI-linked names. This creates potential rebalancing-flow and volatility-feedback effects that did not exist at today’s scale a few years ago. ([Reuters][10])

The third is **crypto derivatives fragmentation plus regulation/onshoring**: CEX, DEX, ETF options, perps, and regulated US products are all interacting with different participant bases and margin regimes. ([mdpi.com][2])

The fourth is **China program-trading regulation**. China’s 2025–2026 rules add reporting and monitoring obligations for program trading, HFT thresholds, Stock Connect reporting, and exchange-level scrutiny. That may reduce some ultra-fast edges while leaving slower cross-sectional, open-to-close, and cross-session signals more feasible. ([Simmons & Simmons][16])

## Options/volatility verdict

There is credible current evidence for **systematic volatility-selling**, but only in carefully constrained forms: short-dated index put-writing, preferably capped-risk, dynamically sized, and regime-filtered. I would not prioritize naked short-vol as a clean edge.

There is also credible evidence for **volatility-surface-based overlays**: use skew and term structure for risk timing, crash-risk detection, and factor allocation. This may be more robust than trying to trade every option signal directly.

For **volatility-buying**, the most credible current angle I found is not generic equity long-vol, but **long-dated rates volatility** or selective convex hedges where macro uncertainty is underpriced relative to realized repricing risk. ([advisoranalyst.com][11])

## Single most interesting idea for next week

The one I would spend the next research week on is:

**Dynamic CEX → DEX crypto funding-rate differential carry, with spread-persistence and reversal filters.**

Not naive funding carry. The naive version may already be compressed. The opportunity is to test whether **venue fragmentation, CEX price discovery, DEX lag, funding-spread persistence, and crowded-position unwinds** create a tradable, market-neutral return stream.

Why this is the best next-week candidate:

It is a genuinely different mechanism from your validated crypto trend-following. It is current and structurally evolving. The data can be collected from public exchange APIs and open datasets. Recent research gives both encouragement and a warning: cross-venue funding spreads exist, but many disappear after costs unless you model persistence, reversal, and execution carefully. ([mdpi.com][2])

A one-week test should be tightly scoped: collect funding, mark price, index price, open interest, volume, and fees for the top liquid perps across Binance/OKX/Bybit plus Hyperliquid/Drift-style DEX venues; normalize funding to a common horizon; test whether CEX funding/spread changes predict DEX funding/spread changes; then compare static carry, high-spread threshold carry, and high-spread-plus-persistence-filter carry after fees and conservative slippage.

The pass/fail criterion should be simple: **does it produce a low-correlation, market-neutral return stream after realistic costs that survives 2024–2026 compression?** If yes, it is a strong complement to your existing crypto trend-following.

[1]: https://arxiv.org/html/2510.14435v4 "Cryptocurrency as an Investable Asset Class: Coming of Age"
[2]: https://www.mdpi.com/2227-7390/14/2/346 "The Two-Tiered Structure of Cryptocurrency Funding Rate Markets | MDPI"
[3]: https://www.reuters.com/legal/government/coinbase-kalshi-bring-regulated-perpetual-crypto-futures-us-investors-2026-05-29/?utm_source=chatgpt.com "Coinbase, Kalshi bring regulated perpetual crypto futures to US investors"
[4]: https://arxiv.org/abs/2601.06499 "[2601.06499] Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO"
[5]: https://arxiv.org/html/2603.10559v1 "A Bipartite Graph Approach to U.S.-China Cross-Market Return Forecasting"
[6]: https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025/ "The State of the Options Industry: 2025 | Cboe"
[7]: https://arxiv.org/abs/2508.16598 "[2508.16598] Sizing the Risk: Kelly, VIX, and Hybrid Approaches in Put-Writing on Index Options"
[8]: https://www.man.com/insights/the-shape-of-fear "The Shape of Fear: Managing Risk Through Options Markets | Man Group"
[9]: https://www.citadelsecurities.com/news-and-insights/global-market-intelligence/1h-2026-market-structure-flows/ "1H 2026 Market Structure & Flows - Citadel Securities"
[10]: https://www.reuters.com/business/us-retail-investors-fuel-surge-leveraged-etf-trading-study-shows-2026-02-24/ "US retail investors fuel surge in leveraged ETF trading, study shows | Reuters"
[11]: https://advisoranalyst.com/wp-content/uploads/2026/01/SocGen-Quant-Outlook-The-2026-playbook-for-the-systematic-investor.pdf "SocGen - Quant Outlook - The 2026 playbook for the systematic investor"
[12]: https://www.nasdaq.com/articles/tech-tuesday-sec-approves-first-kind-options-spot-bitcoin-etf-nasdaq-ibit?utm_source=chatgpt.com "TECH TUESDAY: SEC Approves First-of-Kind Options on ..."
[13]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5848549 "On-Chain Data and Strategy in Cryptocurrency Markets: Predictive Information Beyond Prices by Ye Luo, Zhenling Pang, Yifei Wang, Zigan Wang, Min Zhu :: SSRN"
[14]: https://arxiv.org/html/2604.19476v2 "Cross-Stock Predictability via LLM-Augmented Semantic Networks"
[15]: https://arxiv.org/html/2308.00016v2 "Alpha-GPT: Human-AI Interactive Alpha Mining for Quantitative Investment"
[16]: https://www.simmons-simmons.com/en/publications/cmpm3fwk100c0ut6kaf1azue5/csrc-s-new-regulations-on-programme-trading "China's new regulations on programme trading | Simmons & Simmons"
