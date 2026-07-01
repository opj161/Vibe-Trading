**This is a well-observed and important robustness issue in quantitative trading, particularly acute in 24/7 markets like crypto.** Your systematic EMA(10,30) crossover with volatility targeting and risk-parity allocation is a clean, classic trend-following setup. The massive Sharpe swing (–0.06 to +1.19) purely from shifting the daily bar close time (every 4h UTC offset) on identical underlying data, plus the strong asymmetry (BTC relatively stable at Sharpe ~1.06–1.43 vs SOL wildly unstable at –0.64 to +0.26), highlights a real implementation-detail risk that interacts with asset volatility and signal marginality. Higher-vol assets produce more boundary-sensitive crossovers because small price increments near the EMA lines are more likely to flip the signal depending on exactly where the artificial “day” ends.

I researched this across academic literature (arXiv, SSRN, journals), foundational quant texts, recent practitioner/CTA-oriented work (2024–2026), and crypto-specific microstructure studies. Below I address each part methodically, with sources, dates, nuances, evidence strength, edge cases, and practical implications. I prioritized rigorous, recent, credible sources over retail blogs.

### 1. Is this a named, documented phenomenon?

It does not have one single famous name like “look-ahead bias” or “survivorship bias,” but it is a recognized instance of **broader documented problems**:

- **Temporal aggregation bias** (econometrics/finance time-series literature): Changing the sampling/aggregation interval or boundary systematically alters estimated dynamics, introduces moving-average components into errors, and biases short-run parameters while often preserving long-run relations. This is well-studied in macro/monetary policy transmission and price transmission contexts. In trading, it manifests exactly as you observed: different “daily” partitions of the same continuous price path change inferred trends, crossovers, and performance metrics non-monotonically.

- **Arbitrary time-bar sampling / boundary effects in continuous markets** (quant trading & market microstructure): Time bars (fixed-clock intervals) are criticized because markets process information at varying rates. They oversample low-activity periods and undersample high-activity ones, producing returns with poor statistical properties (serial correlation, heteroskedasticity, non-normality). In 24/7 crypto (no natural session close, no overnight gap), the choice of close time is economically arbitrary and can inject or remove edge via boundary artifacts.

The most direct recent crypto-specific treatment is the December 15, 2025 paper in *Financial Innovation* (Springer) by Grądzki, Wójcik & Lessmann: “Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning.” They explicitly state that traditional time-based sampling (e.g., daily or hourly bars) in crypto “force traders to wait for arbitrary points in time” and “significantly delay the capture of critical market shifts,” leading to suboptimal outcomes. They contrast this with information-driven alternatives on tick data (BTC/ETH, 2018–2023 period). Time bars underperformed; certain information-driven methods succeeded even after costs.

Lopez de Prado’s *Advances in Financial Machine Learning* (Wiley, 2018, Chapter 2 on Financial Data Structures) is the foundational practitioner reference. It argues time bars should generally be avoided for ML/features because of the statistical defects above; information-driven bars (especially dollar bars) are preferred for more stationary, informative sampling. Many subsequent practitioner notes and implementations cite this directly for trend/momentum signals.

**Nuance/edge cases**: The effect is stronger for fast signals (short EMA windows) and marginal crossovers, exactly as you saw with SOL vs BTC. It is a form of implicit data snooping or multiple-testing risk when practitioners optimize or cherry-pick a convenient close time. Serious quant workflows (purged/combinatorial cross-validation per Lopez de Prado) treat bar construction choices as hyperparameters to be robustness-tested, not assumed neutral. In FX/crypto desks, close-time conventions (e.g., NY 16:00 or specific exchange) are standardized precisely because of this sensitivity.

**Implication**: Your finding is not an anomaly; it is expected behavior when using clock-time bars in continuous, volatile markets. It qualifies as genuine implementation/strategy risk rather than pure “data error.”

### 2. Established techniques to make fast MA-crossover signals robust to arbitrary bar-boundary timing

#### Multi-offset signal ensembles/averaging
This is a practical robustness technique but **not heavily documented as a standalone studied method** with specific “right number of offsets” or optimal combiners in academic/CTA literature for daily bars. It aligns conceptually with ensemble methods and bagging for variance reduction in noisy financial data (Lopez de Prado, AFML Chapter 6 discusses ensembles, bagging, and their value in finance for reducing variance from redundant/noisy observations or labels).

Your observation—that an ensemble of 6 offsets converges roughly to the *average* of single-offset Sharpes (robustness/variance reduction, not excess edge)—is the **expected and documented behavior** for simple averaging of correlated signals. If the different boundary versions are highly correlated (same underlying trend information, just phase-shifted noise), the ensemble smooths the equity curve and stabilizes the Sharpe estimate without creating new alpha. This is analogous to portfolio diversification or bootstrap aggregating.

**Nuances and smarter alternatives**:
- Simple average or majority vote: Good baseline for robustness.
- Weighted by historical stability (e.g., inverse variance of recent Sharpe or signal consistency) or recent performance: Can tilt toward more reliable offsets dynamically and potentially extract modest extra stability/edge.
- Treat offsets as multiple features and use meta-labeling or a lightweight selector/regime detector (Lopez de Prado meta-labeling framework) to decide which boundary (or combination) to trust in current conditions.
- Continuous/rolling boundary or fractional/phase-aware signals: More advanced; avoids discrete set entirely.
- Right number: 4–8 evenly spaced offsets (your 6 is reasonable) often suffices for variance reduction; diminishing returns beyond that if highly correlated.

Overall, this is a solid, low-cost robustness layer, especially combined with your existing vol-targeting/risk-parity.

#### Alternative bar construction (volume, dollar, tick, range bars)
**Yes—strongly advocated and with supporting evidence**, especially from Lopez de Prado (AFML 2018) and the 2025 Grądzki et al. crypto paper.

- **Theoretical advantages** (Lopez de Prado): Time bars have poor statistical properties. Dollar bars (sample when a fixed dollar volume is traded) are particularly robust because they normalize for price level changes and produce more constant “information content” per bar. Volume and tick bars improve on pure time but can still be distorted by wash trading or varying trade sizes. Range bars focus on price excursion. These are more event-driven and less sensitive to arbitrary clock boundaries.

- **Empirical evidence in crypto, including for trend/momentum-style signals**: Grądzki et al. (Dec 2025) tested exactly these on tick-level BTC/ETH data (2018–mid-2023). CUSUM filter (volatility-aware information-driven sampling) + Triple Barrier labeling consistently outperformed traditional time bars, producing positive performance after transaction costs in deep learning setups (Sharpe ratios up to ~2.0 in optimized configurations for ETH). Volume and dollar bars were mixed/negative in some of their tests (susceptible to distortions like wash trading; do not inherently adapt to volatility). Range bars were intermediate. They note time bars’ arbitrariness explicitly harms responsiveness in 24/7 crypto.

Other practitioner implementations citing AFML report that moving averages, trends, and momentum features extracted from dollar bars often show better OOS behavior and statistical properties than time-bar equivalents. For pure trend-following, the improvement is more about reduced noise/false signals and better alignment with actual market activity than guaranteed higher Sharpe in every regime. Evidence is stronger theoretically + in ML/feature contexts than in exhaustive published simple MA-crossover horse races on crypto.

**Nuance/edge cases**: In very low-liquidity periods or with wash trading, volume/dollar bars can introduce their own artifacts. Parameter choice (bar size/threshold) matters and should be robustness-tested (often ~50 bars/day heuristic from Lopez de Prado for statistical properties). CUSUM or hybrid vol-aware variants appear particularly promising for crypto from the 2025 study. These sidestep the boundary problem entirely by making sampling activity- or volatility-dependent rather than clock-dependent.

**Implication for your strategy**: Switching (or hybridizing) to dollar bars or CUSUM-style sampling is one of the cleanest ways to eliminate the arbitrary close-time sensitivity while potentially improving signal quality. Your vol-targeting already complements this well.

#### Session-based or volatility-adjusted bar timing
**Yes—crypto exhibits meaningful time-of-day seasonality in liquidity/volume**, so aligning bars to it is less arbitrary than pure UTC offsets.

Multiple studies and practitioner observations confirm a reverse V-shaped intraday pattern in BTC (and broadly crypto): lower activity overnight/early Asia, rising through European session, peaking during US/EU overlap (highest volume/volatility around US open/close hours). This is driven by traditional market participant overlap. Recent 2025 guides and options-market studies reinforce persistent intraday patterns (e.g., concentration around specific GMT windows).

Aligning daily bars to, e.g., NY close (16:00 ET) or volume-weighted session boundaries reduces arbitrariness and better matches genuine liquidity regimes. Quantpedia analyses of BTC also highlight differential performance in “overnight” vs session periods.

**Evidence strength**: Solid for liquidity/vol patterns; somewhat indirect but supportive for improved signal robustness in trend strategies (better bars during high-info periods). Not a complete panacea (still some boundary choice), but meaningfully “smarter” than uniform UTC.

### 3. Ensemble-of-offsets converging to average Sharpe — expected behavior? Smarter methods?

**Yes, this is the expected/documented behavior** for simple averaging of correlated phase-shifted signals (variance reduction / robustness, akin to bagging). It smooths noise without necessarily creating excess edge if the core information is shared. Lopez de Prado’s ensemble discussion supports this framing in finance contexts.

**Smarter combination methods for potential excess signal**:
- Dynamic/adaptive weighting (recent Sharpe, signal stability, or inverse recent variance) — tilts toward more reliable offsets in current regimes.
- Meta-model or regime detector on top of the ensemble (which offset or combination performs best now?).
- Continuous weighting or fractional boundaries instead of discrete set.
- Hybrid: Use the ensemble as a robustness layer while primary signal comes from information-driven bars.

Pure averaging is excellent for what you want (robustness). Extracting genuine extra edge usually requires moving beyond fixed time bars or adding adaptive/meta layers.

### 4. Why higher-vol alts (SOL) show more fragility than BTC? Per-asset EMA adjustment by volatility?

**Yes — this matches theory and indirect evidence**. Higher daily volatility (~3.5–3.8% SOL vs ~2.1–2.3% BTC) produces noisier price paths with more frequent marginal EMA crossovers. Small boundary shifts are more likely to flip the signal when the asset is wiggling around the crossover level. Lower-vol BTC produces cleaner, more persistent trends with fewer boundary-dependent flips. This is consistent with microstructure: higher noise/vol increases false signals in lagging indicators like short-window MAs.

**Documented mitigation via per-asset adjustment**: Yes. Kaufman’s Adaptive Moving Average (KAMA) in *Trading Systems and Methods* (multiple editions, e.g., 5th/6th) explicitly adapts MA speed to market noise/volatility/efficiency ratio — faster in trending low-noise regimes, slower in choppy high-noise ones. This is a standard way to equalize effective signal quality across assets.

In multi-asset trend-following practice (including CTAs), per-asset or vol-normalized parameters (or efficiency-ratio adaptation) are common alongside position-level vol targeting/risk-parity to reduce exactly this kind of asymmetry and fragility. Using identical 10/30 spans across assets is convenient but suboptimal when vols differ materially. Your risk-parity allocation already helps at the portfolio level; signal-level adaptation would further stabilize the SOL leg.

**Implication**: Test KAMA-style or vol-scaled lookbacks per asset (or a blended approach). This is a documented, low-overhead way to reduce the observed asymmetry.

### 5. Realistic Sharpe expectations for live crypto CTA/trend-following (2025–2026 context) and sensitivity views

**Live/realistic ranges** (prioritizing credible sources):
- Traditional diversified CTAs (SG Trend Index, Barclay CTA, Simplify Managed Futures ETF/CTA proxy, etc.): Long-term Sharpe historically ~0.5–1.0 range, with strong years >1 and drawdowns in choppy regimes. 2022 was strong for many trend followers; recent years mixed. Crypto inclusion is discussed for diversification and crisis alpha (Man Group research note, Jan 2026).
- Crypto-specific or crypto-heavy trend/backtests: Highly variable. Simple daily MA-style on BTC can produce Sharpe 1.0–1.5+ in favorable multi-year windows (your BTC single-offset results are plausible for good periods). Broader alt baskets or adaptive versions in recent backtests claim higher (e.g., one Feb 2026 arXiv systematic TF framework reported 2.41 Sharpe OOS 2022–2024 on 150+ pairs with adaptive elements; Grądzki et al. 2025 DL setups reached ~2.0 Sharpe in optimized CUSUM+Triple Barrier configs). Live results are lower due to costs, slippage (especially alts), execution, and regime shifts. Pure crypto trend is higher-beta/higher-drawdown than diversified traditional CTA.
- 2025 context: Crypto had periods of strength and drawdowns; trend followers benefited selectively from directional moves but faced chop in others.

**Sensitivity of daily-bar systematic strategies to this implementation-detail risk**: Serious practitioners and researchers (Lopez de Prado school, CTA quant teams) consider it **material and worth explicit robustness testing**. Small choices in data construction, bar timing, or parameters can materially inflate in-sample performance via implicit snooping. It is treated as part of overall strategy risk (intertwined with genuine edge extraction). Daily-bar approaches in 24/7 markets are viewed as inherently more fragile to such details than event-driven or higher-frequency alternatives. Good practice includes testing across multiple boundaries/ensembles, standardizing conventions, or migrating to information-driven bars. Your systematic exploration is exactly the right professional approach.

**Overall recommendations for your setup**:
- Keep the ensemble-of-offsets as a robustness layer (or upgrade to adaptive weighting).
- Strongly consider migrating primary bars to dollar bars or CUSUM-style (or hybrid) — this directly attacks the root arbitrariness and has supporting crypto evidence.
- Explore per-asset adaptive MA (KAMA-style or vol/efficiency-adjusted lookbacks) to address SOL fragility.
- Align to session-aware boundaries (e.g., US/EU overlap influence) as a secondary robustness check.
- Continue rigorous OOS/purged testing and cost/slippage modeling. The fact that your ensemble averages rather than magically improves is healthy — it confirms you are measuring real robustness rather than overfitting to one lucky boundary.

This phenomenon and the mitigation paths are well-grounded in the literature you would expect (Lopez de Prado 2018 as cornerstone; recent crypto-specific 2025 journal paper as direct validation). Your results are consistent with it and demonstrate good quant hygiene. If you share more details on your exact backtest setup, data sources, or code structure, I can help refine specific implementation suggestions (e.g., dollar bar construction in your environment).