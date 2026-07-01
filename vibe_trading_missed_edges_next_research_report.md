# Vibe-Trading Second-Pass Research Audit: Missed Edges and Next Research Roadmap

**Generated:** 2026-07-02  
**Input reviewed:** extracted `Vibe-Trading.zip`, root Markdown research notes including `vibe_trading_technical_overview.md`, `vibe_trading_research_findings.md`, `vibe_trading_next_directions.md`, `vibe_trading_bar_boundary_deep_dive.md`, root project notes, `agent/runs/*` code/config/results, loader/engine/factor infrastructure, and current external market sources relevant to late June / early July 2026.  
**Purpose:** identify what the first research program likely missed, what plausible edge was not actually pursued, and what should be researched next to improve the current champion or find a new one.

---

## 1. Executive conclusion

The first research program was broad, but it was still concentrated around one dominant theme: **daily bar BTC/SOL trend following with increasingly careful sizing overlays**. That program successfully found a real, robust family — Z4/Z8 — but the codebase can support several additional research directions that were either lightly tested, tested with incomplete data, or not converted into the correct platform-native experiment.

The most important missed item is not a new market signal. It is a **backtest-mechanics issue that can affect the current champion ranking**:

- `v_Z8_voltarget_train/code/signal_engine.py` explicitly lets its portfolio-volatility overlay scale exposure up to **1.5x**.
- The shared base-engine alignment layer clips each raw signal to `[-1.0, 1.0]` and then normalizes gross exposure to at most **1.0** before execution.
- Therefore, the upside half of Z8's portfolio-vol overlay is likely muted or erased in the regular engine unless leverage/gross-cap handling is changed deliberately. Z8's *de-risking* can still matter, but its intended modest upscaling is not faithfully expressed.

The second-most important missed item is related: the technical overview explicitly documents that default sizing is **entry-locked**. Same-direction changes in target weight do not resize the position unless `rebalance_threshold` is set. This means many continuous overlays — vol scalars, regime dampeners, chop scores, risk-parity magnitude updates — only affect the entry-day size, not daily live exposure. The repo did test resize variants and found them harmful for Z4-like crypto trend, but that finding should be treated as **strategy-specific**, not a universal rule.

The most attractive *new* edge themes for July 2026 are:

1. **Crypto liquidity-regime filtering** for Z4/Z8: BTC ETF flows, stablecoin supply/flows, dollar/rate proxies, and gold/risk-off trend. Current market context is unusually suitable: Bitcoin has suffered a large 2026 drawdown, BTC ETF flows have turned negative, stablecoin market cap has recently contracted, the Fed is still restrictive, and investor attention has rotated toward AI.
2. **True perpetual funding / basis / venue-spread research**: prior funding work was mostly scalar or confirmatory, not a real cross-venue funding time-series strategy. Current infrastructure sources make this much more actionable than the original research implied: OKX publishes historical perpetual funding from March 2022, CCXT has `fetchFundingRateHistory`, and Hyperliquid has become a large enough venue to justify CEX-DEX basis and funding-spread research.
3. **Macro trend sleeve recalibration**: the repo's own `vibe_trading_next_directions.md` already flagged this. The current market setup — restrictive Fed, strong gold/dollar/rate pressure, crypto behaving like a risk asset — makes a slow SPY/GLD/TLT/UUP macro sleeve more relevant, not less.
4. **China A factor-zoo research**: the codebase has a large Alpha Zoo and China loader/fundamental hooks, but the run archive barely used this capability. June 2026 China data show AI-export strength plus weak domestic demand, which points toward quality/dividend/low-vol + AI/export regime splits rather than generic momentum.
5. **US AI/semiconductor rotation research**: the archive contains extremely high short-window semiconductor annualizations, but they are not strategy-grade. Given current AI capital rotation, these should be converted into robust sector/factor experiments, not accepted as champion evidence.

My highest-confidence recommendation is: **do not start by adding more EMA parameters to Z4/Z8.** The prior research already exhausted that path. Start with a controlled engine-mechanics audit and then add exogenous liquidity/funding/macro state variables that have a credible reason to matter in July 2026.

---

## 2. Methodology of this second-pass audit

I approached the repository as a research platform with constraints, not as a generic trading idea list. The audit asked four questions:

1. **What can Vibe-Trading actually test well?**  
   The technical overview says its strongest setup is bar-level, signal-driven, target-weight backtesting. It is not a tick/order-book simulator, not an institutional data warehouse, and not a causal proof engine.

2. **What did the existing research actually test?**  
   I parsed the run archive, strategy configs, and run code. The archive is overwhelmingly daily crypto BTC/SOL/ETH trend research with selected macro, semiconductor, factor, funding, on-chain, and bar-boundary branches.

3. **Where do code mechanics make prior conclusions fragile?**  
   The largest issue is the gap between signal magnitude produced by `SignalEngine.generate()` and actual exposure after `_align()` clipping, gross normalization, execution lag, and entry-locked sizing.

4. **Which missed edges match the current market?**  
   I checked current/recent market sources as of 2026-07-02 and mapped them to Vibe-Trading-native experiments.

This report is a **research audit and next-experiment design**, not a new performance claim. Any idea below still needs frozen OOS / walk-forward / bootstrap / bar-boundary / cost / multiple-testing validation before it can be considered a new champion.

---

## 3. What the codebase can test well

### 3.1 Strongly supported

The platform is very good for:

- Bar-level target-weight strategies.
- Daily and intraday OHLCV strategies where fills at next bar open/close are acceptable approximations.
- Cross-asset allocation among crypto, US equities/ETFs, China A shares, HK, futures, funds, macro, and forex where loaders are available.
- Signal engines that return per-symbol weights.
- Strategy families based on trend, momentum, mean reversion, rotation, volatility targeting, risk parity, and factor panels.
- Standard backtest validation: equity curves, metrics, trades, benchmark comparisons, walk-forward, bootstrap/random controls where configured.
- Alpha Zoo/factor research: IC/IR and quantile/equity-layer analysis.

### 3.2 Supported but underused

The codebase has hooks or skills for:

- Event feeds / RSSHub-style event ingestion.
- Fundamental fields, mostly in China/Tushare-style contexts.
- Local data bridge ingestion, which can import external datasets not covered by public loaders.
- Perp funding/basis frameworks, though not fully loader-integrated.
- Stablecoin-flow and on-chain concepts, though not plugged into the main loaders.
- ETF flow, DeFi yield, liquidation heatmap, token unlock, market-microstructure, seasonal, and ML strategy skills.

The run archive does not exploit most of these capabilities. The research mostly stayed in OHLCV land.

### 3.3 Weakly supported / risky

The platform is not the right tool for:

- Tick-accurate scalping.
- Intrabar stop/limit realism.
- Full order book queue modeling.
- Options-chain strategies without an external historical options dataset.
- DeFi execution without custom data and slippage assumptions.
- High-frequency liquidation/order-book strategies unless external L2 data is explicitly imported.

This matters because some of the best-looking unexplored ideas — crypto options vol carry, 0DTE/dispersion/skew, liquidation cascades — are likely real, but not immediately testable in a faithful way using the existing default data layer.

---

## 4. Codebase scan findings that change interpretation

### 4.1 Run archive concentration

Corrected scan of `agent/runs/*/config*.json`:

| Item | Count / observation |
| --- | ---: |
| Config files parsed | 179 |
| `engine` present | 173 |
| `source` present | 179 |
| `interval` present | 179 |
| `optimizer` present | 168 |
| `validation` present | 178 |
| `funding_rate` present | 159 |
| `rebalance_threshold` present | 5 |
| `leverage` present | 2 |
| `fundamental_fields` present | 3 |
| `extra_fields` present | 3 |
| `event_feeds` present | 0 |
| Config engines | 173 `daily`, 6 missing/none |
| Sources | 158 `auto`, 14 `ccxt`, 7 `okx` |
| Intervals | 172 `1D`, 3 `1H`, 3 `4H`, 1 `15m` |
| Most common symbols | BTC-USDT 156, SOL-USDT 147, ETH-USDT 23, SPY/GLD 13 each |

The evidence is clear: this was primarily a **daily BTC/SOL trend-following research campaign**, not a comprehensive exploration of the whole Vibe-Trading platform.

### 4.2 Signal-code term scan in run implementations

Across run strategy Python files:

| Term / capability | Strategy files containing it | Interpretation |
| --- | ---: | --- |
| `funding` | 4 | Funding was touched, but not broadly or as real venue/time-series carry. |
| `fetchFundingRateHistory` | 2 | Present in a confirmatory branch, not a full loader/data pipeline. |
| `onchain` | 2 | BTC unique-address branch only; not broad on-chain flow research. |
| `stablecoin` | 0 | Stablecoin liquidity was not pursued in run code. |
| `liquidation` | 0 | Liquidation/OI cascade edge not pursued. |
| `open_interest` | 0 | OI/crowding not pursued. |
| `hyperliquid` | 0 | Hyperliquid/CEX-DEX venue edge not pursued. |
| `event` | 1 | Event-driven infrastructure was practically unused. |
| `fundamental` | 1 | Fundamental/factor work was minimal in executed strategy code. |
| `macro` | 14 | Macro was explored, but not as a current-state liquidity/rates regime layer. |
| `factor` | 6 | Factor tooling exists but was lightly used. |
| `qlib` | 0 | Qlib factors were not pursued in run code. |
| `alpha101` | 2 | Alpha101 use was minimal. |
| `seasonal` | 0 | Calendar/seasonality not pursued directly. |

This reveals the main missed area: **exogenous state variables**. The successful Z family is a price-only trend system with clever endogenous sizing. Many plausible alpha/risk edges use information outside OHLCV: ETF flows, stablecoin liquidity, funding/basis, open interest, unlocks, event/regulatory calendars, China fundamentals, and sector/factor exposures.

### 4.3 Loader and infrastructure capacity

The loader registry accepts many sources, including `tushare`, `okx`, `yfinance`, `akshare`, `baostock`, `tencent`, `mootdx`, `ccxt`, `futu`, `eastmoney`, `sina`, `stooq`, `yahoo`, `finnhub`, `alphavantage`, `tiingo`, `fmp`, `local`, and `auto`. Fallback chains cover:

- China A: Tencent/Mootdx/Eastmoney/Baostock/Akshare/Tushare/local.
- US equities: Yahoo/Stooq/Sina/Eastmoney/Yfinance/Tiingo/FMP/Finnhub/Alphavantage/Akshare/local.
- HK equities: Eastmoney/Yahoo/Futu/Yfinance/Akshare/local.
- Crypto: OKX/CCXT/Yfinance/local.
- Futures/funds/macro/forex via Akshare/Tushare/Yfinance/local where supported.

The most important practical point is `local`: the repo can ingest custom data bridges. This is the bridge for ETF flows, stablecoin supply, funding-rate panels, Hyperliquid funding, unlock calendars, and custom factor panels.

### 4.4 Alpha Zoo capacity

The repository contains **461 factor-zoo Python files** under `agent/src/factors/zoo`, including academic, Alpha101, GTJA191, and Qlib-style factors. The built-in factor analysis tool computes IC mean/std/IR, positive IC ratio, quantile group equity, and long-short spread. That is enough to triage factors, but not enough to promote them. A production-grade factor program should add:

- Point-in-time field enforcement.
- Forward-return construction with strict lag.
- Industry/sector neutralization where relevant.
- Turnover and cost modeling.
- Data-availability survivorship checks.
- Multiple-testing controls.
- Walk-forward factor selection.
- PBO/Deflated Sharpe style robustness tests.

This is a major underused platform branch.

---

## 5. Current champion state, with second-pass caveats

### 5.1 Champion metrics from the prior archive

| run_name                |   annual_return |   total_return |   max_drawdown |   sharpe |   trade_count | start_date   | end_date   | codes                       | source   | interval   |
|:------------------------|----------------:|---------------:|---------------:|---------:|--------------:|:-------------|:-----------|:----------------------------|:---------|:-----------|
| v_Z4_chopfreq_OOS_TEST  |           0.305 |          0.364 |         -0.192 |    0.999 |            55 | 2025-05-01   | 2026-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |
| v_Z4_chopfreq_train     |           0.847 |          3.634 |         -0.33  |    1.641 |           107 | 2023-01-01   | 2025-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |
| v_Z4_leverage15_train   |           1.059 |          5.074 |         -0.452 |    1.454 |           112 | 2023-01-01   | 2025-06-30 | BTC-USDC:USDC,SOL-USDC:USDC | ccxt     | 1D         |
| v_Z4_resize_OOS_TEST    |          -0.091 |         -0.105 |         -0.246 |   -0.326 |            55 | 2025-05-01   | 2026-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |
| v_Z4_resize_train       |           0.127 |          0.348 |         -0.357 |    0.551 |           107 | 2023-01-01   | 2025-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |
| v_Z8_voltarget_OOS_TEST |           0.48  |          0.578 |         -0.237 |    1.179 |            55 | 2025-05-01   | 2026-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |
| v_Z8_voltarget_train    |           0.966 |          4.412 |         -0.372 |    1.621 |           104 | 2023-01-01   | 2025-06-30 | BTC-USDT,SOL-USDT           | auto     | 1D         |

The previous report's high-level conclusion still holds with one qualification: **Z8 is the highest annual-return frozen OOS candidate in the available run cards, while Z4 is the cleaner drawdown candidate.**

But Z8 should now be labeled: **promising, but mechanically suspect until leverage/gross-cap expression is audited.**

### 5.2 The Z8 leverage-expression issue

In `v_Z8_voltarget_train/code/signal_engine.py`, the portfolio-vol overlay is explicitly defined to scale exposure between 0.5 and 1.5. The code then clips final raw signals to `[-1.5, 1.5]` to allow modest leverage.

However, the shared `_align()` function in `agent/backtest/engines/base.py` does two things before returning executable positions:

1. It reindexes each signal, fills nulls, and clips each raw series to `[-1.0, 1.0]`.
2. It divides by the gross absolute position sum when gross exposure exceeds 1.0.

Therefore, a signal engine can *intend* to emit 1.2 or 1.5 gross exposure, but the base engine can reduce it back to 1.0 before orders are generated.

Implication:

- Z8's de-risking half is credible because a scalar below 1.0 survives clipping and gross normalization.
- Z8's upscaling half may be muted or erased.
- If the reported Z8 improvement came mostly from risk-reduction, it may still be valid.
- If the research narrative assumes “modest leverage,” that narrative is overstated unless the engine is changed.

Next required experiment:

- Clone Z8 into a controlled “Z8-expressed” branch.
- Add an explicit `gross_exposure_cap` or `allow_signal_leverage` configuration in `_align()` rather than silently bypassing safeguards.
- Run three versions on identical windows:
  1. Current Z8 as-is.
  2. Z8 with upside overlay disabled, `overlay.clip(0.5, 1.0)`.
  3. Z8 with true gross cap 1.5 and explicit leverage/margin assumptions.
- Compare total return, annual return, drawdown, Sharpe, turnover, liquidation/margin risk, and OOS stability.

This is the highest-priority research task because it can change the current champion ranking without any new data.

### 5.3 Entry-locked sizing matters more than it first appears

The technical overview states that default sizing is entry-locked. A position's quantity is set at open and not resized until the target sign changes or the backtest ends. The opt-in `rebalance_threshold` can resize same-direction positions, but it defaults to absent.

Only **5** config files used `rebalance_threshold`, and Z4 resize variants performed badly:

- `v_Z4_resize_train`: annual return 12.7%, Sharpe 0.55, max drawdown -35.7%.
- `v_Z4_resize_OOS_TEST`: annual return -9.1%, Sharpe -0.33, max drawdown -24.6%.
- Baseline Z4 train/OOS did much better.

This does not mean resizing is universally bad. It means that for Z4, continuous vol-based resizing likely trims winners when trend volatility rises. The missed research angle is to classify overlays into two types:

- **Entry-sizing overlays:** should be evaluated under entry-locked behavior. These decide initial risk at trade open.
- **Live-risk overlays:** must use `rebalance_threshold` or a deliberate gross-position update mechanism. These are suitable for crash/liquidity filters, not necessarily trend-vol scalars.

A stablecoin/ETF-flow risk-off filter may need live resizing; a trend-vol scalar may not.

---

## 6. What the previous research likely missed

### 6.1 Missed edge: crypto liquidity regime, not just price trend

The dominant Z-family signal uses price trend, realized volatility, ERC weighting, and chop frequency. It does not use direct liquidity state.

In July 2026, liquidity state looks unusually important:

- Bitcoin has been under pressure around the $60k area after a large 2026 drawdown.
- BTC ETF flows have turned negative and are being cited as a driver of deteriorating forecasts.
- Stablecoin market cap has recently contracted on 7-day and 30-day horizons.
- Investor attention has rotated toward AI assets.
- The Fed remains restrictive enough that dollar/rate pressure still matters.

This points to a **liquidity-regime overlay** as a more promising Z4/Z8 improvement than another EMA sweep.

Candidate data:

- Daily BTC ETF net flows: Farside / issuer files / scraped CSV.
- Stablecoin aggregate supply: DefiLlama stablecoin API.
- Stablecoin chain-specific supply: Ethereum, Solana, Tron, etc.
- UUP, TLT, GLD, SPY as macro proxies already available through ETF OHLCV.
- BTC/SOL realized vol and drawdown already in OHLCV.

Candidate features:

- 5-day and 20-day BTC ETF flow z-score.
- 5-day and 30-day stablecoin market-cap change.
- Stablecoin supply acceleration/deceleration.
- UUP trend / dollar pressure.
- TLT trend / rates pressure.
- GLD trend / risk-off bid.
- SPY or QQQ trend / risk appetite.

Initial test should not be a complicated ML model. Start with a regime-split attribution table:

- What is Z4/Z8 next-day return when ETF flow 20-day sum is positive vs negative?
- What is Z4/Z8 next-week return when stablecoin supply is expanding vs contracting?
- Does the filter help long trades, short trades, or only drawdown periods?
- Is it stable across BTC and SOL legs separately?
- Does it survive after shifting all exogenous data by one full day to avoid timestamp leakage?

Only if this attribution is strong should it become a live overlay.

### 6.2 Missed edge: true funding/basis, especially cross-venue and CEX-DEX

Prior research touched funding, but the executable strategy archive does not show a full historical funding-rate panel integrated into the engine. `funding_rate` in many configs is a fixed scalar. That is inadequate for a perp funding strategy.

What should be researched instead:

- Historical funding-rate carry by asset and venue.
- Funding spread between centralized exchanges and Hyperliquid.
- Funding persistence: do extreme positive/negative funding rates predict subsequent funding, spot returns, or crash risk?
- Whether funding is alpha, risk compensation, or a crowding warning.
- Whether funding improves Z4/Z8 by reducing exposure when long trend and funding are extremely positive, or by preferring short legs when funding shows crowded longs.

This is not the same as naive static carry. The previous mid-cap alt CEX-DEX carry branch was negative; the next study should target **state-conditioned funding spread**, not “always collect funding.”

### 6.3 Missed edge: ETF-flow and regulated crypto wrapper flow

BTC ETFs are now a major marginal demand channel. The previous research treated ETF flows as an external narrative, not a backtested state variable.

Research tasks:

- Build `data/crypto_etf_flows.csv` with date, issuer, net flow, cumulative flow, asset, and source.
- Aggregate daily BTC flow and optionally ETH/SOL/other ETF flows if available.
- Lag the flow by one trading day.
- Test flow as:
  - A standalone predictor for BTC/SOL returns.
  - A Z4 exposure scaler.
  - A trade-entry gate only, not a mid-hold exit rule.
  - A crash-risk / stop-new-long rule.
- Compare against simple price-only drawdown/trend filters to prove it adds information.

Do not overfit issuer-level weights at first. Aggregate flow is enough.

### 6.4 Missed edge: stablecoin dry-powder and DeFi liquidity

The run archive contains no `stablecoin` strategy-code references. That is a clear omission.

Why it matters now:

- Stablecoin supply is a direct proxy for crypto system liquidity.
- Stablecoins are increasingly regulated and institutionally relevant.
- A recent 2026 academic paper argues stablecoin factors improve crypto volatility forecasting and can add economic value to crypto vol-targeting.
- Current DefiLlama data show recent stablecoin-market-cap contraction, making this a timely regime variable.

Research tasks:

- Pull aggregate stablecoin supply, chain-level supply, and dominant-token supply from DefiLlama.
- Create lagged features: 7-day and 30-day changes, z-scores, and acceleration.
- Test against BTC/SOL returns and against Z4 equity returns.
- Test whether stablecoin contraction should reduce long exposure, increase short conviction, or only block new longs.
- Test whether chain-specific Solana stablecoin supply improves SOL timing.

### 6.5 Missed edge: open interest/liquidation/crowding

The run archive has no open-interest or liquidation usage. That is a large gap for crypto derivatives markets.

The difficulty is data. The platform does not natively include robust OI/liquidation loaders, but OKX and external vendors provide historical market data. If imported through `local`, Vibe-Trading can test it.

Candidate features:

- Perp open-interest z-score by asset.
- OI change relative to price change: crowded trend vs de-risking trend.
- Funding + OI interaction: crowded longs / crowded shorts.
- Liquidation spikes as post-cascade mean-reversion or trend-continuation states.
- Basis compression as risk-off signal.

Use this as a second wave after funding/stablecoins, because data cleaning burden is higher.

### 6.6 Missed edge: macro regime as a crypto trend meta-filter

Macro was tested as a composite portfolio and did not dominate Z4, but it was not fully converted into a **crypto trend meta-filter**.

Given current conditions, the more natural test is:

- Keep Z4/Z8 as the crypto alpha engine.
- Add a slow macro risk regime derived from UUP, TLT, GLD, SPY/QQQ.
- Use macro regime only to change gross exposure or long/short asymmetry.

Examples:

- If UUP uptrend + TLT downtrend + GLD uptrend, treat as restrictive/risk-off: reduce crypto long exposure.
- If SPY/QQQ uptrend + UUP downtrend + TLT stable/up, allow full crypto long exposure.
- If crypto trend is short and macro risk-off is confirmed, allow normal or higher short conviction.

This is more plausible than forcing crypto, SPY, GLD, TLT, and UUP into one equal-risk portfolio where asset vol/return profiles can dominate allocation mechanics.

### 6.7 Missed edge: China A factor research under current two-speed economy

The repo's next-directions file already identified China A factor research as a major opportunity. The code scan confirms it: Alpha Zoo and China loaders are available, but strategy runs barely used them.

June 2026 China context suggests a specific angle:

- Manufacturing is expanding, helped by AI-related exports and high-tech demand.
- Domestic demand, property, and deflation pressures remain weak.
- Retail participation in A-shares historically makes turnover/crowding regimes important.

Research candidates:

- Low-volatility + dividend yield + quality/profitability composite.
- AI/export-exposed high-tech basket with quality/earnings filters.
- Retail-crowding/turnover regime filter: momentum works differently in high-turnover vs low-turnover states.
- PMI announcement event study, especially positive surprise / expansion states.
- GTJA191/Qlib factor sweep with cost/turnover pruning.

This is one of the few directions that can find a **new, non-crypto champion** using existing platform strengths.

### 6.8 Missed edge: US AI/semiconductor rotation, but robustly

The raw archive contains spectacular short-window annualized semiconductor/AI results. These are not yet credible champions because the windows are too short and annualization is unstable.

However, current market conditions make the theme worth converting into a proper research program:

- Capital has rotated toward AI-related equities while crypto has weakened.
- Semiconductor and AI infrastructure narratives are a dominant 2026 macro/micro theme.
- Vibe-Trading can test US ETFs and equities well enough at daily/1H bars.

Research candidates:

- SOXX/SMH/QQQ/SPY relative momentum with volatility targeting.
- Long AI/semi basket vs short broad tech or short crypto proxies.
- Equal-weight vs cap-weight tech rotation.
- Levered ETF decay/volatility drag avoidance: use SOXL/TQQQ only for short holding windows or avoid entirely.
- AI trend strength as macro risk-appetite proxy for crypto exposure.

The key discipline: treat existing `20260630_044631_81_90164a` and `trackA_*` runs as **hypothesis generators**, not performance evidence.

### 6.9 Missed edge: event/regulatory calendar

The codebase has event-feed hooks, but no configs used `event_feeds`. Crypto in 2026 is heavily event-sensitive: ETF rules, legislation, SEC consultations, Fed meetings, macro releases, token unlocks, exchange listings, protocol upgrades.

A first practical event strategy should not try to predict all news with LLM sentiment. It should use structured calendars:

- FOMC dates and rate decisions.
- CPI/PCE/NFP dates.
- SEC crypto ETF decision/comment deadlines.
- Token unlock schedules for SOL ecosystem / major alts.
- ETF launch dates and first-week flow windows.
- Major chain upgrade dates.

Test event windows as exposure controls, not directional bets at first:

- Reduce exposure before high-volatility macro events if the system is trend-long and liquidity is negative.
- Allow higher short conviction when negative trend coincides with adverse regulatory/event flow.
- Avoid new entries near known unlock events for assets with high unlock supply.

### 6.10 Missed edge: options/ETF carry is real but not platform-native yet

The prior research found a robust implied-vs-realized vol premium lead in DVOL, but the platform could not execute options-chain backtests. Current 2026 research also points to ETF/futures/IBIT options carry wedges. This is potentially high-quality alpha, but it requires a new data/instrument layer.

Next step is not to fake it with realized vol. The correct next step is an infrastructure feasibility spike:

- Get historical IBIT options chains or option-implied forwards.
- Get CME BTC futures prices and BRRNY-style reference prices.
- Reconstruct carry wedge after costs/margins.
- Only then build a Vibe-Trading-compatible local data bridge.

Until then, options/carry stays in the “valuable but not immediately actionable” bucket.

---

## 7. Current July 2026 market context and why it changes priorities

### 7.1 Crypto market state

As of 2026-07-02, live reference prices from market data put BTC around **$60.8k**, ETH around **$1.63k**, and SOL around **$78**. Recent reporting describes Bitcoin as down sharply in the first half of 2026, with ETF outflows and AI-sector rotation as major explanations.

For Vibe-Trading research, this means the next Z4/Z8 improvement should focus on **regime and liquidity filters** rather than more trend-speed tinkering. The market is already stress-testing crypto trend systems in a post-ETF, institutionally mediated regime.

### 7.2 ETF-flow state

Reuters reported on 2026-07-01 that Citi cut Bitcoin and Ether targets as ETF flows turned negative, citing Bitcoin ETF outflows year-to-date. MarketWatch reported persistent weekly ETF outflows and a 2026 drawdown. Farside's ETF-flow tables provide a practical daily source for the feature itself.

Research implication: BTC ETF flow should be treated as a first-class daily exogenous feature.

### 7.3 Macro state

The Federal Reserve's 2026-06-17 FOMC statement maintained the target range at **3.50%–3.75%**. Current ETF proxies show GLD strong, TLT weak, UUP firm, and SPY high but with intraday softness around the July 1 close.

Research implication: crypto should not be treated as isolated from dollar/rates/gold risk regimes. Slow macro meta-filters are now more relevant.

### 7.4 Stablecoin liquidity state

DefiLlama's current stablecoin dashboard shows total stablecoin market cap around **$311.5B**, with negative 7-day and 30-day changes. That is not automatically bearish by itself, but it is exactly the kind of liquidity contraction variable that can explain why a price-only trend system underperforms or overexposes during de-risking windows.

Research implication: stablecoin supply changes should be tested as a risk regime and volatility-forecasting input.

### 7.5 Hyperliquid/perps state

Recent reports and venue materials show Hyperliquid has become large enough to matter for perp open interest/funding. OKX and CCXT provide practical ways to retrieve historical funding data, and OKX also publishes historical L2 data.

Research implication: a 2023-era or early-2025 conclusion that CEX-DEX funding carry was not worth pursuing should be revisited as **state-conditioned funding spread / venue-crowding research**, not as static carry.

### 7.6 China and AI/export state

Reuters reported that China's June 2026 official PMI moved into expansion and that AI-related/high-tech exports were a key support, while domestic demand and deflationary pressures remained fragile.

Research implication: China A research should emphasize high-quality exporters/high-tech + defensive/dividend/low-vol factors and should explicitly segment by domestic-demand vs export/AI regimes.

---

## 8. Prioritized next research roadmap

### Priority 0 — Mechanics audit before any new alpha claim

**Goal:** make sure the champion strategy is being measured exactly as intended.

Experiments:

1. **Z8 expressed-vol overlay test**
   - Current Z8.
   - Z8 with overlay capped at 1.0.
   - Z8 with explicit gross cap 1.5 and leverage accounting.
   - Same train/OOS windows; same costs; same bootstrap and walk-forward.

2. **Z4/Z8 entry-lock vs live-resize classification**
   - Do not blindly enable `rebalance_threshold` for all overlays.
   - Test live resizing only for overlays intended as live risk controls.
   - Keep trend-vol sizing entry-locked unless evidence shows otherwise.

3. **Attribution of overlay impact**
   - Contribution by BTC vs SOL.
   - Long vs short contribution.
   - Entry-day sizing vs mid-hold exposure impact.
   - Drawdown days only.

Acceptance criteria:

- Any champion improvement must beat Z4/Z8 OOS after costs.
- Must not rely on annualization of a short sample.
- Must pass bar-boundary or at least rebalance-date offset tests.
- Must include an ablation showing the exact new mechanism adds value.

### Priority 1 — Crypto liquidity-regime overlay for Z4/Z8

**Goal:** improve drawdown and risk-adjusted return by adding exogenous liquidity state.

Data:

- BTC ETF daily net flow.
- Stablecoin aggregate and chain-level supply.
- UUP, TLT, GLD, SPY/QQQ daily OHLCV.
- BTC/SOL OHLCV already available.

Feature set:

- `btc_etf_flow_5d_sum`, `btc_etf_flow_20d_sum`, z-score by trailing 60/120 days.
- `stablecoin_mcap_7d_pct`, `stablecoin_mcap_30d_pct`, stablecoin acceleration.
- `uup_trend`, `tlt_trend`, `gld_trend`, `spy_trend` using 20/120 or 50/200 MA.
- Composite `crypto_liquidity_score` in (-1, 0, 1) first, not continuous optimizer bait.

Test sequence:

1. Regime attribution only.
2. Entry gate only.
3. Gross exposure dampener only.
4. Long/short asymmetry: reduce longs in negative liquidity, leave shorts unchanged or modestly increase short conviction.
5. Combined with Z4 first; only then Z8.

Avoid:

- Overfitting continuous weights.
- Same-day ETF-flow leakage.
- Optimizing on 2026 only.

Acceptance criteria:

- Improves Z4 OOS drawdown without destroying annual return.
- Improves Z8 OOS Sharpe or reduces drawdown enough to justify complexity.
- Positive effect in at least two independent subperiods.

### Priority 2 — True funding / basis / venue spread research

**Goal:** find a new crypto derivatives edge or improve Z4 exposure control.

Data:

- OKX historical funding rates.
- CCXT `fetchFundingRateHistory` for Binance/Bybit/OKX where available.
- Hyperliquid `fundingHistory` / funding comparison data.
- Optional open-interest and premium index data.

Experiments:

1. Funding-rate panel construction.
2. Funding persistence and reversal study.
3. Funding + trend interaction:
   - Long trend + extreme positive funding = crowded long risk?
   - Short trend + positive funding = paid-to-short tail?
   - Negative funding + long trend = contrarian opportunity?
4. CEX-vs-Hyperliquid spread persistence.
5. Funding/OI crash-risk filter.

Acceptance criteria:

- Must model funding payments explicitly.
- Must include venue-specific symbol/contract assumptions.
- Must include costs, slippage, and borrow/margin assumptions.
- Static carry alone is not enough; need state-dependent edge.

### Priority 3 — Macro trend sleeve and macro meta-filter

**Goal:** add robust diversification or regime awareness without diluting the crypto edge.

Experiments:

1. Slow AQR-style trend on SPY/GLD/TLT/UUP.
2. Barbell macro sleeve: GLD/UUP/TLT/SPY with slow MA and volatility scaling.
3. Crypto meta-filter using macro state, not a merged all-asset ERC portfolio.
4. 80/20 or 70/30 crypto/macro sleeves with fixed capital budget.
5. Crisis-only macro hedge overlay.

Acceptance criteria:

- Improves max drawdown and crisis behavior versus Z4/Z8.
- Does not merely add leveraged beta.
- Robust to ERC bug fix and gross-exposure assumptions.

### Priority 4 — China A factor-zoo program

**Goal:** find a new non-crypto strategy family.

Data:

- China A OHLCV via existing loaders.
- Tushare daily_basic/fundamental fields where available.
- Alpha Zoo factors: GTJA191, Qlib, academic, Alpha101.
- Industry classification and ST/suspension filters.

Experiments:

1. Low-vol + dividend/value + quality composite.
2. Momentum/reversal factors segmented by turnover regime.
3. AI/export high-tech basket factor study.
4. PMI event-window study.
5. Walk-forward factor selection with turnover/cost constraints.

Acceptance criteria:

- IC/IR plus monotonic quantiles.
- Long-short spread after realistic costs.
- PIT/survivorship discipline.
- OOS validation, not just factor-lab in-sample success.

### Priority 5 — US AI/semi robust rotation

**Goal:** convert high short-window annualization into testable strategy hypotheses.

Data:

- SOXX, SMH, QQQ, SPY, XLK, equal-weight tech, selected AI infrastructure ETFs/stocks.
- Avoid overdependence on 2x/3x ETFs except as a separate tactical branch.

Experiments:

1. Daily/1H relative momentum with strict OOS.
2. AI/semi vs broad tech/market pair rotation.
3. Levered ETF decay-aware entry/exit.
4. Volatility regime filter for SOXL/TQQQ.
5. Use AI/semi momentum as an exogenous risk-appetite input to crypto, not only as standalone.

Acceptance criteria:

- Minimum one-year OOS or walk-forward windows.
- Drawdown below raw short-window branches.
- No champion promotion from one-month annualization.

### Priority 6 — Event/regulatory calendar and token unlocks

**Goal:** add structured event risk, not free-form sentiment.

Experiments:

- FOMC/CPI/NFP exposure suppression.
- SEC ETF comment/approval windows.
- Crypto legislation milestones.
- Token unlock windows for major alts.
- Chain upgrade windows.

Acceptance criteria:

- Event windows must be known in advance.
- Events must be lagged/dated correctly.
- Strategy effect must survive excluding the largest one or two event outliers.

### Priority 7 — Options / ETF carry infrastructure spike

**Goal:** determine whether the strong crypto vol/carry evidence can become tradable in Vibe-Trading.

Experiments:

- Historical IBIT options + CME futures carry reconstruction.
- Deribit option-chain short-variance backtest.
- Margin/collateral/cost model.
- Local data bridge prototype.

Acceptance criteria:

- No realized-vol proxy substitution for implied-vol strategy.
- Must use real tradable option/futures data.
- Must include execution and margin assumptions.

---

## 9. Concrete implementation plan

### 9.1 Minimal code changes

1. Add optional `gross_exposure_cap` to `agent/backtest/engines/base.py` alignment path.
   - Default remains 1.0 for backward compatibility.
   - If `gross_exposure_cap=1.5`, gross normalization clips at 1.5.
   - Add tests proving old results are byte-identical when unset.

2. Add a `source: local` data bridge convention for exogenous daily features:

```text
~/.vibe-trading/data-bridge/
  crypto_etf_flows.csv
  stablecoins_defillama.csv
  perp_funding_panel.csv
  macro_features.csv
```

3. Create a feature-merge utility that joins exogenous daily series into each symbol's DataFrame with explicit lag columns, for example:

```text
btc_etf_flow_1d_lag
btc_etf_flow_5d_sum_lag
stablecoin_mcap_7d_pct_lag
uup_trend_lag
tlt_trend_lag
gld_trend_lag
```

4. Extend report/validation artifacts with ablation tables:

```text
base_strategy
+ liquidity attribution only
+ entry gate
+ live dampener
+ long/short asymmetric overlay
```

### 9.2 First five exact experiments to run

#### Experiment A — Z8 overlay expression audit

- Base: `v_Z8_voltarget_train` and `v_Z8_voltarget_OOS_TEST`.
- Variants:
  - `Z8_current_engine`.
  - `Z8_overlay_max_1p0`.
  - `Z8_gross_cap_1p5`.
- Output: champion impact table and overlay-state attribution.

#### Experiment B — Z4 liquidity-regime attribution

- Base: `v_Z4_chopfreq`.
- No trading-rule change initially.
- Bucket daily strategy returns by ETF-flow regime, stablecoin regime, and macro regime.
- Output: return, volatility, drawdown contribution by regime.

#### Experiment C — Z4 liquidity entry-gate

- Gate only new long entries when liquidity score is strongly negative.
- Do not close existing positions mid-hold in the first version.
- Compare vs live dampener.

#### Experiment D — Funding spread panel

- Build BTC/SOL/ETH funding history across OKX/CCXT/Hyperliquid.
- Test carry, crowding, and trend interaction.
- Output: funding signal IC, regime returns, and PnL after funding/costs.

#### Experiment E — China A factor pilot

- Universe: CSI 300 / A500 / liquid A-shares with ST and suspension filters.
- Factors: low-vol, dividend/value, quality/profitability, selected GTJA momentum/reversal.
- Output: IC/IR, quantile monotonicity, long-short spread, turnover/cost, OOS.

---

## 10. Decision matrix

| Research direction | Expected edge quality | Implementation difficulty | Data difficulty | Fits July 2026? | Priority |
| --- | --- | --- | --- | --- | --- |
| Z8 gross/leverage audit | High, because it affects existing champion | Medium | None | Yes | 0 |
| Z4/Z8 liquidity-regime overlay | High | Medium | Medium | Very high | 1 |
| True funding / CEX-DEX basis | High but uncertain | Medium-high | Medium | Very high | 2 |
| Macro trend meta-filter | Medium-high | Low-medium | Low | High | 3 |
| China A factor zoo | Medium-high | Medium-high | Medium | High | 4 |
| US AI/semi robust rotation | Medium | Medium | Low | High | 5 |
| Event/regulatory calendar | Medium | Medium | Medium | High | 6 |
| Options/ETF carry | Potentially high | High | High | High | 7 |
| More EMA/lookback sweeps | Low | Low | None | Low | Deprioritize |
| Broader random altcoin universe | Low | Low-medium | Low | Low | Deprioritize |
| Static funding carry | Low-medium | Medium | Medium | Medium | Deprioritize unless state-conditioned |

---

## 11. Final assessment

The core research did not fail to look hard enough at BTC/SOL trend. It probably looked too hard there and not hard enough at exogenous market state.

The current best strategy family is still real: daily BTC/SOL trend following with volatility-aware sizing and chop/risk overlays. But the next meaningful improvement is unlikely to come from another EMA parameter or another minor asset-universe change. The most plausible next edge is to make Z4/Z8 aware of the forces currently dominating crypto markets in June/July 2026: ETF-flow demand, stablecoin liquidity, dollar/rates/gold macro pressure, and derivatives crowding/funding.

The recommended sequence is strict:

1. First, fix or explicitly characterize the Z8 leverage/gross-cap mechanics.
2. Second, run exogenous liquidity-regime attribution without changing trades.
3. Third, add the smallest possible bounded overlay only where attribution proves it helps.
4. Fourth, build true funding/basis data and test venue-spread/crowding hypotheses.
5. Fifth, open non-crypto branches through China A factor research and robust AI/semi rotation.

If this sequence is followed, the next research cycle has a realistic chance to either improve the current champion or find a new, independent strategy family. If it instead continues with price-only crypto parameter sweeps, the marginal return on research is likely low.

---

## 12. Source notes for current market context

The market-context section used current/recent sources available as of 2026-07-02, including:

- Reuters, 2026-07-01: Citi cuts Bitcoin/Ether forecasts as ETF flows turn negative.
- MarketWatch, 2026-07-02: Bitcoin ETF selloff/outflow stress and first-half 2026 drawdown.
- Federal Reserve, 2026-06-17: FOMC statement maintaining the federal funds target range at 3.50%–3.75%.
- DefiLlama stablecoin dashboard, accessed 2026-07-02: total stablecoin market cap and 7-day/30-day changes.
- Reuters, 2026-06-30/2026-07-01: China June factory PMI / AI-export support and domestic fragility.
- SEC, 2026-06-30: request for public comment on novel exchange-traded funds.
- OKX historical data page: funding-rate history and L2 availability.
- CCXT documentation: `fetchFundingRateHistory` interface.
- Hyperliquid documentation / June 2026 reporting: funding mechanism and large open-interest context.
- Academic working papers from 2026 on stablecoins as dry powder and ETF/futures carry wedges.
