# Handoff: Vibe-Trading Crypto Strategy Research Session

**For:** a fresh agent picking up this work with no memory of the conversation that produced it.
**Written:** 2026-07-01, end of a long single session. Superseded by later updates below — read to the bottom.
**Repo state:** branch `fix-channel-settings`, several uncommitted changes (see §3). Nothing in this session has been committed — that's a decision for whoever picks this up, not made yet.

> **FINAL UPDATE — this research arc is complete.** An autonomous `/loop` continuation ran §28 through §40 of `vibe_trading_research_findings.md`, ending in an explicit, reasoned dead-end assessment (§40) rather than an arbitrary stop. **If picking this up fresh, read `vibe_trading_research_findings.md` start to finish (through §40) — do not treat this file's earlier task lists (§5 below) as still-open work; they are a historical record.** Summary of the full arc:
>
> - **§18-24**: a mechanics audit found and fixed 4 real bugs (commission miscalibration, two lookahead leaks, an annualization mismatch), then DSR/PBO correction, then 9 independent signal-representation/asset-speed/universe redesigns — **none beat Variant L**.
> - **§25**: capstone synthesis — why the strategy works, what drives wins/losses. Some numbers superseded by §28.
> - **§26**: fixed a real OKX-loader capability gap (missing years of available history); confirmed the core mechanism profitable through the real 2018/2022 bear markets.
> - **§27-28**: found and fixed a second real bug — spot-data backtests were silently charged/credited a perpetual-futures funding fee with no basis on spot markets. Researched, fixed, 29 configs rerun. Reversed one §26 conclusion (2024 was not actually a bad year) and made **L** the clear champion (DSR 91.7%).
> - **§29-32**: executed the §27 brainstorm's top 4 tasks. Three came back negative (ETH-drop confirmed correct; vol-double-counting real but doesn't survive OOS; broad-universe expansion loses decisively). **The fourth — a portfolio-level "chop-frequency" exposure scalar (Z4) — became the session's standout finding** after an initial negligible test was directly challenged as under-explored and redone properly.
> - **§33**: found and fixed two real date-alignment bugs in the hand-rolled optimizer replica used to test Z4 (careful derivation from `base.py`'s exact shift semantics). Once fixed, **Z4 durably and dominantly beats L**: OOS Sharpe +28% relative (1.36 vs 1.06), max drawdown -39% relative (-19.2% vs -31.4%), return essentially tied. Confirmed through the extended 2020-2025 window (drawdown improved in *every single year* without exception) and a 4-trial DSR check (99.35% confidence).
> - **§34-35**: executed the remaining two brainstorm tasks. Task 5 (portfolio vol-targeting overlay, **Z8**) delivered a real additional return/Sharpe improvement stacked on Z4, and discovered a genuine platform constraint (notional leverage above 100% is structurally impossible via signal-engine weights alone — `base.py`'s `.clip(lower=1.0)`). Task 6 (trend-strength-weighted allocation) confirmed its flagged high risk and was cleanly rejected.
> - **§36-37**: two more stress tests. Does chop-dampening rescue ETH's participation? No — cleanly disconfirmed. Does Z4 generalize to a second venue (Binance)? Yes — confirmed venue-robust, with the OKX-vs-Binance absolute gap correctly attributed to the already-diagnosed bar-boundary confound (§15), not a new venue effect.
> - **§33.8**: does Z4 generalize to a second asset pair (BTC+AVAX)? Yes for the mechanism (helps proportionally *more* on a weaker pair); no for SOL's specific edge (irreplaceable — AVAX's baseline is far weaker).
> - **§38-39**: applied CSCV-based Probability of Backtest Overfitting (the more rigorous standard flagged since §19.3) — found 80% PBO among the near-identical Z1-Z4 trial family, reconciled honestly against the 99.35% DSR (different questions: "is the edge real" vs "is picking this exact variant reliable"). Directly tested the ensemble response that finding motivated (**Z12** = Z2+Z4 average) — a genuine tie with Z4 alone, no forced winner, same pattern as the original §17 N-vs-L tie.
> - **§40**: capstone dead-end assessment. Every angle with a clear evidence-based reason to expect new information has been tested; remaining candidates are either a different research scope (perpetual futures with real funding realism) or low-value fishing the log's own statistical tools argue against.
>
> **Final recommendation: Z4 (`v_Z4_chopfreq_train`/`_OOS_TEST`) for drawdown-focused use, or Z4+Z8 (`v_Z8_voltarget_train`/`_OOS_TEST`) for return/Sharpe-focused use** — both durable, multiply-confirmed improvements over L. L itself (`v_L_dropeth_train`/`_OOS_TEST`) remains a valid, well-understood fallback if the extra implementation complexity of the hand-rolled ERC replica (§33.1, needed because uniform exposure scalars are a no-op under the real `respect_magnitude` optimizer hook) isn't worth it for a given use case.
>
> **§41 (loop continued at user's request past the §40 dead-end assessment)** tested three more angles, all confirming rather than overturning the recommendation: BTC+DOGE (sharpened the boundary condition on when chop-dampening helps vs. hurts — it hurts assets with frequent short-term reversals even during an uptrend, unlike sustained-trend SOL/AVAX); genuine perpetual futures with researched fees/funding (confirmed perpetual trading fees are *cheaper* than spot, not more expensive, and Z4's results are not sensitive to realistic funding-rate assumptions); and a joint bear-market+venue test on Binance's extended 2020-2025 window (confirmed the "improves drawdown every single year" pattern holds jointly, not just separately — 2024 was the standout, control lost -43.6% that year on Binance, Z4 lost only -11.7%). **Genuinely open, if this is ever picked up again**: a rigorous perpetual-vs-spot isolation controlling for bar-boundary offset (needs new data-loader infrastructure, not just new backtests); re-plumbing Z4 into the real optimizer rather than the hand-rolled replica (an implementation-quality task, not a research question). See §41.4 for the final, narrower dead-end assessment — every combination of {asset pair, venue, time window, funding regime, statistical rigor tool} testable with existing infrastructure has now been tested at least once, several multiple times jointly.

---

## 1. What this session was about (narrative summary, historical — see update above for current state)

Two unrelated threads happened in this conversation, in this order:

1. **Root-caused and fixed a real concurrency bug** in `agent/backtest/loaders/registry.py` (a TOCTOU race in loader registration that caused spurious `"Unknown data source"` errors under the harness's parallel tool execution) — unrelated to everything below, already fixed, low priority to revisit unless it regresses.
2. **The main thread, and the one this handoff is about**: set up the project's own MCP server (`agent/mcp_server.py`) as a Claude Code tool (`mcp__vibe-trading__*`), then used it to research, build, and iteratively improve a systematic crypto trend-following strategy (EMA crossover + volatility targeting + risk-parity allocation on BTC/SOL) — an effort that, per the update above, has since been carried through many further rounds culminating in Z4/Z8 as the validated leading candidates.

---

## 2. Required reading, in this order

1. **`vibe_trading_technical_overview.md`** — pre-existing platform reference: what Vibe-Trading is, its backtest contract (`config.json` + `code/signal_engine.py`), data loaders, market engines, validation tools. Read this first if unfamiliar with the platform.
2. **`vibe_trading_research_findings.md`** — the full experimental log, now spanning §1 through §40. This is the primary source of truth — read to the end, not just early "recommended strategy" call-outs, many of which are explicitly marked superseded by later sections.
3. **`vibe_trading_bar_boundary_deep_dive.md`** — synthesis of four external deep-research reports on the bar-boundary phenomenon; §4 contains the original prioritized task list that motivated much of §15-24's work (now completed).
4. **`CLAUDE.md`** — project-level standing rules and a condensed version of key findings, auto-loaded every session.
5. **The four raw external research reports** — only if double-checking a specific citation beyond what's in the deep-dive doc: `Bar Boundary Sensitivity Analysis.md`, `bar-boundary-research-report-grok.md`, `Crypto Bar Boundary Robustness.md`, `bar-boundary-research-report-gpt.md`.

---

## 3. Current repo/environment state (historical snapshot from the original session — see `git status` for the live picture)

- **MCP server**: `agent/mcp_server.py` is registered as `vibe-trading` at project scope in `.mcp.json` (stdio transport). Exposes read-only research/backtest tools as `mcp__vibe-trading__*`.
- **All backtest run directories persist on local disk** at `agent/runs/v_*` (gitignored via `agent/.gitignore`) — every variant's exact `config.json`, `code/signal_engine.py`, and `artifacts/` are still there, including the extensive Z1-Z12 series from the autonomous /loop arc. Use these directly rather than re-deriving parameters from prose.
- **Ephemeral scratchpad data does NOT persist across sessions** — any intermediate CSVs cached under `/tmp/claude-*/.../scratchpad/` during offset-sweep or multi-asset analysis are session-specific. If extending that analysis, re-fetch via `mcp__vibe-trading__get_market_data` or the loaders directly (quick, a few seconds per symbol/venue).
- Nothing in this repo has been committed by this research thread. Deciding when/how to commit (single commit? split by concern?) is an open decision for whoever picks this up — not something to do unilaterally without confirming with the user first.

---

## 4. Findings worth flagging explicitly (now fully superseded by the update at the top — kept for historical continuity)

The early-session "no clean champion between L and N" finding (originally in `vibe_trading_research_findings.md` §17) was itself later superseded by the funding-fee fix (§28) and then by Z4's discovery and validation (§29-39) — see the top-of-file update for the current, final picture.

---

## 5. Original task list (historical — fully executed, see the update at the top; kept only for provenance)

The original prioritized task list from `vibe_trading_bar_boundary_deep_dive.md` §4 (statistical rigor, continuous intraday EMA, asset-specific signal speed, broader asset sweep, alternative bar construction, session/liquidity-aware boundaries, re-examining earlier conclusions) was executed in full across `vibe_trading_research_findings.md` §19-24. The subsequent §27 brainstorm's 6 tasks (loss mitigation via portfolio exposure scalar, win maximization via vol-targeting/leverage, universe expansion, ETH rolling-window decomposition, vol-double-counting ablation, trend-strength-weighted allocation) were executed in full across §29-39. **Nothing from either list remains open** — see §40 for the reasoned dead-end assessment and the top-of-file summary for the final recommendation.
