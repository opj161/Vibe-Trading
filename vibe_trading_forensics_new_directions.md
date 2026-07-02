# New research directions from raw run-data forensics (2026-07-02)

**Method:** this document was produced by going through actual run artifacts — `trades.csv`,
`positions.csv`, `equity.csv`, `config.json` across the champion lineage
(`v_Z4_extended_train`, `v_Z4_chopfreq_OOS_TEST`, `v_ZA4_regimeconviction_ext_train`,
`v_ZA4_regimeconviction_OOS_TEST`, `fwd_Z4/Z8/ZA4_20260702`, `v_Z4_leverage15_train`) — plus one
fresh external dataset fetched for this analysis (real Binance perp funding-rate history,
2025-06→2026-07, saved to `research/data/binance_funding_fwd_window.csv`). Every number below is
reproducible from those files. None of these directions is a rephrasing of a prior "next step":
each names a pattern that exists in the trade/position data but was never explicitly identified
in findings §1-73.

---

## Direction 1 — The champion misallocates the majority of its capital to its worst asset, by construction

### Evidence (specific, per run)

BTC's share of gross exposure vs. BTC's share of realized P&L, from `positions.csv` + `trades.csv`:

| Run | BTC mean share of gross capital | BTC net P&L | Portfolio P&L | BTC P&L share |
|---|---:|---:|---:|---:|
| `v_Z4_extended_train` (2020-11→2025-06) | **71%** | +$5.08M | +$22.3M | **12.5%** |
| `v_Z4_chopfreq_OOS_TEST` (2025-05→2026-06) | **62%** | +$15.0k | +$395k | **3.8%** |
| `fwd_ZA4_20260702` (2025-06→2026-07) | **60%** | **-$71.3k** | +$649k | **negative** |

Per-direction detail makes it worse: in `fwd_Z8_20260702` BTC lost money on *both* sides
(longs -$41.9k, shorts -$66.4k) **in a year BTC itself fell ~46%** — the EMA(10,30) signal
whipsawed on BTC even though the underlying trend was strongly down. Meanwhile SOL contributed
+$720k (fwd_ZA4) / +$746k (fwd_Z8). Even in the bull-dominated extended train, BTC's
P&L-per-unit-capital was ~14x worse than SOL's ($5.1M from 71% of capital vs $17.2M from 29%).

### Why this happened and why nobody named it

The hand-rolled ERC allocator sizes by *inverse volatility contribution* and is completely
return-blind — BTC's lower vol mechanically hands it the **larger** notional share. This is
exactly the anti-pattern the arc already convicted at the sleeve level (§50.2: "naive per-asset
ERC drags capital toward the lower-alpha sleeve", the CP1 lesson) — but that lesson was never
turned around and pointed at the champion's own 2-asset ERC. The closest precedent is the
single most successful universe change of the whole arc: dropping ETH (§L, Sharpe 1.17→1.48
lineage) — which had exactly this data shape before it was made.

### Why it's more promising than what we've been doing

Every recent negative result was an *overlay* (7-for-7 failures); this is a *universe/allocation*
change — the category with an unbroken winning record (risk parity, drop-ETH, long-bias tilt,
chop scalar, vol overlay, gross recovery: all winners). And it is the largest quantified
inefficiency currently sitting inside the champion: ~60-75% of capital producing ≤12.5% of profit.

### Concrete test

Pre-registered 3-variant grid, extended train window 2020-11→2025-06 only (the 2025-26 window is
burned for design decisions), DSR across 3 trials, standard costs (`maker 0.0008/taker 0.0010`,
`funding_rate: 0.0`):
1. Control: ZA4 as frozen.
2. **SOL-only** full stack (vol-target + chop scalar + regime damp; ERC degenerates to identity).
3. **BTC-capped**: identical to control but BTC's post-ERC weight capped at 30% of gross
   (its historical P&L share, roughly), the freed budget flowing to SOL.
Winner (if any beats control by DSR) goes into `forward_validation/frozen/` as a *new named
variant* and is arbitrated by forward data only. Known risk to watch: single-asset concentration
loses the diversification that §69.4 showed carries the strategy when one asset's raw signal
degrades — which is why the capped variant (not only the drop variant) is in the grid.

---

## Direction 2 — The "perps are the preferred live wrapper" decision rests on a funding model with the wrong sign

### Evidence

The engine models funding as a **static** rate with longs-pay/shorts-receive
(`v_Z4_leverage15_train/config.json`: `funding_rate: 3e-05`; engine default 1e-4; §41.2's
"funding-insensitivity" and ZB3's spot-vs-perp equivalence were both established under this
static model). The champion's forward-year book is **net short 58% of days** — under the static
model, running on perps would have *collected* funding.

Real Binance funding rates for the same window (fetched this session, 1,189 settlements each):
BTC mean +3.5% annualized (24% of settlements negative), **SOL mean -0.9% annualized, 44% of
settlements negative** — funding flips negative exactly in the bear regime, i.e. crowded shorts
*pay*. Marking the champion's actual daily positions (`positions.csv`) against the real rates:

| Run | Static-model funding P&L (engine assumption) | **Real-rate funding P&L** | Swing |
|---|---:|---:|---:|
| `fwd_Z8_20260702` | +$25.2k (+2.5%) | **-$17.8k (-1.8%)** | 4.3pp |
| `fwd_ZA4_20260702` | +$50.7k (+5.1%) | **-$20.3k (-2.0%)** | 7.1pp |

The loss is concentrated in SOL shorts (-$20.6k / -$25.4k) — the strategy's single profit engine.
Perps' fee advantage over spot (0.02%/0.05% vs 0.08%/0.10%) is worth roughly 1-2%/yr at this
turnover; real funding costs ~2%/yr *more* than modeled. The wrapper decision is at best a wash
and plausibly inverted, and no prior test could see this because none used real funding series.

### Why it's more promising

This is not a new signal (7-for-7 dead end) — it is **execution economics on the already-validated
strategy**, a category the arc has never once optimized. It changes realized P&L on day one of
any live deployment, and the data to do it right is free and already partially saved.

### Concrete test

1. Fetch full Binance funding history (available back to 2019) for BTC/SOL; extend
   `research/data/binance_funding_fwd_window.csv`.
2. Re-run the ZB3 spot-vs-perp comparison with a real-funding-series cost pass (post-hoc
   attribution over `positions.csv` is sufficient — no engine change needed for the read).
3. Decision output, per side: spot for shorts (margin-borrow ~1-3%/yr, only while short) vs perp
   (funding-exposed), or a funding-sign-conditional wrapper. This is a deployment decision, not a
   backtest-selection exercise — no burned-window issue.

---

## Direction 3 — The strategy's current cost center is short-side whipsaw churn, and it is direction-specific

### Evidence

§70.1's durability finding ("<8d trades lose, >30d trades win") was reported **pooled**. Split by
direction it is much sharper (from `trades.csv`, exits only):

| Run | Bucket | LONG n / P&L | SHORT n / P&L |
|---|---|---|---|
| `v_Z4_chopfreq_OOS_TEST` | <8d | 7 / -$70.7k | **22 / -$214.0k** |
| | >30d | 3 / +$183.6k (100% win) | 5 / +$512.1k (100% win) |
| `fwd_ZA4_20260702` | <8d | 7 / -$104.6k | **19 / -$355.7k** |
| | >30d | 3 / +$270.6k (100% win) | 2 / +$668.2k (100% win) |

In the forward year, **73% of all short trades (19/26) died inside 8 days**, and that bucket alone
gave back more than half of the short side's gross winnings. Long-side whipsaw is one third as
frequent. ZA4's regime dampener addresses *counter-regime* trades (longs in a downtrend); nothing
in the stack addresses *same-regime* churn — shorts entered in a downtrend that get squeezed out
by violent bear rallies within days.

### Why it's more promising

This finally makes the blocked ZD1 idea concrete and asymmetric. ZD1 (§70.2) failed for a
*mechanical* reason — `rebalance_threshold` resizes against price-dependent implied weight,
reintroducing §43's continuous-rebalance failure — not because durability sizing was refuted. The
direction-split evidence sharpens both the required engine primitive and the design: the churn to
attack is specifically short-side, and the fix is entry-sizing (allocation space, 5-for-5), not
entry-gating (signal space, 0-for-11).

### Concrete test

1. Implement the missing engine primitive: **one-shot, quantity-based resize** (scale position
   *quantity* by a factor once, at a trigger, never touching it again — categorically different
   from the weight-maintenance `rebalance_threshold`). Small, testable change in
   `agent/backtest/engines/base.py`.
2. Pre-registered ZD2: shorts enter at half their computed size and double (one-shot) after
   surviving 10 days; longs unchanged. One variant, one control, extended window; DSR; freeze and
   forward-track if it survives.

---

## Direction 4 — The "broad universes lose" closure was learned entirely on bull-window data, and the current profit engine is precisely the thing those tests never exercised

### Evidence

Every universe-breadth rejection in the log — §31 (G/Y1 broad momentum), §33.8 (AVAX/DOGE
baselines "too weak"), §36 (ETH hurts even with chop dampening), §41.1 — used train windows
ending ≤2025-06, i.e. data dominated by idiosyncratic alt *rallies*. What actually pays now, per
the trade data above, is **short alt downtrends**: SOL shorts are +$558k of fwd_ZA4's +$649k
(86%), +$642k of fwd_Z8's +$637k (≈100%). Alt bear markets are more correlated and more sustained
than alt bulls — a regime in which the old "alt baselines too weak" conclusion may simply not
hold, and no test has ever looked, because the bear window (2025-07 onward) is either burned OOS
or the future.

### Why it's more promising

It re-examines a *stale assumption* rather than adding sophistication, and it can be done with
**zero data-snooping cost**: no backtest on the burned window at all.

### Concrete test (freeze-and-track, deliberately no backtest selection)

Freeze **one** pre-specified broadened variant now — ZA4's exact stack over BTC+SOL+ETH+AVAX
(the four deepest-history OKX pairs already verified in CLAUDE.md), no parameter changes, regime
dampener active (in a bear it automatically halves counter-regime longs) — into
`forward_validation/frozen/` alongside the champions, and let the quarterly ritual arbitrate it
against ZA4 on genuinely new data. Cost: one config + one signal-engine copy. If the bear-regime
hypothesis is wrong, the ledger says so for free; if right, it is the first new-evidence-validated
universe change since drop-ETH.

---

## What was deliberately *not* proposed

- Anything overlay-shaped on Z4 (0-for-7), any signal-timing redesign (0-for-11+), VRP structure
  variants (closed to forward-tracking in §73), funding *carry* as a strategy (closed 3x — note
  Direction 2 is about execution cost of the existing strategy, not a carry trade).
- Re-tuning anything against 2025-07→2026-06: that window is burned for selection everywhere
  above; it is used only to *name* patterns, with all selection pushed to the pre-2025 extended
  window or to frozen forward-tracking.

## Suggested order

Direction 2 first (pure analysis, changes live deployment economics immediately), then Direction 1
(three backtests, biggest quantified inefficiency), Direction 4 (one config, zero marginal cost,
starts accruing evidence immediately), Direction 3 last (requires the engine primitive).
