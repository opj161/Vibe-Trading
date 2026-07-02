from typing import Dict

import numpy as np
import pandas as pd

EMA_FAST_SPAN = 10
EMA_SLOW_SPAN = 30
VOL_LOOKBACK = 10
TARGET_DAILY_VOL = 0.025
VOL_SCALAR_MIN = 0.25
VOL_SCALAR_MAX = 1.0
SHORT_CONVICTION_TILT = 0.43  # ~70/30 long/short weighting, per AdaptiveTrend (arXiv:2602.11708)
COV_LOOKBACK = 60
CHOP_LOOKBACK = 10
CHOP_FLIPS_FLOOR = 0.5   # scalar at 0 flips in the lookback window
CHOP_FLIPS_CEILING = 4   # scalar floors out at this many flips or more
CHOP_SCALAR_MIN = 0.5

# ZD2 (Direction 3 of vibe_trading_forensics_new_directions.md): a properly
# implemented version of ZD1 (see vibe_trading_research_findings.md §70.2,
# ZD1's failure), built on a genuinely new engine primitive --
# config["one_shot_resize"] (agent/backtest/engines/base.py::
# _maybe_one_shot_resize) -- instead of ZD1's misuse of
# rebalance_threshold, which is a continuous price-implied-weight-
# maintenance mechanism (silently reintroduces the section 43 continuous-
# rebalance failure whenever the position's mark-to-market weight drifts
# from a constant target purely from price movement) and cannot cleanly
# express "freeze quantity, one later step". one_shot_resize instead
# reacts only to elapsed holding time and fires at most once per position.
#
# Motivated by section 70.1/70.3's direction-specific whipsaw finding:
# 73% of forward-year SHORT trades died inside 8 days (vs. ~1/3 as
# frequent for longs), and that bucket alone gave back more than half the
# short side's gross winnings. This file is byte-identical to ZA4 (see
# forward_validation/frozen/ZA4/signal_engine.py) except for the final
# SHORT_ENTRY_SCALE step below -- shorts enter at half their fully-computed
# ZA4 size; config.json's one_shot_resize doubles the QUANTITY back
# (2.0x) once a short survives 10 trading days without its direction
# flipping. Applied as the true final step (after gross-recovery scaling)
# so it doesn't disturb the ERC/mag_share ratio between simultaneously
# active BTC/SOL positions of different signs, and doesn't get
# subsequently doubled away by GROSS_RECOVERY_SCALE.
SHORT_ENTRY_SCALE = 0.5


def _erc_weights(cov: np.ndarray) -> np.ndarray:
    """Equal risk contribution weights (mirrors RiskParityOptimizer._calc_weights)."""
    n = cov.shape[0]
    vols = np.sqrt(np.diag(cov))
    if np.any(vols < 1e-12):
        return np.ones(n) / n
    inv_vol = 1.0 / vols
    w = inv_vol / inv_vol.sum()
    for _ in range(5):
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < 1e-12:
            break
        mrc = (cov @ w) / port_vol
        rc = w * mrc
        target = port_vol / n
        w = w * (target / (rc + 1e-12))
        w = w / w.sum()
    return w


class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        symbols = list(data_map.keys())
        close_df = pd.concat({s: df["close"] for s, df in data_map.items()}, axis=1).sort_index()
        ret_df = close_df.pct_change()

        direction_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
        vol_scalar_df = pd.DataFrame(0.0, index=close_df.index, columns=symbols)
        for symbol in symbols:
            close = close_df[symbol]
            ema_fast = close.ewm(span=EMA_FAST_SPAN, adjust=False).mean()
            ema_slow = close.ewm(span=EMA_SLOW_SPAN, adjust=False).mean()
            long_setup = (ema_fast > ema_slow) & (close > ema_slow)
            short_setup = (ema_fast < ema_slow) & (close < ema_slow)
            direction_df.loc[long_setup, symbol] = 1.0
            direction_df.loc[short_setup, symbol] = -SHORT_CONVICTION_TILT

            realized_vol = ret_df[symbol].rolling(VOL_LOOKBACK).std()
            vol_scalar_df[symbol] = (TARGET_DAILY_VOL / realized_vol).clip(
                lower=VOL_SCALAR_MIN, upper=VOL_SCALAR_MAX
            )

        raw_magnitude_df = (direction_df * vol_scalar_df).fillna(0.0)

        any_flip = (direction_df.diff().abs() > 1e-9).any(axis=1).astype(float)
        rolling_flips = any_flip.rolling(CHOP_LOOKBACK, min_periods=1).sum()
        frac = ((rolling_flips - CHOP_FLIPS_FLOOR) / (CHOP_FLIPS_CEILING - CHOP_FLIPS_FLOOR)).clip(0.0, 1.0)
        exposure_scalar = 1.0 - frac * (1.0 - CHOP_SCALAR_MIN)

        result = raw_magnitude_df.mul(exposure_scalar, axis=0)
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
                result.at[ts, symbol] = sign * combined_weight * exposure_scalar.at[ts]

        # ZA4: counter-regime conviction dampening, applied POST-allocation.
        SMA_REGIME_LOOKBACK = 200
        COUNTER_REGIME_SCALE = 0.5
        sma_slow = close_df.rolling(SMA_REGIME_LOOKBACK, min_periods=100).mean()
        for symbol in symbols:
            has_regime = sma_slow[symbol].notna()
            bull = close_df[symbol] > sma_slow[symbol]
            disagree = has_regime & (((result[symbol] > 0) & ~bull) | ((result[symbol] < 0) & bull))
            result.loc[disagree, symbol] *= COUNTER_REGIME_SCALE

        # ZA1 gross-recovery test (see frozen ZA4 for full rationale).
        GROSS_RECOVERY_SCALE = 2.0
        result = (result * GROSS_RECOVERY_SCALE).clip(-1.0, 1.0)

        # ZD2 treatment: shorts enter at half their fully-computed size.
        # Entry-locked sizing means only this final value on the day a
        # short opens ever reaches execution; one_shot_resize (config.json)
        # handles the "double after 10 days" half of the design.
        is_short = result < 0
        result = result.mask(is_short, result * SHORT_ENTRY_SCALE)

        return {symbol: result[symbol] for symbol in symbols}
