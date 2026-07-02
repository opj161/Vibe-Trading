"""Global equity (US / HK) backtest engine.

Market rules:
  US:
    - T+0, long/short allowed
    - Zero commission (retail brokers)
    - Fractional shares supported (round to 0.01)
    - Low slippage (high liquidity)
  HK:
    - T+0, long/short allowed
    - Stamp tax 0.1% bilateral + levies
    - Lot-size rounding (simplified to 100 shares)
    - Higher slippage than US
"""

from __future__ import annotations

import pandas as pd

from backtest.engines.base import BaseEngine


class GlobalEquityEngine(BaseEngine):
    """US / HK equity engine, selected by *market* parameter.

    Config keys:
      - slippage_us: default 0.0005
      - slippage_hk: default 0.001
      - hk_stamp_tax: default 0.001 (0.1% bilateral)
      - hk_commission: default 0.00015 (万1.5)
      - hk_levy: default 0.0000565 (SFC + FRC)
      - hk_settlement: default 0.00002 (CCASS)
      - short_borrow_annual_rate: default 0.0 (opt-in). Daily-accrued fee on
        open short positions' notional, modeling real-world stock-loan/
        margin-interest cost. Previously undocumented as an actual gap:
        every prior long/short US/HK equity backtest on this platform
        costlessly shorted, unlike the crypto engine's funding-fee and
        margin/liquidation modeling. Default 0.0 preserves prior behavior
        exactly; set e.g. 0.003-0.01 (0.3%-1%/yr, easy-to-borrow large-cap
        range) for a realistic long/short backtest. Hard-to-borrow/crowded
        shorts can run far higher — this is a flat approximation, not a
        per-symbol locate-fee model.
    """

    def __init__(self, config: dict, market: str = "us"):
        config = {**config, "leverage": config.get("leverage", 1.0)}
        super().__init__(config)
        self.market = market

        # US defaults
        self.slippage_us: float = config.get("slippage_us", 0.0005)
        # HK defaults
        self.slippage_hk: float = config.get("slippage_hk", 0.001)
        self.hk_stamp_tax: float = config.get("hk_stamp_tax", 0.001)
        self.hk_commission: float = config.get("hk_commission", 0.00015)
        self.hk_levy: float = config.get("hk_levy", 0.0000565)
        self.hk_settlement: float = config.get("hk_settlement", 0.00002)
        self.short_borrow_annual_rate: float = config.get("short_borrow_annual_rate", 0.0)

    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """US/HK: T+0, both directions allowed."""
        return True

    def round_size(self, raw_size: float, price: float) -> float:
        """US: fractional shares (0.01). HK: 100-share lots."""
        if self.market == "hk":
            return max(int(raw_size / 100) * 100, 0)
        return round(max(raw_size, 0.0), 2)

    def calc_commission(self, size: float, price: float, _direction: int, is_open: bool) -> float:
        """US: zero commission. HK: stamp tax + levies.

        ``_direction`` is unused — reserved for future short-borrow fees
        (US Reg-T margin, HK SBL costs).
        """
        if self.market == "hk":
            notional = size * price
            comm = notional * self.hk_commission       # broker commission
            comm += notional * self.hk_stamp_tax       # stamp tax bilateral
            comm += notional * self.hk_levy            # SFC + FRC levies
            comm += notional * self.hk_settlement      # CCASS settlement
            return comm
        # US: zero commission (SEC fee negligible)
        return 0.0

    def apply_slippage(self, price: float, direction: int) -> float:
        """US: low slippage. HK: moderate slippage."""
        rate = self.slippage_hk if self.market == "hk" else self.slippage_us
        return price * (1 + direction * rate)

    def on_bar(self, symbol: str, bar: pd.Series, timestamp: pd.Timestamp) -> None:
        """Daily short-borrow fee accrual on any open short position.

        Opt-in (``short_borrow_annual_rate`` defaults to 0.0, so this is a
        no-op unless explicitly configured) — mirrors the crypto engine's
        per-bar funding-fee hook, applied to the same daily-accrual pattern
        for the equity-shorting-cost analog.
        """
        if self.short_borrow_annual_rate <= 0.0:
            return
        pos = self.positions.get(symbol)
        if pos is None or pos.direction >= 0:
            return
        mark_price = float(bar.get("close", pos.entry_price))
        daily_rate = self.short_borrow_annual_rate / 365.0
        self.capital -= pos.size * mark_price * daily_rate
