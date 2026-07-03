from typing import Dict

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# AQR-style tri-horizon TSMOM blend + SG Trend Indicator-style 20/120-day SMA
# crossover, per Tier A anchors in research/Macro-Trend-Calibration-Strategy-2.md
# and research/Macro-Trend-Calibration-Strategy-1.md (vibe_trading_next_directions.md
# section 3.1). Tests whether recalibrating signal SPEED (not just position
# sizing) fixes the crypto-tuned EMA(10,30)'s outright loss on SPY+GLD
# (vibe_trading_research_findings.md section 43.5).
TSMOM_LOOKBACKS = [21, 63, 252]  # ~1mo, ~3mo, ~12mo trading days (AQR)
MA_FAST_SPAN = 20   # SG Trend Indicator disclosed methodology: 20/120-day SMA
MA_SLOW_SPAN = 120
VOL_LOOKBACK = 60   # institutional standard EWMA vol lookback (60-65d), not crypto's 10d
TARGET_DAILY_VOL = 0.010  # ~1.0%/day, matches SPY/GLD's own typical realized range
VOL_SCALAR_MIN = 0.25
VOL_SCALAR_MAX = 1.0
COV_LOOKBACK = 60


def _erc_weights(cov: np.ndarray) -> np.ndarray:
    """Equal risk contribution weights via convex log-barrier solve (Maillard/
    Roncalli/Teiletche). NOTE: this is NOT Z4/Z8's hand-rolled iteration --
    that undamped multiplicative fixed-point update diverges into large
    negative weights on a genuinely negatively-correlated n>2 portfolio
    (equities vs. bonds), verified directly while building this multi-asset
    macro strategy and fixed at the platform level in
    agent/backtest/optimizers/risk_parity.py (see its docstring and
    tests/test_risk_parity.py::test_negatively_correlated_multi_asset_stays_nonnegative).
    Z4/Z8 are left untouched since BTC/SOL's ~0.7-0.8 positive correlation
    never triggers this failure mode for them."""
    n = cov.shape[0]
    vols = np.sqrt(np.diag(cov))
    if np.any(vols < 1e-12):
        return np.ones(n) / n
    if n == 1:
        return np.array([1.0])

    w0 = (1.0 / vols)
    w0 = w0 / w0.sum()

    def objective(w: np.ndarray) -> float:
        return 0.5 * w @ cov @ w - np.sum(np.log(w)) / n

    def grad(w: np.ndarray) -> np.ndarray:
        return cov @ w - (1.0 / n) / w

    result = minimize(
        objective, w0, jac=grad, method="L-BFGS-B",
        bounds=[(1e-8, None)] * n,
        options={"maxiter": 200, "ftol": 1e-14},
    )
    w = np.clip(result.x, 0.0, None)
    if w.sum() < 1e-12:
        return np.ones(n) / n
    return w / w.sum()


class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        symbols = list(data_map.keys())
        close_df = pd.concat({s: df["close"] for s, df in data_map.items()}, axis=1).sort_index()
        ret_df = close_df.pct_change()

        # Universal vol scalar applied per-asset, before combining sub-signals
        # -- this is the "normalize by own realized vol" step both reports
        # describe as the mechanism that makes a single lookback set
        # comparable across asset classes (avoids per-asset lookback tuning).
        vol_scalar_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
        for symbol in symbols:
            realized_vol = ret_df[symbol].ewm(span=VOL_LOOKBACK, min_periods=20).std()
            vol_scalar_df[symbol] = (TARGET_DAILY_VOL / realized_vol).clip(
                lower=VOL_SCALAR_MIN, upper=VOL_SCALAR_MAX
            )

        # Four equal-weighted sub-signals per AQR/SG Tier A anchors.
        sub_signal_dfs = []
        for lb in TSMOM_LOOKBACKS:
            direction = np.sign(close_df / close_df.shift(lb) - 1.0)
            sub_signal_dfs.append(direction)

        sma_fast = close_df.rolling(MA_FAST_SPAN).mean()
        sma_slow = close_df.rolling(MA_SLOW_SPAN).mean()
        ma_direction = np.sign(sma_fast - sma_slow)
        sub_signal_dfs.append(ma_direction)

        # Equal-weighted average of the 4 sub-signal directions, each already
        # vol-scaled to the asset's own target-vol magnitude.
        combined = sum(d.fillna(0.0) for d in sub_signal_dfs) / len(sub_signal_dfs)
        raw_magnitude_df = (combined * vol_scalar_df).fillna(0.0)

        direction_df = np.sign(combined).fillna(0.0)

        result = raw_magnitude_df.copy()
        dates = close_df.index
        for i, ts in enumerate(dates):
            active = direction_df.columns[direction_df.loc[ts] != 0].tolist()
            if not active or i < COV_LOOKBACK:
                continue
            window = ret_df.loc[:ts, active].tail(COV_LOOKBACK)
            if len(window) < max(COV_LOOKBACK // 2, 5) or window.isna().any().any():
                continue
            cov = window.cov().to_numpy()
            weights = _erc_weights(cov)

            mags = raw_magnitude_df.loc[ts, active].abs()
            mag_sum = mags.sum()
            if mag_sum <= 1e-12:
                continue
            mag_share = mags / mag_sum

            for j, symbol in enumerate(active):
                sign = np.sign(direction_df.at[ts, symbol])
                combined_weight = weights[j] * mag_share[symbol]
                result.at[ts, symbol] = sign * combined_weight

        result = result.clip(-1.0, 1.0)
        return {symbol: result[symbol] for symbol in symbols}
