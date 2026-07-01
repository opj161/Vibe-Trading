# **Quantitative Analysis of Temporal Discretization Risk and Mitigation Strategies in Cryptocurrency Trend-Following**

The arbitrary determination of a "daily close" in continuous, twenty-four-hour financial markets presents a significant structural vulnerability for systematic trading systems. In traditional equity markets, physical operating hours impose natural boundaries for asset pricing. In contrast, the global cryptocurrency market operates continuously across multiple liquid venues, such as Binance, OKX, and Hyperliquid, with no structural pauses.  
For daily trend-following systems—such as an Exponential Moving Average (EMA) crossover strategy—the temporal boundary selected to define a daily bar represents a non-trivial implementation parameter. The choice of timezone or UTC offset is economically arbitrary, yet empirical testing reveals that purely shifting the daily candle close hour can swing backtested Sharpe ratios from deeply negative levels to highly profitable outcomes on identical underlying price series. This susceptibility highlights a deeper, systemic issue concerning how high-frequency financial time series are temporally discretized.

## **Taxonomic Classification of Temporal Discretization and Reference-Day Risk**

This acute sensitivity to daily bar boundaries is a documented phenomenon in quantitative finance and financial econometrics. It is classified under two distinct, mathematically formalized concepts: **reference-day (or sampling-phase) risk** and **temporal aggregation bias**.

### **Reference-Day and Sampling-Phase Risk**

Reference-day risk defines the statistical variance and estimation errors introduced into asset return properties (such as mean, variance, covariance, and systematic risk parameters like Beta) solely based on the specific calendar point selected to calculate periodic returns1. In standard financial datasets, monthly returns are calculated using a specific day of the month as the reference point (e.g., month-end). Research demonstrates that altering this reference day within a given month induces massive, non-monotonic fluctuations in estimated portfolio parameters, frequently distorting asset pricing models and risk metrics1.  
In a twenty-four-hour trading environment, this phenomenon is more precisely termed *sampling-phase risk*2. Selecting a daily close time (e.g., 00:00 UTC versus 12:00 UTC) represents a phase shift ($\phi$) in the discrete sampling of a continuous price path:  
$$
P_{t, \phi} = P(t \cdot \Delta t + \phi)
$$
where $\Delta t$ is the twenty-four-hour sampling interval and $\phi \in [0, 24)$ is the temporal offset in hours. When a moving average crossover system is calculated using these daily price series, marginal fluctuations around the temporal boundary $\phi$ determine whether a crossover event is registered on day $t$ or delayed until day $t+1$. This one-day execution lag generates substantial path dependency, translating to significant tracking error in live trading5.

### **Temporal Aggregation Bias and Autocorrelation Seasonality**

Temporal aggregation bias occurs when high-frequency processes are aggregated into lower-frequency discrete observations8. In econometric theory, temporal aggregation alters the autocorrelation structure of the underlying data8.  
Recent literature directly addresses how the choice of aggregation boundaries impacts the first-order autocorrelation coefficient, $\text{AR}(1)$, of aggregated returns15. If the high-frequency returns follow a stationary, time-homogeneous process (such as a standard autoregressive moving average process), the choice of the temporal start and end boundaries is statistically immaterial15. However, if the high-frequency return series exhibits intraday or intraweek seasonality in its autocorrelation structure, the $\text{AR}(1)$ of the aggregated series becomes highly dependent on the boundary definition15.  
The cryptocurrency market is characterized by highly pronounced, persistent intraday seasonalities in both volatility and trading volume16. These seasonalities are driven by institutional trading hours in major geographical regions (the overlap of US, European, and Asian sessions), the release of macroeconomic news, and programmatic events such as perpetual futures funding rate settlement times (occurring every eight hours on major exchanges)16.  
When daily bars are constructed, these seasonal dynamics are integrated across different intervals depending on the chosen UTC close $\phi$15. A bar ending at 16:00 UTC integrates peak North American liquidity and US monetary policy announcements directly at its close, whereas a bar ending at 00:00 UTC or 08:00 UTC integrates different Asian or European session dynamics16.  
Consequently, the aggregated daily returns exhibit distinct autoregressive features depending on $\phi$, altering the timing of technical indicators and producing disparate Sharpe ratios on the same underlying series15.

## **Robust Moving-Average Architectures and Alternative Bar Construction**

To decouple systematic signals from arbitrary clock-time boundaries, quantitative researchers utilize structural modifications. These range from alternative bar construction methods to seasonality-aligned trading intervals.

### **Alternative Bar Construction Frameworks**

The traditional method of segmenting data into fixed temporal intervals (time bars) is structurally flawed21. By sampling at constant time steps, time bars oversample periods of low market activity (such as weekends or holidays) and undersample periods of extreme volatility and high volume (such as market crashes or CPI releases)21. This misaligned sampling violates the assumptions of standard statistical models, yielding returns characterized by heteroscedasticity, non-normality, and highly unstable auto-covariance21.  
To build trend-following models that are immune to clock-time boundary choices, researchers implement alternative bar construction techniques:

* **Tick Bars:** These bars are sampled after a fixed number of transactions ($N_{\text{ticks}}$) occur21. While they synchronize data sampling with transaction frequency, they are vulnerable to order fragmentation, where a single large institutional order is executed as hundreds of micro-transactions, causing artificial spikes in bar sampling21.  
* **Volume Bars:** These bars are sampled every time a predefined volume of the asset is traded ($V_{\text{target}}$)21. This resolves order fragmentation by aggregating volume directly and compresses low-activity trading periods while expanding highly active periods into multiple bars21.  
* **Dollar Bars:** These bars are sampled whenever a predefined fiat-equivalent market value is exchanged ($D_{\text{target}}$)21. Dollar bars are highly robust for assets that experience massive price changes over time, as they maintain a constant economic scale per bar and exhibit superior statistical properties21.  
* **Information-Driven Bars (Imbalance and Run Bars):** Originally developed by Marcos Lopez de Prado, these bars sample data dynamically whenever the cumulative imbalance of buy and sell transactions (measured in ticks, volume, or dollar value) deviates significantly from historical expectations22. This forces the sampling frequency to accelerate when informed traders are actively entering the market, capturing price discovery before a new equilibrium is reached22.

Empirical research confirms that alternative bar structures are less sensitive to arbitrary boundary effects for trend and momentum signals5. In a study analyzing tick-level cryptocurrency data for Bitcoin (BTC) and Ethereum (ETH) from January 2018 to June 2023, researchers evaluated the out-of-sample performance of trading models using information-driven sampling5.  
The study demonstrated that combining CUSUM-filtered event-based sampling with the Triple Barrier Method for target labeling significantly outperformed traditional time bars and next-bar predictions, achieving consistently positive, statistically stable risk-adjusted returns even after accounting for transaction costs5.  
By sampling based on real market information and volatility thresholds rather than arbitrary clock time, these strategies successfully eliminated the sampling-phase risk inherent in standard backtests5.

| Bar Construction Type | Primary Sampling Trigger | Volatility/Volume Adaptation | Autocorrelation Normality | Mitigation of Boundary Arbitrariness |
| :---- | :---- | :---- | :---- | :---- |
| **Time Bars** | Fixed elapsed duration $\Delta t$ [cite: 21, 22] | None (ignores market volume and structural volatility shifts)21 | Low (exhibits severe heteroscedasticity and time-varying serial correlation)21 | Low (highly vulnerable to timezone/close hour selection)5 |
| **Volume Bars** | Predefined cumulative volume $V_{\text{target}}$ [cite: 21, 22] | High (accelerates sampling during high-volume regimes)21 | Moderate-High (returns show lower autocorrelation and closer approximation to IID normal)21 | High (boundaries are determined by transaction volume, not time)5 |
| **Dollar Bars** | Predefined cumulative fiat value $D_{\text{target}}$ [cite: 21, 22] | High (adjusts for both volume spikes and major long-term asset price shifts)21 | High (stable variance; highly suited for long-term machine learning models)21 | High (completely immune to timezone-based daily close variations)5 |
| **Information Imbalance Bars** | Cumulative buy/sell tick, volume, or dollar imbalance22 | Outstanding (samples dynamically based on asymmetric informed order flow)22 | Outstanding (optimizes statistical properties by capturing informational arrivals)22 | Outstanding (perfectly aligns sampling with the physical process of price discovery)5 |

### **Session-Based and Seasonality-Adjusted Bar Timing**

For systematic strategies constrained to time-based bars, aligning the daily bar boundaries with intraday liquidity and volume patterns offers a secondary defense against discretization risk16.  
Rather than selecting an arbitrary timezone close, setting the daily bar boundary to coincide with peak liquidity periods (such as the US-European overlap or the primary perpetual futures funding rate settlements at 00:00, 08:00, and 16:00 UTC) ensures that the daily "close" is computed when the limit order books are deepest and the price represents an efficient, high-volume consensus16. This minimizes the impact of localized, low-volume microstructure noise on the EMA calculation, reducing the frequency of spurious, boundary-dependent crossover signals2.

## **Deconstruction of Signal Ensembling and Advanced Aggregation Metrics**

When evaluating a multi-offset signal ensemble (e.g., averaging daily EMA signals computed across six distinct UTC offsets), the resulting Sharpe ratio typically converges to the average of the single-offset Sharpe ratios, rather than exceeding the best-performing individual offset. This behavior is mathematically expected but can be optimized through alternative aggregation methods.

### **The Mathematics of Ensemble Variance Reduction**

Ensembling identical trend-following strategies that differ solely by their daily close hour represents a variance-reduction technique rather than a source of additive alpha30. Because the underlying asset price series (BTC and SOL) is identical, the pairwise correlation ($\rho_{i, j}$) between the returns of the six offset strategies is extremely high (typically $\rho_{i, j} \ge 0.95$).  
If $N$ highly correlated strategies are combined in an equally weighted portfolio, the variance of the ensemble portfolio return, $\sigma^2_p$, is bounded by the high cross-correlation. Let each offset strategy have a return $r_i$ with variance $\sigma^2_i = \sigma^2$ and pairwise correlation $\rho$. The portfolio variance is given by:  
$$
\sigma^2_p = \frac{\sigma^2}{N} + \frac{N-1}{N} \rho \sigma^2
$$
As $\rho \to 1$, the portfolio variance $\sigma^2_p \to \sigma^2$. Consequently, ensembling highly correlated, phase-shifted signals does not yield the diversification benefits of combining uncorrelated assets30. Instead, it acts as a **noise-filtering mechanism**5.  
The "best" single offset in a backtest (e.g., Sharpe of +1.19) is often a result of favorable sample selection, where the arbitrary close time coincidentally aligned with optimal execution points during that specific historical window32. The "worst" offset (e.g., Sharpe of \-0.06) represents a negative sampling-phase shock1. Ensembling these signals averages out this non-systematic discretization noise, ensuring that the live strategy performance converges toward the true, expected long-term trend-following risk premium ($S^*$) rather than a localized, overfit peak33.

### **Advanced Aggregation and Continuous Forecast Methods**

To extract maximum risk-adjusted performance from a multi-offset framework, systematic traders replace binary signal ensembling with more sophisticated combination architectures:

#### **Continuous Trend Forecast Mapping**

In a standard crossover strategy, a binary signal is generated (e.g., +1 for long, \-1 for short) based on whether the fast EMA is above or below the slow EMA35. This binary transition maximizes discretization risk, as a marginal fractional crossing triggers an immediate $100\%$ portfolio rebalance.  
To mitigate this, quantitative practitioners implement continuous forecast mappings, where the signal strength is a continuous function of the distance between the two moving averages35. Following the methodology outlined by systematic managers like Rob Carver, a raw forecast ($RF_t$) is calculated as the difference between the fast and slow EMA, normalized by a volatility measure to ensure scale-invariance35:  
$$
RF_t = \frac{\text{EMA}(10)_t - \text{EMA}(30)_t}{\sigma_{t}}
$$
This raw forecast is then multiplied by a forecast scalar to produce a standardized continuous forecast ($CF_t$) bounded between \-20 and +20 (representing maximum short and maximum long positions, respectively)35:  
$$
CF_t = \text{clip}\left( RF_t \times \text{Scalar}, -20, 20 \right)
$$
Under this continuous framework, the portfolio's target position scales smoothly as the trend strengthens or weakens35. Discretization risk is reduced because a marginal, boundary-dependent crossover at an arbitrary hour only results in a minor, fractional change in target position size, rather than a violent, full reversal35.

#### **Volatility Targeting and Execution Buffering**

To complement the continuous forecast, systematic trend-following funds apply dynamic volatility targeting and trading buffers to manage costs and control portfolio turnover34.  
The optimal position size for each asset is scaled inversely with its rolling volatility to maintain a constant risk contribution38.  
To prevent excessive trading fees and slippage from continuous, fractional adjustment of target positions, an execution buffer ($F$) is established around the current position38. A trade is executed only if the difference between the target position and the actual held position exceeds a defined threshold (typically set to $10\%$ of the target size)38:  
$$
|\text{Target Position} - \text{Actual Position}| > F \times \text{Target Position}
$$
This buffer filters out the noise of continuous signal adjustments, ensuring that transactions are only executed when a trend shift is sufficiently large and statistically meaningful38.

## **Microstructural Analysis of Volatility-Asymmetry and Adaptive Lookback Windows**

The empirical observation that Solana (SOL) exhibits significantly higher bar-timing fragility than Bitcoin (BTC) is a direct consequence of their distinct volatility profiles and the mathematical properties of moving average filters.

### **The Mechanics of Volatility-Asymmetry**

Solana's higher average daily volatility ($\sigma \approx 3.5\text{-}3.8\%$) relative to Bitcoin's ($\sigma \approx 2.1\text{-}2.3\%$) directly increases the frequency of marginal, boundary-dependent crossover events19. In highly volatile assets, the price path crosscuts the moving average lines with greater frequency and a steeper trajectory.  
When daily time bars are sampled discretely, high-volatility assets suffer from pronounced *discretization bias* near the decision boundaries41. High intraday price excursions frequently generate false, temporary crossover signals that mean-revert before the end of the day.  
If the daily close hour ($\phi$) is sampled during one of these transient intraday excursions, the model registers a false trend-change signal, triggering a whipsaw trade43. For a lower-volatility asset like Bitcoin, the price path is smoother, and crossovers are typically driven by persistent, macroeconomic trend shifts rather than transient intraday noise, rendering the signal highly stable across various UTC offsets.

### **Volatility-Adjusted Lookback Adaptation**

Applying a uniform lookback window (such as a 10/30-day span) across assets with vastly different volatility scales assumes their information diffusion rates and trend half-lives are identical—an assumption that is theoretically and empirically invalid44. To resolve this asymmetry, systematic models must adapt their lookback windows dynamically based on localized asset volatility44.  
Two primary quantitative methodologies exist to dynamically adjust moving-average lookbacks:

#### **Volatility-Scaled Trend Signals (Rolling t-Statistics)**

Rather than relying on simple price-based EMAs, advanced trend-following strategies utilize rolling-window $t$\-statistics of past returns to adapt signals to changing volatility regimes44. This approach, advocated by Campbell (2006), constructs a standardized trend signal by dividing the rolling mean return of the last $\ell$ days by its rolling standard deviation, normalized by the lookback length44:  
$$
T_{t, \ell} = \frac{\bar{r}_{t, \ell}}{\sigma_{t, \ell} / \sqrt{\ell}}
$$
A non-linear, bounded transformation is then applied to scale the trend prediction44:  
$$
\phi(T_{t, \ell}) = \tanh(\alpha \cdot T_{t, \ell})
$$
where $\alpha$ is a tuning parameter optimized via cross-validation44. Because the trend signal is scaled inversely by volatility ($\sigma_{t, \ell}$), a sudden increase in Solana's volatility automatically dampens the $t$\-statistic44.  
To trigger a trend reversal during a high-volatility regime, the asset must exhibit a much larger, more sustained price move, effectively shielding the crossover logic from transient intraday noise and stabilizing the signal across different temporal boundaries44.

#### **Volatility-Sensitive Mixture of Experts (MoE)**

Alternatively, systematic systems deploy a Mixture of Experts (MoE) framework to manage heterogeneous volatility regimes across multi-asset baskets45. In this architecture, a gating network dynamically monitors the rolling volatility of each asset in the portfolio45.  
Assets classified as low-volatility (such as BTC) are routed to tighter, faster trend-following experts designed to capture quick momentum shifts45. High-volatility, high-beta assets (such as Solana) are routed to slower, heavily smoothed trend-following models or linear-regression experts optimized for high-noise regimes45.  
By dynamically adjusting model complexity and smoothing parameters based on asset-specific volatility classifications, the MoE framework achieves a significantly more robust, out-of-sample risk-adjusted return profile across the entire asset universe45.

## **Institutional Return Expectations and Implementation-Detail Risk (2025–2026)**

To contextualize systematic cryptocurrency trend-following returns, quantitative managers benchmark their backtests against live fund performance and institutional risk-management standards.

### **Live Crypto Fund Performance Benchmarks**

During the 2025–2026 period, the digital asset fund ecosystem matured rapidly, characterized by substantial capital inflows and the expansion of institutional-grade multi-strategy, market-neutral, and directional trend-following vehicles47.  
According to institutional indices and databases, including the *AIMA/PwC 7th Annual Global Crypto Hedge Fund Report (2025)*, over $55\%$ of traditional hedge funds maintain active exposure to digital assets, utilizing sophisticated prime brokerage and triparty custody frameworks to manage counterparty risk48.  
Performance data from 2025 demonstrates a stark divergence between directional systematic strategies and market-neutral/arbitrage overlays50. While directional trend-following strategies suffered from choppy, range-bound market regimes during certain quarters of 2025 (causing losses for several algorithmic managers), market-neutral, basis-trading, and dollar-neutral strategies generated highly consistent, double-digit risk-adjusted returns49.

| Systematic Strategy Type | 2025 Benchmark Return | Average Sharpe Ratio | Average Sortino Ratio | Max Historical Drawdown |
| :---- | :---- | :---- | :---- | :---- |
| **Cash-and-Carry Basis (Delta Neutral)** | **$12.0\% - 18.0\%$** | **$4.84$** [cite: 50] | $7.50$ | $< 1.0\%$ [cite: 50] |
| **Dollar Neutral / Statistical Arbitrage** | **$31.23\%$** [cite: 50] | $2.39$ [cite: 47, 50] | $4.51$ [cite: 50] | $2.0\% - 5.0\%$ |
| **Active Multi-Strategy Crypto Funds** | **$14.40\%$** [cite: 50, 51] | $1.53$ [cite: 51] | $2.10$ | $5.0\% - 8.0\%$ |
| **Directional Trend-Following (BTC/SOL)** | **$-2.50\% - -6.00\%$** [cite: 50] | $0.50 - 0.80$ [cite: 50] | $0.80 - 1.10$ | $12.0\% - 20.0\%$ [cite: 19] |

While top-performing crypto-native systematic funds operating across complete multi-year bull/bear cycles have historically targetted Sharpe ratios in the range of $1.50 - 2.50$, realistic expectations for a simple, daily-bar directional trend-following strategy on a major-cap basket sit between $0.60$ and $1.00$47.

### **Institutional Treatment of Implementation-Detail Risk**

In the institutional quant community, the high sensitivity of a daily trend-following signal to the arbitrary hour of the daily candle close is classified as a critical **implementation-detail risk** (also known as operational model risk or discretization leakage)6.  
Serious practitioners do not view a daily-bar model with a Sharpe ratio that swings from $+1.19$ to $-0.06$ across four-hour offsets as a viable trading system32. Such severe sensitivity is a primary diagnostic indicator of *overfitting to noise*19. The +1.19 Sharpe ratio is recognized as a spurious artifact of sampling-phase coincidence, where that specific clock-boundary sequence happened to bypass localized whipsaws in the historical dataset1.  
To prevent the deployment of such fragile models, quantitative funds enforce strict validation and parameter perturbation protocols prior to capital allocation19:

1. **Parameter Perturbation Sweeps:** Any candidate systematic strategy must undergo comprehensive sensitivity testing19. All model parameters—including moving average lookbacks, rebalancing intervals, execution delays, and sampling offsets—are perturbed by $\pm 20\%$19. If a minor change in any parameter (such as shifting the candle close or altering the EMA lookback by a few days) causes a catastrophic decay or a non-monotonic shift in performance, the model is flagged as overfit and rejected19.  
2. **Short Train / Long Test Walk-Forward Validation:** Rather than traditional long-term in-sample training, models are subjected to rigorous rolling walk-forward analyses (e.g., a 6-month training window followed by a 1-month out-of-sample testing split)19. This prevents the strategy from accumulating "regime memory" and ensures that the predictive signals are robust to rapid shifts in market microstructure and volatility regimes19.  
3. **Friction and Funding-Inclusive Modeling:** For cryptocurrency assets, backtests must incorporate actual historical eight-hour perpetual funding payments and precise slippage schedules rather than theoretical cost of carry19. Strategies that appear highly profitable on a daily close basis frequently degrade once realistic execution delays and funding rate drags are integrated into the simulation5.

#### **Works cited**

1. Reference-Day Risk and the Use of Monthly Returns Data \- ResearchGate, [https://www.researchgate.net/publication/238044004\_Reference-Day\_Risk\_and\_the\_Use\_of\_Monthly\_Returns\_Data](https://www.researchgate.net/publication/238044004_Reference-Day_Risk_and_the_Use_of_Monthly_Returns_Data)  
2. Official Daily Open and Daily Close Prices | TrendSpider Learning Center, [https://trendspider.com/learning-center/official-daily-open-and-daily-close-prices/](https://trendspider.com/learning-center/official-daily-open-and-daily-close-prices/)  
3. Signal Processing for Intelligent Sensor Systems with MATLAB, [https://api.pageplace.de/preview/DT0400.9781439879504\_A37902348/preview-9781439879504\_A37902348.pdf](https://api.pageplace.de/preview/DT0400.9781439879504_A37902348/preview-9781439879504_A37902348.pdf)  
4. 1 Introduction \- arXiv, [https://arxiv.org/html/2601.16696](https://arxiv.org/html/2601.16696)  
5. Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning, [https://d-nb.info/1390878104/34](https://d-nb.info/1390878104/34)  
6. blue sky alliance fund \- One Investment Group, [https://oneinvestment.com.au/wp-content/uploads/2018/04/Blue-Sky-Alliance-Fund-PDS-20170929.pdf](https://oneinvestment.com.au/wp-content/uploads/2018/04/Blue-Sky-Alliance-Fund-PDS-20170929.pdf)  
7. Integrated Managed Account Portfolio Service (MAPS), [https://atriuminvest.com.au/wp-content/uploads/Atrium-MAPS-PDS-Books-1-2\_1-April-2026.pdf](https://atriuminvest.com.au/wp-content/uploads/Atrium-MAPS-PDS-Books-1-2_1-April-2026.pdf)  
8. Persistence under temporal aggregation and differencing | Request PDF \- ResearchGate, [https://www.researchgate.net/publication/263545557\_Persistence\_under\_temporal\_aggregation\_and\_differencing](https://www.researchgate.net/publication/263545557_Persistence_under_temporal_aggregation_and_differencing)  
9. Temporal Aggregation Bias and Monetary Policy Transmission \- Christian Matthes, [https://cm1518.github.io/files/JMW.pdf](https://cm1518.github.io/files/JMW.pdf)  
10. Temporal Aggregation Bias and Monetary Policy Transmission \- Federal Reserve, [https://www.federalreserve.gov/econres/feds/files/2022054r1pap.pdf](https://www.federalreserve.gov/econres/feds/files/2022054r1pap.pdf)  
11. A review of temporal aggregation and systematic sampling on time-series analysis \- Sign in, [https://pure.bond.edu.au/ws/portalfiles/portal/268607868/A\_review\_of\_temporal\_aggregation\_and\_systematic\_sampling\_on\_time-series\_analysis.pdf](https://pure.bond.edu.au/ws/portalfiles/portal/268607868/A_review_of_temporal_aggregation_and_systematic_sampling_on_time-series_analysis.pdf)  
12. Don't Ruin the Surprise: Temporal Aggregation Bias in Structural Innovations \- American Economic Association, [https://www.aeaweb.org/conference/2025/program/paper/yrEQfn8a](https://www.aeaweb.org/conference/2025/program/paper/yrEQfn8a)  
13. Sparse Tree-Based Aggregation for Time Series Regressions \- arXiv, [https://arxiv.org/html/2606.03665v1](https://arxiv.org/html/2606.03665v1)  
14. Sparse Tree-Based Aggregation for Time Series Regressions \- arXiv, [https://arxiv.org/pdf/2606.03665](https://arxiv.org/pdf/2606.03665)  
15. Temporal Aggregation and Seasonality in Autocorrelations of Stock Returns, [https://www.wsir.org/10papers/3.pdf](https://www.wsir.org/10papers/3.pdf)  
16. (PDF) Periodicity in Cryptocurrency Volatility and Liquidity \- ResearchGate, [https://www.researchgate.net/publication/354950011\_Periodicity\_in\_Cryptocurrency\_Volatility\_and\_Liquidity](https://www.researchgate.net/publication/354950011_Periodicity_in_Cryptocurrency_Volatility_and_Liquidity)  
17. Macroeconomic news and intraday seasonal volatility in the cryptocurrency markets, [https://ideas.repec.org/a/taf/applec/v56y2024i38p4594-4610.html](https://ideas.repec.org/a/taf/applec/v56y2024i38p4594-4610.html)  
18. Bayesian Analysis of Bitcoin Volatility Using Minute-by-Minute Data and Flexible Stochastic Volatility Models \- MDPI, [https://www.mdpi.com/2227-7390/13/16/2691](https://www.mdpi.com/2227-7390/13/16/2691)  
19. 4 years of a 15x-leveraged daily BTC signal — Sharpe 2.2, MDD \-13%. Here's the stuff that actually kept leverage from killing me. : r/algotrading \- Reddit, [https://www.reddit.com/r/algotrading/comments/1ss5btv/4\_years\_of\_a\_15xleveraged\_daily\_btc\_signal\_sharpe/](https://www.reddit.com/r/algotrading/comments/1ss5btv/4_years_of_a_15xleveraged_daily_btc_signal_sharpe/)  
20. Comparing Volume to its past time-of-day behavior instead of a Volume moving average : r/Daytrading \- Reddit, [https://www.reddit.com/r/Daytrading/comments/1mlyi54/comparing\_volume\_to\_its\_past\_timeofday\_behavior/](https://www.reddit.com/r/Daytrading/comments/1mlyi54/comparing_volume_to_its_past_timeofday_behavior/)  
21. Alternative Bars in Alpaca: Part I \- (Introduction), [https://alpaca.markets/learn/alternative-bars-01](https://alpaca.markets/learn/alternative-bars-01)  
22. Financial Data Structures | RiskLab AI, [https://www.risklab.ai/research/financial-data-science/financial\_data\_structures](https://www.risklab.ai/research/financial-data-science/financial_data_structures)  
23. Why are time bars considered to over-sample information during low-activity periods? : r/algotrading \- Reddit, [https://www.reddit.com/r/algotrading/comments/1hrc5yp/why\_are\_time\_bars\_considered\_to\_oversample/](https://www.reddit.com/r/algotrading/comments/1hrc5yp/why_are_time_bars_considered_to_oversample/)  
24. Seasonality in cryptocurrencies \- IDEAS/RePEc, [https://ideas.repec.org/a/eee/finlet/v31y2019ics1544612318304513.html](https://ideas.repec.org/a/eee/finlet/v31y2019ics1544612318304513.html)  
25. jzajpt/id-bars: Utility for generating information-driven bars written in Rust. \- GitHub, [https://github.com/jzajpt/id-bars](https://github.com/jzajpt/id-bars)  
26. Information-driven bars for financial machine learning: imbalance bars \- Medium, [https://medium.com/data-science/information-driven-bars-for-financial-machine-learning-imbalance-bars-dda9233058f0](https://medium.com/data-science/information-driven-bars-for-financial-machine-learning-imbalance-bars-dda9233058f0)  
27. Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning \- IDEAS/RePEc, [https://ideas.repec.org/a/spr/fininn/v11y2025i1d10.1186\_s40854-025-00866-w.html](https://ideas.repec.org/a/spr/fininn/v11y2025i1d10.1186_s40854-025-00866-w.html)  
28. A Simple Estimation of Bid-Ask Spreads from Daily Close, High, and Low PricesWe propose a new method to estimate the bid-ask spread when quote data are not available. Compared to other low-frequency estimates, it utilizes a wider information set, namely, close, high, and low prices, which are readily \- IDEAS/RePEc, [https://ideas.repec.org/p/usg/sfwpfi/201604.html](https://ideas.repec.org/p/usg/sfwpfi/201604.html)  
29. A Simple Estimation of Bid-Ask Spreads from Daily Close, High, and Low Prices \- Alexandria (UniSG), [https://alexandria.unisg.ch/server/api/core/bitstreams/dfb85399-5bcf-465c-8b63-9bfc97ad2ee0/content](https://alexandria.unisg.ch/server/api/core/bitstreams/dfb85399-5bcf-465c-8b63-9bfc97ad2ee0/content)  
30. Quant research team of the year: Deutsche Bank \- Risk.net, [https://www.risk.net/awards/5364611/quant-research-team-of-the-year-deutsche-bank](https://www.risk.net/awards/5364611/quant-research-team-of-the-year-deutsche-bank)  
31. Constructing Long-Only Multifactor Strategies: Portfolio Blending vs. Signal Blending \-, [https://alphaarchitect.com/constructing-long-only-multifactor-strategies-portfolio-blending-vs-signal-blending/](https://alphaarchitect.com/constructing-long-only-multifactor-strategies-portfolio-blending-vs-signal-blending/)  
32. Which Leakage Types Matter? A Quantitative Landscape Across 2,047 Benchmark Datasets, [https://arxiv.org/html/2604.04199v1](https://arxiv.org/html/2604.04199v1)  
33. SI405: Why Most Trend Following Improvements Should Fail ft. Rob Carver, [https://www.toptradersunplugged.com/captivate-podcast/si405-why-most-trend-following-improvements-fail-ft-rob-carver/](https://www.toptradersunplugged.com/captivate-podcast/si405-why-most-trend-following-improvements-fail-ft-rob-carver/)  
34. Rob Carver on Trend Following, Skew, and the Total Portfolio Shift | Systematic Investor | Ep.375 \- Buyside Digest, [https://www.buysidedigest.com/podcast/rob-carver-on-trend-following-skew-and-the-total-portfolio-shift-systematic-investor-ep-375/](https://www.buysidedigest.com/podcast/rob-carver-on-trend-following-skew-and-the-total-portfolio-shift-systematic-investor-ep-375/)  
35. Binary vs Continuous Signals, LSTM, and Rob Carver's Philosophy – Some Open Questions : r/algotrading \- Reddit, [https://www.reddit.com/r/algotrading/comments/1m15x7e/binary\_vs\_continuous\_signals\_lstm\_and\_rob\_carvers/](https://www.reddit.com/r/algotrading/comments/1m15x7e/binary_vs_continuous_signals_lstm_and_rob_carvers/)  
36. Correlations, Weights, Multipliers.... (pysystemtrade) \- This Blog is Systematic, [https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html](https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html)  
37. Some more trading rules \- This Blog is Systematic, [https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html](https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html)  
38. Futures Fast Trend Following, with Trend Strength \- QuantConnect.com, [https://www.quantconnect.com/research/15875/futures-fast-trend-following-with-trend-strength/](https://www.quantconnect.com/research/15875/futures-fast-trend-following-with-trend-strength/)  
39. Combined Carry and Trend \- QuantConnect.com, [https://www.quantconnect.com/research/16001/combined-carry-and-trend/](https://www.quantconnect.com/research/16001/combined-carry-and-trend/)  
40. Vol targeting: A CA(g)R race \- This Blog is Systematic, [https://qoppac.blogspot.com/2022/06/vol-targeting-cagr-race.html](https://qoppac.blogspot.com/2022/06/vol-targeting-cagr-race.html)  
41. Boundary-Regularized Bayesian Autoregressive Changepoint Detection with Applications to Natural Gas Markets \- MDPI, [https://www.mdpi.com/2075-1680/15/5/385](https://www.mdpi.com/2075-1680/15/5/385)  
42. Addressing discretization-induced bias in demographic prediction | PNAS Nexus, [https://academic.oup.com/pnasnexus/article/4/2/pgaf027/7990337](https://academic.oup.com/pnasnexus/article/4/2/pgaf027/7990337)  
43. 127 Systematic Investor Series ft Moritz Seibert – February 15th, 2021, [https://www.toptradersunplugged.com/podcast/127-systematic-investor-series-ft-moritz-seibert-february-15th-2021/](https://www.toptradersunplugged.com/podcast/127-systematic-investor-series-ft-moritz-seibert-february-15th-2021/)  
44. Enhanced LSTM Trend Forecasting for EquitiesThe authors would like to thank an anonymous reviewer for valuable comments and suggestions that improved various aspects of this paper. \- arXiv, [https://arxiv.org/html/2603.14453v1](https://arxiv.org/html/2603.14453v1)  
45. Adaptive Market Intelligence: A Mixture of Experts Framework for Volatility-Sensitive Stock Forecasting \- ResearchGate, [https://www.researchgate.net/publication/394322530\_Adaptive\_Market\_Intelligence\_A\_Mixture\_of\_Experts\_Framework\_for\_Volatility-Sensitive\_Stock\_Forecasting](https://www.researchgate.net/publication/394322530_Adaptive_Market_Intelligence_A_Mixture_of_Experts_Framework_for_Volatility-Sensitive_Stock_Forecasting)  
46. An Equilibrium Model of Moving-average Predictability and Time-series Momentum, [https://www.ckgsb.edu.cn/Userfiles/doc/12.03%20Yingzi%20Zhu.pdf](https://www.ckgsb.edu.cn/Userfiles/doc/12.03%20Yingzi%20Zhu.pdf)  
47. Institutional Capital Allocation in Digital Assets: A Comparative Analysis of the Top Ten Cryptocurrency Investment Funds \- Medium, [https://medium.com/@gwrx2005/institutional-capital-allocation-in-digital-assets-a-comparative-analysis-of-the-top-ten-6ff5364a1a3a](https://medium.com/@gwrx2005/institutional-capital-allocation-in-digital-assets-a-comparative-analysis-of-the-top-ten-6ff5364a1a3a)  
48. An Empirical Framework for Evaluating and Selecting Cryptocurrency Funds Using DEMATEL-ANP-VIKOR \- MDPI, [https://www.mdpi.com/1911-8074/19/1/29](https://www.mdpi.com/1911-8074/19/1/29)  
49. Crypto Alpha From Volatility and Inefficiency \- The Hedge Fund Journal, [https://thehedgefundjournal.com/amphibian-quant-crypto-alpha-volatility-inefficiency/](https://thehedgefundjournal.com/amphibian-quant-crypto-alpha-volatility-inefficiency/)  
50. Market Neutral Strategy in Crypto: Does It Actually Work? \- TradingView Hub, [https://www.tv-hub.org/guide/market-neutral-strategy-crypto](https://www.tv-hub.org/guide/market-neutral-strategy-crypto)  
51. Sigil Fund: Active crypto hedge fund strategies, [https://www.sigilfund.com/](https://www.sigilfund.com/)  
52. Why Most Trend Following Improvements Should Fail ft. Rob Carver, [https://www.toptradersunplugged.com/podcast/why-most-trend-following-improvements-should-fail-ft-rob-carver/](https://www.toptradersunplugged.com/podcast/why-most-trend-following-improvements-should-fail-ft-rob-carver/)  
53. What Are Trend Following Trading Strategies and How do They Work? \- Intuition Now, [https://now.intuition.com/blog/what-are-trend-following-trading-strategies-and-how-do-they-work](https://now.intuition.com/blog/what-are-trend-following-trading-strategies-and-how-do-they-work)

