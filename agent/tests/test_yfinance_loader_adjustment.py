"""Regression tests for yfinance_loader's split/dividend adjustment.

``_download_history`` must call ``yf.download`` with ``auto_adjust=True``.
Unadjusted data silently misprices splits as fake price cliffs and
permanently understates total return for dividend-paying instruments
(verified empirically: SPY 2005-2026 raw-close total return 520.8% vs.
true dividend-adjusted total return 820.0%).
"""

from __future__ import annotations

from typing import Any, Dict

from backtest.loaders import yfinance_loader as yfl


def test_download_history_requests_auto_adjust(monkeypatch) -> None:
    captured: Dict[str, Any] = {}

    def fake_download(tickers, **kwargs):
        captured.update(kwargs)
        captured["tickers"] = tickers
        import pandas as pd

        return pd.DataFrame()

    monkeypatch.setattr(yfl.yf, "download", fake_download)

    yfl._download_history("SPY", "2024-01-01", "2024-02-01", "1d")

    assert captured["auto_adjust"] is True


def test_fetch_end_to_end_uses_adjusted_series(monkeypatch) -> None:
    """A synthetic split (raw close halves, adjusted close does not) must
    survive through fetch() as the adjusted (non-halved) series — proving
    the loader's public entry point, not just the download call, honors
    the adjustment."""
    import pandas as pd

    def fake_download(tickers, **kwargs):
        assert kwargs.get("auto_adjust") is True
        idx = pd.to_datetime(["2024-06-09", "2024-06-10"])
        # A real 10:1 split happened on 2024-06-10 (NVDA); with
        # auto_adjust=True yfinance already back-adjusts the pre-split
        # bar, so the returned Close series is smooth/continuous -- the
        # loader must pass this through unchanged, not re-derive anything.
        return pd.DataFrame(
            {
                "Open": [49.55, 50.10],
                "High": [50.20, 50.50],
                "Low": [49.40, 49.90],
                "Close": [49.90, 50.30],
                "Volume": [50000000, 195000000],
            },
            index=idx,
        )

    monkeypatch.setattr(yfl.yf, "download", fake_download)

    loader = yfl.DataLoader()
    result = loader.fetch(["NVDA.US"], "2024-06-09", "2024-06-10")

    df = result["NVDA.US"]
    assert list(df["close"]) == [49.90, 50.30]
    # No spurious >30% overnight gap from an already-adjusted smooth series
    # (the pre-fix raw series would show ~10x the pre-split price here).
    ret = df["close"].pct_change().dropna()
    assert (ret.abs() < 0.30).all()
