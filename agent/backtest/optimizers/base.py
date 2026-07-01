"""Shared base class for portfolio optimizers.

Handles preprocessing, rolling covariance windows, and weight normalization;
subclasses implement ``_calc_weights``.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

import numpy as np
import pandas as pd


class BaseOptimizer(ABC):
    """Abstract portfolio optimizer.

    Subclasses implement ``_calc_weights``; the base handles:
    - active asset selection
    - rolling window slicing and sanity checks
    - covariance matrix + NaN checks
    - applying weights while preserving signal sign (default), or scaling
      those weights by each signal's relative magnitude when
      ``respect_magnitude=True``

    By default the optimizer keeps only the *sign* of a signal-engine's raw
    position and replaces the magnitude entirely with its own risk-based
    weight — a signal engine expressing relative conviction across assets
    (e.g. a long/short tilt) has no effect unless ``respect_magnitude=True``
    is passed, in which case the risk-based weight is scaled by each active
    asset's share of total |signal| magnitude before renormalizing.

    Attributes:
        lookback: Lookback days for covariance / mean.
        respect_magnitude: When True, scale the risk-based weight by each
            asset's relative signal magnitude instead of ignoring it.
        params: Extra keyword args for subclasses.
    """

    def __init__(
        self, lookback: int = 60, respect_magnitude: bool = False, **kwargs: Any
    ) -> None:
        self.lookback = lookback
        self.respect_magnitude = respect_magnitude
        self.params = kwargs

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def optimize(
        self,
        ret: pd.DataFrame,
        pos: pd.DataFrame,
        dates: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """Apply optimizer to position weights.

        Args:
            ret: Return matrix (dates x codes).
            pos: Raw signal positions.
            dates: Date index aligned with ``pos``.

        Returns:
            Adjusted position matrix (not dollar-normalized).
        """
        codes = pos.columns.tolist()
        if len(codes) <= 1:
            return pos

        result = pos.copy()
        for i, dt in enumerate(dates):
            active = [c for c in codes if abs(pos.at[dt, c]) > 1e-9]
            if not active or i < self.lookback:
                continue

            # Exclude dt's own return: it requires dt's close, which isn't
            # observed yet when this weight is applied at dt's open.
            window = ret.loc[:dt, active].iloc[:-1].tail(self.lookback)
            if len(window) < max(self.lookback // 2, 5):
                continue

            ctx = self._build_context(window, active)
            if ctx is None:
                continue

            weights = self._calc_weights(ctx)
            if weights is None or len(weights) != len(active):
                continue

            if self.respect_magnitude:
                weights = self._scale_by_magnitude(pos, dt, active, weights)

            for j, c in enumerate(active):
                sign = np.sign(pos.at[dt, c])
                result.at[dt, c] = sign * weights[j]

        return result

    def _scale_by_magnitude(
        self,
        pos: pd.DataFrame,
        dt: Any,
        active: List[str],
        weights: np.ndarray,
    ) -> np.ndarray:
        """Scale risk-based weights by each asset's relative signal magnitude.

        Args:
            pos: Raw signal positions.
            dt: Current date.
            active: Active asset codes at ``dt``.
            weights: Risk-based weights (sum to 1) from ``_calc_weights``.

        Returns:
            Weights rescaled by relative |signal| magnitude, renormalized to
            sum to 1 (falls back to the unscaled ``weights`` if every active
            signal is ~0, which should not happen since ``active`` already
            filters on magnitude > 1e-9).
        """
        magnitudes = np.array([abs(pos.at[dt, c]) for c in active])
        mag_total = magnitudes.sum()
        if mag_total <= 1e-12:
            return weights
        combined = weights * (magnitudes / mag_total)
        combined_total = combined.sum()
        if combined_total <= 1e-12:
            return weights
        return combined / combined_total

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _build_context(
        self, window: pd.DataFrame, active: List[str]
    ) -> "Dict[str, Any] | None":
        """Build context dict for ``_calc_weights``.

        Default: covariance only. Override to add means, vols, etc.
        Return None to skip the date.

        Args:
            window: Return window for active assets.
            active: Active asset codes.

        Returns:
            Context dict with at least ``cov``, or None.
        """
        cov = window.cov().values
        if np.isnan(cov).any():
            return None
        return {"cov": cov}

    # ------------------------------------------------------------------
    # Subclass API
    # ------------------------------------------------------------------

    @abstractmethod
    def _calc_weights(self, ctx: Dict[str, Any]) -> np.ndarray:
        """Compute target weights from context.

        Args:
            ctx: Dict from ``_build_context``.

        Returns:
            Weight vector (n,) summing to 1.
        """

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(w: np.ndarray) -> np.ndarray:
        """Normalize nonnegative weights to sum 1."""
        w = np.maximum(w, 0.0)
        s = w.sum()
        if s > 1e-12:
            return w / s
        return np.ones(len(w)) / len(w)

    @staticmethod
    def _equal_weight(n: int) -> np.ndarray:
        """Equal weights for n assets."""
        if n == 0:
            return np.array([])
        return np.ones(n) / n
