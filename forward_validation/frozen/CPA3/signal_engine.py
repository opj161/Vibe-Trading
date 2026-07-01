from typing import Dict

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# Sleeve-level composite: fixes what v_CP1_composite_crypto_macro_full found
# to be the real mechanism -- a single per-asset ERC spanning BOTH asset
# classes (CP1) actually made things WORSE than Z4 alone (Sharpe 1.29 vs
# Z4's own 1.55), because pure risk-parity equalizes VOLATILITY across all
# 4 assets with no regard for each SLEEVE's own Sharpe quality, silently
# pulling weight away from the higher-quality crypto sleeve toward the
# lower-vol-but-lower-Sharpe macro sleeve. This variant instead: (1) keeps
# each sleeve's OWN already-validated internal per-asset ERC allocation
# completely unchanged (Z4's BTC/SOL ERC; M1's SPY/GLD ERC), then (2)
# blends the two SLEEVES via a single FIXED top-level weight (a hardcoded
# constant derived from prior research, not computed dynamically in-sample
# -- avoids any lookahead/data-snooping in the sleeve weight itself).
# SLEEVE_CRYPTO_WEIGHT = 0.3 here (a deliberately round, non-fitted number);
# see v_CP3_sleeve_2080_full for a lower-crypto-weight alternative informed
# by the two sleeves' realized-vol ratio.
SLEEVE_CRYPTO_WEIGHT = 0.3

CRYPTO_SYMBOLS = {"BTC-USDT", "SOL-USDT"}
MACRO_SYMBOLS = {"SPY.US", "GLD.US"}

Z4_EMA_FAST_SPAN = 10
Z4_EMA_SLOW_SPAN = 30
Z4_VOL_LOOKBACK = 10
Z4_TARGET_DAILY_VOL = 0.025
Z4_VOL_SCALAR_MIN = 0.25
Z4_VOL_SCALAR_MAX = 1.0
Z4_SHORT_CONVICTION_TILT = 0.43
Z4_CHOP_LOOKBACK = 10
Z4_CHOP_FLIPS_FLOOR = 0.5
Z4_CHOP_FLIPS_CEILING = 4
Z4_CHOP_SCALAR_MIN = 0.5

M1_TSMOM_LOOKBACKS = [21, 63, 252]
M1_MA_FAST_SPAN = 20
M1_MA_SLOW_SPAN = 120
M1_VOL_LOOKBACK = 60
M1_TARGET_DAILY_VOL = 0.010
M1_VOL_SCALAR_MIN = 0.25
M1_VOL_SCALAR_MAX = 1.0

COV_LOOKBACK = 60


def _erc_weights(cov: np.ndarray) -> np.ndarray:
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


def _sleeve_erc_result(close_df, ret_df, symbols, direction_df, raw_magnitude_df):
    """Apply per-asset ERC WITHIN one sleeve only (matches each sleeve's own
    validated design -- Z4's BTC/SOL ERC or M1's SPY/GLD ERC)."""
    result = raw_magnitude_df.copy()
    dates = close_df.index
    for i, ts in enumerate(dates):
        active = [s for s in symbols if direction_df.at[ts, s] != 0] if ts in direction_df.index else []
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
            result.at[ts, symbol] = sign * weights[j] * mag_share[symbol]
    return result


def _crypto_raw_magnitude(close_df, ret_df, symbols):
    direction_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
    vol_scalar_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
    for symbol in symbols:
        close = close_df[symbol]
        ema_fast = close.ewm(span=Z4_EMA_FAST_SPAN, adjust=False).mean()
        ema_slow = close.ewm(span=Z4_EMA_SLOW_SPAN, adjust=False).mean()
        long_setup = (ema_fast > ema_slow) & (close > ema_slow)
        short_setup = (ema_fast < ema_slow) & (close < ema_slow)
        direction_df.loc[long_setup, symbol] = 1.0
        direction_df.loc[short_setup, symbol] = -Z4_SHORT_CONVICTION_TILT
        realized_vol = ret_df[symbol].rolling(Z4_VOL_LOOKBACK).std()
        vol_scalar_df[symbol] = (Z4_TARGET_DAILY_VOL / realized_vol).clip(
            lower=Z4_VOL_SCALAR_MIN, upper=Z4_VOL_SCALAR_MAX
        )
    raw_magnitude_df = (direction_df * vol_scalar_df).fillna(0.0)
    any_flip = (direction_df.diff().abs() > 1e-9).any(axis=1).astype(float)
    rolling_flips = any_flip.rolling(Z4_CHOP_LOOKBACK, min_periods=1).sum()
    frac = ((rolling_flips - Z4_CHOP_FLIPS_FLOOR) / (Z4_CHOP_FLIPS_CEILING - Z4_CHOP_FLIPS_FLOOR)).clip(0.0, 1.0)
    exposure_scalar = 1.0 - frac * (1.0 - Z4_CHOP_SCALAR_MIN)
    raw_magnitude_df = raw_magnitude_df.mul(exposure_scalar, axis=0)
    return direction_df, raw_magnitude_df


def _macro_raw_magnitude(close_df, ret_df, symbols):
    vol_scalar_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
    for symbol in symbols:
        realized_vol = ret_df[symbol].ewm(span=M1_VOL_LOOKBACK, min_periods=20).std()
        vol_scalar_df[symbol] = (M1_TARGET_DAILY_VOL / realized_vol).clip(
            lower=M1_VOL_SCALAR_MIN, upper=M1_VOL_SCALAR_MAX
        )
    sub_signal_dfs = []
    for lb in M1_TSMOM_LOOKBACKS:
        sub_signal_dfs.append(np.sign(close_df[symbols] / close_df[symbols].shift(lb) - 1.0))
    sma_fast = close_df[symbols].rolling(M1_MA_FAST_SPAN).mean()
    sma_slow = close_df[symbols].rolling(M1_MA_SLOW_SPAN).mean()
    sub_signal_dfs.append(np.sign(sma_fast - sma_slow))
    combined = sum(d.fillna(0.0) for d in sub_signal_dfs) / len(sub_signal_dfs)
    raw_magnitude_df = (combined * vol_scalar_df).fillna(0.0)
    direction_df = np.sign(combined).fillna(0.0)
    return direction_df, raw_magnitude_df


class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        symbols = list(data_map.keys())
        crypto_syms = [s for s in symbols if s in CRYPTO_SYMBOLS]
        macro_syms = [s for s in symbols if s in MACRO_SYMBOLS]

        close_df = pd.concat({s: df["close"] for s, df in data_map.items()}, axis=1).sort_index()
        ret_df = close_df.pct_change()

        crypto_dir, crypto_raw = _crypto_raw_magnitude(close_df, ret_df, crypto_syms)
        macro_dir, macro_raw = _macro_raw_magnitude(close_df, ret_df, macro_syms)

        crypto_result = _sleeve_erc_result(close_df, ret_df, crypto_syms, crypto_dir, crypto_raw)
        macro_result = _sleeve_erc_result(close_df, ret_df, macro_syms, macro_dir, macro_raw)

        # ZA4-style counter-regime conviction dampening, crypto legs only
        # (the macro sleeve's AQR-blend already embeds slow trend legs).
        SMA_REGIME_LOOKBACK = 200
        COUNTER_REGIME_SCALE = 0.5
        sma_slow = close_df[crypto_syms].rolling(SMA_REGIME_LOOKBACK, min_periods=100).mean()
        for symbol in crypto_syms:
            has_regime = sma_slow[symbol].notna()
            bull = close_df[symbol] > sma_slow[symbol]
            disagree = has_regime & (((crypto_result[symbol] > 0) & ~bull) | ((crypto_result[symbol] < 0) & bull))
            crypto_result.loc[disagree, symbol] *= COUNTER_REGIME_SCALE

        crypto_result = crypto_result * SLEEVE_CRYPTO_WEIGHT
        macro_result = macro_result * (1.0 - SLEEVE_CRYPTO_WEIGHT)

        # Full-deployment gross recovery (findings log section 63.3/63.4): the
        # sleeve ERC weights*mag_share product construction idles ~half the
        # book; scale x2 under base.py's 1.0 gross cap to recover it.
        GROSS_RECOVERY_SCALE = 2.0
        result = pd.concat([crypto_result, macro_result], axis=1)[symbols]
        result = (result * GROSS_RECOVERY_SCALE).clip(-1.0, 1.0)
        return {symbol: result[symbol] for symbol in symbols}
