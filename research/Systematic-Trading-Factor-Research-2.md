## Bottom line

The strongest current research queue is **not** “run all 456 factors and rank IC.” It is:

1. **US large-cap quality + value + momentum composite**, sector/risk neutralized, with momentum crash controls.
2. **China A-shares low-volatility / low-risk + value / dividend + profitability-quality**, with explicit retail-flow and policy-regime filters.
3. **China A short-horizon residual reversal / liquidity-pressure signals**, but only after very conservative transaction-cost and capacity modeling.
4. **Hong Kong high-dividend / low-volatility / value**, as a lower-confidence, liquidity-constrained exploratory sleeve.
5. **Standalone raw Alpha101 / Qlib158 / GTJA191 technical factors** should be treated as *feature candidates*, not live premia, until they survive net-cost, post-selection, point-in-time validation.

The key current regime fact: **momentum is still working, but it is also visibly crowded and crash-prone.** J.P. Morgan’s 2Q 2026 factor outlook says momentum had its best multi-year run since the dot-com era and that dispersion inside momentum is the widest since 1990, creating risk of sharp underperformance; at the same time, value and quality still look attractive, especially in the US. ([J.P. Morgan][1])

---

## Credibility tiers I use below

**Tier A** = recent 2025–2026 live/practitioner/index evidence from major providers such as J.P. Morgan, S&P DJI, MSCI, SSGA, Acadian, Premia.
**Tier B** = recent academic or SSRN/arXiv evidence, plausible but not necessarily live/net-cost deployable.
**Tier C** = older canonical evidence, sponsor factsheets, or experimental AI/LLM alpha-mining claims.

---

## Ranked factor families / combinations to backtest first

| Rank | Candidate                                                                    | Evidence strength                  | Best starting universe                                                                                          | Rebalance / holding period                                    | Why this should be first-pass tested                                                                                                                                                                                                                                                                                                                                                                             | Main caveat                                                                                                                                                                              |
| ---: | ---------------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 | **US large-cap quality + value + momentum composite**                        | **Tier A**                         | S&P 500 or Russell 1000, liquid common stocks only                                                              | Monthly signal refresh; 1–3 month holding; sector-neutral     | S&P’s quality-value-momentum index research reported that the S&P 500 QVM composite beat the S&P 500 by about 9% in Q1/YTD 2026 and argues the factors diversify each other because quality, value, and momentum have low or negative correlations. ([Indexology Blog][2])                                                                                                                                       | Momentum leg is crowded; test with momentum de-crowding, valuation filters, skip-month return, and crash overlays.                                                                       |
|    2 | **China A low-risk / low-vol + value / dividend + profitability-quality**    | **Tier A / B**                     | CSI 300 + CSI 500, or MSCI China A / Stock Connect large-mid universe                                           | Monthly; 1–3 month holding; slower rebalance for fundamentals | MSCI’s late-2025 China factor work says China A’s leading factors differ from global norms, with high-dividend-yield and low-volatility factors consistently outperforming while global-style momentum is less dominant. ([MSCI][3]) Premia’s Q1 2026 China A review says the rotation from growth to value continued, with low risk and value flourishing while growth/quality fell. ([premia-partners.com][4]) | China A factors are regime-sensitive; Acadian finds retail surges can temporarily invert factor behavior and cut value’s historical edge. ([acadian-asset.com][5])                       |
|    3 | **China A retail-flow-aware residual reversal / liquidity-pressure signals** | **Tier B**                         | Liquid CSI 500 / CSI 800; avoid ST, suspended, tiny, limit-locked names                                         | Weekly to monthly; 5–20 trading-day holding                   | Recent research argues short-term reversal still persists globally when measured as firm-specific rather than industry-wide reversal. ([SSRN][6]) China A also has recurring retail-flow episodes, which makes flow/reversal/liquidity pressure economically plausible. ([acadian-asset.com][5])                                                                                                                 | This is the highest transaction-cost and capacity risk bucket. It must be tested net of spread, impact, turnover, suspensions, limit-up/down constraints, and realistic execution delay. |
|    4 | **US value + quality, with momentum only as a risk filter**                  | **Tier A**                         | S&P 500 / Russell 1000                                                                                          | Monthly or quarterly; 3–6 month holding                       | J.P. Morgan says value remains attractive globally, especially in the US, and quality valuations are compelling after a poor recent stretch. ([J.P. Morgan][1]) SSGA also argues quality remains useful in uncertain markets even after lagging during strong 2025 equity returns. ([SSGA][7])                                                                                                                   | Value can be a value trap without profitability, leverage, accrual, and sector controls.                                                                                                 |
|    5 | **Standalone momentum, risk-adjusted and de-crowded**                        | **Tier A evidence, but high risk** | US large-cap first; global ex-US / HK only after liquidity checks; China A only as residual/news-aware momentum | Monthly; 1–3 month holding; exclude most recent month         | S&P reported unusually strong 2026 momentum rebounds, including a historically large April rally in US momentum indices. ([Indexology Blog][8]) J.P. Morgan also says momentum supported recent factor gains. ([J.P. Morgan][1])                                                                                                                                                                                 | This is the classic “still working, therefore dangerous” factor now. Do not run naked 12-month momentum without crowding, valuation, and reversal-risk controls.                         |
|    6 | **Hong Kong high-dividend / low-vol / value with liquidity screen**          | **Tier B-/C+**                     | Hang Seng Composite large/mid, Southbound-eligible, high ADV only                                               | Monthly or quarterly; 1–3 month holding                       | There are investable Hong Kong high-dividend/low-volatility index constructions focused on liquid, Southbound-eligible names, but direct recent factor-premium evidence is much thinner than for US or China A. ([hsi.com.hk][9])                                                                                                                                                                                | HK liquidity and foreign-flow conditions can dominate factor behavior; treat as exploratory until your platform validates net returns.                                                   |
|    7 | **Raw Alpha101 / Qlib158 / GTJA191 brute-force factor mining**               | **Tier C unless validated**        | China A for GTJA-style signals; US only as a robustness test; HK with strict liquidity                          | Depends on signal; many are short horizon                     | Alpha101’s original paper is old and short-horizon, with holding periods around 0.6–6.4 days; that is inherently cost-sensitive. ([arXiv][10]) Recent AI-alpha work also reports Alpha158/LightGBM-style features showing severe decay in S&P 500 tests. ([arXiv][11])                                                                                                                                           | Use these as a hypothesis library, not a “factor premium” library. Cluster, neutralize, penalize turnover, and apply DSR/PBO before believing anything.                                  |

---

## Live-vs-decayed status by factor category

### Momentum

**Current status: live, but crowded and crash-prone.** Recent evidence is unusually favorable for US and global large-cap momentum, but also unusually risky. J.P. Morgan describes momentum’s recent run as the best multi-year stretch since the dot-com era and flags the widest dispersion within momentum since 1990, which increases crash risk. ([J.P. Morgan][1]) S&P also reported a historically strong April 2026 rebound in its US momentum indices. ([Indexology Blog][8])

For your platform, momentum should be tested as **risk-adjusted 12-1 momentum**, residual momentum, earnings-revision momentum, and quality-filtered momentum. Avoid pure top-decile price momentum without valuation, liquidity, and crowding diagnostics.

**China A caveat:** classic global momentum is much weaker there. MSCI explicitly says China A’s factor leadership differs from global norms, with low-volatility and high-dividend-yield standing out more than momentum. ([MSCI][3]) A 2026 China momentum paper also argues classic momentum is absent or fragile in China because attention-driven buying can reverse outside news days. ([Yuchen XU][12])

---

### Value

**Current status: credible and relatively strong, especially in the US and China A.** J.P. Morgan’s 2Q 2026 view says value is attractive globally and particularly in the US, even after recent positive quarters. ([J.P. Morgan][1]) In China A, Premia’s Q1 2026 review says the rotation from growth to value continued and that value flourished during the quarter. ([premia-partners.com][4])

Best implementation: sector-neutral book-to-price / earnings-yield / cash-flow-yield / dividend-yield composite, with profitability and leverage screens. In China, dividend yield and shareholder-return proxies appear more relevant than a naive US-style book-to-market factor.

---

### Quality / profitability

**Current status: credible as a combination factor, less compelling as a standalone timing bet.** J.P. Morgan says quality had its worst 12 months since COVID but that valuations are now compelling, especially in the US. ([J.P. Morgan][1]) SSGA similarly argues quality tends to help in weak or uncertain markets, while it lagged during the strong 2025 bull market. ([SSGA][7])

For research, I would split “quality” into at least four sleeves: profitability, earnings stability, accruals/accounting quality, and leverage. Do not assume Qlib/GTJA “quality-ish” technical proxies are equivalent to audited fundamental profitability.

---

### Low-volatility / low-risk

**Current status: regionally strong in China A, defensive but cyclical elsewhere.** MSCI’s China A work says low-volatility and high-dividend-yield have been unusually persistent winners in China A. ([MSCI][3]) Premia also says low risk flourished in Q1 2026 as risk appetite shifted. ([premia-partners.com][4]) SSGA’s broader global view is more conditional: low-volatility tends to help in weak markets but lags in strong bull markets. ([SSGA][7])

Best test: low-vol + value/dividend, not low-vol alone. Low-vol alone can become an expensive bond-proxy trade.

---

### Size

**Current status: weak as a standalone factor; useful as a control.** In US large caps, size is not a deployable edge for your stated universe. In China A, small caps were strong in Q1 2026, but Premia links that partly to AI adoption, retail sentiment, and policy expectations rather than a clean structural size premium. ([premia-partners.com][4]) Acadian’s China work also warns that retail surges can favor high-risk, smaller, more thematic names temporarily. ([acadian-asset.com][5])

Use size mostly for neutralization, capacity control, and regime diagnostics.

---

### Short-term reversal

**Current status: plausible but fragile.** Recent academic work argues short-term reversal still persists globally when measured properly as firm-specific reversal rather than mixing firm and industry reversal. ([SSRN][6]) But this is exactly the kind of factor that can disappear after spread, impact, taxes, borrow, and execution delay.

This is a better candidate for **liquid China A and US large-cap residual reversal overlays** than for broad, high-turnover long/short portfolios.

---

### Volume, liquidity, and microstructure factors

**Current status: highest implementation risk.** These are often not “premia” in the same sense as value or quality; they are compensation for providing liquidity, bearing execution risk, or exploiting temporary pressure. That means they can look great gross and fail net.

For GTJA191 / Alpha101-style volume-price factors, require all of the following before promotion: net returns after impact, capped ADV participation, realistic delay, stable performance across subperiods, no dependence on untradeable limit-up/limit-down names, and a demonstrable edge after removing market, sector, beta, size, and volatility exposure.

---

## Regional conclusions

### US large caps

The US is the best universe for **quality + value + momentum combinations**, not for raw short-horizon alpha mining. S&P’s QVM evidence and J.P. Morgan’s 2026 factor views both support this: momentum has worked, value remains attractive, and quality looks inexpensive after lagging. ([Indexology Blog][2])

Recommended first US test:

* Universe: S&P 500 or Russell 1000 common stocks, ex-ADRs if desired.
* Factors: value, profitability-quality, residual/risk-adjusted momentum, low-vol as risk control.
* Rebalance: monthly.
* Holding: 1–3 months for momentum composite; 3–6 months for value-quality.
* Portfolio: sector-neutral, beta-controlled, liquidity-capped, long/short and long-only versions.

---

### China A-shares

China A is the best universe for your **GTJA191-style library**, but not because every GTJA signal is a live premium. The strongest recent evidence favors **low-volatility / low-risk, dividend/value, and China-specific regime adaptation**. MSCI says China A factor leadership differs from global norms; Premia says value and low risk led Q1 2026; Acadian says retail surges can temporarily invert normal factor behavior. ([MSCI][3])

Recommended first China A test:

* Universe: CSI 300 + CSI 500, or Stock Connect large/mid names.
* Exclude: ST stocks, suspended names, very low ADV, recent IPOs, limit-locked names where execution is unrealistic.
* Factors: low-vol, high dividend/value, profitability, residual reversal, liquidity pressure, retail-crowding proxies.
* Rebalance: monthly for core factors; weekly/monthly for short-term reversal tests.
* Holding: 1–3 months for low-risk/value; 5–20 days for residual reversal/liquidity, only if costs are modeled harshly.

---

### Hong Kong equities

Hong Kong has the weakest recent direct factor evidence of the three. There are high-dividend/low-volatility index constructions for Hong Kong and Southbound-eligible equities, but that is not the same as proof of a durable live premium. ([hsi.com.hk][9]) Hong Kong has also had notable liquidity and flow issues in recent years, which can dominate factor backtests. ([Impact Factors - HKU Business School -][13])

Recommended HK test:

* Universe: Hang Seng Composite large/mid, Southbound-eligible, high-ADV names.
* Factors: dividend yield, value, low-volatility, quality/profitability, liquidity.
* Rebalance: monthly or quarterly.
* Holding: 1–3 months.
* Caveat: use conservative capacity assumptions and avoid microcap factor mining.

---

## Momentum right now: good time or bad time?

My judgment: **good time to study momentum, bad time to run it naked.**

The evidence says momentum is still live: S&P reported strong 2026 momentum index performance, and J.P. Morgan says momentum led recent factor gains. ([Indexology Blog][8]) But the same J.P. Morgan report says the run is historically extended and internally crowded, with dispersion inside momentum at an extreme. ([J.P. Morgan][1]) MSCI’s crowding research also warns that crowded high-momentum names can be vulnerable, while uncrowded high-momentum names perform better. ([MSCI][14])

So I would test momentum only in these forms:

* residual momentum, not raw return;
* 12-1 or 6-1 momentum, excluding the most recent month;
* risk-adjusted momentum;
* momentum + quality;
* momentum + value/crowding filter;
* momentum with explicit crash-risk diagnostics after sharp market rebounds.

---

## Factor combinations with the best current evidence

The strongest current combination is **quality + value + momentum** in US large caps. S&P’s 2026 QVM research argues that quality is defensive, value is procyclical, and momentum captures trend persistence, so the combination is more resilient than any single factor. ([Indexology Blog][2])

The strongest China combination is **low-risk / low-vol + dividend/value + profitability**, with a retail-regime filter. MSCI’s China research highlights low-volatility and high-dividend-yield, while Acadian’s China work shows that retail surges can disrupt normal factor ordering. ([MSCI][3])

The most interesting short-horizon combination is **residual reversal + liquidity pressure + volatility control**. Recent short-term reversal research supports the idea that reversal is not dead if measured correctly, but this should be treated as a net-cost execution strategy rather than a clean factor premium. ([SSRN][6])

---

## Implementation pitfalls specific to 2024–2026 research

### 1. Point-in-time data is non-negotiable

Use filing-date availability, not fiscal-period dates. For price-volume factors, use only data known at the rebalance timestamp. For China A, explicitly model suspensions, limit-up/limit-down constraints, ST status, IPO seasoning, and historical Stock Connect / index membership where relevant.

Recent point-in-time backtesting work continues to emphasize that look-ahead bias means using information that was not available at the time of trading, and survivorship bias means testing only names that survived to the present. ([MDPI][15])

### 2. Do not use today’s universe historically

For US, do not backtest on today’s S&P 500 constituents. For China A, do not use today’s CSI 300/500 or Stock Connect list backward. For HK, do not ignore delisted, suspended, or merged names. Emerging-market survivorship effects can be large; recent work on small-cap emerging-market data finds survivor-only databases can materially overstate returns and Sharpe ratios. ([arXiv][16])

### 3. Report net, not just IC

For every factor, report:

* rank IC and IC decay;
* gross decile spread;
* net decile spread after costs;
* one-way and two-way turnover;
* ADV participation;
* capacity at target AUM;
* drawdown and crash months;
* beta, sector, size, volatility, and liquidity exposures.

Transaction-cost-aware factor research argues that factor construction should explicitly trade off expected exposure against trading costs, rather than optimizing gross signal strength alone. ([Lancaster University][17])

### 4. Treat high-turnover factors as guilty until proven innocent

This especially affects Alpha101, Qlib158 technicals, GTJA191 volume-price factors, and short-term reversal. MSCI’s China A momentum factsheet shows very high turnover compared with China A quality, illustrating why momentum-style implementation can be much more cost-sensitive than fundamental quality. ([MSCI][18])

### 5. Correct for the factor zoo

Your platform already applies Deflated Sharpe Ratio / Probability of Backtest Overfitting logic; keep doing that. For this library, I would additionally:

* cluster highly correlated factors before testing;
* pre-register factor families before running grid searches;
* record every trial, not just winners;
* use purged and embargoed cross-validation;
* run Combinatorial Purged Cross-Validation where possible;
* compute DSR/PBO at the *family-selection* level, not just the final portfolio level.

CFA Institute material by López de Prado continues to emphasize that many published anomalies are factor-zoo artifacts unless corrected for multiple testing, backtest overfitting, and implementation costs. ([CFA Institute Research and Policy Center][19])

---

## AI-era market structure: what has actually changed?

There is credible evidence that AI and LLMs are changing trading workflows, but **not yet strong evidence that classic value, quality, low-volatility, and momentum premia have permanently changed form after 2023**. The stronger claim is narrower: AI has likely increased speed, thematic crowding, dispersion, and stress fragility.

The IMF warned in 2024 that AI-driven trading could make markets faster and more efficient while also increasing trading volumes and volatility during stress. ([IMF][20]) AFM’s 2026 work similarly says AI is reshaping pre-trade, execution, and post-trade workflows while introducing new market-integrity risks. ([afm.nl][21])

The new anomalies worth investigating are therefore not “LLM factor #37.” They are:

1. **AI-theme dispersion / disruption exposure**: winners and losers from AI adoption, capex, margin pressure, and valuation risk.
2. **Retail-options / call-flow crowding overlays** in US mega-cap tech and semiconductors.
3. **China A retail-surge regimes**, including DeepSeek/AI-driven optimism episodes, where normal value/quality/low-risk relationships can temporarily invert. ([acadian-asset.com][5])
4. **LLM-generated factor crowding risk**: recent LLM-alpha work warns that models may rediscover homogeneous factors, increasing crowding and decay rather than producing genuinely new alphas. ([arXiv][22])

Treat LLM-discovered alphas as **Tier C until independently validated** with point-in-time data, locked prompts/models, no post-hoc selection, net costs, and DSR/PBO.

---

## How I would map this to your existing factor families

**GTJA191**: prioritize for China A only. Test volume-price, reversal, volatility, liquidity, and retail-flow proxies, but require harsh cost modeling and regime splits.

**Qlib158**: useful as a generic technical feature set, but not sufficient evidence of live premia. Treat it as a feature benchmark, especially for China A and HK, not a deployable alpha book.

**Alpha101**: most likely to fail net-cost validation in US large caps because many signals are short-horizon and turnover-heavy. Use only in liquid universes with capacity caps.

**Academic set**: likely highest signal-to-noise if it includes value, profitability, quality, low-volatility, and conservative investment. These should be your anchor factors.

---

## What still needs independent validation before trusting any result

Before any factor is considered “live” in your platform, I would require:

1. Out-of-sample validation by date and region.
2. Point-in-time universe and fundamentals.
3. Net-cost returns using spread, commissions, taxes, borrow, slippage, and market-impact assumptions.
4. Capacity and turnover limits.
5. Neutralization tests: market beta, sector, size, volatility, liquidity, country/share-class where relevant.
6. Crisis-period diagnostics, especially momentum crashes and China retail-surge regimes.
7. DSR/PBO after accounting for all tested factors and parameter variants.
8. Paper-trading or shadow-live validation before capital allocation.

---

## The most important thing I found that your questions did not directly ask

The most important extra finding is that **China A factor performance may be regime-inverted by retail participation bursts**. Acadian’s 2026 work says retail surges happen roughly twice a year on average and can flip long-run factor relationships; value loses about a quarter of its historical edge during these episodes, while high-volatility, high-risk, and smaller thematic names can temporarily lead. ([acadian-asset.com][5])

That matters more than the usual “China factors differ from US factors” point. It means your platform should not just test “GTJA191 works / does not work in China.” It should test whether each factor works **conditional on retail-surge, policy, AI-theme, and liquidity regimes**. A factor that looks decayed unconditionally may be useful once regime-conditioned, and a factor that looks strong unconditionally may be mostly compensation for being short a retail mania.

[1]: https://am.jpmorgan.com/us/en/asset-management/institutional/insights/portfolio-insights/asset-class-views/factor/ "
        
        
        
        Factor Views 2Q 2026
        
        
         \| J.P. Morgan Asset Management
    "
[2]: https://www.indexologyblog.com/2026/05/29/new-tools-for-tracking-sector-liquidity/ "New Tools for Tracking Sector Liquidity – Indexology® Blog | S&P Dow Jones Indices"
[3]: https://www.msci.com/research-and-insights/paper/are-you-really-capturing-the-right-factors-unlocking-deeper-insights-in-china-a-share-factor-investing "Are You Really Capturing the Right Factors? Unlocking Deeper Insights in China A-Share Factor Investing | MSCI"
[4]: https://www.premia-partners.com/en/insight/china-a-shares-q1-2026-factor-review "China A-shares Q1 2026 factor review | Premia Partners"
[5]: https://www.acadian-asset.com/investment-insights/equities/quick-take-retail-surges-and-factor-inversions-in-china-a-shares "Quick Take: Retail Surges and Factor Inversions in China A-Shares | Acadian Asset Management"
[6]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6630998&utm_source=chatgpt.com "Short-Term Reversal Persists Globally-If Properly Measured"
[7]: https://www.ssga.com/us/en/institutional/insights/systematic-active-monthly-january-2026 "Quality’s role amid equity market uncertainty | State Street"
[8]: https://www.indexologyblog.com/2026/05/08/sp-momentum-indices-shine-in-april-rally/?utm_source=chatgpt.com "S&P Momentum Indices Shine in April Rally"
[9]: https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/methodologies/IM_hshylve.pdf?utm_source=chatgpt.com "Hang Seng SCHK High Dividend Low Volatility Index"
[10]: https://arxiv.org/pdf/1601.00991?utm_source=chatgpt.com "101 Formulaic Alphas"
[11]: https://arxiv.org/html/2502.16789v2?utm_source=chatgpt.com "AlphaAgent: LLM-Driven Alpha Mining with Regularized ..."
[12]: https://yuchenxu.com/paper/Momentum.pdf?utm_source=chatgpt.com "Dissecting Momentum in China - Yuchen XU"
[13]: https://impact.hkubs.hku.hk/reviving-hong-kongs-stock-market-key-challenges-and-strategic-solutions/?utm_source=chatgpt.com "Reviving Hong Kong's Stock Market: Key Challenges and ..."
[14]: https://www.msci.com/research-and-insights/blog-post/crowd-control-momentum-and-concentrated-markets?utm_source=chatgpt.com "Crowd Control, Momentum and Concentrated Markets"
[15]: https://www.mdpi.com/2227-7390/14/12/2182?utm_source=chatgpt.com "Point-in-Time Backtesting of Momentum-Trend Equity ..."
[16]: https://arxiv.org/abs/2603.19380?utm_source=chatgpt.com "Survivorship Bias in Emerging Market Small-Cap Indices: Evidence from India's NIFTY Smallcap 250"
[17]: https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-163-Federico-Baldi-Lanfranchi.pdf?utm_source=chatgpt.com "Transaction-cost-aware Factors"
[18]: https://www.msci.com/indexes/index/703813/msci-china-a-onshore-momentum-index "MSCI China A Onshore Momentum Index"
[19]: https://rpc.cfainstitute.org/sites/default/files/docs/research-reports/rf_lopezdeprado_causalityprimer_online.pdf?utm_source=chatgpt.com "Causality and Factor Investing: A Primer"
[20]: https://www.imf.org/en/blogs/articles/2024/10/15/artificial-intelligence-can-make-markets-more-efficient-and-more-volatile?utm_source=chatgpt.com "Artificial Intelligence Can Make Markets More Efficient— ..."
[21]: https://www.afm.nl/~/profmedia/files/rapporten/2026/ai-in-capital-markets-balancing-innovation-and-integrity.pdf?utm_source=chatgpt.com "AI in Capital Markets: Balancing Innovation and Integrity"
[22]: https://arxiv.org/abs/2502.16789?utm_source=chatgpt.com "AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay"
