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

# Task 5 of the section 27 brainstorm (see vibe_trading_research_findings.md
# section 34): a portfolio-level (strategy-level) volatility-targeting
# overlay, stacked on top of Z4's already-validated chop-frequency scalar --
# distinct from the existing PER-ASSET vol-targeting (which sizes each
# asset's own signal independently). Standard CTA practice: target total
# realized STRATEGY volatility via a shared leverage/gross-exposure
# multiplier, allowing both de-risking (below-target realized vol) AND
# modest leverage (above-target realized vol) rather than a pure dampener.
PORTFOLIO_VOL_LOOKBACK = 20
TARGET_PORTFOLIO_ANNUAL_VOL = 0.35  # ~ Z4's own realized annualized vol, a neutral starting point
PORTFOLIO_OVERLAY_MIN = 0.5
PORTFOLIO_OVERLAY_MAX = 1.5

# Portfolio-level shared-noise exposure scalar (Task 4 of the section 27
# brainstorm, see vibe_trading_research_findings.md section 32).
#
# IMPORTANT implementation note, discovered while building this: applying
# a uniform (same-for-all-assets) scalar to raw signal magnitude and
# routing it through config.json's "optimizer": "risk_parity" +
# respect_magnitude=true hook is a NO-OP. _scale_by_magnitude computes
# risk_parity_weight * (|raw_signal_i| / sum(|raw_signal|)) -- a pure
# RATIO -- so multiplying every active asset's raw_signal by the same
# constant cancels out of both numerator and denominator and never
# reaches execution. Confirmed empirically: an earlier version of this
# file routed through the optimizer hook and produced numbers
# byte-identical to Variant L (no effect at all). Fixed by hand-rolling
# the same equal-risk-contribution weighting the risk_parity optimizer
# performs (Spinu 2013-style inverse-vol seed + Newton refinement, same
# 60-day covariance lookback, same lookahead-safe exclusion of the
# current day's own not-yet-observed return) directly in the signal
# engine, so the exposure scalar can be applied as a genuinely final step
# that the ratio-based optimizer hook would otherwise erase.
#
# Distinct from Variant M's failed per-asset trend-strength GATE (signal-
# space, filtered each asset's own entries independently): this leaves
# each asset's own EMA(10,30) direction completely untouched and instead
# scales TOTAL portfolio notional exposure down (uniformly, post-
# allocation) on days the two assets' raw directions disagree in sign --
# targeting the section 23 finding that BTC's and SOL's EMA-crossover
# flip days co-occur far more than chance (p<0.0001).


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

        # Design D: a genuinely different mechanism from Z1-Z3's same-day
        # snapshot triggers -- a continuous "chop score" based on ROLLING
        # cross-asset flip frequency, closer to the actual Rebalance-
        # Timing-Luck framing (timing luck scales with turnover, section
        # 23/vibe_trading_bar_boundary_deep_dive.md section 2) than a
        # single day's sign agreement. Any symbol's direction changing on a
        # given day counts as one "flip"; the rolling count over the last
        # CHOP_LOOKBACK days is linearly mapped to an exposure scalar
        # between 1.0 (quiet, 0 flips) and CHOP_SCALAR_MIN (choppy,
        # CHOP_FLIPS_CEILING+ flips) -- continuous, not a hard on/off
        # switch, so it can respond to degree of recent instability rather
        # than a single day's binary state.
        any_flip = (direction_df.diff().abs() > 1e-9).any(axis=1).astype(float)
        rolling_flips = any_flip.rolling(CHOP_LOOKBACK, min_periods=1).sum()
        frac = ((rolling_flips - CHOP_FLIPS_FLOOR) / (CHOP_FLIPS_CEILING - CHOP_FLIPS_FLOOR)).clip(0.0, 1.0)
        exposure_scalar = 1.0 - frac * (1.0 - CHOP_SCALAR_MIN)

        # result[ts] becomes pos_final[ts+1] after base.py's external
        # shift(1) -- this loop's frame of reference is PRE-shift, unlike
        # the real optimizer's `dt` which is POST-shift. Two fidelity
        # corrections validated against Variant L directly (see
        # vibe_trading_research_findings.md section 33): the covariance
        # window must NOT exclude ts's own return (that exclusion is only
        # correct in the real optimizer's post-shift frame), and
        # pre-lookback rows must pass through the raw signal (scaled by
        # exposure_scalar for internal consistency) rather than zero.
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

        # Portfolio-level (strategy-level) volatility-targeting overlay,
        # genuinely final step. Simulate the retrospective portfolio return
        # this Z4-mechanics `result` WOULD have realized at each date
        # (result[t-1] executed against ret[t], mirroring base.py's real
        # execution lag exactly), then scale total exposure by
        # TARGET_PORTFOLIO_ANNUAL_VOL / rolling-realized-vol, clipped to
        # [PORTFOLIO_OVERLAY_MIN, PORTFOLIO_OVERLAY_MAX] -- allows both
        # de-risking AND modest leverage, unlike the chop-frequency scalar
        # (which only ever dampens). Uses only strictly past portfolio
        # returns at each date (rolling window ending at ts, using
        # result.shift(1) so ts's own not-yet-realized return is excluded)
        # -- leakage-safe by construction.
        simulated_portfolio_ret = (result.shift(1) * ret_df[symbols]).sum(axis=1)
        realized_vol = simulated_portfolio_ret.rolling(PORTFOLIO_VOL_LOOKBACK, min_periods=10).std() * np.sqrt(365)
        target_daily_equiv = TARGET_PORTFOLIO_ANNUAL_VOL
        overlay = (target_daily_equiv / realized_vol).clip(PORTFOLIO_OVERLAY_MIN, PORTFOLIO_OVERLAY_MAX)
        overlay = overlay.fillna(1.0)  # no history yet -> neutral, not de-risked or levered
        result = result.mul(overlay, axis=0)

        result = result.clip(-1.5, 1.5)  # allow the overlay's leverage headroom past +-1.0
        return {symbol: result[symbol] for symbol in symbols}
