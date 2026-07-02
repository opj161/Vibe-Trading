# Vibe-Trading winning strategy technical overview
Generated from the uploaded codebase scan. Primary universe scanned: `agent/runs/**/run_card.json` completed backtests. I found **241 run cards** with complete metrics and artifacts. I also found exploratory research CSVs with extreme annualized rows, but those lack run-card reproducibility metadata and are treated as research notes, not completed backtest runs.
## Ranking method
- `annual_profit = annual_return × initial_equity`.
- Where a run card omitted `initial_cash`, I inferred initial equity from the first row of `artifacts/equity.csv`.
- Primary ranking uses run cards because they tie metrics to config hash, strategy hash, data window, and artifacts.
## Raw annual-profit winner
**Run:** `agent/runs/20260630_044631_81_90164a`

**Strategy hash:** `f2f137e9037b440b68bdee5ec014826bed2001e2db0e3603af948788b985aff2`

**Config hash:** `d3f60f0c57ae4fae9f6dad4ef23773a5b2252304173935e9f3ff88a8bf29e682`

**Important reproducibility note:** this run card says `code/signal_engine.py` and `config.json`, but the hashes match `code/signal_engine_15m.py` and `config_15m.json`. The current plain `signal_engine.py` / `config.json` in that folder are the later 1H variant.

| Metric | Value |
|---|---:|
| Annual profit on $1M | $1,549,753 |
| Annual return | 154.98% |
| Period profit | $77,268 |
| Total return | 7.73% |
| Final equity | $1,077,268 |
| Max drawdown | -10.10% |
| Sharpe | 2.307 |
| Sortino | 2.067 |
| Calmar | 15.35 |
| Profit factor | 1.5552 |
| Win rate | 64.00% |
| Trade records / closed positions | 75 |
| Benchmark return | 0.55% |
| Excess return | 7.18% |

**Window/config:** 15-minute bars, `source=auto`, `2026-06-01` → `2026-06-29`, codes `SOXL.US, SOXS.US, SOXX.US, SMH.US, QQQ.US, TQQQ.US, SQQQ.US`, commission `0.0005`, slippage `0.0001`. Actual starting equity was $1,000,000 by engine default/equity artifact; the config uses `initial_capital`, while the engine code uses `initial_cash`, so this key appears not to have set starting cash for this run.

## Strategy mechanics
This is a semiconductor/Nasdaq **intraday mean-reversion** strategy, not the opening-range breakout requested by the original prompt. It uses SOXX as the reference instrument and expresses long/short semiconductor exposure through a multi-leg basket.

Core parameters from `SignalEngine.__init__`:

```python
rsi_period = 14
bb_period = 20
bb_std = 2.0
rsi_oversold = 30
rsi_overbought = 70
rsi_exit_long = 55
rsi_exit_short = 45
max_hold_bars = 16  # four hours on 15m bars
position_size = 0.5
```
Signal rules:

- Reference price: `SOXX.US.close`; fallback to `SMH.US`, then `QQQ.US` if missing.
- Long regime: `RSI(14) < 30` and close below lower Bollinger Band `(20, 2)`; target long exposure through `SOXL.US`, `SOXX.US`, `SMH.US`, `QQQ.US`, `TQQQ.US`.
- Short/bearish regime: `RSI(14) > 70` and close above upper Bollinger Band `(20, 2)`; target long `SOXS.US` and `SQQQ.US`, plus negative weights in `SOXX.US`, `SMH.US`, and `QQQ.US`.
- Exit long when `RSI > 55` or close above BB middle, or max hold reaches 16 bars.
- Exit short when `RSI < 45` or close below BB middle, or max hold reaches 16 bars.
- Engine applies next-bar execution by shifting signal series one bar and normalizes gross exposure to `sum(abs(weights)) <= 1.0`.

Effective normalized exposures after engine gross normalization:

- Bullish state: `SOXL 25% + SOXX 25% + SMH 25% + QQQ 12.5% + TQQQ 12.5%`.
- Bearish state: `SOXS 25% - SOXX 25% - SMH 25% - QQQ 12.5% + SQQQ 12.5%`.

## PnL attribution by traded symbol

| code    |   exit_trades | pnl      | avg_pnl   | win_rate   | avg_return_pct   |
|:--------|--------------:|:---------|:----------|:-----------|:-----------------|
| SOXL.US |            10 | $68,490  | $6,849    | 80.0%      | 2.75%            |
| SMH.US  |            15 | $13,511  | $901      | 66.7%      | 0.37%            |
| SOXX.US |            15 | $12,164  | $811      | 66.7%      | 0.34%            |
| TQQQ.US |            10 | $10,625  | $1,062    | 70.0%      | 0.86%            |
| QQQ.US  |            15 | $1,196   | $80       | 60.0%      | 0.07%            |
| SQQQ.US |             5 | $-3,422  | $-684     | 40.0%      | -0.48%           |
| SOXS.US |             5 | $-25,295 | $-5,059   | 40.0%      | -1.93%           |

Interpretation: the win came from bullish semiconductor mean reversion. `SOXL.US` contributed about $68.5k, while the bearish inverse leg `SOXS.US` lost about $25.3k; the 1x confirmation/traded legs `SOXX.US` and `SMH.US` added about $25.7k combined.

## Exposure and daily behavior

- Equity bars: 521; trading days: 20.
- Average daily return: 0.40%; median daily return: 0.06%; median positive day: 1.48%.
- 90th percentile daily return: 4.71%; best day: 5.20%; worst day: -4.24%.
- Positive/negative/flat days: 10 / 5 / 5.
- Active bars: 170 of 521 (32.6%); max gross: 1.0; average gross while active: 1.0.
- Bullish bars: 95; bearish bars: 75; end-of-day non-flat days: 1.

## Validation and caveats
- Monte Carlo validation: actual Sharpe 2.2378, p-value Sharpe 0.452, p-value max DD 0.997, simulations 1000.
- The annual-profit number is a short-window annualization of a 20-trading-day June sample; the realized period profit was only $77k on $1M.
- The strategy violates the original request’s “trade only SOXL/SOXS” idea because it trades SOXX, SMH, QQQ, TQQQ, and SQQQ as well.
- The code does not explicitly force flat near the close. Position artifacts show one non-flat end-of-day bar, although max hold is four hours and most days end flat.
- The current folder contains both 15m and 1H variants; use the hash-matched `_15m` files for reproduction.

## More durable/OOS winner
If the ranking requires a longer, frozen, forward/OOS candidate rather than the raw annualized run-card maximum, the top current run is `agent/runs/fwd_ZA4_20260702`: BTC/SOL daily trend with EMA(10,30), 10-day vol targeting, ERC allocation, chop-frequency exposure scalar, 200-day counter-regime dampening, and gross recovery. It produced annual profit about $548k on $1M, total return 60.46%, Sharpe 1.22, max drawdown -27.37%, and profit factor 2.14 from 2025-06-01 to 2026-07-02. This is much less explosive than the 15m semiconductor run, but it is far more aligned with the codebase’s documented champion lineage.

## Top completed run-card leaderboard by annual profit

| run_dir                                                         | annual_profit   | annual_return   | period_profit   | total_return   | final_value   | max_drawdown   |   sharpe |   profit_factor | win_rate   |   trade_count | start_date   | end_date   | interval   | source   | codes                                                 |
|:----------------------------------------------------------------|:----------------|:----------------|:----------------|:---------------|:--------------|:---------------|---------:|----------------:|:-----------|--------------:|:-------------|:-----------|:-----------|:---------|:------------------------------------------------------|
| agent/runs/20260630_044631_81_90164a                            | $1,549,753      | 154.98%         | $77,268         | 7.73%          | $1,077,268    | -10.10%        |     2.31 |            1.56 | 64.00%     |            75 | 2026-06-01   | 2026-06-29 | 15m        | auto     | SOXL.US,SOXS.US,SOXX.US,SMH.US,QQQ.US,TQQQ.US,SQQQ.US |
| agent/runs/v_V_btcsol_extended_train                            | $1,503,210      | 150.32%         | $71,325,337     | 7132.53%       | $72,325,337   | -47.38%        |     1.66 |            2.14 | 34.76%     |           164 | 2020-11-01   | 2025-06-30 | 1D         | okx      | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Rung1_naivebh_train                                | $1,489,552      | 148.96%         | $8,766,980      | 876.70%        | $9,766,980    | -53.59%        |     1.63 |            0    | 100.00%    |             2 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/20260630_143522_65_eb0647/audit_runs/trackA_1h_trend | $1,319,300      | 131.93%         | $1,290,719      | 129.07%        | $2,290,719    | -36.20%        |     1.49 |            1.58 | 35.59%     |            59 | 2025-07-01   | 2026-06-29 | 1H         | yfinance | SOXL.US,SOXX.US,SMH.US,QQQ.US                         |
| agent/runs/v_ZA1_grossrecovery_ext_train                        | $1,255,275      | 125.53%         | $43,457,149     | 4345.71%       | $44,457,149   | -44.70%        |     1.57 |            2.19 | 34.76%     |           164 | 2020-11-01   | 2025-06-30 | 1D         | okx      | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_ZA4_regimeconviction_ext_train                     | $1,200,765      | 120.08%         | $38,661,097     | 3866.11%       | $39,661,097   | -43.53%        |     1.56 |            2.19 | 35.12%     |           168 | 2020-11-01   | 2025-06-30 | 1D         | okx      | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_X1_singlevol_train                                 | $1,193,635      | 119.36%         | $6,119,402      | 611.94%        | $7,119,402    | -47.99%        |     1.54 |            2.27 | 28.72%     |            94 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Rung3_signalonly_train                             | $1,155,984      | 115.60%         | $5,817,996      | 581.80%        | $6,817,996    | -40.84%        |     1.61 |            2.38 | 28.85%     |           104 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Z0_extended_control_train                          | $1,131,572      | 113.16%         | $33,169,058     | 3316.91%       | $34,169,058   | -44.41%        |     1.51 |            2.19 | 34.76%     |           164 | 2020-11-01   | 2025-06-30 | 1D         | okx      | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_ZA3_grossvol_ext_train                             | $1,129,784      | 112.98%         | $33,035,550     | 3303.55%       | $34,035,550   | -46.29%        |     1.52 |            2.23 | 33.33%     |           177 | 2020-11-01   | 2025-06-30 | 1D         | okx      | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Rung2_riskmanagedbh_train                          | $1,122,274      | 112.23%         | $5,554,748      | 555.47%        | $6,554,748    | -41.34%        |     1.65 |            0    | 100.00%    |             2 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Z4_leverage15_train                                | $1,058,506      | 105.85%         | $5,073,667      | 507.37%        | $6,073,667    | -45.23%        |     1.45 |            2.37 | 29.46%     |           112 | 2023-01-01   | 2025-06-30 | 1D         | ccxt     | BTC-USDC:USDC,SOL-USDC:USDC                           |
| agent/runs/v_L_dropeth_train                                    | $1,022,031      | 102.20%         | $4,808,321      | 480.83%        | $5,808,321    | -46.70%        |     1.48 |            2.3  | 29.03%     |            93 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/v_Rung4_signalvol_train                              | $995,407        | 99.54%          | $4,619,116      | 461.91%        | $5,619,116    | -38.35%        |     1.57 |            2.36 | 29.52%     |           105 | 2023-01-01   | 2025-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT                                     |
| agent/runs/20260630_143522_65_eb0647/audit_runs/trackA_15m_orb  | $991,778        | 99.18%          | $85,485         | 8.55%          | $1,085,485    | -11.26%        |     1.96 |            1.73 | 56.25%     |            16 | 2026-05-15   | 2026-06-29 | 15m        | yfinance | SOXL.US,SOXX.US,SMH.US,QQQ.US                         |

## Top OOS / forward / validation-tagged run-card leaderboard by annual profit

| run_dir                                    | annual_profit   | annual_return   | period_profit   | total_return   | final_value   | max_drawdown   |   sharpe |   profit_factor | win_rate   |   trade_count | start_date   | end_date   | interval   | source   | codes             |
|:-------------------------------------------|:----------------|:----------------|:----------------|:---------------|:--------------|:---------------|---------:|----------------:|:-----------|--------------:|:-------------|:-----------|:-----------|:---------|:------------------|
| agent/runs/fwd_ZA4_20260702                | $547,994        | 54.80%          | $604,600        | 60.46%         | $1,604,600    | -27.37%        |     1.22 |            2.14 | 27.27%     |            44 | 2025-06-01   | 2026-07-02 | 1D         | okx      | BTC-USDT,SOL-USDT |
| agent/runs/fwd_Z8_20260702                 | $544,479        | 54.45%          | $600,657        | 60.07%         | $1,600,657    | -22.54%        |     1.32 |            2.46 | 28.30%     |            53 | 2025-06-01   | 2026-07-02 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_Z8_voltarget_OOS_TEST         | $479,876        | 47.99%          | $578,366        | 57.84%         | $1,578,366    | -23.74%        |     1.18 |            2.28 | 30.91%     |            55 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/fwd_Z4_20260702                 | $460,685        | 46.07%          | $506,891        | 50.69%         | $1,506,891    | -19.19%        |     1.32 |            2.43 | 28.30%     |            53 | 2025-06-01   | 2026-07-02 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_ZD1_durability_OOS_TEST       | $403,064        | 40.31%          | $484,765        | 48.48%         | $1,484,765    | -20.74%        |     1.17 |            2.2  | 32.08%     |            53 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_ZA3_grossvol_OOS_TEST         | $350,350        | 35.03%          | $419,864        | 41.99%         | $1,419,864    | -30.33%        |     0.9  |            1.71 | 31.11%     |            45 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_ZA4_regimeconviction_OOS_TEST | $345,608        | 34.56%          | $414,047        | 41.40%         | $1,414,047    | -27.37%        |     0.93 |            1.76 | 31.25%     |            48 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_ZB1_z8derisk_OOS_TEST         | $333,018        | 33.30%          | $398,618        | 39.86%         | $1,398,618    | -18.55%        |     1.07 |            2.06 | 32.73%     |            55 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_Z0_control_OOS_TEST           | $320,175        | 32.02%          | $381,852        | 38.19%         | $1,381,852    | -29.06%        |     0.86 |            1.63 | 31.82%     |            44 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_Z16_ema_ensemble_OOS_TEST     | $313,781        | 31.38%          | $374,061        | 37.41%         | $1,374,061    | -20.33%        |     1.02 |            1.95 | 31.48%     |            54 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_Z4_chopfreq_OOS_TEST          | $305,495        | 30.55%          | $363,976        | 36.40%         | $1,363,976    | -19.19%        |     1    |            1.93 | 32.73%     |            55 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |
| agent/runs/v_Z19_onchain_dampen_OOS_TEST   | $303,657        | 30.37%          | $362,730        | 36.27%         | $1,362,730    | -19.18%        |     1    |            1.93 | 32.73%     |            55 | 2025-05-01   | 2026-06-30 | 1D         | auto     | BTC-USDT,SOL-USDT |

## Exact 15m config

```json
{
  "source": "auto",
  "codes": ["SOXL.US", "SOXS.US", "SOXX.US", "SMH.US", "QQQ.US", "TQQQ.US", "SQQQ.US"],
  "start_date": "2026-06-01",
  "end_date": "2026-06-29",
  "interval": "15m",
  "initial_capital": 100000,
  "commission": 0.0005,
  "slippage": 0.0001,
  "validation": {
    "monte_carlo": {
      "n_simulations": 1000
    }
  }
}
```
