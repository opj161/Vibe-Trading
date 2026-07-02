# NautilusTrader BTC/SOL Deribit Options Backtest — Implementation Plan v2

**Status:** ready to implement. Supersedes `vibe_nautilus_options_backtest_implementation_plan.md`
(the external-agent draft). That draft was directionally correct but was written without access to
the raw data, the live Python environment, or the actual NautilusTrader source at the installed
version. This plan corrects it against all three, with file/line references verified on
2026-07-02.

**Goal (from research log §81/§82):** the champion strategy's shorts expressed as
~10%-of-notional premium-budget puts (hybrid "H1") beat linear shorts on both the BTC and SOL
Deribit tapes. That finding was produced by hand-rolled pandas studies
(`research/vrp_deribit/phase4*.py`, `phase5_sol_expression.py`). This project rebuilds the option
expression on a real backtest engine (NautilusTrader) to (1) prove the numbers survive real
execution/portfolio accounting, (2) test realism upgrades the pandas studies can't model
(real per-print mark availability, both-side fees, contract-size rounding), and (3) create the
bridge toward live Deribit deployment (Nautilus has a live Deribit adapter).

---

## 0. Verified environment and data state (everything the old plan flagged as "unknown" is resolved)

| Item | State (verified 2026-07-02) |
|---|---|
| Raw BTC option tape | **PRESENT**: `data/parquet/btc_option_trades_deribit.parquet`, 23,845,156 rows |
| Raw SOL option tape | **PRESENT**: `data/parquet/sol_usdc_option_trades_deribit.parquet`, 665,251 rows |
| Tape schema (both) | `trade_seq, trade_id, timestamp, tick_direction, price, mark_price, iv, instrument_name, index_price, direction, amount, contracts, block_trade_id, block_rfq_id, block_trade_leg_count, combo_id, combo_trade_id, liquidation` — **note `mark_price` per print**: enables a real-mark replay mode with zero external data purchases (see §3, Mode B) |
| NautilusTrader | **`nautilus_trader==2.0.0rc1` installed in the Vibe venv** (`.venv/bin/python`, Python 3.13.12). This is the **v2 pyo3-native package** — the only one exposing the option-chain backtest API. All required imports verified working: `OptionSeriesId, StrikeRange, OptionChainSlice, OptionGreeks, CryptoOption, IndexInstrument, Currency('USDC')` from `nautilus_trader.model` (flat namespace — **no** `nautilus_trader.model.instruments` submodule in v2); `CappedOptionFeeModel` from `nautilus_trader.execution`; `ParquetDataCatalog` from `nautilus_trader.persistence`; `BacktestNode/…Config` from `nautilus_trader.backtest`; `Strategy.subscribe_option_chain` exists |
| Nautilus source for reference | `/home/j_opp/projects/nautilus_trader` @ v1.230.0 release commit — the **same repo snapshot** that produced the 2.0.0rc1 wheel (`python/pyproject.toml` says `2.0.0rc1`). Rust core in `crates/`, v2 Python re-exports + stubs in `python/nautilus_trader/`. The v1 Cython package at the repo root is **irrelevant to this project** — the old plan's `.pyx` references should be ignored. The local v2 extension is *not* built; the installed PyPI wheel is what we use |
| Direction-run ledgers | `research/vrp_deribit/derived/btc_direction_runs.csv` (110 runs, 2020-11→2026-07) and `sol_direction_runs.csv` (127 runs; **53** fall inside the SOL tape window 2024-03-11→2026-07-02). Schema: `start,end,dir,days` |
| The "46 vs 53 rows" discrepancy | **Resolved — not stale data.** `phase5_sol_per_run.csv` has 46 rows because `run_tracks()` does `continue` when a run spans <2 daily index dates (`phase5_sol_expression.py:185-186`) — 7 one-day runs never reach `per_run`, but *are* still counted in the "53 in-window / 14 skipped" narrative numbers, which are computed on different denominators. The parity harness must reproduce this exact skip, and the repro report must state both denominators explicitly |

Installation note: if the venv is ever rebuilt, `pip install --pre nautilus_trader==2.0.0rc1`
(pre-release wheels are on regular PyPI; the `--pre` flag is required). Pin the exact rc —
v2 is under active development and the API moves between rcs.

---

## 1. Exact parity target: what the Vibe scripts actually do (extracted from code, not narrative)

The parity target is the behavior of `phase4_trend_expression_options.py`,
`phase4b_hybrid_and_stress.py` (BTC) and `phase5_sol_expression.py` (SOL). The old plan got most
of this right; the following is the complete, code-verified specification. Every item below is a
parity requirement.

### 1.1 Constants (identical across BTC/SOL)

```
CAPITAL = 1_000_000; ENTRY_NOTIONAL = 500_000; SPOT_TAKER = 0.001
OPT_FEE_RATE = 0.0003; OPT_FEE_CAP = 0.125; SETTLE_FEE_RATE = 0.00015
PREMIUM_BUDGET_FRAC = 0.10; DTE_BAND = (20, 40); ENTRY_FWD_DAYS = 3
HALF_SPREAD: BTC = 0.0061 (hardcoded); SOL = measured from the tape at runtime as
  median(|price - mark_price| / mark_price) over ATM-band 20-40DTE prints — was 1.31% (n=32,638)
```

### 1.2 Derived inputs

- **Daily index**: last `index_price` print of each UTC day, from the tape itself
  (BTC: `derived/daily_index.csv` via `data_prep.py`; SOL: built in-process,
  `phase5:build_derived`).
- **Vol surface**: per-UTC-day volume(`amount`)-weighted mean `iv` in DTE buckets
  {7:(3,11), 14:(11,21), 30:(20,40), 60:(45,75), 90:(75,105)}, |log-moneyness|<0.075.
  IV lookup: interpolate **linearly in log(DTE)** across bucket midpoints; clamp to end
  buckets; walk back up to 10 calendar days for a missing surface day (`nearest_surf`);
  fall back to the leg's entry-print `iv`; floor at 5.0 vol points. Sigma = iv/100.
- **BS marks**: plain Black-Scholes, zero rates. BTC: `phase3.bs_price_and_delta` returns a
  BTC-denominated price (converted to USD by × current index S each day). SOL:
  `phase5.bs_usd` returns USD price per 1 SOL directly. T = seconds-to-expiry / (365·86400).

### 1.3 Per-run mechanics

For each direction run (`start`, `end`, `dir`):

- `dates` = daily-index dates in `[start, end]`. **If <2 dates: run is skipped entirely**
  (this is the 46-vs-53 mechanism — must reproduce).
- **SPOT baseline** (frozen-quantity, engine-faithful): `qty = 500k / S(dates[0])`;
  daily pnl = `dir · qty · ΔS`; minus `0.001·500k` on first day and `0.001·qty·S_end` on last.
- **Option leg chain**: `leg_start = dates[0]`; loop while `leg_start < dates[-1]`:
  - **Selector**: the **earliest** print in `[leg_start, leg_start+3d]` with matching type
    (C for long runs, P for short), `20 ≤ DTE ≤ 40`, `|ln(strike/index_price)| < 0.075`.
    (The code is `(w.trade_dt - anchor).abs().idxmin()` over an already-post-anchor window —
    i.e. earliest. It is *not* nearest-ATM.) No entry ⇒ leg chain ends (run may be
    option-skipped). `entry_dt = trade_dt.floor("D")`.
  - **Sizing**: OPT-DELTA: `contracts = qty_spot / max(|delta₀|, 0.05)` with delta₀ from BS at
    the entry print's iv/S/T. OPT-BUDGET: `contracts = 0.10·500k / ask_per_unit` where
    `ask_per_unit = price·(1+hs)·S` (BTC) or `price·(1+hs)` (SOL). **No lot rounding anywhere.**
  - **Entry cost** = `ask_per_unit · contracts`. **Entry fee** =
    `min(0.0003·S·contracts, 0.125·entry_cost)`.
  - **Daily P&L layout** over leg dates (entry_dt → `end_leg = min(floor(expiry), dates[-1])`):
    day 0 = `mark₀ − entry_cost − fee`; days 1..n-2 = diff of daily BS marks;
    final day = `exit_val − mark[n-2]`.
  - **Exit**: if `end_leg` reached expiry: `exit_val = intrinsic(S_close_of_expiry_day) −
    min(0.00015·S_end·contracts, 0.125·max(intrinsic, ε))`. **Note: the Vibe scripts settle at
    the daily index close of the floored expiry date, not Deribit's real 08:00 UTC settlement
    TWAP** — parity must replicate this; the corrected mode should use the 08:00-nearest index
    print. If exited by signal flip: `exit_val = mark_final · (1−hs)` — **spread but NO fee on
    flip exits** (confirmed asymmetry, the old plan's item #3 was right).
  - **Roll**: if the leg ended at expiry before `dates[-1]`, next `leg_start = leg_end + 1d`.
- **Skip accounting quirk**: phase4 (BTC) sets `found_any` only after a *rolled* leg or when a
  track's total ≠ 0 (`phase4:200-206`); phase5 (SOL) sets `entry_found` immediately on any
  entry (`phase5:205`). Reproduce per-script when matching the printed skip counts.

### 1.4 Aggregation and metrics

- Tracks are summed per-day across runs into one daily P&L series per track; **hybrids are
  built by running long-dir runs and short-dir runs separately and adding the chosen
  track series** (H1 = spot(longs) + opt_budget(shorts)).
- Equity = `1M + cumsum(daily pnl reindexed to a full calendar-day range, fill 0)`.
  Sharpe = `mean/std · √365` of equity pct-changes; MaxDD on that equity; annualized return
  geometric over `len(cal)/365.25` years; DSR via
  `agent/backtest/validation.deflated_sharpe_ratio(n_trials=2, bars_per_year=365)`.
- Per-run CSV (`phase4_per_run.csv` / `phase5_sol_per_run.csv`): `start, dir, days, spot,
  opt_delta, opt_budget` (+`bucket` on write); duration buckets `[0,8], (8,30], (30,∞)`.
- Stress = rerun option tracks with `half_spread × 2`.

### 1.5 Premium conventions (the single highest-risk item — one multiplier mistake invalidates everything)

- **BTC (inverse-style tape)**: `price` is in BTC per 1 BTC of underlying;
  `premium_usd = price × index_price × contracts`.
- **SOL_USDC (linear)**: `price` is in USDC per 1 SOL; `premium_usd = price × sol_units`,
  **no index multiplication**. Instrument format `SOL_USDC-{D}{MMM}{YY}-{STRIKE}-{C|P}`,
  expiry 08:00 UTC. (BTC format `BTC-{D}{MMM}{YY}-{STRIKE}-{C|P}`, same expiry hour —
  parsers exist: `data_prep.parse_instruments`, `phase5.parse_sol_instruments`; **reuse them**,
  do not rewrite.)

---

## 2. Verified NautilusTrader mechanics (with source references, v1.230.0 tag == 2.0.0rc1 crates)

These were checked in the Rust source and/or exercised in the installed wheel. Implementers can
rely on them without re-deriving.

1. **Option-chain backtest blueprint**: `examples/backtest/tardis_option_chain.py` (in the
   nautilus clone) is a complete working pattern: load instruments from a `ParquetDataCatalog`,
   build `OptionSeriesId(venue, underlying, settlement_currency, expiration_ns)`, configure
   `BacktestVenueConfig(book_type=L1_MBP, account_type=MARGIN, oms_type=NETTING,
   fee_model=CappedOptionFeeModel(...))`, feed `BacktestDataConfig(data_type="QuoteTick"|"OptionGreeks",
   instrument_ids=[...])`, subscribe via `self.subscribe_option_chain(series_id, strike_range=…,
   snapshot_interval_ms=…)`, handle `on_option_chain(slice)`. Docs: `docs/concepts/options.md`.
2. **Catalog write API (v2)**: `ParquetDataCatalog.write_instruments`, `write_quote_ticks`,
   `write_trade_ticks`, `write_option_greeks`, `write_mark_price_updates`,
   `write_index_price_updates` — all present in the installed wheel. `OptionGreeks(instrument_id,
   delta, gamma, vega, theta, rho, mark_iv, bid_iv, ask_iv, underlying_price, open_interest,
   ts_event, ts_init, convention)`. `QuoteTick(instrument_id, bid_price, ask_price, bid_size,
   ask_size, ts_event, ts_init)`.
3. **`CryptoOption`** ctor params confirmed: `instrument_id, raw_symbol, underlying,
   quote_currency, settlement_currency, is_inverse, option_kind, strike_price, activation_ns,
   expiration_ns, price_precision, size_precision, price_increment, size_increment, ts_event,
   ts_init, multiplier, lot_size, …, maker_fee, taker_fee, …`. `Currency.from_str("USDC")` works.
4. **`CappedOptionFeeModel`** (`crates/execution/src/models/fee.rs:423-505`):
   `fee = min(rate_fee, cap·fill_px) · multiplier · fill_qty`, where `rate_fee = rate` for
   **inverse** instruments (fee lands in the crypto settlement currency — exactly Deribit's BTC
   convention) and `rate_fee = rate · underlying_px` for **linear** (errors if no underlying
   price available). `cap` defaults to 0.125. With multiplier=1, quantity=underlying-amount, and
   fill at the synthetic ask, this reproduces Vibe's entry-fee formula **exactly** for linear
   normalized instruments. It charges on **every fill (entry AND close)** — Vibe charges entry
   only; see §5 fee-mode handling.
5. **Underlying price for linear fees** (`crates/execution/src/matching_engine/engine.rs:5182-5209`):
   resolution order is cache `Last` → `Mark` → `Mid` price of `{underlying}.{venue}`, then falls
   back to the option's **cached `OptionGreeks.underlying_price`**. We always write Greeks with
   `underlying_price` set, so linear fee computation is safe even without an index price stream.
6. **Option expiry is native and automatic** in backtest runs
   (`crates/backtest/src/engine.rs:1401` → `exchange.process_instrument_expirations` →
   `matching_engine.check_instrument_expiration`, `engine.rs:2192+`). Requirements: an
   underlying instrument registered under the ID `{underlying}.{venue}` **and a `Last` price for
   it in the cache — which only comes from `TradeTick`s** (`crates/common/src/cache/mod.rs:7089-7092`;
   `IndexPriceUpdate` does *not* feed `cache.price`). If the underlying is an `IndexInstrument`,
   expiry **cash-settles at intrinsic** (`option_cash_settlement`, engine.rs:2436+). So the
   catalog must carry `TradeTick`s for `BTC.DERIBIT` / `SOL_USDC.DERIBIT` (synthesize from the
   tape's `index_price`; daily closes suffice, plus a print shortly before each expiry).
7. **Expiry settlement fills carry ZERO commission** (`engine.rs:2643`,
   `Some(Money::zero(...))`) — the old plan's item #4 confirmed at the exact line. Vibe's
   settlement fee must be added in post-processing (recommended) — do **not** patch Nautilus.
8. **Custom settlement price override exists**: `BacktestVenueConfig(settlement_prices={instrument_id: Price})`
   (`crates/backtest/src/exchange.rs:139,295,980`). Parity mode uses this to force Vibe's
   daily-close-intrinsic settlement value per expiring instrument, eliminating one source of
   drift.
9. **Matching for options is quote-driven L1**: market/marketable-limit orders fill as takers
   against the replayed BBO; no L2 queue simulation (`docs/concepts/options.md`). Synthetic BBO
   (bid=mark·(1−hs), ask=mark·(1+hs)) therefore gives *deterministic, exactly-Vibe-priced* fills.
10. **Deribit quantity semantics**: Nautilus quantities map to Deribit *amount* (base-currency
    units), not contract counts (`docs/integrations/deribit.md`). Vibe's `contracts`/`units`
    variables are already underlying amounts — they map 1:1 to Nautilus `Quantity` with
    multiplier=1. Use `size_precision=6` for parity (no rounding); real min-amount rounding
    (BTC options: 0.1 BTC step; SOL_USDC: 10-SOL contracts) is a **corrected-mode stress**, not
    a parity behavior.

---

## 3. Architecture: three modes, two of them buildable today with owned data

**Mode A — strict Vibe parity (execution-side).** Purpose: prove the Nautilus bridge (catalog,
instruments, fills, fees, expiry, accounting) reproduces §81/§82 numbers. Key simplification vs
the old plan: **contract selection runs offline, not inside the strategy.** Selection is a pure
tape query, and running Vibe's selector on the tape trivially returns Vibe's choices — putting
it inside a chain-subscribed strategy adds a series planner and subscription machinery while
testing nothing execution-related. So Mode A precomputes an **`OptionLegPlan` ledger** (one row
per leg: instrument, entry ts, quantity, expected cost) with the *same code path as the parity
unit tests*, then the Nautilus strategy simply executes the plan: buy at synthetic ask on the
leg's entry timestamp, sell at synthetic bid on flip exits, let native expiry cash-settle rolls.
The synthetic catalog only needs quotes at the event times that matter (entry ts, daily marks,
exit ts) — generated with the **imported Vibe surface/BS helpers** (`phase3.bs_price_and_delta`,
`build_vol_surface`, `phase5.bs_usd` etc. — we are in-repo; import them, do not reimplement).

**Mode B — real-mark replay (the honest realism upgrade, no external data needed).** The old
plan's "market-replay mode" required Tardis BBO data (paid, not owned). But the tapes carry
`mark_price` on **every one of 24.5M real prints** — Deribit's own mark at real print
timestamps. Mode B builds the catalog from *per-print real marks*: for each instrument, every
print becomes a `QuoteTick` (bid=mark·(1−hs), ask=mark·(1+hs)) + an `OptionGreeks` (tape `iv`,
`index_price` as underlying_price, BS delta). Selection now happens **in-sim** via
`subscribe_option_chain` + a series planner, constrained by *actual quote availability* — the
realistic-coverage question the old plan wanted Tardis for, answerable with owned data. Marks
replace BS-surface marks for exits too (real mark at the exit-nearest print). Differences vs
Mode A quantify the surface-marking approximation in §81/§82 — a genuinely new result.

**Mode C — Tardis BBO replay (optional, deferred).** Only if a Tardis license is ever acquired.
Nautilus's Tardis pipeline (`crates/adapters/tardis/`, `docs/integrations/tardis.md`) writes
`option_summary` → OptionGreeks and BBO → QuoteTick natively. Nothing in Modes A/B blocks or
presupposes it. Do not build anything for it now (YAGNI).

### 3.1 Module layout

New directory `research/nautilus_deribit_options/` inside the Vibe repo:

```
config.py                # frozen constants (mirror §1.1), paths, tolerances
runs_loader.py           # direction-run CSVs -> list[VibeRun]
tape.py                  # load/parse either tape -> normalized trades DataFrame
                         #   (reuses data_prep.parse_instruments / phase5.parse_sol_instruments)
selector.py              # Vibe parity selector (earliest-eligible, §1.3) + Mode B variants
leg_planner.py           # offline Mode A leg-plan builder (selector + sizing + roll chain)
instruments.py           # CryptoOption / IndexInstrument factories (normalized USDC quoting)
catalog_parity.py        # Mode A synthetic catalog builder (quotes/greeks/index trades)
catalog_realmark.py      # Mode B per-print real-mark catalog builder
strategy_plan.py         # Mode A strategy: executes a precomputed OptionLegPlan ledger
strategy_chain.py        # Mode B strategy: series planner + in-sim chain-slice selection
run_backtest.py          # BacktestNode wiring for both modes (venue, data configs, kickoff)
postprocess.py           # fills -> per-run attribution, fee-mode adjustments, settlement fees,
                         #   spot-leg combination, metrics (reuse agent/backtest/validation DSR)
compare.py               # parity comparison vs frozen targets; emits repro_report.md
_tests/                  # pytest; see §7
```

Keep each file focused; the heavy lifting (surface, BS, parsing) is imported from
`research/vrp_deribit/`, not duplicated.

### 3.2 Data model

```python
@dataclass(frozen=True)
class VibeRun:
    run_id: str; underlying: str          # "BTC" | "SOL_USDC"
    start: pd.Timestamp; end: pd.Timestamp
    direction: int; days: int

@dataclass(frozen=True)
class OptionLegPlan:                       # Mode A executable ledger row
    run_id: str; track: str                # "opt_delta" | "opt_budget"
    instrument_id: str; entry_ts: pd.Timestamp
    quantity: float; expected_ask: float; expected_entry_cost: float
    expected_entry_fee: float; exit_kind: str   # "flip" | "expiry"
    exit_ts: pd.Timestamp; leg_index: int       # roll ordinal within the run

@dataclass
class RunAttribution:                      # postprocess output row (superset of Vibe per-run CSV)
    run_id: str; underlying: str; direction: int; days: int
    start: pd.Timestamp; end: pd.Timestamp
    spot_pnl: float; opt_delta_pnl: float; opt_budget_pnl: float
    legs: int; skip_reason: str | None
    entry_fees: float; close_fees: float; settlement_fees: float
    bucket: str
```

---

## 4. Catalog construction details

### 4.1 Instruments (both modes)

- **Normalized-linear quoting for BOTH underlyings** (old plan's recommendation, confirmed
  correct): quote and settle option instruments in USDC, `is_inverse=False`, `multiplier=1`,
  `lot_size=1`, `size_precision=6`. BTC option prices are pre-converted to USD
  (`price_btc × index_price`) when generating quotes. This keeps all P&L in one currency and
  matches Vibe's USD research accounting. True BTC-inverse accounting is a later,
  optional validation layer — do not start there (multi-currency P&L conversion noise would
  contaminate the parity gate).
- `price_precision`: BTC options 1 (USD ticks are coarse but synthetic quotes are ours — use 2
  to be safe); SOL options 4. Verify chosen precision round-trips the smallest synthetic price
  in the tape window (a unit test).
- **Underlyings as `IndexInstrument`**: `BTC.DERIBIT`, `SOL_USDC.DERIBIT` (the ID's symbol part
  **must equal the option's `underlying` string** — that's how the matching engine derives it,
  engine.rs:2335). Cash settlement then follows automatically (§2.6).
- Instrument universe: only instruments actually selected by the leg plans (Mode A) or all
  instruments with ≥1 ATM-band 20-40DTE print in some run's entry window plus their full print
  history (Mode B) — do **not** write 49k SOL + all BTC instruments blindly; catalog size and
  backtest event volume matter.

### 4.2 Mode A synthetic event stream (per selected leg)

- `QuoteTick` at: entry print timestamp (bid/ask from the **real entry print price** ± hs — the
  fill must equal Vibe's `price·(1±hs)`); each subsequent UTC day at a fixed synthetic time
  (e.g. 00:00:00.001) with bid/ask from the **surface BS mark** ± hs; the flip-exit timestamp.
- `OptionGreeks` at entry (and daily if convenient): delta from the entry BS call,
  `underlying_price = index_price`, `mark_iv = iv/100` (**decimal, not percent** — Deribit/Tardis
  convention in Nautilus; verify against `nautilus_pyo3.pyi` stub and one adapter test before
  committing).
- `TradeTick` for the index instrument: daily closes from `daily_index` + one print just before
  each relevant expiry (08:00 UTC) whose price is the **daily close Vibe uses** (parity) — this
  plus the `settlement_prices` override (§2.8) pins native settlement to Vibe's value exactly.
- Time hygiene: tape timestamps are ms-UTC; Nautilus wants ns (`ts_event = ms·1_000_000`).
  Vibe floors entry to day for marking but the *fill* must occur at the actual print ts;
  reconcile by making the day-0 quote the entry print itself (Vibe's day-0 P&L
  `mark₀ − cost − fee` is then reproduced in postprocess from the fill + first daily mark).

### 4.3 Mode B real-mark stream

- Every print of an in-universe instrument → `QuoteTick(bid=mark·(1−hs), ask=mark·(1+hs))` +
  `OptionGreeks(mark_iv=iv/100, underlying_price=index_price, delta=BS delta at print)`.
- Optionally also `write_mark_price_updates` for cleaner portfolio marking.
- Index `TradeTick`s: last print per day per §4.2 (real 08:00-nearest print for expiry here —
  corrected settlement, not Vibe's daily-close approximation).
- Entry-window liquidity is now *real*: a leg can only fill when a print existed. Expect
  coverage differences vs Mode A (SOL skip rate ≥ 26%); that is a result, not a bug.

---

## 5. Fees, spreads, settlement — three explicit fee modes

| Mode | Entry fee | Flip-exit fee | Expiry settlement fee | Purpose |
|---|---|---|---|---|
| `parity` | capped Deribit formula (via fee model) | **removed in postprocess** (Vibe charges none) | added in postprocess (Vibe formula, §1.3) | reproduce §81/§82 |
| `native` | fee model | fee model (charged) | added in postprocess | conservative realism |
| `stress` | native + `hs × {2,3}` + min-amount rounding (BTC 0.1, SOL 10) | 〃 | 〃 | robustness gates |

Implementation: always run the venue with
`CappedOptionFeeModel(maker_rate=0.0003, taker_rate=0.0003)` (cap defaults to 0.125) and do fee
**adjustments in postprocess from the fills ledger** — do not write a custom fee model and do not
run separate engines per fee mode. Every fill carries its commission; subtracting flip-exit
commissions and adding Vibe's settlement fee is arithmetic on the ledger. This keeps one code
path and makes parity-vs-native a single diff column in the report.

Spread stress is a **catalog parameter** (hs multiplier at quote generation), mirroring how
phase4b/phase5 rerun `run_tracks` with `half_spread×2`.

---

## 6. Build sequence with acceptance gates

Work in order; each gate is a hard stop-and-verify. Run everything with the Vibe venv python.
Follow repo TDD discipline: tests first per phase (`_tests/`), pytest, AAA style.

### Phase 0 — freeze the parity target (½ day)
1. Re-run `data_prep.py`, `phase4_trend_expression_options.py`, `phase4b_hybrid_and_stress.py`,
   `phase5_sol_expression.py` from the present raw parquets. Capture full stdout.
2. Copy the regenerated `derived/*.csv` + stdout into
   `research/vrp_deribit/derived/frozen_20260702/` (new, committed). These are the acceptance
   numbers; §81/§82 narrative values are the sanity cross-check (expect exact-or-near match;
   document any drift and its cause before proceeding).
3. Record both SOL denominators (53 in-window runs; N per-run rows after the <2-date skip; 14
   option-skip runs) in a `TARGETS.md` alongside.

**Gate 0**: frozen CSVs exist; headline numbers reconcile with §81.3/§82.3 tables.

### Phase 1 — parsers, instruments, conventions (1 day)
Build `tape.py`, `instruments.py`, `runs_loader.py` + tests.

**Gate 1** (unit tests): BTC/SOL symbol parsing (reusing Vibe parsers) round-trips to
`CryptoOption` with correct strike/expiry(08:00 UTC)/kind/underlying; **premium-convention
tests**: BTC `price=0.05, S=60_000, qty=1 → premium 3_000 USD`; SOL
`price=12, qty=100 → premium 1_200` and **no** index multiplication; quantity==amount semantics;
price/size precision round-trips; `Currency("USDC")` wiring.

### Phase 2 — selector + leg planner, validated against the tape (1 day)
Build `selector.py`, `leg_planner.py`.

**Gate 2** (the cheapest high-value gate — no Nautilus involved): run the leg planner over all
110 BTC + 53 SOL runs and assert the produced (instrument, entry_ts, quantity, entry_cost) set
reproduces Vibe's per-run `opt_delta`/`opt_budget` **entry legs** exactly — verify by
re-computing Vibe leg P&L with the imported helpers from the plan and matching the frozen
per-run CSVs to ≤$1 per run. Include tests: earliest-not-nearest-ATM selection; no-lookahead
(prints outside `[anchor, anchor+3d]` rejected); roll chaining; the `<2-dates` run skip; the
phase4-vs-phase5 skip-count quirk.

### Phase 3 — Mode A catalog + one-leg Nautilus smoke (1-2 days)
Build `catalog_parity.py`, `strategy_plan.py`, `run_backtest.py`, minimal `postprocess.py`.
Run **one BTC short run and one SOL short run** end-to-end (pick runs that include a mid-run
expiry roll so native settlement is exercised).

**Gate 3**: fills land at the synthetic ask/bid (= Vibe's entry/exit prices) at the right ns
timestamps; entry commission equals Vibe's capped fee to float tolerance; native cash
settlement fires with the overridden settlement price; post-processed leg P&L matches the
phase-2 recomputation to ≤$1.

### Phase 4 — full Mode A parity, BTC then SOL (2 days)
All runs, all tracks, hybrids assembled in postprocess (spot legs computed in pandas exactly as
Vibe does — do not simulate linear legs in Nautilus yet).

**Gate 4**: vs frozen targets — per-run option P&L within ±$500 or ±0.5% (whichever larger);
track totals within ±1%; Sharpe within ±0.02; matched/skipped SOL short decomposition
(−$119k spot vs +$83k puts on the 20 matched; +$149k on 8 skipped) reproduced; duration-bucket
table reproduced; 2× spread stress reproduced. Any systematic residual must be explained
(expected sources: Price/Quantity quantization, day-0 P&L attribution split) before proceeding.
Emit `repro_report.md`.

### Phase 5 — native-fee + rounding sensitivity (½-1 day)
Same runs, `native` and `stress` fee modes from the same fills ledger; add min-amount rounding
to the leg planner as a stress variant.

**Gate 5**: H1 hybrid on both tapes remains better than spot baseline under native fees and 2×
spread (the §81/§82 headline must not depend on the no-close-fee artifact). Report degradation
per fee component.

### Phase 6 — Mode B real-mark replay (2-3 days)
Build `catalog_realmark.py`, `strategy_chain.py` (series planner: per run, all expiries with
`20 ≤ DTE(run_start) ≤ 40`; subscribe per-series; select earliest eligible slice entry — plus
optional nearest-ATM / target-delta variants), run full BTC + SOL.

**Gate 6**: coverage table (entries found vs Mode A; skip reasons); per-run P&L comparison Mode
B vs Mode A quantifying the surface-marking approximation; H1 conclusion re-stated on real
marks. Economic consistency with §81/§82, not numeric parity, is the bar here.

### Phase 7 — robustness grid (1-2 days, compute-bound)
On Mode B (native fees): budget {5, 7.5, 10, 12.5, 15}%, DTE bands {14-30, 20-40, 30-60},
moneyness bands {ATM ±7.5%, 5% OTM, 10% OTM}, spread {1×, 2×, 3×}, fallback {skip, nearest
available, flat}. Pre-register the plateau expectation (old plan §15 Gate 6) before running;
report plateaus, not the argmax. Use `probability_of_backtest_overfitting` from
`agent/backtest/validation.py` on the grid if promoted claims are made.

**Gate 7**: H1-style hybrid works across a parameter plateau, not a point.

### Phase 8 — (deferred, explicitly out of scope now) Tardis Mode C; live/paper mapping via the
Nautilus Deribit adapter; true BTC-inverse accounting. Record as follow-ups in the final report.

Total estimate: ~8-11 working days of agent time, front-loaded with cheap gates.

---

## 7. Test list (minimum; extend as needed)

```
test_tape_parsing.py         # both symbol formats, expiry 08:00 UTC, unparsed-name drop
test_premium_conventions.py  # §1.5 BTC and SOL cases; the SOL no-index-multiplier assertion
test_selector_parity.py      # earliest-eligible vs nearest-ATM discrimination; window bounds;
                             #   no-lookahead; DTE/moneyness filters; roll chaining
test_leg_planner.py          # Gate-2 per-run reproduction on a fixture subset of the tape
test_instruments.py          # CryptoOption/IndexInstrument construction, precision round-trips,
                             #   underlying-ID convention {underlying}.{venue}
test_catalog_parity.py       # quotes/greeks/index-trades written and readable; ts ns conversion;
                             #   mark_iv decimal convention
test_fee_modes.py            # capped fee formula vs Vibe formula equality at fill prices;
                             #   parity-mode close-fee removal; settlement-fee postprocess
test_expiry_settlement.py    # native cash settlement fires; zero commission observed;
                             #   settlement_prices override honored; roll re-entry after expiry
test_postprocess.py          # per-run attribution assembly; hybrid combination; metrics equal
                             #   Vibe's metric function on identical inputs (sqrt(365), calendar
                             #   reindex, DSR n_trials=2)
test_mode_b_selection.py     # in-sim selection matches offline selector when quotes are dense;
                             #   skip recorded when no print in window
```

---

## 8. Corrections to the previous plan (summary for the record)

1. **Environment**: implementation targets **nautilus_trader v2 (2.0.0rc1, pyo3)** — installed
   and verified in the Vibe venv. The old plan's v1 file references (`crypto_option.pyx`,
   `backtest/engine.pyx`, v1 `persistence/catalog/parquet.py`) are the wrong API surface; v2's
   flat `nautilus_trader.model` namespace and the pyo3 `ParquetDataCatalog` writers are the
   real ones.
2. **Raw tapes are present** — Gate 0 is a cheap rerun+freeze, not a blocker.
3. **46-vs-53 resolved** (<2-daily-dates run skip, `phase5:185`), plus the phase4/phase5
   skip-count quirk documented — the parity harness reproduces rather than "fixes" these.
4. **Mode B redefined around the tapes' own per-print `mark_price`** — real-mark replay with
   in-sim selection needs no Tardis purchase; Tardis demoted to optional Mode C.
5. **Mode A simplified**: offline leg planner + plan-executing strategy instead of in-sim
   parity selection with a series planner; chain subscriptions are exercised where they earn
   their keep (Mode B). Gate 2 (pure-pandas leg reproduction) added as the cheapest
   high-value checkpoint before any Nautilus wiring.
6. **Mechanics verified at source level** (with lines): capped-fee inverse/linear split and its
   exact equivalence to Vibe's entry fee; fee-context fallback to `OptionGreeks.underlying_price`;
   expiry auto-processing; `Last`-price-needs-TradeTicks; zero settlement commission;
   `settlement_prices` venue override (the old plan didn't know it exists — it removes the need
   for "custom settlement logic").
7. **Vibe settles expiries at the daily index close, not Deribit's 08:00 settlement** — a
   previously-undocumented parity detail; parity replicates it via the override, corrected mode
   uses the 08:00-nearest print.
8. **Single fee code path** (always CappedOptionFeeModel + postprocess adjustments) replaces the
   old plan's strict/corrected dual fee-model machinery.
9. Selection rule confirmed **earliest-eligible** (the `abs().idxmin()` reduces to earliest on a
   post-anchor window) — the old plan's correction of "nearest ATM" was right; kept.

## 9. Standing risks / gotchas for the implementing agent

- **v2 is an rc.** Pin `==2.0.0rc1`. If a needed API is broken, check the local clone's
  `python/tests/` and `crates/` for the intended behavior before working around it; report
  divergence in the final writeup rather than silently patching.
- **`mark_iv` units**: Deribit tape `iv` is in percent (e.g. `65.3`); Nautilus `OptionGreeks`
  convention must be verified once against the Tardis adapter parse code
  (`crates/adapters/tardis/`) before the first catalog write. Wrong units poison ATM tracking
  and delta selection silently.
- **Event volume**: Mode B on BTC could emit tens of millions of quote events if the universe
  isn't pruned (§4.1). Prune to run-relevant instruments and consider `snapshot_interval_ms`
  thinning; `BacktestRunConfig(chunk_size=…)` controls memory.
- **Do not modify anything under `research/vrp_deribit/`** except adding the frozen-targets
  directory: those scripts are the parity oracle. New code lives entirely in
  `research/nautilus_deribit_options/`.
- **Known Vibe research-discipline rules apply** (CLAUDE.md): pre-register grid expectations,
  no re-tuning against the acceptance targets, report plateaus not argmaxes, and the final
  report goes into `vibe_trading_research_findings.md` as a new section following the existing
  §-numbering and honesty conventions (skip-rate integrity checks, per-run decompositions).
