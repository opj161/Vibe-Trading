"""Risk parity: equalize marginal risk contributions.

Convex log-barrier formulation (Maillard, Roncalli & Teiletche 2010) solved
via L-BFGS-B, so w_i * MRC_i is equal across assets by construction.
"""

from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from backtest.optimizers.base import BaseOptimizer


class RiskParityOptimizer(BaseOptimizer):
    """Equal risk contribution weights via a convex log-barrier solve.

    Previously used a naive multiplicative fixed-point iteration
    (``w = w * (target / (rc + eps))``, unconstrained and undamped). That
    iteration is only well-behaved for near-diagonal covariance matrices
    (e.g. two positively-correlated assets, the only case any strategy on
    this platform had exercised) -- on a realistic n>2 portfolio containing
    a genuinely negatively-correlated asset (equities+bonds, say), it
    diverges into large-magnitude *negative* weights instead of converging
    (verified directly: a 4-asset equities/gold/bonds/FX-style covariance
    matrix produced weights like [-0.26, -0.12, 0.40, 0.97], which then
    silently flips signal *direction* downstream since sign(weight) no
    longer matches sign(signal) -- see vibe_trading_research_findings.md's
    macro-trend-recalibration round for how this surfaced). The existing
    test suite never caught this because every existing test's covariance
    matrix came from i.i.d. or weakly-correlated synthetic returns.

    Fixed by solving the equivalent convex problem
    ``minimize 0.5*w'*Cov*w - (1/n)*sum(log(w_i))`` (Maillard/Roncalli/
    Teiletche's log-barrier ERC formulation): convex, has a unique positive
    minimizer for any positive-definite covariance matrix, and is solved
    reliably from the same inverse-vol seed via L-BFGS-B with a positivity
    bound -- no undamped multiplicative update, no possibility of a
    sign-flipping negative weight.
    """

    def _calc_weights(self, ctx: Dict[str, Any]) -> np.ndarray:
        """Equal risk contribution weights."""
        cov = ctx["cov"]
        n = cov.shape[0]
        if n == 0:
            return self._equal_weight(0)

        vols = np.sqrt(np.diag(cov))
        if np.any(vols < 1e-12):
            return self._equal_weight(n)

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
            return self._equal_weight(n)
        return w / w.sum()


def optimize(
    ret: pd.DataFrame,
    pos: pd.DataFrame,
    dates: pd.DatetimeIndex,
    lookback: int = 60,
    respect_magnitude: bool = False,
) -> pd.DataFrame:
    """Module-level entry: risk-parity-adjusted positions.

    Args:
        respect_magnitude: When True, scale each asset's risk-parity weight
            by its relative raw-signal magnitude instead of discarding it
            (see ``BaseOptimizer``). Set via config.json
            ``optimizer_params: {"respect_magnitude": true}``.
    """
    return RiskParityOptimizer(
        lookback=lookback, respect_magnitude=respect_magnitude
    ).optimize(ret, pos, dates)
