## Executive conclusion

What you found is **real and important**, but I would not call it a single well-standardized named anomaly. The closest rigorous labels are **sampling-frequency sensitivity**, **temporal aggregation / time-bar aggregation effects**, **bar-construction risk**, and, in backtesting terms, **implementation-detail or protocol fragility**. In crypto, the issue is amplified because “daily close” is not anchored to an exchange session the way it is in equities or futures.

Your practical interpretation is also right: a 6-offset ensemble converging toward the **average** single-offset Sharpe is exactly what I would expect. It is a robustness / nuisance-parameter averaging method, not a free alpha source, unless one offset corresponds to a real, persistent liquidity or behavioral mechanism.

---

## 1. Is this documented or named?

I did **not** find a canonical academic term specifically called “daily candle close-time sensitivity” or “bar-boundary effect” for crypto EMA crossovers. The phenomenon sits at the intersection of several established literatures:

**Sampling-frequency sensitivity of technical rules.** Hudson, McGroarty, and Urquhart’s 2017 paper *Sampling frequency and performance of different types of technical trading rules* directly studies how technical trading rules change when the sampling frequency changes; they find that trend-following rules deteriorate at higher frequencies while mean-reversion rules improve, attributing part of the effect to high-frequency noise. This is not exactly your offset experiment, but it is the closest “technical rules are fragile to how prices are sampled” literature. ([CentAUR][1])

**Parameter fragility in crypto technical trading.** Hudson and Urquhart’s 2021 *Technical Trading and Cryptocurrencies* notes that moving-average rules are among the most studied crypto rules and that different technical-rule parameters can generate sharply contrasting returns. They also find that Bitcoin may be less profitable out of sample than some smaller cryptocurrencies, consistent with greater efficiency in the most liquid asset. ([Springer Link][2])

**Financial data structures / bar construction.** Lopez de Prado’s *Advances in Financial Machine Learning* frames this under the choice of data structure: time bars, tick bars, volume bars, dollar bars, imbalance bars, and run bars are different samplings of the same underlying market process. That is very close to your concern: the “daily bar” is a modeling choice, not a natural object in a 24/7 market. ([그대안의작은호수 | 살아온 날의 흔적, 살아갈 날의 기록][3])

**Implementation-risk / backtest-protocol fragility.** A 2026 arXiv paper on implementation risk in portfolio backtesting studies how Sharpe ratios can change sign across different backtest engines, even when the intended strategy is the same. The authors recommend reporting the strategy specification separately from engine-specific outputs and using robustness diagnostics when Sharpe flips across implementation choices. Your candle-close offset is the same kind of nuisance implementation variable. ([arXiv][4])

So the phrase I would use in a paper or internal research note is:

> **Bar-boundary sensitivity of time-aggregated technical signals in continuous markets**

And the literature search terms I would use are:

“sampling frequency technical trading rules,” “temporal aggregation technical analysis,” “financial data structures event bars,” “time bars versus dollar bars,” “implementation risk backtesting Sharpe,” “backtest overfitting technical trading rules,” and “cryptocurrency intraday seasonality liquidity.”

---

## 2. Techniques to make EMA crossover robust to arbitrary daily close timing

### A. Multi-offset signal ensemble

This is the cleanest fix for your exact problem.

Instead of choosing one close time, treat close time as a **nuisance parameter** and average across it. The best implementation is usually not a majority vote on long/flat/short states, but an average of **continuous signal strength**, for example:

[
s_{h,t} = \frac{\text{EMA}*{10,h,t} - \text{EMA}*{30,h,t}}{\sigma_{h,t}}
]

Then combine:

[
s_t = \frac{1}{H}\sum_{h=1}^{H} s_{h,t}
]

and map the combined score into a capped position.

This is consistent with the broader ensemble literature: bagging and ensemble averaging are primarily variance-reduction tools, and simple averaging is often hard to beat because it avoids estimation error from fitting weights. ([SSRN][5])

For your case, I would prefer:

**Best default:** equal-weighted average of continuous normalized EMA-spread signals across offsets.

**Less preferred:** binary voting across offsets.

**Riskier:** Sharpe-weighting offsets, because it turns the close time into another optimized hyperparameter and creates data-snooping risk.

Using 6 offsets every 4 hours is a defensible start. Using 24 hourly offsets is better if computation and data handling are easy. The correct number is not theoretically fixed; I would choose the smallest number where the ensemble signal, turnover, and Sharpe dispersion stabilize.

### B. Avoid daily bars entirely: use intraday EMA with calendar-time decay

A more elegant solution is to compute the EMA on 1-hour or 4-hour bars using a decay constant equivalent to 10 and 30 calendar days. That avoids making the daily close the point at which the signal is created.

For example, instead of “10 daily closes,” define an EMA with a **10-day time constant** evaluated on hourly data. Then rebalance once per day, or continuously with turnover controls. This keeps the economic idea — 10-day versus 30-day trend — while reducing discontinuity from arbitrary daily aggregation.

This does not remove all implementation choices, because you still choose execution time, but it makes the signal much less dependent on one daily OHLC boundary.

### C. Event-based bars: useful, but not a magic fix

Volume bars, dollar bars, tick bars, range bars, and CUSUM bars are designed to sample market activity rather than clock time. Lopez de Prado’s framework explicitly includes dollar bars, imbalance bars, run bars, and related information-driven bars. ([그대안의작은호수 | 살아온 날의 흔적, 살아갈 날의 기록][3])

The best recent crypto-specific evidence I found is Grądzki’s 2025 paper in *Financial Innovation*. It argues that time bars are problematic in continuously active crypto markets because they force decisions at arbitrary clock times, and it compares CUSUM, range, volume, and dollar bars on crypto tick data from 2018 to June 2023. ([Springer Link][6])

The result is nuanced: CUSUM bars combined with triple-barrier labeling outperformed time bars, but volume and dollar bars did **not** consistently improve results in that study. The paper also warns that crypto volume bars can be distorted by wash trading and that thresholds are asset-specific. ([Springer Link][6])

So for your EMA crossover specifically:

* **CUSUM / range bars** are more promising than raw volume or dollar bars.
* You must recalibrate lookbacks, because “10/30 bars” no longer means “10/30 days.”
* Event bars reduce arbitrary clock-boundary risk but introduce **threshold-selection risk**.
* I would not assume they improve out-of-sample crypto trend following unless you validate them walk-forward.

### D. Session-aware bars

There is real evidence that crypto has intraday seasonality despite trading 24/7. Brauneis et al. 2025 study 1,940 crypto pairs across 38 exchanges and find pronounced time-of-day patterns in trading activity, volatility, and liquidity, with a peak around 16:00–17:00 UTC. ([Springer Link][7])

Hansen, Kim, and Kimbrough 2021 also find systematic day-of-week, hour-of-day, and within-hour periodicity in Bitcoin and Ether volatility/liquidity across Coinbase Pro, Binance, and Uniswap, with some patterns linked to algorithmic trading and funding-time effects. ([arXiv][8])

That means a “smarter” daily boundary is not crazy. But I would be careful: choosing the offset with the best Sharpe is data mining. A session-aware boundary should be justified **ex ante**, for example by liquidity, spread, funding, or execution-cost considerations, not by backtested PnL.

---

## 3. Should the 6-offset ensemble average the Sharpes?

Yes, that behavior is expected.

With equal weights, the ensemble’s expected return is approximately the average of the component returns. Its volatility depends on cross-offset correlation:

[
\sigma^2_{\text{ensemble}} = w^\top \Sigma w
]

If the six offset strategies are highly correlated, the ensemble Sharpe will land near the average component Sharpe. If they are less correlated and have similar positive means, the ensemble can exceed the average Sharpe through variance reduction. But it should not be expected to beat the best single offset unless the best offset reflects a real causal feature rather than backtest luck.

The danger is that “best offset” is one more hyperparameter. Bailey and Lopez de Prado’s Deflated Sharpe Ratio and Probability of Backtest Overfitting frameworks are directly relevant here because they adjust for strategy selection across multiple trials. ([PM Research][9])

A smarter combination method may help, but only if it is strongly regularized. I would rank methods this way:

1. **Equal-weight continuous signal average** — best default.
2. **Median or trimmed-mean signal across offsets** — robust to one pathological offset.
3. **Inverse-turnover or inverse-signal-instability weighting** — acceptable if weights are slow-moving and pre-specified.
4. **Sharpe-weighted offsets** — dangerous unless validated with purged walk-forward testing and heavy shrinkage.
5. **Machine-learned offset weights** — likely overfit unless you have far more independent history than daily crypto provides.

A useful diagnostic is to report not only ensemble Sharpe, but also:

* mean Sharpe across offsets,
* median Sharpe across offsets,
* worst-quartile Sharpe,
* offset Sharpe dispersion,
* signal sign-disagreement rate,
* turnover dispersion,
* and PnL correlation across offsets.

For your results, I would treat the **offset-average Sharpe** as the honest baseline, not the best-offset Sharpe.

---

## 4. Why would SOL be much more fragile than BTC?

I did not find a paper specifically saying “Solana EMA signals are more candle-close sensitive than Bitcoin signals.” But your explanation is consistent with known mechanics.

A faster EMA crossover is sensitive when the fast and slow averages are close. Higher volatility creates more marginal crossings and more path-dependence inside the aggregation window. Since SOL has higher daily volatility than BTC in your test, the same 10/30-day EMA pair is effectively a **faster and noisier signal** for SOL than for BTC.

Crypto technical-trading literature also suggests that Bitcoin behaves differently from smaller or less mature crypto assets. Hudson and Urquhart 2021 find that Bitcoin may be less profitable out of sample than other cryptocurrencies, plausibly because it is more liquid and efficient. ([Springer Link][2]) Grądzki 2025 similarly notes that smaller cryptocurrencies may offer more inefficiencies but also bring liquidity and data-quality risks. ([Springer Link][6])

A documented and sensible remedy is not necessarily “one EMA pair for every asset.” Serious trend systems often diversify across lookbacks and normalize signals by volatility. Recent crypto trend-following research also tends to use ensembles or adaptive selection rather than one fixed 10/30 rule: Zarattini, Pagani, and Barbon’s 2025 *Catching Crypto Trends* uses an ensemble of Donchian-channel lookbacks with volatility-based position sizing across a liquid crypto basket. ([SSRN][10])

For your setup, I would test:

[
L_i = L_{\text{BTC}} \times \left(\frac{\sigma_i}{\sigma_{\text{BTC}}}\right)^2
]

If BTC daily vol is 2.2% and SOL is 3.6%, the scaling factor is roughly:

[
(3.6/2.2)^2 \approx 2.7
]

So a BTC 10/30 equivalent becomes approximately **27/80** for SOL under a constant-volatility-horizon interpretation. I would not adopt that formula blindly, but it is a disciplined hypothesis: higher-vol assets need slower signals to achieve comparable trend/noise balance.

The more robust alternative is to trade a **lookback ensemble per asset**, such as 10/30, 20/60, 40/120, then volatility-normalize and combine. That is usually safer than trying to find one “correct” SOL-specific EMA pair.

---

## 5. Realistic Sharpe expectations for crypto CTA / trend strategies in 2025–2026

Public, audited live Sharpe ratios for crypto CTA funds are hard to obtain. Most fund-level data is proprietary, self-reported, or index-aggregated. The most defensible public references are published backtests, preprints, and broad hedge-fund surveys.

For published crypto trend-following backtests:

* Zarattini, Pagani, and Barbon’s 2025 *Catching Crypto Trends* reports that a rotational trend-following strategy on the top 20 liquid coins, using multiple Donchian lookbacks and volatility sizing, achieved a net-of-fees Sharpe above 1.5 and annualized alpha of 10.8% versus buy-and-hold Bitcoin. ([SSRN][10])
* Bui and Nguyen’s 2026 *AdaptiveTrend* preprint reports an out-of-sample annualized Sharpe of 2.41 from 2022–2024 across 150+ crypto pairs using a more complex high-frequency adaptive trend framework. This is not a simple daily EMA CTA strategy, so I would treat it as an optimistic research benchmark, not a live expectation. ([arXiv][11])
* Grądzki 2025 reports a Sharpe around 2 for a CUSUM-bar / triple-barrier / deep-learning crypto strategy, but again this is not a simple daily trend-following CTA model. ([Springer Link][6])

For live/proxy data:

* The AIMA/PwC 2025 Global Crypto Hedge Fund Report shows that crypto participation among hedge funds increased in 2025, but it does not give clean live Sharpe ratios for trend-following sub-strategies. 
* BarclayHedge’s Cryptocurrency Traders Index is an arithmetic average of net returns of crypto programs in its database. As of its June 30, 2026 page, the index was down **7.03% YTD through May 2026**, while broader systematic CTA indices were positive. ([Barclay Hedge][12])

So I would frame expectations this way:

A clean, diversified crypto trend-following backtest Sharpe around **1.0–1.5** can be plausible. Sharpe above **2** exists in published crypto research, but usually with more complex models, broader universes, higher-frequency data, adaptive selection, or ML/event-bar frameworks. A two-asset BTC/SOL daily EMA system showing a best-offset Sharpe of 1.19 but an offset range from -0.06 to 1.19 should be treated as **implementation-fragile**, not as a stable 1.19 Sharpe strategy.

---

## What I would do in your research pipeline

Use the close time as a nuisance parameter and make robustness part of the strategy definition:

1. Report the **offset-average Sharpe**, not the best-offset Sharpe.
2. Use an **equal-weight ensemble of continuous normalized EMA-spread signals** across 6 or 24 offsets.
3. Add an **offset-fragility penalty** to model selection.
4. Test **intraday EMA with calendar-time decay** as the main replacement for daily candles.
5. Test **CUSUM/range bars**, but treat thresholds as hyperparameters requiring walk-forward validation.
6. Use **asset-specific volatility-scaled lookbacks** or a per-asset lookback ensemble.
7. Apply **Deflated Sharpe / PBO-style corrections** whenever comparing offsets, lookbacks, assets, or bar types.

My strongest conclusion: your result is not a minor artifact. It is exactly the kind of implementation-detail sensitivity that can turn a backtest from a strategy into a parameter-selection accident. For a 24/7 market, the daily bar close should be treated as a model input, not a neutral convention.

[1]: https://centaur.reading.ac.uk/79174/ " Sampling frequency and the performance of different types of technical trading rules  - CentAUR"
[2]: https://link.springer.com/article/10.1007/s10479-019-03357-1 "Technical trading and cryptocurrencies | Annals of Operations Research | Springer Nature Link"
[3]: https://www.smallake.kr/wp-content/uploads/2018/07/SSRN-id3104847.pdf "SSRN_AFML.pdf"
[4]: https://arxiv.org/html/2603.20319v1 "Implementation Risk in Portfolio Backtesting: A Previously Unquantified Source of Error"
[5]: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3637108_code434076.pdf?abstractid=3257420&mirid=1&utm_source=chatgpt.com "Advances in Financial Machine Learning: Lecture 4/10"
[6]: https://link.springer.com/article/10.1186/s40854-025-00866-w "Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning | Financial Innovation | Springer Nature Link"
[7]: https://link.springer.com/article/10.1007/s11156-024-01304-1 "The crypto world trades at tea time: intraday evidence from centralized exchanges across the globe | Review of Quantitative Finance and Accounting | Springer Nature Link"
[8]: https://arxiv.org/abs/2109.12142 "[2109.12142] Periodicity in Cryptocurrency Volatility and Liquidity"
[9]: https://www.pm-research.com/content/iijpormgmt/40/5/94?utm_source=chatgpt.com "The Deflated Sharpe Ratio: Correcting for Selection Bias ..."
[10]: https://papers.ssrn.com/sol3/Delivery.cfm/5209907.pdf?abstractid=5209907&mirid=1 "Catching Crypto Trends; A Tactical Approach for Bitcoin and Altcoins by Carlo Zarattini, Alberto Pagani, Andrea Barbon :: SSRN"
[11]: https://arxiv.org/abs/2602.11708 "[2602.11708] Systematic Trend-Following with Adaptive Portfolio Construction: Enhancing Risk-Adjusted Alpha in Cryptocurrency Markets"
[12]: https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=Barclay-CTA-Indices&indexName=Cryptocurrency-Traders-Index "BarclayHedge Indices - BarclayHedge"
