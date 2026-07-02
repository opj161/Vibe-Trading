"""Plan §1.5's premium-convention cases -- the single highest-risk item in
the whole project. BTC (inverse-style tape): premium_usd = price *
index_price * contracts. SOL_USDC (linear): premium_usd = price * sol_units,
NO index multiplication.
"""
import leg_planner as LP


def test_btc_premium_uses_price_times_index_times_qty():
    # Arrange: plan §1.5's exact BTC case -- price=0.05, S=60_000, qty=1
    price, S, qty = 0.05, 60_000.0, 1.0

    # Act: BTC's ask_per_unit formula is price*(1+hs)*S; at hs=0 this
    # reduces to price*S, and premium = ask_per_unit * qty.
    ask_per_unit = LP._ask_per_unit(price, S, half_spread=0.0, is_btc=True)
    premium = ask_per_unit * qty

    # Assert
    assert premium == 3_000.0


def test_sol_premium_uses_price_times_qty_no_index_multiplier():
    # Arrange: plan §1.5's exact SOL case -- price=12, qty=100, premium=1200
    price, qty = 12.0, 100.0
    S_irrelevant = 999_999.0  # must NOT affect the result -- the whole point of the test

    # Act
    ask_per_unit = LP._ask_per_unit(price, S_irrelevant, half_spread=0.0, is_btc=False)
    premium = ask_per_unit * qty

    # Assert: no index multiplication for SOL
    assert premium == 1_200.0


def test_btc_vs_sol_ask_per_unit_diverge_when_index_is_included():
    # Arrange: identical price/half-spread, different is_btc flag
    price, S, hs = 0.05, 60_000.0, 0.0061

    # Act
    btc_ask = LP._ask_per_unit(price, S, hs, is_btc=True)
    sol_ask = LP._ask_per_unit(price, S, hs, is_btc=False)

    # Assert: BTC scales by S, SOL does not -- these must NOT be equal,
    # guarding against accidentally collapsing the two conventions
    assert btc_ask == price * (1 + hs) * S
    assert sol_ask == price * (1 + hs)
    assert btc_ask != sol_ask
