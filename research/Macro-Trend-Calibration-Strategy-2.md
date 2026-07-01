## Bottom line

Your failed SPY+GLD test is not surprising. A daily **EMA(10,30)** crossover is much faster than the public, institutional macro-trend templates I could verify. The clearest disclosed “live CTA proxy” construction I found is the **SG Trend Indicator**, which uses a **20/120-day moving-average crossover** across 55 liquid futures and targets 15% annualized volatility. AQR’s best-known managed-futures replication uses an equal blend of **1-, 3-, and 12-month** time-series momentum signals across 67 markets. Those are much slower, and more diversified, than your crypto-tuned fast crossover. ([Société Générale][1])

The practical takeaway: for macro assets, start with a **multi-speed ensemble centered on 3–12 month trend**, keep only a minority fast sleeve for crisis responsiveness, and do not expect SPY+GLD alone to behave like a diversified CTA portfolio.

---

# 1. What real trend-following funds / indexes actually disclose

Public fund-level signal details are usually proprietary. The credible public numbers come mostly from **index methodology documents**, **manager research disclosures**, and **CTA-replication papers**.

| Evidence tier                                     |                                            Source type | Disclosed construction                                                                                                                                                                                       |                                                                                                    Implementable number |
| ------------------------------------------------- | -----------------------------------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------: |
| **Tier A: live benchmark proxy**                  |                         SG Trend Indicator methodology | Daily moving-average crossover, always long/short, 55 liquid futures across equity indices, currencies, fixed income, and commodities; 15% vol target; equal 25% sector risk weights.                        |                                                **20/120 trading-day moving-average crossover**. ([Société Générale][1]) |
| **Tier A: live manager universe benchmark**       |                 SG Trend Index constituent methodology | Tracks the largest trend-following CTAs open to investment; 2026 constituents include AlphaSimplex, AQR, Aspect, Graham, iSAM, Lynx, Man AHL, PIMCO Trends, Transtrend, and Winton.                          |                Not signal-disclosed, but this is the live-manager benchmark to compare against. ([Société Générale][2]) |
| **Tier A/B: practitioner-academic replication**   | AQR “Century of Evidence on Trend-Following Investing” | Equal-weighted combination of 1-, 3-, and 12-month time-series momentum across 67 markets, vol-scaled to 10% annualized.                                                                                     |                                                                       **1/3/12-month lookback blend**, equal-weighted.  |
| **Tier B: actual manager disclosure**             |                               Man AHL “Need for Speed” | Uses double EWMA moving-average crossover models; multiple speeds chosen to span trend horizons and reduce correlation; slower speeds have higher risk-adjusted returns, faster speeds improve crisis alpha. |                                  Multi-speed EWMA crossover family; exact pairs not fully disclosed. ([HedgeNordic][3]) |
| **Tier B: index methodology**                     |                KFA MLM / Mount Lucas-style trend index | Pure trend-following using price versus a long-term moving average across commodities, fixed income, and currencies; expected vol around 15%; notably excludes equities.                                     | “Long-term moving average,” exact lookback less transparent in the public source I found. ([engage.kraneshares.com][4]) |
| **Tier B: manager education / industry practice** |                                  Graham Capital primer | Moving-average and breakout models are described as two of the most prominent models used by trend followers; signals are generally run at multiple lengths and vol-scaled.                                  |                                    Supports MA + breakout families, not exact windows. ([Graham Capital Management][5]) |

**Key implication:** the strongest public anchors are **20/120 days** and **1/3/12 months**. Your **10/30 daily EMA** is closer to a short tactical system than a mainstream macro-trend engine.

---

# 2. Current regime: 2022 through now

Trend-following has had a **very uneven but still structurally relevant** period since 2022.

**2022 was highly favorable.** Inflation, rate shocks, bond bear trends, currency trends, and commodity moves created one of the best recent CTA environments. Cambridge Associates cites **SG Trend +27.4% in 2022**, while global equities were down. ([Cambridge Associates][6])

**2023–mid-2025 became difficult.** The same source says SG Trend suffered a **-20.4% drawdown from May 2024 to May 2025**, driven by abrupt reversals, range-bound price action, and lack of persistent trends. Man also reported that trend following’s rolling 12-month loss through April 2025 was about **-18.6%**, unusually severe for SG Trend history. ([Cambridge Associates][6])

**Late 2025 recovered materially.** Bentley Reid reported that trend ended 2025 with seven consecutive positive months, with Q4 helped by **long metals, long equities, and short dollar** positioning. It also noted that the SG Trend drawdown to the May 2025 low was about **-21.8%**, one of the deepest since 1999. 

**As of July 1, 2026, the live benchmarks are positive YTD.** BarclayHedge/SG data shows **SG Trend +8.52% YTD** and **SG CTA +8.99% YTD**, both estimated as of July 1, 2026. ([portal.barclayhedge.com][7])

By asset class, the recent pattern looks roughly like this:

| Asset class          | 2022-present trend regime                                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Equities**         | 2022 short trend worked; 2023–2026 mostly long equity trend helped, but tariff/risk reversals in 2025 created whipsaw.                            |
| **Gold / metals**    | One of the more favorable recent sectors, especially into late 2025, but gold has recently corrected from extreme highs.                          |
| **Government bonds** | Strong opportunity in 2022 from short bonds / rising yields; more mixed afterward as central-bank expectations reversed repeatedly.               |
| **FX**               | USD strength and then USD weakness created opportunities, but FX has been reversal-prone; late 2025 short-dollar positioning helped trend funds.  |

---

# 3. Multi-speed ensemble evidence

The evidence strongly favors **multi-speed ensembles**, not one optimized crossover.

AQR’s long-run replication uses an equal blend of **1-, 3-, and 12-month** time-series momentum. This is not a cosmetic detail: the whole construction is deliberately multi-horizon, cross-asset, vol-scaled, and then compared across more than a century of market history. 

Man AHL’s research reaches the same practical conclusion from a live-manager perspective: trend returns from different speeds have been positive over the long term and relatively lowly correlated with each other. Faster signals improve crisis response and skew, while slower signals tend to have better Sharpe after costs. Their explicit conclusion is effectively: trade multiple speeds, but understand the speed trade-off. ([HedgeNordic][3])

A recent CTA-replication paper also frames live CTA behavior as a mixture of **short- and long-term trend factors**, not a single horizon. ([arXiv][8])

**My read:** for SPY/GLD/bonds/FX, your default should not be “find the best MA pair.” It should be “anchor the system to a robust speed stack,” then test whether an asset-specific tilt is justified.

---

# 4. Crypto trend vs macro trend diversification

This is where the evidence is weakest.

I found credible evidence that **traditional macro trend following** has historically had low correlation to stocks and bonds and has often performed well in extended equity bear markets. AQR reports positive performance in many of the worst 60/40 drawdowns, while also warning that fast crashes like 1987 are different because they do not give slower trend systems time to adapt. 

I found credible evidence that **crypto trend-following can work**, but the direct literature on **crypto trend-following return correlation versus macro CTA return correlation during risk-off events** is still thin. A 2024 crypto trend-following study finds positive crypto trend results but emphasizes that transaction costs matter. Another Bitcoin correlation paper finds that Bitcoin’s correlation with U.S. equity indices has intensified in some regimes, peaking as high as **0.87 in 2024**. ([SSRN][9])

So the honest conclusion is:

**Crypto trend-following may diversify macro trend-following, but that is not guaranteed during the exact windows you care about.** Raw crypto increasingly behaves like high-beta risk in some deleveraging regimes. The diversification benefit comes only if your crypto trend system can flip flat/short quickly enough before or during the drawdown.

For your own testing, I would compute event-conditional correlations between:

* your BTC+SOL trend returns,
* SG Trend / SG CTA,
* DBMF or KMLM as investable proxies,
* SPY drawdown windows,
* BTC drawdown windows,
* joint risk-off windows where both equities and crypto fall.

Do not rely on full-sample correlation alone.

---

# 5. Realistic performance benchmarks

Use these as priors before backtesting:

| System scope                                             |                                                                                                                                                                                           Credible expectation |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
| **Single-market macro trend**                            |                                                Noisy; gross Sharpe around **0.2–0.4** is already respectable. AQR found the average individual market trend Sharpe was about **0.4 gross** across 67 markets.  |
| **Diversified macro trend, 50+ markets, 10% vol target** |                  Long-run net Sharpe around **0.3–0.6** is credible; above **1.0 net** over long samples should be treated skeptically unless costs, roll, financing, and capacity are very carefully modeled. |
| **Drawdown at 10–15% vol**                               |                                                                 Expect **15–25%** drawdowns. AQR reports trend drawdowns up to about **25%**, and SG Trend recently experienced roughly **20–22%** drawdowns.  |
| **Win rate**                                             | I did not find a reliable recent public live-CTA win-rate benchmark. Treat **monthly hit rate above 55–60%** as suspicious; trend systems usually earn through convexity and large winners, not high hit rate. |
| **Crisis alpha**                                         |        More reliable in **slow, persistent bear markets** than in instant crashes. AQR explicitly notes trend performed well in bear markets that unfolded over months, but not necessarily in rapid crashes.  |

A useful sanity check: the TTU Trend Following Index reported long-run CAGR around **7.04%** with max drawdown about **20.81%**, while SG Trend had max drawdown around **20.61%** in the cited period. ([Top Traders Unplugged][10])

---

# 6. Current macro backdrop as of July 1, 2026

**Rates:** the Fed’s target range is **3.50%–3.75%** after the June 17, 2026 meeting. Reuters polling in late June found most economists expected the Fed to hold that range for the rest of the year, with inflation still a concern. ([Federal Reserve][11])

**Equities:** U.S. equity valuations are elevated. FactSet reported the S&P 500 forward 12-month P/E around **20.9–21.0** in spring 2026, above both 5- and 10-year averages. MarketWatch reported the S&P 500 gained about **9.5% in the first half of 2026**, with tech again dominating. ([insight.factset.com][12])

**Gold:** the structural backdrop is still supportive because central banks continue to accumulate gold. The World Gold Council reported Q1 2026 central-bank purchases of **244 tonnes**, and its 2026 survey found **89%** of reserve managers expected global central-bank gold holdings to rise over the next 12 months. But near term, Reuters reported gold around **$4,010/oz** on July 1, 2026, near a seven-month low after a quarterly loss, pressured by yields, dollar strength, and ETF outflows. ([World Gold Council][13])

**Implication for trend-following right now:**
Equity and gold signals may still have long-term trend support, but both are vulnerable to sharp valuation/rate-driven reversals. Bonds are especially sensitive to policy repricing. FX looks tradable, but likely noisy. This argues for a **multi-speed, volatility-normalized ensemble**, not a single fast crossover.

---

# 7. Recommended starting parameterization

This is what I would use as a credibility-tiered starting grid before doing any optimization.

## Tier 1: highest-credibility baseline

Use this for every macro asset first.

| Component      |                                                    Signal | Weight |
| -------------- | --------------------------------------------------------: | -----: |
| Fast           |   1-month time-series momentum, about **21 trading days** |    25% |
| Medium         |   3-month time-series momentum, about **63 trading days** |    25% |
| Core CTA proxy |                   **20/120-day moving-average crossover** |    25% |
| Slow           | 12-month time-series momentum, about **252 trading days** |    25% |

Sources: AQR’s **1/3/12-month** blend and SG Trend Indicator’s **20/120-day** crossover. 

This avoids the biggest mistake in your SPY+GLD test: letting a **10/30-day** signal dominate assets whose trends often mature over quarters, not weeks.

---

## Tier 2: asset-class tilts

| Asset class          | Starting signal mix                                         | Rationale                                                                                         |
| -------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Equity index**     | 20% 1-month, 30% 3-month, 25% 20/120 MA, 25% 12-month       | Equities can crash quickly, so keep some fast crisis response, but do not make fast the core.     |
| **Gold**             | 10% 1-month, 30% 3-month, 30% 20/120 MA, 30% 12-month       | Gold macro trends often persist, but reversals around real rates and USD can be sharp.            |
| **Government bonds** | 10–15% 1-month, 30% 3-month, 30% 20/120 MA, 25–30% 12-month | Rate cycles are slow; fast bond signals can get chopped up by central-bank repricing.             |
| **FX**               | 20% 1-month, 30% 3-month, 25% 20/120 MA, 25% 12-month       | FX trends can be policy-driven but noisy; medium/slow should dominate, with a modest fast sleeve. |

These weights are **engineering recommendations**, not directly disclosed fund weights. The sourced numbers are the lookbacks themselves.

---

## Tier 3: alternatives worth testing

| Alternative                              | Concrete implementation                                                                                    | Why consider it                                                                                                                                                               |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Volatility-scaled breakouts**          | 63-day and 252-day high/low breakout, scaled by realized volatility                                        | Breakout models are commonly used by trend followers alongside moving averages; use the same 3- and 12-month anchors as AQR’s trend windows. ([Graham Capital Management][5]) |
| **Normalized trend strength**            | Position proportional to z-score of price minus 120-day moving average, capped at target risk              | Avoids binary flip behavior around the moving average.                                                                                                                        |
| **Carry-augmented trend**                | Add FX carry, bond roll-down/carry, commodity curve carry where relevant; keep trend as the primary signal | Man’s CTA replication work explicitly treats carry/no-carry as one of the dimensions driving manager dispersion. ([man.com][14])                                              |
| **Correlation / trend-breadth dampener** | Reduce gross exposure when cross-asset correlations rise and trend breadth narrows                         | AQR found trend performance is worse when cross-market correlations are high, because diversification falls and vol targeting cuts positions.                                 |
| **Risk-off fast sleeve**                 | Small 1-month or 20/60-day sleeve applied mainly to equity index and bonds                                 | Man AHL finds faster trend improves crisis responsiveness, but at a Sharpe/cost trade-off. ([HedgeNordic][3])                                                                 |

I would not start by optimizing MA pairs per asset. Start with these institutional anchors, then test whether each asset earns the right to deviate.

---

# Credibility-tiered final recommendation

**Most defensible starting system:**

* Universe: equity index, gold, government bonds, FX; ideally more than one instrument per sleeve.
* Signal: equal-weighted blend of **1-month, 3-month, 12-month time-series momentum** plus **20/120-day MA crossover**.
* Vol target: 10% portfolio vol for research comparability; 15% only if you are comfortable with CTA-like drawdowns.
* Capital allocation: risk parity across asset classes, but cap correlated exposures.
* Dampener: based on realized volatility, trend breadth, and average cross-asset correlation.
* Expected long-run net Sharpe: **0.3–0.6**.
* Expected max drawdown: **15–25%** at institutional CTA-style vol.
* Red flag: if your SPY+GLD-only macro system shows Sharpe above **1.0** over 20 years after realistic costs, assume overfit until proven otherwise.

---

# The most interesting thing I found

The most important underappreciated point is that **trend-following does not mainly fail because the lookback is “wrong”; it often fails because too many markets start behaving like the same market.**

AQR’s century-scale evidence found that trend-following performance is worse when cross-market correlations are high. That matters directly for your portfolio-level exposure dampener. You may want the dampener to respond not only to “chop” or volatility, but also to **trend crowding, trend breadth, and cross-asset correlation concentration**. In other words: the next upgrade may not be a better EMA pair. It may be a better answer to: “Are these independent trends, or just one global macro trade wearing four labels?”

[1]: https://wholesale.banking.societegenerale.com/fileadmin/indices_feeds/SG_Trend_Indicator_Methodology_Summary.pdf "PowerPoint Presentation"
[2]: https://wholesale.banking.societegenerale.com/fileadmin/indices_feeds/SG_Trend_Index_Constituents.pdf "PowerPoint Presentation"
[3]: https://hedgenordic.com/2023/03/the-need-for-speed-in-trend-following-strategies/ "The Need for Speed in Trend-Following Strategies - HedgeNordic"
[4]: https://engage.kraneshares.com/s/c3e5b938/managed-futures-etf-kmlm-presentation/?utm_source=chatgpt.com "Managed Futures ETF Overview | KMLM"
[5]: https://www.grahamcapital.com/blog/trend-following-primer/?utm_source=chatgpt.com "Trend-Following Primer"
[6]: https://www.cambridgeassociates.com/insight/does-trend-followings-recent-struggle-signal-that-the-strategy-is-structurally-broken/?utm_source=chatgpt.com "Does Trend-Following's Recent Struggle Signal That the ..."
[7]: https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=SG-Prime-Services-Indices&indexName=SG-Trend-Index&utm_source=chatgpt.com "SG Trend Index - BarclayHedge Indices"
[8]: https://arxiv.org/abs/2507.15876?utm_source=chatgpt.com "Re-evaluating Short- and Long-Term Trend Factors in CTA Replication: A Bayesian Graphical Approach"
[9]: https://papers.ssrn.com/sol3/Delivery.cfm/4551518.pdf?abstractid=4551518&mirid=1&utm_source=chatgpt.com "Trend-following Strategies for Crypto Investors"
[10]: https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/?utm_source=chatgpt.com "Trend Following Performance Report — June, 2025"
[11]: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260617a.htm?utm_source=chatgpt.com "Federal Reserve issues FOMC statement"
[12]: https://insight.factset.com/sp-500-earnings-season-update-april-17-2026?utm_source=chatgpt.com "S&P 500 Earnings Season Update: April 17, 2026"
[13]: https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-q1-2026?utm_source=chatgpt.com "Gold Demand Trends: Q1 2026"
[14]: https://www.man.com/insights/deep-dive-trend-following?utm_source=chatgpt.com "A Trend Following Deep Dive: The Dynamics of Dispersion"
