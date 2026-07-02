# Venue, Data & Infrastructure Assessment — 2026-07-03

**Scope:** given the true deployment scale ($1-5k, `vibe_trading_fresh_assessment_20260703.md`
§8) and the user's existing accounts (**Hyperliquid, Binance, Interactive Brokers**), assess:
(1) which venue should host each leg of the deployable composite, (2) what the local
`microforge`/`edgeforge` projects contribute beyond the already-completed §68 alpha audit,
(3) Nautilus adapter coverage, and (4) the free-data resource map. One new quantitative
analysis was executed (venue-conditional funding attribution,
`research/assessment_20260703/venue_funding.py`); fee/regulatory facts were re-verified
against current (2026) sources.

---

## 1. The new analysis: venue-conditional funding attribution

§75 measured the real funding cost of the champion's positions on **Binance only**.
edgeforge's Hyperliquid funding lake (45 symbols, settlement-level, 2023-05 → 2026-06)
makes the same measurement possible for HL. Method: every champion direction run since
2023-06 integrated against actual settlement-by-settlement funding, constant-$1-notional
(§75's convention), positive funding = longs pay shorts on both venues.

| Leg | Runs / position-days | Binance (%/yr in position) | Hyperliquid (%/yr in position) |
|---|---|---:|---:|
| BTC LONG | 27 / 540d | **−10.7%** | **−23.9%** |
| BTC SHORT | 34 / 430d | **+4.1%** | **+5.8%** |
| SOL LONG | 29 / 498d | **−12.2%** | **−29.7%** |
| SOL SHORT | 37 / 490d | **−1.5%** | **−2.1%** |

Three deployment rules fall out, now confirmed on two independent venues:

1. **Never express longs as perps.** The strategy is long precisely when funding spikes
   (trend-following's built-in adverse selection): perp longs would surrender 10-30%/yr
   of the long side's exposure-time — a material fraction of the whole edge. **Longs =
   spot, always.** Hyperliquid's hourly funding is 2-2.5x *worse* than Binance's 8h
   funding for this strategy's long days — the "all-HL, one venue" simplification is
   quantitatively dead.
2. **BTC shorts are paid to exist on both venues** (+4-6%/yr); HL is slightly better
   (+1.7%/yr) and has cheaper taker fees.
3. **SOL shorts carry a small, tolerable drag on both** (−1.5 to −2%/yr) — the §75
   funding-sign check remains worth doing per entry, but the drag is second-order at
   retail scale; it does not force the puts expression early.

## 2. Venue mapping for the deployable composite ($1-5k)

Current verified fee schedules (2026): Hyperliquid perps 0.015%/0.045% maker/taker
(spot 0.04/0.07, thin books for BTC/SOL wrappers); Binance spot 0.10% (0.075% with BNB;
maker can be lower), USDT-M futures 0.02%/0.05%; IBKR European stocks tiered ~0.05% of
trade value (small minimums), fractional shares supported.

| Composite leg | Venue | Why | Note |
|---|---|---|---|
| Macro sleeve (70%) | **IBKR** | already owned; fractional; ~0.05% tiered | **PRIIPs blocks US ETFs for EEA retail** — implement with UCITS equivalents (e.g. an S&P 500 UCITS ETF + a gold ETC); signals still computed on SPY/GLD data (yfinance), tracking difference negligible for monthly EMA-blend signals |
| Crypto longs | **Binance spot** | deepest books; no funding (rule 1); 0.075-0.1% ≤ modeled 0.1% | maker orders can cut this further; strategy was validated at 0.1% taker, so live costs ≤ model |
| Crypto shorts | **Binance USDT-M perps** (start) | one-venue crypto ops; taker 0.05% ≈ HL's 0.045%; +4.1%/yr BTC carry | switch/extend to **HL perps** when automation arrives: +1.7%/yr better BTC carry, Nautilus-native Rust adapter, and the testnet drill path already exists |
| BTC/SOL puts (≥$10-25k, later) | **Deribit** | only venue with the tested books | unchanged from §8's scaling map |

Net effect on the model: **every live fee is at or below what the frozen strategies
assumed** (0.1% taker per side) — the validated numbers are conservative for this venue
mapping, not optimistic. At $1-5k, minimums are comfortable on all three venues
(Binance spot ~$5 min notional; USDT-M BTC 0.001 BTC / SOL 1 SOL; HL $10 min; IBKR
fractional from ~$1-5).

## 3. microforge / edgeforge: what they contribute (post-§68 view)

§68/§69 already harvested the *research* value: funding-carry corroborated dead (90/90
rejected scorecards), the 9-asset ensemble independently re-validated as no-edge, the OI
overlay tested (negative), the 1s-candle bar-boundary re-test done. **The remaining value
is operational, and it is real:**

| Asset | Where | Use |
|---|---|---|
| **HL funding lake** (45 syms, hourly, 2023-05→) | `edgeforge/data/lake/funding/` | powered §1's venue decision; reusable for quarterly funding re-attribution and the per-entry funding-sign check |
| **HL testnet credentials** | `edgeforge/.env` | **copied to `Vibe-Trading/.env` (gitignored) 2026-07-03** — unlocks Nautilus HL adapter paper drills whenever automation becomes proportionate |
| Binance-futures 1h lake (BTC/ETH/SOL/DOGE/XRP/NEAR/TON/WLD, 2020-01→2026-06) | `edgeforge/data/lake/binance-futures/` | convenient local backtest source (no API refetch); registerable via the platform's local loader if needed |
| asset_ctxs (mark/oracle/OI/premium, minute-level, 20 syms, 2024-03→) | `edgeforge/data/lake/asset_ctxs/` | the only local OI source; overlay already tested negative (§69) — keep for monitoring/diagnostics only |
| Telegram bot credentials + alerting pattern | `edgeforge/.env`, edgeforge src | the right-sized notification layer for the manual-execution loop (signal alerts, kill-switch pings) |
| HL S3 archive access pattern (requester-pays, boto3) | edgeforge STACK docs | if deeper HL history is ever needed; cents per pull |
| microforge event-sourced capture (trade/book/funding WS) | `microforge/data/normalized/` | architecture reference for a future own-capture layer; its data itself is redundant (days of depth) or superseded (Binance funding already fetched full-history in §75) |

Also worth adopting *as prior art* rather than data: edgeforge's PROJECT constraints
("Hyperliquid-only, <$10k, one-operator complexity budget, hard kill switches,
reduce-only exits, reconciliation-on-boot") — it is the same problem this platform now
faces at $1-5k, thought through independently. Its conclusions (NautilusTrader
production target, Polars+Parquet lake, no CCXT for live execution, no distributed
infra) match this platform's §5/§8 verdicts.

## 4. Nautilus adapter coverage: all four venues, one framework

Verified in the local clone (`ADAPTERS.md`, `crates/adapters/`): **Binance, Hyperliquid,
Interactive Brokers, Deribit all have Data + Execution adapters.** The long-term
architecture this enables: a single Nautilus deployment could run the entire composite —
IBKR macro sleeve, Binance/HL crypto sleeve, Deribit options — with the same strategy
code that was already parity-validated this week. That remains **deferred until
~$10-25k** per §8.6 (manual execution is proportionate below that), but every venue
decision above was made compatible with it, and the HL testnet keys + edgeforge's drill
experience make HL the natural first automated leg.

## 5. Free-data resource map (no paid providers)

| Source | Provides | Depth | Status |
|---|---|---|---|
| Binance Vision (`data.binance.vision`) | bulk klines/aggTrades/funding, spot+futures | 2017/2019 → | free; best bulk source; platform already reaches Binance via ccxt |
| Hyperliquid info API | candles (≤~5000/interval), **full funding history**, L2 snapshot | funding full; candles shallow | free; edgeforge lake already holds the useful parts |
| Hyperliquid S3 archive | L2 book, asset_ctxs (OI/mark/oracle) | ~2023 → | requester-pays (cents); access pattern in edgeforge |
| Deribit public API | options chains, marks, IV, trades (expired), DVOL, funding | 2016 → (expired-only for options) | free; already the platform's options backbone; daily snapshotter still the open TODO |
| deribit-historical-data fetcher | full expired-option trade tapes | 2016 → | free; already produced the BTC/SOL/(ETH-fetchable) tapes |
| yfinance | adjusted equities/ETF/macro daily | decades | free; macro sleeve signal source (adjustment bug already fixed platform-side) |
| IBKR API | delayed quotes free; historical bars | years | no market-data subscription needed for daily-bar manual execution |
| FRED / stooq | rates, macro series, indices | decades | free; relevant to macro-breadth research (§8.6 item 5) |
| Coinglass free tier | cross-venue OI/funding/liquidations dashboards | recent | monitoring only |
| Tardis.dev free samples | first-of-month L2/derivatives ticks | samples | spot-checks only; full replay remains the deferred Mode C |

**Notably absent for free:** deep intraday multi-year L2/tick beyond HL's archive, US
single-stock fundamentals (PRIIPs-irrelevant anyway at this scale), and live unexpired
Deribit option chains history — the last one is exactly what the (still recommended,
still unbuilt) daily chain snapshotter fixes going forward at zero cost.

## 6. Actions taken / recommended

**Done this session:** venue funding attribution (script committed); HL testnet keys
copied into gitignored `.env`; fee/regulatory facts re-verified (HL 0.015/0.045; PRIIPs
UCITS constraint confirmed for EEA retail at IBKR).

**Adopt (no new research needed):**
1. Composite venue mapping per §2 (IBKR-UCITS macro / Binance spot longs / Binance perp
   shorts, HL as the future automated shorts venue).
2. Funding-sign check per entry from the venues' public endpoints (free, one API call).
3. Telegram-based alerting for the manual loop, reusing edgeforge's pattern.
4. Quarterly: re-run `venue_funding.py` (funding regimes drift) alongside the existing
   quarterly items (H1 forward-track, SOL options capacity).

**Explicitly not worth it:** moving crypto longs to HL (funding rule 1 + thin spot);
buying any data (nothing in the current plan is blocked on paid data); porting either
external project's strategies (§68 stands); building own WS capture now (edgeforge/
microforge already capture what matters, and the strategy is daily-bar).
