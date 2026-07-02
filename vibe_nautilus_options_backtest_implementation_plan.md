# Vibe-Trading × NautilusTrader BTC/SOL Deribit Options Backtest Implementation Plan

**Scope:** Validate whether the Vibe-Trading BTC/SOL Deribit options-expression research can be implemented natively in NautilusTrader, identify issues/gaps in the prior plan, and produce a corrected implementation blueprint.

**Codebases scanned:**

- `Vibe-Trading(2).zip`, extracted under `/mnt/data/vibe_full_scan`
- `nautilus_trader-develop.zip`, extracted under `/mnt/data/nt_scan/nautilus_trader-develop`

**Important limitation:** the raw Deribit option trade Parquets referenced by Vibe are **not present** in the uploaded Vibe archive. The validation below is based on the repository code, derived CSV outputs, and research logs. A full rerun against raw BTC/SOL Deribit option tapes is a required acceptance gate.

---

## 1. Executive verdict

The plan remains directionally correct: **NautilusTrader is the right implementation host** for a serious BTC/SOL Deribit options backtest. It provides native primitives that FinceptTerminal lacks: crypto option instruments, option-chain slices, BBO/Greeks replay, Deribit/Tardis integrations, matching, portfolio accounting, capped option fees, and native option expiry handling.

However, the implementation plan needs several important corrections:

1. **Exact Vibe parity is not the same as realistic market replay.** Vibe’s current research scripts use real historical option entry prints but model exits/marks using a Black-Scholes surface plus empirical spread haircuts. A Nautilus backtest using only real BBO replay will not exactly match Vibe §81/§82. We need a dedicated **parity mode** with synthetic Vibe-style quotes/marks before running a more realistic **market-replay mode**.

2. **The Vibe selector is not “nearest ATM.”** For exact parity, Vibe selects the earliest valid post-anchor trade within the entry window after filtering for DTE and moneyness. Improved market mode can use nearest-ATM/quote-quality ranking, but parity mode must reproduce the original rule.

3. **The Vibe option fee model appears asymmetric in code.** The BTC/SOL scripts charge option entry fees and expiry settlement fees, but ordinary signal-flip option exits do not appear to charge a separate close fee. Nautilus’s capped option fee model will charge entry and close executions. Therefore the implementation needs both a strict-parity fee mode and a corrected/native fee mode.

4. **Nautilus native option expiry settlement currently has zero commission.** Vibe charges a settlement/delivery fee at expiry. We must add expiry settlement fees through post-processing or custom settlement logic.

5. **The uploaded SOL derived CSV and the research narrative disagree on run count.** The uploaded `phase5_sol_per_run.csv` has 46 rows, while the research write-up says 53 in-window SOL direction runs. The key matched/skipped short decomposition still matches the narrative, but the first implementation gate must rerun the Vibe scripts from raw Parquets and freeze the true acceptance target.

6. **BTC and SOL premium conventions must be tested explicitly.** BTC Deribit options are BTC-premium/inverse-style in the Vibe script; SOL_USDC options are linear USDC-style. SOL premium is `price × SOL_units`, with no index multiplier. This deserves a dedicated unit test because a single multiplier mistake invalidates the result.

Final recommendation:

> Build a Nautilus-native Vibe options backtest in two modes: first a strict Vibe-parity mode using synthetic Vibe-style catalog data, then a realistic market-replay mode using Tardis/Deribit BBO and Greeks. Do not port the full Vibe signal engine first; import the validated Vibe direction-run ledgers and focus the implementation on option expression.

---

## 2. What Vibe-Trading actually contains

### 2.1 Relevant Vibe research files

The core options research lives in:

```text
research/vrp_deribit/data_prep.py
research/vrp_deribit/phase1_vrp_validation.py
research/vrp_deribit/phase2_short_straddle_backtest.py
research/vrp_deribit/phase3_delta_hedged_backtest.py
research/vrp_deribit/phase4_trend_expression_options.py
research/vrp_deribit/phase4b_hybrid_and_stress.py
research/vrp_deribit/phase5_sol_expression.py
```

The key derived run/result files are:

```text
research/vrp_deribit/derived/btc_direction_runs.csv
research/vrp_deribit/derived/sol_direction_runs.csv
research/vrp_deribit/derived/phase4_per_run.csv
research/vrp_deribit/derived/phase5_sol_per_run.csv
```

The raw option tapes referenced by the scripts are not included in the uploaded archive:

```text
data/parquet/btc_option_trades_deribit.parquet
data/parquet/sol_usdc_option_trades_deribit.parquet
```

That means the current upload is sufficient for code review and derived-result validation, but not for full reproduction.

---

### 2.2 BTC phase 4 mechanics

`phase4_trend_expression_options.py` uses these core constants:

```text
CAPITAL = 1_000_000
ENTRY_NOTIONAL = 500_000
SPOT_TAKER = 0.001
OPT_FEE_RATE = 0.0003
OPT_FEE_CAP = 0.125
SETTLE_FEE_RATE = 0.00015
HALF_SPREAD = 0.0061
PREMIUM_BUDGET_FRAC = 0.10
DTE_BAND = (20, 40)
ENTRY_FWD_DAYS = 3
```

BTC entry logic:

```text
anchor window: [run_start, run_start + 3 days]
option type: call for long expression, put for short expression
DTE: 20–40 days
moneyness: abs(log(strike / underlying)) < 0.075
selection: earliest valid post-anchor trade after filters
```

BTC premium convention in the Vibe script:

```text
premium_usd = option_price_btc × BTC_index_price × contracts
```

BTC budget sizing:

```text
budget = 10% × ENTRY_NOTIONAL
contracts = budget / (entry_price_btc × (1 + half_spread) × BTC_index_price)
```

BTC delta sizing diagnostic:

```text
contracts = spot_qty / max(abs(delta), 0.05)
```

Vibe’s BTC phase 4/4b research conclusion:

```text
Spot baseline: approximately +$1.24M, Sharpe ~0.91
Option budget track: approximately +$1.62M, Sharpe ~0.91
H1 hybrid, spot longs + budget puts for shorts: approximately +$1.56M, Sharpe ~1.00, MaxDD ~-21.0%
```

---

### 2.3 SOL phase 5 mechanics

`phase5_sol_expression.py` uses the same strategy constants, but with a different premium convention.

SOL instrument parsing expects symbols like:

```text
SOL_USDC-28JUN24-150-P
```

SOL premium convention in the Vibe script:

```text
premium_usd = option_price × SOL_units
```

There is **no index multiplication** for SOL_USDC options in the Vibe research code.

SOL budget sizing:

```text
budget = 10% × ENTRY_NOTIONAL
SOL_units = budget / (entry_price_usd × (1 + half_spread))
```

SOL half-spread is measured from the tape as:

```text
median(abs(price - mark_price) / mark_price)
```

The research log reports the measured SOL half-spread as approximately:

```text
1.31%
```

The SOL phase 5 research conclusion:

```text
Spot baseline: approximately +$209k, Sharpe ~0.37, MaxDD ~-35.7%
H1 hybrid, spot longs + budget puts for shorts: approximately +$262k, Sharpe ~0.54, MaxDD ~-21.7%
2x spread stress: approximately +$238k, Sharpe ~0.51
```

The most important SOL decomposition:

```text
Matched short runs:
  spot shorts: approximately -$119k
  budget puts: approximately +$83k
  swing: approximately +$202k

Skipped option-entry short runs:
  skipped spot shorts were approximately +$149k winners
```

This means the hybrid won despite a coverage handicap.

---

### 2.4 Derived-result validation issue

The uploaded `phase5_sol_per_run.csv` has 46 rows:

```text
18 long rows
28 short rows
20 matched short rows with nonzero budget-put P&L
8 skipped short rows with zero budget-put P&L
```

But the research narrative says:

```text
53 real SOL direction runs
33 short runs
14 no-option-entry runs
```

The matched/skipped short decomposition in the CSV aligns with the narrative, but the row count does not. This is likely a stale/partial derived-output issue or a mismatch between the uploaded archive and the latest run. It must be resolved before treating any Nautilus reproduction as valid.

**Acceptance requirement:** rerun Vibe `phase4`/`phase4b`/`phase5` from raw Parquets, regenerate all derived CSVs, and freeze those outputs as the official parity target.

---

### 2.5 Vibe’s existing `options_portfolio.py` is not enough

Vibe also contains:

```text
agent/backtest/engines/options_portfolio.py
```

This is a theoretical Black-Scholes options backtest engine driven by underlying OHLCV. It supports synthetic option pricing, Greeks, expiry, and portfolio bookkeeping.

It does **not** reconstruct real Deribit historical option chains, select real historical contracts, replay option BBO, model venue fills, or use Deribit instrument metadata. It is useful as a payoff/pricing reference, not as the target implementation engine.

---

## 3. What NautilusTrader actually provides

### 3.1 Relevant Nautilus files and docs

The most important Nautilus files/docs scanned were:

```text
docs/concepts/options.md
docs/concepts/data/option_greeks.md
docs/integrations/deribit.md
docs/integrations/tardis.md
examples/backtest/tardis_option_chain.py

nautilus_trader/model/instruments/crypto_option.pyx
nautilus_trader/backtest/engine.pyx
nautilus_trader/backtest/config.py
nautilus_trader/persistence/catalog/parquet.py

crates/adapters/deribit/src/common/parse.rs
crates/adapters/tardis/src/replay.rs
crates/execution/src/models/fee.rs
crates/execution/src/matching_engine/engine.rs
crates/model/src/data/option_chain.rs
crates/data/src/option_chains/manager.rs
```

---

### 3.2 Native option-chain replay

Nautilus option-chain backtesting expects a catalog with:

```text
CryptoOption or OptionContract instruments
QuoteTick records for option BBO
OptionGreeks records for IV/delta/underlying price
```

`OptionChainSlice` joins latest BBO and Greeks. This is exactly the primitive needed for historical contract selection.

The example:

```text
examples/backtest/tardis_option_chain.py
```

shows:

- loading option instruments from a `ParquetDataCatalog`,
- building `OptionSeriesId`,
- subscribing to option chains,
- selecting options by delta/strike range,
- submitting market/limit orders,
- running through `BacktestNode`.

This is the correct implementation blueprint.

---

### 3.3 CryptoOption supports Deribit-style instruments

Nautilus `CryptoOption` contains the fields needed for Deribit BTC/SOL options:

```text
instrument_id
raw_symbol
underlying
quote_currency
settlement_currency
is_inverse
option_kind
strike_price
activation_ns
expiration_ns
price_precision
size_precision
price_increment
size_increment
multiplier
lot_size
maker_fee
taker_fee
```

This maps to both:

```text
BTC-28JUN24-70000-P
SOL_USDC-28JUN24-150-P
```

Nautilus’s Deribit parser already handles Deribit option symbols and creates `CryptoOption` instruments from Deribit metadata.

Important Deribit quantity note from the adapter documentation/code:

```text
Nautilus quantities map to Deribit amount, not Deribit contracts.
Options and linear futures amounts are underlying base-currency amounts.
The adapter does not apply a contract_size again as multiplier.
```

This is critical for SOL: quantity should be treated as SOL units unless a separate provider-specific conversion is deliberately introduced.

---

### 3.4 Tardis support is directly relevant

The Tardis adapter can write Nautilus catalog data from Tardis replay files.

Relevant Tardis format support:

```text
instrument metadata -> CryptoOption instruments
option_summary -> OptionGreeks
option_summary BBO extraction -> QuoteTick
```

A realistic market-replay implementation should use:

```text
Tardis option_summary with extract_bbo_as_quotes=true
```

This gives actual BBO and Greeks rather than Vibe’s trade-entry/surface-exit approximation.

Caveat: Tardis data availability/licensing is a separate dependency. The implementation should not require Tardis for strict Vibe parity, but it is the preferred market-replay source.

---

### 3.5 Native capped option fee model

Nautilus includes:

```text
CappedOptionFeeModel
```

It supports a maker/taker fee rate and a cap rate. This maps well to Vibe/Deribit-style option fees:

```text
fee = min(rate × underlying_price, cap × option_price) × quantity × multiplier
```

For non-inverse/linear options, Nautilus requires access to the option underlying price when computing fees. This can come from:

- an underlying instrument price in the cache, or
- cached `OptionGreeks.underlying_price`.

Therefore the implementation must provide underlying index prices and/or `OptionGreeks.underlying_price`, especially for SOL_USDC options.

---

### 3.6 Native option expiry exists, but settlement fee is missing

Nautilus has native option expiry handling. For options whose underlying is an `IndexInstrument`, expiry can cash settle by intrinsic value.

This requires underlying instruments like:

```text
BTC.DERIBIT
SOL.DERIBIT
```

However, native Nautilus expiry close fills currently have zero commission. Vibe charges a settlement fee:

```text
SETTLE_FEE_RATE = 0.00015
```

Therefore expiry settlement fee must be added via:

1. post-processing adjustment, or
2. a custom fee/settlement hook, or
3. strategy-level manual settlement before native expiry.

The cleanest first implementation is post-processing, because it preserves native matching/portfolio flow while making the research ledger correct.

---

### 3.7 Important option-chain subscription constraint

Nautilus option-chain subscriptions are series-based:

```text
OptionSeriesId = venue + underlying + settlement_currency + expiration_ns
```

Vibe selection searches a 20–40 DTE band, which can span multiple expiries. Therefore a single subscription is not enough.

The implementation needs a **series planner** that precomputes all candidate expiries per run and subscribes to the corresponding series, or dynamically manages subscriptions as the clock advances.

---

## 4. Corrected implementation architecture

Create a new module, preferably inside the Vibe repo so it can directly access Vibe runs and research outputs:

```text
research/nautilus_deribit_options/
```

Recommended files:

```text
README.md
config.py
signal_loader.py
vibe_tape_loader.py
deribit_symbols.py
surface.py
instrument_factory.py
catalog_vibe_parity.py
catalog_tardis_market.py
series_planner.py
selector.py
sizing.py
strategy.py
run_backtest.py
postprocess.py
stress_grid.py

_tests/
    test_deribit_symbols.py
    test_premium_conventions.py
    test_fee_model.py
    test_selector_parity.py
    test_no_lookahead.py
    test_rollover.py
    test_settlement_fee.py
```

---

## 5. Two-mode design

### 5.1 Mode A — Vibe strict-parity mode

Purpose:

> Reproduce Vibe §81/§82 as closely as possible using the same direction runs, contract-selection rules, premium conventions, spread assumptions, and fee behavior.

This mode should use a synthetic Nautilus catalog generated from Vibe’s raw Deribit trade Parquets and Vibe’s Black-Scholes/vol-surface marking logic.

Inputs:

```text
research/vrp_deribit/derived/btc_direction_runs.csv
research/vrp_deribit/derived/sol_direction_runs.csv

data/parquet/btc_option_trades_deribit.parquet
data/parquet/sol_usdc_option_trades_deribit.parquet
```

Optional Vibe-derived surface/index files, regenerated if stale:

```text
research/vrp_deribit/derived/daily_index.csv
research/vrp_deribit/derived/term_structure.csv
```

Output objective:

```text
Reproduce BTC/SOL per-run results and H1 hybrid relationships.
```

Important parity details:

- selector must choose the earliest valid post-anchor trade, not necessarily the nearest ATM option;
- BTC premium must follow the Vibe BTC convention;
- SOL premium must not use an index multiplier;
- strict parity should optionally reproduce Vibe’s apparent no-close-fee behavior on ordinary option exits;
- expiry settlement fee must be applied because Vibe applies it;
- synthetic quote events must exist at entry, run-end exits, daily marks if needed, and expiry/roll points.

---

### 5.2 Mode B — Nautilus market-replay mode

Purpose:

> Test the same Vibe option-expression rule under more realistic historical tradability using actual BBO/Greeks replay.

Recommended data source:

```text
Tardis option_summary -> Nautilus OptionGreeks
Tardis BBO extraction -> Nautilus QuoteTick
Tardis instrument metadata -> Nautilus CryptoOption
```

Market-replay mode should use true Nautilus matching, BBO, fees, option-chain slices, and expiry handling.

This mode is expected to differ from Vibe strict parity because it uses actual historical quote availability and fill mechanics instead of Vibe’s trade-entry/surface-exit approximation.

Output objective:

```text
Validate whether the H1 hybrid survives real BBO costs, quote gaps, expiry, and native portfolio accounting.
```

---

## 6. Data model

### 6.1 `VibeRun`

```python
@dataclass(frozen=True)
class VibeRun:
    run_id: str
    underlying: str          # BTC or SOL
    start: pd.Timestamp
    end: pd.Timestamp
    direction: int           # +1 long, -1 short
    days: float
    target_notional_usd: float = 500_000.0
    source: str = "ZA4_or_ZD2_direction_runs"
```

### 6.2 `OptionCandidate`

```python
@dataclass(frozen=True)
class OptionCandidate:
    instrument_id: str
    raw_symbol: str
    underlying: str
    option_kind: str         # C or P
    strike: float
    expiry: pd.Timestamp
    dte: float
    underlying_price: float
    log_moneyness: float
    bid: float
    ask: float
    mid: float
    delta: float | None
    mark_iv: float | None
    ts: pd.Timestamp
    spread_frac: float
```

### 6.3 `OptionLegPlan`

```python
@dataclass(frozen=True)
class OptionLegPlan:
    run_id: str
    expression: str          # budget_put, delta_put, etc.
    candidate: OptionCandidate
    quantity: float
    premium_budget_usd: float
    expected_entry_cost_usd: float
    sizing_mode: str
```

### 6.4 `RunAttribution`

```python
@dataclass
class RunAttribution:
    run_id: str
    underlying: str
    direction: int
    start: pd.Timestamp
    end: pd.Timestamp
    selected_instrument: str | None
    strike: float | None
    expiry: pd.Timestamp | None
    dte_at_entry: float | None
    log_moneyness_at_entry: float | None
    entry_ts: pd.Timestamp | None
    exit_ts: pd.Timestamp | None
    quantity: float
    premium_paid: float
    entry_fee: float
    close_fee: float
    settlement_fee: float
    spot_pnl: float
    option_pnl: float
    hybrid_pnl: float
    skip_reason: str | None
```

---

## 7. Catalog construction

### 7.1 Vibe parity catalog

`catalog_vibe_parity.py` should:

1. Load Vibe raw option trade Parquets.
2. Parse Deribit instrument symbols.
3. Create Nautilus `CryptoOption` instruments.
4. Create underlying `IndexInstrument` entries:

```text
BTC.DERIBIT
SOL.DERIBIT
```

5. Create tradable linear instruments for spot/perp longs if simulating longs through Nautilus orders:

```text
BTC_USDC.DERIBIT or BTC-PERPETUAL.DERIBIT
SOL_USDC.DERIBIT or SOL-PERPETUAL.DERIBIT
```

6. Generate synthetic `QuoteTick` BBO for option entries and exits.
7. Generate `OptionGreeks` with:

```text
underlying_price
mark_iv as decimal, not percent
delta
```

8. Write all data to `ParquetDataCatalog`.

For parity mode, synthetic BBO should be generated from Vibe’s price/mark assumptions:

```text
bid = model_mid × (1 - half_spread × stress_multiplier)
ask = model_mid × (1 + half_spread × stress_multiplier)
```

BTC normalized parity option:

```text
model_mid_usd = model_mid_btc × BTC_index_price
```

SOL parity option:

```text
model_mid_usd = model_mid_usdc
```

Recommended parity choice:

> Use normalized USD/USDC option instruments first. True BTC-inverse accounting can be implemented later after parity is proven.

Why: true BTC-settled accounting introduces multi-currency P&L conversion, which creates noise when the first goal is reproducing Vibe’s USD research numbers.

---

### 7.2 Tardis market-replay catalog

`catalog_tardis_market.py` should:

1. Use Nautilus’s Tardis replay pipeline where possible.
2. Load/write Deribit option instruments.
3. Convert `option_summary` into `OptionGreeks`.
4. Extract BBO as `QuoteTick` using `extract_bbo_as_quotes=true`.
5. Include BTC/SOL underlying index or spot/perp price streams.
6. Confirm settlement/quote currencies and `is_inverse` flags.

This catalog is the basis for realistic market replay.

---

## 8. Series planning and option-chain subscription

Because `OptionSeriesId` is expiry-specific, implement:

```text
series_planner.py
```

For each Vibe run, compute all expiries satisfying:

```text
20 <= DTE(run_start, expiry) <= 40
```

Then subscribe to each relevant series:

```text
OptionSeriesId(
    venue="DERIBIT",
    underlying="BTC" or "SOL",
    settlement_currency="BTC" for true inverse BTC or "USDC" for normalized/SOL,
    expiration_ns=expiry_ns,
)
```

For strict parity mode, it may be simpler to precompute exact candidate instruments and feed/subcribe only those instruments. For market-replay mode, use native option-chain slices.

---

## 9. Contract selector

`selector.py` should support multiple modes.

### 9.1 Strict Vibe parity selector

This is the first required selector.

Rules:

```text
entry window: run_start <= ts <= run_start + 3 days
option kind: PUT for short-expression H1
DTE: 20–40
moneyness: abs(log(strike / underlying_price)) < 0.075
selection: earliest valid post-anchor trade/slice after filters
```

This rule is intentionally not optimized. It exists to reproduce Vibe.

### 9.2 Improved market-replay selector

After parity is proven, test better selectors:

```text
nearest ATM
5% OTM
10% OTM
target delta
minimum spread
minimum BBO freshness
minimum open interest / recent quote count
DTE target near 30 days
```

The selector should always return both the chosen candidate and the reason for rejected candidates.

---

## 10. Sizing

`sizing.py` should implement at least two modes.

### 10.1 Premium-budget sizing

This is the main production/research mode.

```text
premium_budget_usd = premium_budget_frac × target_notional_usd
```

Default:

```text
premium_budget_frac = 0.10
```

BTC normalized parity:

```text
quantity_btc_units = premium_budget_usd / option_ask_usd
```

BTC true inverse mode:

```text
premium_usd = option_ask_btc × BTC_index_price × quantity_btc_units
quantity_btc_units = premium_budget_usd / (option_ask_btc × BTC_index_price)
```

SOL linear mode:

```text
premium_usdc = option_ask_usdc × quantity_sol_units
quantity_sol_units = premium_budget_usd / option_ask_usdc
```

Respect Nautilus instrument `lot_size`, `size_increment`, and `min_trade_amount`.

### 10.2 Delta-matched diagnostic sizing

This is not the preferred implementation mode, but it is required to reproduce the research finding that SOL delta matching collapses.

```text
quantity = spot_quantity / max(abs(delta), 0.05)
```

---

## 11. Strategy state machine

`strategy.py` should implement `VibeHybridOptionsStrategy` as a native Nautilus strategy.

### 11.1 Per-underlying state

```text
flat
linear_long
pending_put_entry
open_put
closing
rolling
skipped
```

### 11.2 On run start

If direction is long:

```text
open linear long exposure
```

If direction is short:

```text
create pending put-entry request
entry deadline = run_start + 3 days
budget = 10% × target_notional
```

### 11.3 On option-chain slice / quote update

If there is a pending short-entry request:

1. evaluate candidate puts,
2. apply selector,
3. size by premium budget,
4. submit buy order.

Order style:

```text
market order or marketable limit at ask
```

For parity mode, marketable limit at synthetic ask gives controlled fill behavior.

### 11.4 On run end

If linear long is open:

```text
close linear position
```

If put is open:

```text
sell put at market/bid or marketable limit
```

### 11.5 On option expiry before run end

If native expiry occurs while a short run continues:

1. allow or simulate cash settlement,
2. apply settlement fee in post-processing,
3. open a new pending put-entry request if rolling is enabled.

This reproduces Vibe’s roll-through-expiry behavior.

### 11.6 If no option entry appears

Default parity fallback:

```text
skip option entry and record skip_reason
```

Alternative research fallbacks to test later:

```text
nearest available option
reduced linear short
flat
wider DTE/moneyness window
```

---

## 12. Fees, fills, and settlement

### 12.1 Strict parity fee mode

Purpose: reproduce Vibe code behavior.

Use:

```text
entry fee: min(OPT_FEE_RATE × underlying_price × quantity, OPT_FEE_CAP × premium)
ordinary close fee: optional/off for strict code parity
expiry settlement fee: SETTLE_FEE_RATE logic from Vibe
```

Because Vibe code appears not to charge ordinary close fees on signal-flip option exits, strict mode should preserve that behavior for first reproduction.

### 12.2 Corrected/native fee mode

Purpose: more conservative and closer to exchange execution.

Use Nautilus:

```text
CappedOptionFeeModel(maker_rate=0.0003, taker_rate=0.0003, cap_rate=0.125)
```

This will charge entry and close execution fees.

Add expiry settlement fee separately because Nautilus native expiry commission is zero.

### 12.3 Spread stress

Support:

```text
1x measured half-spread
2x measured half-spread
3x measured half-spread
```

Measured starting points from Vibe research:

```text
BTC half-spread: 0.61%
SOL half-spread: 1.31%
```

For market replay, use actual BBO first, then apply stress via worse fill assumptions or quote widening in a stress catalog.

---

## 13. Backtest runner

`run_backtest.py` should follow the Nautilus `BacktestNode` pattern.

Required config pieces:

```text
BacktestVenueConfig
BacktestDataConfig
BacktestRunConfig
BacktestEngineConfig
```

Recommended venue setup for normalized parity:

```text
venue: DERIBIT_SIM
oms_type: NETTING
account_type: MARGIN
book_type: L1_MBP
starting balance: 1,000,000 USDC or USD
fee model: strict parity custom accounting or CappedOptionFeeModel in corrected mode
```

Data config should include:

```text
QuoteTick for option instruments
OptionGreeks for option instruments
underlying index/spot prices
linear instrument prices if linear longs are simulated natively
```

For initial parity, linear spot baseline can be post-processed from Vibe-style run calculations while the option leg is validated in Nautilus. Once option parity is proven, simulate linear longs through Nautilus as well.

---

## 14. Post-processing and diagnostics

Do not rely only on Nautilus aggregate performance output. Vibe’s research insight depends on per-run diagnostics.

`postprocess.py` must produce:

```text
equity_curve.csv
fills.csv
option_legs.csv
run_attribution.csv
skipped_entries.csv
stress_summary.csv
grid_summary.csv
repro_report.md
```

`run_attribution.csv` must include:

```text
run_id
underlying
run_start
run_end
direction
duration_days
expression
selected_instrument
strike
expiry
dte_at_entry
log_moneyness_at_entry
entry_ts
exit_ts
quantity
premium_paid
entry_bid
entry_ask
exit_bid
exit_ask
entry_fee
close_fee
settlement_fee
spot_pnl
option_pnl
hybrid_pnl
skip_reason
```

Required report tables:

```text
spot baseline vs H1 hybrid
option budget vs option delta matched
long runs only
short runs only
matched short runs
skipped short runs
<8d whipsaw bucket
8–30d bucket
>30d bucket
spread stress: 1x / 2x / 3x
```

---

## 15. Acceptance gates

### Gate 0 — Data and target freeze

- Raw BTC/SOL Deribit Parquets are available.
- Vibe phase 4/4b/5 scripts rerun successfully.
- Derived CSV row counts and research-log numbers are reconciled.
- Frozen acceptance files are stored under a dated artifact directory.

### Gate 1 — Parser and premium convention tests

Must pass:

```text
BTC-28JUN24-70000-P parses correctly
SOL_USDC-28JUN24-150-P parses correctly
BTC premium convention matches Vibe phase 4
SOL premium convention matches Vibe phase 5 with no index multiplier
expiry timestamp is correct
quantity maps to Deribit amount semantics
```

### Gate 2 — One-run parity smoke test

For one BTC short run and one SOL short run:

- selected option matches Vibe,
- quantity matches Vibe within rounding tolerance,
- entry cost matches Vibe,
- option P&L matches Vibe under strict parity rules.

### Gate 3 — Full strict-parity reproduction

Reproduce broad Vibe results:

BTC:

```text
H1 Sharpe > spot Sharpe
H1 P&L > spot or close to reported +$1.56M
2x spread stress survives
```

SOL:

```text
H1 P&L > spot P&L
H1 Sharpe > spot Sharpe
H1 MaxDD materially better than spot
matched shorts show approximately +$200k swing
skipped shorts are explicitly reported
```

### Gate 4 — Corrected-fee sensitivity

Rerun with conservative/native fees:

- entry and close option fees,
- settlement fees at expiry,
- 2x and 3x spread stress.

The strategy should not depend entirely on the strict-parity no-close-fee behavior.

### Gate 5 — Market-replay validation

Using Tardis/Deribit BBO/Greeks catalog:

- option entries are based on real BBO availability,
- fills occur through Nautilus matching,
- capped option fees are native,
- settlement fees are post-processed,
- result remains economically consistent with Vibe’s thesis.

### Gate 6 — Robustness plateau

Run a grid and verify the result is not a single lucky parameter point.

Grid:

```text
premium budget: 5%, 7.5%, 10%, 12.5%, 15%
DTE band: 14–30, 20–40, 30–60
moneyness: ATM, 5% OTM, 10% OTM
spread stress: 1x, 2x, 3x
fallback: skip, nearest option, reduced linear short, flat
signal base: ZA4, ZD2 if available
```

Preferred robustness outcome:

```text
7.5%–12.5% budget range works
20–40DTE and 30–60DTE both acceptable
2x spread stress survives
SOL budget puts continue beating delta-matched sizing
matched-short improvement remains large
```

---

## 16. Specific unit tests to write

### 16.1 Symbol parsing

```text
BTC-28JUN24-70000-P
SOL_USDC-28JUN24-150-P
```

Assert:

```text
underlying
settlement/quote currency
option kind
strike
expiry
is_inverse where applicable
```

### 16.2 Premium conventions

BTC:

```text
price_btc = 0.05
BTC_index = 60,000
quantity = 1 BTC
premium_usd = 3,000
```

SOL:

```text
price_usdc = 12
quantity = 100 SOL
premium_usd = 1,200
```

Assert SOL does **not** multiply by SOL index.

### 16.3 Selector parity

Given multiple valid candidates inside the entry window, assert strict parity chooses the earliest valid post-anchor observation, not the closest strike or best spread.

### 16.4 No lookahead

Assert candidates with `ts < run_start` or `ts > run_start + 3 days` are rejected.

### 16.5 Fee behavior

- strict mode reproduces Vibe fee behavior;
- corrected mode charges entry and close fees;
- expiry settlement fee is added because Nautilus native expiry commission is zero;
- linear/SOL option fees have access to `underlying_price`.

### 16.6 Expiry and rollover

If a short run spans an option expiry:

- first option settles,
- settlement fee is applied,
- new option entry is attempted if `roll_on_expiry=True`,
- skip is recorded if no new entry exists.

### 16.7 Skipped entries

If no valid option appears in the 3-day window:

- no position is opened,
- `skip_reason` is populated,
- hybrid P&L reflects the fallback policy.

---

## 17. Build sequence

### Phase 0 — Freeze Vibe target

- Restore raw BTC/SOL option Parquets.
- Rerun Vibe phase 4, phase 4b, and phase 5.
- Resolve SOL run-count discrepancy.
- Save official target CSVs.

### Phase 1 — Metadata and parser layer

Build:

```text
deribit_symbols.py
instrument_factory.py
```

Run parser and premium-convention tests.

### Phase 2 — Signal loader

Build:

```text
signal_loader.py
```

Normalize BTC/SOL direction runs into `VibeRun` objects.

### Phase 3 — One-run parity catalog

Build enough synthetic catalog data for one BTC short run and one SOL short run.

Validate:

- option selection,
- quote creation,
- quantity,
- entry/exit cost,
- fee calculation,
- post-processing P&L.

### Phase 4 — Nautilus strategy smoke test

Build minimal `VibeHybridOptionsStrategy` that can:

- subscribe to a relevant option series,
- receive option-chain slice/quotes,
- buy one put,
- close one put,
- export fills.

### Phase 5 — Full BTC strict parity

Run all BTC direction runs.

Reproduce phase 4/4b tables.

### Phase 6 — Full SOL strict parity

Run all SOL direction runs.

Reproduce phase 5 tables, especially matched/skipped short diagnostics.

### Phase 7 — Corrected/native fee reruns

Turn on conservative fees and settlement-fee post-processing.

Assess degradation.

### Phase 8 — Market-replay catalog

Build Tardis/Deribit BBO/Greeks catalog.

Validate quote availability, option-chain subscriptions, and fill behavior.

### Phase 9 — Market-replay H1 test

Run H1 with real BBO/Greeks.

Compare against strict parity and Vibe research thesis.

### Phase 10 — Robustness grid

Run budget/DTE/moneyness/spread/fallback grids.

Identify robust plateaus rather than one best parameter.

### Phase 11 — Live/paper mapping

Only after research validation:

- map selector to live Deribit chain,
- add quote-quality gates,
- add spread/depth/liquidity filters,
- add kill switches,
- paper trade before capital deployment.

---

## 18. Known gaps and risks

### 18.1 Raw Vibe tapes are absent from uploaded archive

Full parity cannot be proven until raw Parquets are available.

### 18.2 SOL derived-output discrepancy

The uploaded SOL per-run CSV row count differs from the research narrative. Must rerun from raw data and freeze the target.

### 18.3 Vibe fee behavior may be optimistic

The scripts appear not to charge a normal option close fee on signal-flip exits. Corrected/native Nautilus mode may reduce P&L.

### 18.4 Nautilus native expiry omits delivery fee

Post-processing or custom settlement logic is required.

### 18.5 BBO market replay may reduce coverage

The Vibe trade-tape entry model and Tardis BBO model may produce different coverage. This is expected and should be analyzed, not treated as a bug.

### 18.6 Option-chain subscriptions are expiry-specific

A robust series planner is required for 20–40DTE selection.

### 18.7 L1 matching is not full order-book queue simulation

Nautilus option backtests use BBO quote-driven fills for options. For thin SOL options, add spread/depth/freshness stress tests.

### 18.8 True BTC inverse accounting adds complexity

For first reproduction, normalized USD/USDC parity is safer. True inverse BTC mode should be a later validation layer.

---

## 19. Final recommended implementation stance

Use Nautilus for the backtest, but be explicit about the two layers:

```text
Layer 1: Vibe strict parity
Goal: prove the Nautilus bridge understands Vibe §81/§82 exactly.
Data: Vibe raw trade tapes + synthetic surface marks.
Accounting: normalized USD/USDC first.

Layer 2: Nautilus market replay
Goal: test the strategy under actual historical BBO/Greeks and native exchange simulation.
Data: Tardis/Deribit option_summary, BBO, Greeks, instruments.
Accounting: true Deribit instrument conventions where possible.
```

The implementation should **not** begin by porting the full Vibe signal engine. Import Vibe’s direction-run ledgers first and focus on the open research question:

> Given the validated Vibe direction stream, does expressing shorts as premium-budget puts improve profitability and drawdown under realistic Deribit options execution?

This keeps the project small enough to validate, while using Nautilus for the hard parts that actually matter: option instruments, chain replay, fills, fees, expiry, and portfolio accounting.

---

## 20. Short checklist before coding

- [ ] Raw BTC/SOL option Parquets restored.
- [ ] Vibe phase 4/4b/5 rerun successfully.
- [ ] SOL row-count discrepancy resolved.
- [ ] BTC/SOL premium-convention tests written.
- [ ] Nautilus `CryptoOption` metadata validated for BTC and SOL_USDC.
- [ ] Underlying `IndexInstrument` IDs created as `BTC.DERIBIT` and `SOL.DERIBIT`.
- [ ] Strict-parity fee behavior documented.
- [ ] Corrected/native fee mode documented.
- [ ] Expiry settlement fee post-processing implemented.
- [ ] Series planner implemented for multi-expiry 20–40DTE search.
- [ ] Per-run attribution report implemented before running grids.

