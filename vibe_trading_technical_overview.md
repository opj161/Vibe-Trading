# Vibe-Trading Technical Capability Overview

**Generated:** 2026-06-30 13:53:26Z  
**Updated:** 2026-07-01 — added agent-tasking / prompting best-practices section after second repository scan.  
**Updated:** 2026-07-01 — corrected §8.3's execution-loop description after direct, hands-on testing during a research session (`vibe_trading_research_findings.md` §42-43): the original "open, add, reduce, reverse, or close positions" bullet did not match the actual code for any engine (verified by grepping every engine file) — default behavior is open/close only with entry-locked sizing; add/reduce is now a real, opt-in capability (`config["rebalance_threshold"]`) added during that session. Also added a concrete AST-safety-validator edge case (§7.3) found while building a permutation-test script, and the new config key to §7.2. The rest of the document held up against a full session of hands-on backtest/loader/engine/config usage via the MCP tools — see the note at the end of §21 for a fuller assessment.  
**Purpose:** a technical reference for future strategy and research development: what Vibe-Trading can do, how it does it, which data it can collect through its built-in/default data-provider layer, what tests and validations it can run, how strategies are implemented, what outputs it creates, where the strengths are, and where the constraints are.

---

## 1. Executive summary

Vibe-Trading is a Python 3.11+ finance-research agent and backtesting platform. The codebase combines four major systems:

1. **Agent/tooling surface** — CLI, MCP server, API server, skills, swarm/autopilot workflows, and file/web/document tools.
2. **Market-data layer** — a registry of data loaders for A-share, US equity, HK equity, crypto, futures, funds, macro, forex, and local files.
3. **Research/backtest layer** — signal-engine strategy contract, multi-market bar-by-bar execution engines, metrics, run cards, optional validation tests, and optimizers.
4. **Research accelerators** — Alpha Zoo/factor analysis, alpha benchmarking, strict/random-control benchmarking, alpha comparison, and Shadow Account extraction/backtesting/reporting.

The project is best set up for **rapid systematic strategy research** where a researcher wants to:

- write or generate a `SignalEngine` that maps OHLCV/fundamental/event data into target portfolio weights;
- test that strategy across A-share, US/HK equity, crypto, futures, forex, or mixed-market baskets;
- use realistic-but-still-simplified market rules for each venue;
- produce reproducible CSV/JSON/Markdown artifacts;
- run Monte Carlo/bootstrap/walk-forward validation;
- evaluate large factor libraries using cross-sectional IC and group-return analysis;
- turn trade journals into counterfactual “Shadow Account” rule sets;
- perform research workflows through natural-language agent tooling while preserving a conventional file-based backtest contract.

Its strongest setup is **bar-level, signal-driven, target-weight backtesting**. It is not a high-fidelity tick/order-book simulator, not a guaranteed institutional-grade data platform, and not a causal proof engine. Public data providers are useful and broad, but many are unofficial/free endpoints with uneven coverage, rate limits, or endpoint fragility. Use `source: "auto"` for most strategy work unless a provider-specific feature is required.

---

## 2. Agent tasking and prompting: best-practice request design

This section was added after a second scan focused specifically on **how Vibe-Trading expects an agent to be tasked**. The guidance below is derived from the actual agent system prompt, skill contracts, swarm runtime, research-goal tools, data-routing skill, strategy-generation skill, validation tests, and safety gates in this repository. It is therefore not generic “prompt engineering”; it is the practical interface contract that gives Vibe-Trading the highest chance of selecting the right workflow, using the right tools, writing valid strategy code, collecting traceable evidence, and producing reusable artifacts.

### 2.1 Core finding: Vibe-Trading performs best with compact, structured, fully-scoped prompts

An optimal Vibe-Trading prompt is **not** just a trading idea. It should define the research task as an executable experiment:

```text
Mode / workflow: backtest, factor research, Shadow Account, research goal, or explicit swarm preset.
Universe: normalized symbols or a clearly named universe.
Timeframe: start/end dates, holding horizon, and data interval.
Data scope: OHLCV only, fundamentals, events, journal data, or factor panels.
Signal logic: entry, exit, filters, ranking, sizing, and risk controls.
Backtest assumptions: source preference, capital, commission, long/short/leverage constraints.
Validation: Monte Carlo / bootstrap / walk-forward / benchmark / attribution requirements.
Deliverables: exact artifacts or report format expected.
Safety boundary: research-only, no live order execution.
```

The best prompts are **precise enough to become `config.json` plus `code/signal_engine.py`**, but not so over-specified that they force unsupported data, live execution, or non-bar-level simulation. In practice, one dense paragraph or a 8–12 bullet prompt is usually ideal. For swarm prompts, keep the first 2,000 characters especially information-dense because `run_swarm` stores the prompt-derived goal with `_snippet(goal, 2000)` in `agent/src/tools/swarm_tool.py`.

### 2.2 Why this matters: how the agent routes tasks internally

The main agent prompt in `agent/src/agent/context.py` routes requests into a few distinct workflows:

| User intent | Internal route | Prompting implication |
|---|---|---|
| “Create/test/optimize a strategy” | Load `strategy-generate`, write `config.json`, write `code/signal_engine.py`, syntax-check, call `backtest`, read metrics/artifacts, run post-backtest attribution if available. | Give enough detail for both `config.json` and `SignalEngine.generate`. |
| “Team/committee/swarm analysis” | Call `run_swarm(prompt=..., preset_name=...)` only when the user explicitly asks for team-based work. | Name the preset/team explicitly when possible; do not rely on a vague continuation prompt. |
| “Factor analysis/options/general research” | Load the relevant skill, then call the matching tool. | Name the data need, universe, period, statistic, and desired output. |
| “PDF/URL/document” | Use document or web reader tools. | Supply the file/URL and the exact research question. |
| “Analyze my broker export/trading history” | Load `trade-journal`, call `analyze_trade_journal`, optionally move to Shadow Account. | Upload or reference the journal; specify filters if desired. |
| “Extract my own profitable pattern / train a shadow” | Load `shadow-account` first, then extract rules, backtest, render report, optionally scan signals. | Ask for the full Shadow workflow and expect a rule-confirmation step. |
| “Long evidence-driven research” | Start or continue a research goal, attach evidence to criteria, audit before completion. | Provide acceptance criteria and evidence standards. |

Two consequences follow:

1. **A vague prompt causes the agent to ask clarifying questions or apply defaults.** For strategy generation, missing instruments or vague strategy logic are explicitly treated as critical missing information in `strategy-generate/SKILL.md`.
2. **A complete prompt lets the agent go straight to artifacts.** The most efficient path is: parse requirements → write config → write signal engine → syntax check → run backtest → read artifacts → evaluate.

### 2.3 The optimal top-level prompt skeleton

Use this skeleton when asking an agent connected to Vibe-Trading to do substantive research or strategy work:

```text
Task mode: [backtest | factor research | Shadow Account | research goal | swarm preset: <preset_name>]
Objective: [one-sentence research-only objective]
Universe / symbols: [normalized symbols or named universe]
Market: [A-shares | US | HK | crypto | futures | forex | mixed]
Time range and interval: [YYYY-MM-DD to YYYY-MM-DD, 1D/1H/etc.]
Data: [source=auto unless specific; required fields; benchmark; data freshness]
Strategy / research logic: [entry, exit, ranking, filters, holding period, rebalancing]
Position and risk rules: [weights, cash, long/short, stops, leverage cap, max position]
Validation: [Monte Carlo, bootstrap, walk-forward, benchmark regression, regime analysis]
Deliverables: [metrics table, artifacts, report.md, action items, caveats]
Constraints: research-only; do not place orders; use built-in backtest engine; do not fabricate numbers.
```

This structure matches the codebase’s actual requirements: the strategy skill wants instruments, time range, and strategy logic; the backtest runner wants config fields; the worker prompt requires tool-backed numbers; the goal system tracks objective, criteria, evidence, and audit; and the swarm preset system needs explicit routing variables.

### 2.4 Backtest prompt best practices

Backtesting is Vibe-Trading’s strongest path, so prompts should be written to map cleanly onto `config.json` and `SignalEngine.generate(data_map)`.

#### Include these fields

| Prompt element | Why it matters in the codebase | Good example |
|---|---|---|
| Normalized symbols | Loader routing and market detection depend on symbol format. | `AAPL.US`, `00700.HK`, `600519.SH`, `BTC-USDT`. |
| Time range | Strategy skill defaults missing dates to 10 years, but explicit dates make results reproducible. | `2020-01-01 to 2025-12-31`. |
| Interval | Runner supports daily/minute-style intervals, but minute data is heavier. | `interval=1D`; `1H for BTC only`. |
| Source | `source: "auto"` enables mixed-market routing and fallback. | `Use source=auto unless a provider-specific field is required`. |
| Signal logic | Without entry/exit logic, the skill must ask or invent a direction. | `Buy when 20D MA crosses above 60D MA; exit when it crosses below`. |
| Sizing | Signals represent target weights in `[-1.0, 1.0]`; portfolio strategies need normalized weights. | `Top 10 names equal-weighted, each 0.10; others 0`. |
| Risk rules | Helps avoid unrealistic leverage and open-ended positions. | `No shorting; max single-symbol weight 20%; stop-loss at -8%`. |
| Fees/capital | Backtest config defaults exist, but explicit assumptions are reproducible. | `initial_cash=1,000,000; commission=0.001`. |
| Validation | The system prompt says to include Monte Carlo when strategy should produce ≥10 trades. | `Add Monte Carlo 1000, bootstrap 1000, walk-forward 5 windows`. |
| Output | Ensures the agent reads result artifacts and summarizes consistently. | `Report total_return, Sharpe, max_drawdown, trade_count, top winners/losers, action items`. |

#### Best backtest prompt template

```text
Backtest a research-only strategy in Vibe-Trading.

Universe: AAPL.US, MSFT.US, NVDA.US.
Market/source: US equities, source=auto.
Period/interval: 2018-01-01 to 2025-12-31, 1D.
Signal: compute 20D and 60D moving averages on close. Enter long when 20D > 60D and 20D crossed up within the last 3 bars. Exit when 20D < 60D. Add a 10D average-volume filter: only enter when volume > 10D average volume.
Positioning: long-only; equal-weight active positions; cap each symbol at 33%; flat when no signal; no leverage.
Costs: initial_cash=1,000,000; commission=0.001.
Validation: include Monte Carlo with 1000 simulations, bootstrap with 1000 samples at 95% confidence, and 5-window walk-forward.
Deliverables: write config.json and code/signal_engine.py, syntax-check the code, run the built-in backtest tool, then summarize total_return, Sharpe, max_drawdown, trade_count, top winners/losers, beta vs SPY, validation p-values, and two concrete action items. Do not write run_backtest.py. Research only; do not place orders.
```

#### Why this prompt is optimal

It gives the agent everything the strategy workflow asks for: codes, dates, strategy logic, position sizing, config assumptions, validation keys, and expected result fields. It also tells the agent to use the built-in engine instead of wasting effort writing an external runner, which is a specific rule in the agent system prompt and `strategy-generate` skill.

### 2.5 Strategy implementation instructions for an agent

When instructing a coding agent to implement a strategy for Vibe-Trading, be explicit about the contract:

```text
Implement only `code/signal_engine.py` and `config.json`.
`signal_engine.py` must define class `SignalEngine` with method:
    generate(self, data_map: dict[str, pd.DataFrame]) -> dict[str, pd.Series]
Each returned Series must align exactly to the input DataFrame index.
Signal values are target weights in [-1.0, 1.0].
Use only pandas/numpy; include all imports; no `if __name__ == "__main__"` block.
Handle insufficient history with zeros/fillna; no undefined variables; no hardcoded dates/symbols in strategy code.
```

This is exactly how the runner consumes strategies. Vibe-Trading is not asking for an event-driven broker script; it asks for a deterministic signal function over historical data frames.

### 2.6 Research-goal prompts: use acceptance criteria, evidence, and audit language

For long-running research, the repository includes a research-goal layer. Its default criteria are:

1. define the research-only thesis and symbol universe;
2. collect fresh market or benchmark evidence;
3. record caveats, contradictions, and the non-advice boundary.

The goal tools also support custom criteria, evidence fields, artifact paths, provider/source metadata, confidence, caveats, and completion audit rows. Therefore, an optimal research prompt should include the **research objective** plus **explicit acceptance criteria**.

#### Best research-goal prompt template

```text
Start a research-only goal.

Objective: Test whether large-cap US semiconductor momentum has delivered persistent alpha versus SPY after accounting for market beta.
Universe: NVDA.US, AMD.US, AVGO.US, QCOM.US, INTC.US.
Period: 2018-01-01 to 2025-12-31.
Criteria:
1. Collect OHLCV evidence for the universe and SPY with data_as_of noted.
2. Backtest a transparent momentum/risk filter with source=auto.
3. Compare strategy returns to SPY with beta regression and drawdown analysis.
4. Run Monte Carlo/bootstrap validation if there are enough trades.
5. Record caveats: survivorship bias, transaction costs, data-provider limits, no live-trading advice.
Deliverable: Markdown report with evidence table, metrics table, conclusion, and open questions.
```

This phrasing fits the goal store because it separates objective, criteria, evidence, and completion conditions. It also avoids execution language that the goal policy rejects, such as “buy now” or “place order.”

### 2.7 Hypothesis / Research Autopilot prompts

The Research Autopilot path is designed for durable hypotheses that can be turned into backtest configs and linked back to evidence. A hypothesis prompt should contain:

| Field | Why it helps |
|---|---|
| Title | Used to identify the saved hypothesis. |
| Thesis | Used as the research-goal objective. |
| Signal definition | Used by `scaffold_signal_engine` as the docstring and by the agent as implementation guidance. |
| Universe | Used by `generate_backtest_config` to derive codes when possible. |
| Data sources | Resolved to a valid loader if recognized, otherwise degraded to `auto` with a warning. |
| Test period | Required by `generate_backtest_config`. |
| Pass/fail standard | Needed for evidence evaluation after `link_autopilot_backtest`. |

#### Best Autopilot-style prompt

```text
Create or use a research hypothesis and run Research Autopilot.

Title: BTC trend persistence after volatility compression.
Thesis: BTC-USDT has positive forward returns when 20D realized volatility falls below its 120D percentile and price remains above the 60D moving average.
Signal definition: Long BTC-USDT at target weight 1.0 when close > 60D MA and 20D realized volatility is below its rolling 120D 30th percentile; flat otherwise. No shorting.
Universe: BTC-USDT.
Preferred data source: okx, but fall back to auto if needed.
Backtest period: 2020-01-01 to 2025-12-31, interval 1D.
Evaluation: link the run card to the hypothesis, then judge whether Sharpe > 1, max_drawdown < 40%, trade_count > 10, and Monte Carlo Sharpe p-value <= 0.05.
Deliverable: report conclusion as supported / weak / rejected, with caveats.
```

### 2.8 Swarm prompts: name the preset and provide all routing variables up front

The `run_swarm` tool is useful for multi-agent committee analysis, but its routing is keyword/preset based. It auto-matches a preset from the prompt, extracts variables, and then runs a YAML-defined DAG of specialist workers. The code includes a regression test to ensure vague continuation prompts like “Continue and finish the report” do **not** silently fall back to `equity_research_team`.

#### Swarm prompt rules

| Rule | Reason |
|---|---|
| Use swarm only when you actually want a team/committee workflow. | The main agent system prompt says not to use swarm unless explicitly requested. |
| Name the preset when known. | Explicit preset names override keyword scoring and avoid misrouting. |
| Put tickers in normalized format. | Swarm grounding extracts suffixed symbols and promotes some bare US tickers, but suffixed symbols are more reliable. |
| Include market, target, horizon, risk tolerance, and deliverable. | `_build_variables` otherwise applies defaults such as `market="A-shares"`, `risk="moderate"`, `target_variable="return"`, or generic crypto/commodity defaults. |
| Do not send only “continue” / “finish” as a fresh task. | `_resolve_preset` rejects ambiguous continuation fragments unless an explicit preset is supplied. |
| Demand source-backed numbers. | Worker prompts require every specific number to trace to a tool result, a Ground Truth block, or upstream context. |

#### Best swarm prompt template

```text
Use the `investment_committee` swarm preset.

Full task: Evaluate NVDA.US as a research-only long/neutral/avoid decision for a 3-month horizon.
Market: US equities.
Data: fetch current/recent OHLCV through Vibe-Trading tools; use SPY as benchmark; do not cite unsourced prices or percentages.
Committee roles expected: bull case, bear case, risk review, PM final decision.
Decision framework: valuation sensitivity, earnings momentum, technical trend, drawdown risk, market beta, and catalyst calendar.
Deliverable: final committee memo with (1) recommendation, (2) confidence, (3) key evidence table, (4) risk triggers, (5) what would change the view. Research only; no order placement.
```

For a continuation, include the context explicitly:

```text
Continue the previous `investment_committee` analysis using preset_name=investment_committee and the original objective: Evaluate NVDA.US as a research-only long/neutral/avoid decision for a 3-month horizon. Use the existing run result if available; otherwise rerun with the full objective above. Finish the report with a PM decision and risk triggers.
```

### 2.9 Swarm preset routing defaults to be aware of

When the prompt does not provide enough information, `agent/src/tools/swarm_tool.py` fills some variables heuristically. This can be convenient, but it is also a source of accidental mis-tasking.

| Preset | Important variables | Code default if omitted | Prompting best practice |
|---|---|---|---|
| `global_allocation_committee` | `goal`, `risk_tolerance` | risk defaults to `moderate` | State risk tolerance and investable markets. |
| `equity_research_team` | `market`, `goal` | market defaults to `A-shares` | State market and target universe. |
| `quant_strategy_desk` | `market`, `goal` | market defaults to `A-shares` | State strategy type, symbols/universe, validation goal. |
| `factor_research_committee` | `market`, `factor_type` | `factor_type="value"` | State factor family: value, momentum, quality, volatility, sentiment, etc. |
| `event_driven_task_force` | `market`, `event_type` | `event_type="all types"` | State event type and event window. |
| `derivatives_strategy_desk` | `target`, `view` | `view="neutral"` | State directional/volatility view and expiry range. |
| `crypto_research_lab` | `target`, `timeframe` | `BTC, ETH, SOL`; `medium-term 1-3 months` | State exact token/pair and horizon. |
| `commodity_research_team` | `commodity`, `horizon` | `gold`; `3 months` | State commodity and horizon. |
| `portfolio_review_board` | `portfolio`, `review_period`, `goal` | review defaults to `quarterly` | Paste holdings/weights or artifact path and cadence. |
| `ml_quant_lab` | `market`, `target_variable`, `goal` | target defaults to `return` | State prediction target, label horizon, and train/test split. |

Because of these defaults, the safest swarm prompts start with: `Use the <preset_name> preset. Market: ... Target: ... Horizon: ... Goal: ...`.

### 2.10 Data prompts: prefer capability statements over provider micromanagement

Vibe-Trading has a data-routing skill and a loader registry with fallback chains. The optimal prompt usually says **what data is needed**, not which fragile endpoint to hammer.

Good:

```text
Fetch OHLCV for 600519.SH and 000001.SZ from 2021-01-01 to 2025-12-31 using source=auto. Prefer free/default providers. If a provider fails or is unavailable, use same-market fallback and report which source worked.
```

Less good:

```text
Use only Eastmoney and repeatedly retry until it works.
```

Why: the data-routing skill explicitly prefers lower ban-risk sources and says `source: "auto"` should be used for backtest configs unless the user requests a concrete source. It also says missing key-gated providers should be reported instead of failing silently. Prompt for the data need, market, symbol format, date range, fields, and freshness; let the registry select the source unless a provider-specific feature is required.

### 2.11 Factor-research prompts

Factor research requires aligned cross-sectional factor and forward-return panels. An optimal prompt should specify:

| Field | Example |
|---|---|
| Universe | `CSI 300`, `S&P 500`, or explicit symbols. |
| Period | `2020-01-01 to 2025-12-31`. |
| Factor family or ID | `alpha101_001`, `GTJA momentum factors`, `quality/value composite`. |
| Holding horizon | `5D forward return`, `20D forward return`. |
| Neutralization / normalization | `rank transform`, `z-score`, `industry-neutral if sector data is available`. |
| Validation | IC mean, ICIR, positive IC ratio, quantile monotonicity, long-short spread. |
| Lookahead guard | Factor value at T must predict T+1..T+N return, never same-day return. |

#### Best factor prompt template

```text
Run a research-only factor study.

Universe: CSI 300.
Period: 2020-01-01 to 2025-12-31.
Factor source: Alpha Zoo; start with momentum and reversal alphas, or bench alpha101_001 through alpha101_010 if available.
Return target: 5-trading-day forward returns, computed after the factor observation date.
Evaluation: IC mean, IC std, ICIR, positive IC ratio, quintile equity curves, long-short spread, and monotonicity. Flag IC > 0.10 as possible lookahead bias.
Deliverable: table of top factors, interpretation, caveats, and next-step strategy candidates. Do not expose absolute local filesystem paths.
```

### 2.12 Shadow Account prompts

Shadow Account is designed around the user’s own trade journal, not public strategy cloning. The optimal prompt should include the journal path/upload, scope, filters, and desired workflow.

```text
Analyze my uploaded broker export as a research-only Shadow Account workflow.

Steps:
1. Run trade-journal analysis on the uploaded CSV/Excel file.
2. Extract 3–5 human-readable profitable-pattern rules from my closed profitable roundtrips.
3. Show me the rules and ask whether they look like my actual behavior.
4. If accepted, run the shadow backtest across A-shares, HK, US, and crypto where data allows.
5. Render the Shadow report and summarize delta-PnL attribution: noise trades, early exits, late exits, overtrading, and missed signals.
Constraints: do not place orders; today’s matching signals, if any, are research-only and not buy recommendations.
```

This mirrors the `shadow-account` skill’s required order: load the skill first, parse the journal if needed, extract rules, backtest, render report, optionally scan signals with a research-only disclaimer.

### 2.13 Debugging / repair prompts

For failed or suspicious backtests, prompt the agent like a debugger, not like a strategy optimizer. The `backtest-diagnose` skill says to inspect artifacts, classify the issue, fix one issue at a time, rerun, and limit repair iterations.

```text
Diagnose this existing Vibe-Trading backtest run.

Run directory: <run_dir>.
Do not redesign the strategy unless required to fix a bug.
First read config.json, code/signal_engine.py, artifacts/metrics.csv, artifacts/equity.csv, and artifacts/trades.csv if present.
Classify the root cause: runtime error, zero trades, late first trade, low capital utilization, open final position, data-provider issue, or NaN equity.
Apply the smallest code fix with edit_file, syntax-check SignalEngine, rerun backtest, and report before/after metrics.
Limit to 3 repair iterations. If the issue is provider-side rate limit/no data/API quota, do not modify strategy code; recommend a source/token/date fix.
```

### 2.14 What an optimal prompt should not include

| Avoid | Why |
|---|---|
| “Buy/sell/place/submit this order now.” | Research-goal policy rejects live execution objectives; live broker writes are gated and safety-critical. |
| API keys, OAuth tokens, broker credentials, seed phrases, `.env` contents. | Contributor/security rules say secrets must not be copied into the repository or artifacts. |
| “Guarantee profit” or “find a no-loss strategy.” | Backtests and validation estimate historical behavior; they do not prove future profitability. |
| “Use tick/order-book/high-frequency execution realism” for normal backtests. | Default loaders provide historical bars; engines are bar-level, not tick/order-book simulators. |
| “Use all data you know from memory.” | Worker prompts prohibit unsourced market numbers; current prices/percentages must come from tools or grounding. |
| Provider micromanagement when fallback would be better. | `source=auto` and data-routing are designed to reduce provider fragility. |
| Only “continue” / “finish the report” as a new swarm task. | Swarm routing rejects ambiguous continuation fragments to avoid wrong-preset fallback. |
| Unsupported enrichment for the market. | Example: `extra_fields` and `fundamental_fields` are China A-share/Tushare-specific, not US/HK/crypto defaults. |
| Giant unstructured essays with key constraints buried late. | Swarm variable extraction truncates long goals; the agent and workers operate better from front-loaded constraints. |
| Instructions to write long Python directly in bash. | Swarm worker rules prefer `write_file` for scripts, then `bash python script.py`. |

### 2.15 Precision vs concision: how detailed should the prompt be?

The ideal prompt is **concise in wording but precise in constraints**.

| Prompt style | Expected behavior |
|---|---|
| Too vague: “Build me a good strategy.” | Agent should ask for instruments/logic or offer strategy directions; if it guesses, results will be less reusable. |
| Minimal but sufficient: “Backtest BTC-USDT 20/50 MA crossover, 2020–2025, 1D, source=okx, long-only, Monte Carlo 1000.” | Usually enough for a straightforward strategy. |
| Best for research: structured bullets with universe, dates, signal, sizing, validation, deliverables. | Highest chance of correct config, valid signal engine, and useful report. |
| Too verbose: pages of narrative without normalized symbols, dates, or output criteria. | Agent may miss key constraints, especially in swarm mode where variables are extracted from a snippet. |

A good rule: keep the prompt to **one screen for a simple backtest** and **two screens for a full research program**. Put symbols, dates, market, and desired workflow in the first 5–10 lines.

### 2.16 Bad prompt → better prompt examples

| Bad prompt | Why it is weak | Better prompt |
|---|---|---|
| “Find a profitable A-share strategy.” | No universe, period, signal family, or validation standard. | “Backtest an A-share CSI 300 momentum strategy from 2018-01-01 to 2025-12-31, source=auto, monthly rebalance, top 20 by 60D momentum, equal-weight, max 5% per name, compare to 000300.SH, run Monte Carlo/bootstrap.” |
| “Analyze NVDA.” | Ambiguous: single-agent research, swarm committee, backtest, or current quote? | “Use `investment_committee` swarm preset to evaluate NVDA.US for a research-only 3-month long/neutral/avoid decision. Fetch recent OHLCV, benchmark SPY, include bull/bear/risk/PM memo.” |
| “Continue the report.” | Swarm tool rejects ambiguous continuations. | “Continue the previous `investment_committee` report on NVDA.US using preset_name=investment_committee and the original objective: ... Finish the PM decision and risk triggers.” |
| “Use fundamentals on AAPL with extra_fields.” | `extra_fields` are China A-share daily-basic/Tushare-style fields, not a US default. | “For AAPL.US, use available US financial statement/profile/SEC tools for fundamentals; use OHLCV through source=auto. Do not set extra_fields unless supported.” |
| “Backtest BTC/USDT.” | Crypto code format should be `BTC-USDT`. | “Backtest BTC-USDT using OKX/source=auto, 1D, 2020-01-01 to 2025-12-31.” |
| “Run a strategy and tell me if I should buy now.” | Mixes research backtest with live advice/execution. | “Run a research-only backtest and summarize historical evidence, caveats, and what conditions would support further review. Do not provide order instructions.” |

### 2.17 Agent-facing instruction pack for external MCP clients

When Vibe-Trading is used as an MCP toolset inside another AI client, the external agent should be instructed with this operating policy:

```text
Before using Vibe-Trading tools, identify the workflow: backtest, data lookup, factor research, Shadow Account, or swarm.
Load the relevant skill first and follow its contract.
For backtests, create only `config.json` and `code/signal_engine.py`; do not create `run_backtest.py`.
Use `source="auto"` unless a provider-specific field is required.
Use normalized symbols: AAPL.US, 00700.HK, 600519.SH, BTC-USDT.
Use `get_market_data` for OHLCV instead of ad-hoc provider scripts when possible.
Every specific number in the final answer must come from a tool result, generated artifact, or cited upstream context.
After backtest, read `artifacts/metrics.csv`; report total_return, Sharpe, max_drawdown, and trade_count at minimum.
If trades exist, inspect `trades.csv` for attribution; if validation exists, inspect `validation.json`.
For long research, create/continue a research goal and attach evidence to criteria.
For swarm, use an explicit `preset_name` and pass the full original task, not a fragment.
Never place live orders or request broker-write flows unless the user has deliberately entered the separate live-trading mandate path; default to research-only.
```

### 2.18 Prompting for result artifacts

Vibe-Trading creates reusable artifacts, so the prompt should say which ones matter. For backtests, ask for:

| Artifact / result | Prompt phrase |
|---|---|
| Metrics CSV | “Read and summarize `artifacts/metrics.csv`.” |
| Equity curve | “Check `artifacts/equity.csv` for NaNs and drawdown behavior.” |
| Trade blotter | “Use `artifacts/trades.csv` for top winners/losers and exit-reason attribution.” |
| Validation JSON | “If `artifacts/validation.json` exists, report Monte Carlo/bootstrap/walk-forward results.” |
| Run card | “Use `run_card.json` for reproducibility and link it to the hypothesis if using Autopilot.” |
| Markdown report | “Write a concise `report.md` with tables, caveats, and next actions.” |

This fits both the single-agent flow and the swarm worker flow: workers are explicitly instructed to save `report.md`, and the main agent is instructed to present multi-row data as Markdown pipe tables.

### 2.19 Practical prompt checklist

Use this before submitting a high-value task to Vibe-Trading:

- [ ] Did I name the workflow or preset?
- [ ] Did I provide normalized symbols or a named universe?
- [ ] Did I specify market, date range, and interval?
- [ ] Did I say `source=auto` or justify a concrete provider?
- [ ] Did I define entry, exit, filters, sizing, and risk controls?
- [ ] Did I include transaction costs and initial capital if they matter?
- [ ] Did I request validation and benchmark comparison?
- [ ] Did I define the deliverable and must-have metrics?
- [ ] Did I say research-only / no live orders?
- [ ] For swarm: did I provide `preset_name` and avoid a continuation fragment?
- [ ] For long research: did I provide acceptance criteria and evidence standards?

### 2.20 Bottom line for future strategy/research development

The optimal way to task Vibe-Trading is to frame every request as a **reproducible research experiment** rather than a conversational wish. The platform is strongest when the prompt gives it enough structure to produce and verify artifacts: config, strategy code, data pulls, metrics, validation, attribution, and a report. The prompt should be concise, but it should never omit the core experimental variables: universe, timeframe, signal, sizing, data source policy, validation, and deliverable. For team workflows, name the swarm preset and repeat the full objective. For long research, use explicit criteria and evidence. For anything involving broker actions, keep the wording research-only unless deliberately entering the separate live-mandate flow.

## 3. Scan methodology

I inspected the uploaded ZIP directly in the sandbox, extracted it, enumerated the repository structure, parsed loader/factor/test metadata, and read the core implementation files for:

- package/dependency surface: `pyproject.toml`;
- loader registry and loader protocol: `agent/backtest/loaders/registry.py`, `agent/backtest/loaders/base.py`, and each loader implementation;
- agent-facing data tool: `agent/src/market_data.py`, `agent/src/tools/market_data_tool.py`;
- backtest runner: `agent/backtest/runner.py`;
- backtest engines: `agent/backtest/engines/*.py`;
- metrics/validation/run cards: `agent/backtest/metrics.py`, `agent/backtest/validation.py`, `agent/backtest/run_card.py`;
- strategy-generation skill contract: `agent/src/skills/strategy-generate/SKILL.md`;
- Alpha Zoo/factor infrastructure: `agent/src/factors/**`, `agent/src/tools/alpha_*.py`, `agent/src/tools/factor_analysis_tool.py`;
- Shadow Account: `agent/src/shadow_account/**`, `agent/src/tools/shadow_account_tool.py`;
- test suite: `agent/tests/**`, `.github/workflows/test.yml`.

Key static scan counts:

| Item | Count / finding |
|---|---:|
| Python files | 1,055 |
| Markdown files | 375 |
| Frontend TypeScript/TSX files | 78 total |
| User-facing/backend tool modules under `agent/src/tools` | 52 `.py` files |
| Test files under `agent/tests` | 223 `test*.py` files |
| Test functions/classes parsed statically | 2,715 test functions, 316 test classes |
| Pytest collection in the sandbox | 4,227 tests collected before dependency-related collection errors |
| Alpha Zoo alphas loaded by registry | 456 loaded, 0 failed |

The pytest collection errors were expected in this isolated environment because the package and optional/default dependencies were not installed in editable mode here. The repository’s CI installs `pip install -e ".[dev]"` and runs pytest with specific ignores.

---

## 4. Repository architecture at a glance

```text
Vibe-Trading-main/
├── agent/
│   ├── api_server.py                 # Web/API runtime
│   ├── mcp_server.py                 # MCP tool server
│   ├── cli/                          # CLI/TUI entrypoint
│   ├── backtest/
│   │   ├── runner.py                 # config + signal_engine loader, data routing, engine selection
│   │   ├── loaders/                  # market data source adapters and registry
│   │   ├── engines/                  # market execution engines
│   │   ├── metrics.py                # performance metrics
│   │   ├── validation.py             # MC/bootstrap/walk-forward validation
│   │   ├── benchmark.py              # benchmark resolution
│   │   ├── optimizers/               # portfolio optimizers
│   │   └── run_card.py               # reproducibility card writer
│   ├── src/
│   │   ├── tools/                    # agent/MCP tools: backtest, data, alpha, shadow, etc.
│   │   ├── skills/                   # natural-language workflows and coding instructions
│   │   ├── factors/                  # Alpha Zoo registry/operators/bench/compare
│   │   ├── shadow_account/           # trade-journal rule extraction + counterfactual testing
│   │   ├── swarm/                    # multi-agent/autopilot orchestration
│   │   └── ...
│   └── tests/                        # extensive unit/integration/security tests
├── frontend/                         # web UI
├── wiki/                             # docs/wiki static site
├── pyproject.toml                    # package metadata, deps, console scripts
└── docker-compose.yml / Dockerfile
```

Package metadata identifies the project as `vibe-trading-ai`, version `0.1.10`, Python `>=3.11`, with console scripts `vibe-trading = cli:main` and `vibe-trading-mcp = mcp_server:main`. Dependencies include the core scientific stack (`pandas`, `numpy`, `scipy`, `scikit-learn`, `duckdb`, `matplotlib`), agent stack (`langchain`, `langgraph`, `fastapi`, `fastmcp`), data providers (`tushare`, `yfinance`, `akshare`, `ccxt`, `requests`), document tooling, and report rendering (`jinja2`, `weasyprint`). Optional extras include `ibkr`, `ashare`/BaoStock, `deepseek`, harmonic patterns, and multiple messaging channels.

---

## 5. How Vibe-Trading works end-to-end

A typical strategy backtest follows this pipeline:

```text
Natural-language request / run folder
        │
        ▼
config.json + code/signal_engine.py
        │
        ▼
backtest_tool.run_backtest(run_dir)
        │
        ▼
python agent/backtest/runner.py <run_dir>
        │
        ├── validate config schema
        ├── validate run_dir boundary
        ├── AST-validate signal_engine.py import-time safety
        ├── instantiate SignalEngine
        ├── choose data loader(s)
        ├── fetch + sanitize OHLCV data
        ├── optionally enrich fundamentals/events
        ├── choose market engine
        ├── generate signals
        ├── shift signals by one bar
        ├── normalize target weights
        ├── optionally optimize portfolio weights
        ├── execute bar-by-bar with market rules
        ├── compute metrics + validation tests
        ├── write CSV/JSON/Markdown artifacts
        └── print JSON metrics to stdout
```

The core design is file-based and reproducible: every run directory contains a `config.json`, a strategy file at `code/signal_engine.py`, and an `artifacts/` directory after execution. The run card stores config and strategy hashes, data sources, metrics, warnings, and artifact checksums.

---

## 6. Data collection: default providers only

### 6.1 Loader registry and fallback model

The loader layer is centered on `agent/backtest/loaders/registry.py`.

`VALID_SOURCES` contains:

```text
tushare, okx, yfinance, akshare, baostock, tencent, mootdx, ccxt,
futu, eastmoney, sina, stooq, yahoo, finnhub, alphavantage,
tiingo, fmp, local, auto
```

`auto` is not a loader; it is a cross-market selector. `local` is a loader, but explicit `local` requests are intentionally blocked from silently falling through to network sources. That is important: if you ask for `source: "local"` and your local bridge is misconfigured, the system should fail clearly rather than fetching unrelated remote data.

Fallback chains by market:

| Market type | Ordered fallback chain |
|---|---|
| `a_share` | `tencent → mootdx → eastmoney → baostock → akshare → tushare → local` |
| `us_equity` | `yahoo → stooq → sina → eastmoney → yfinance → tiingo → fmp → finnhub → alphavantage → akshare → local` |
| `hk_equity` | `eastmoney → yahoo → futu → yfinance → akshare → local` |
| `crypto` | `okx → ccxt → yfinance → local` |
| `futures` | `tushare → akshare → local` |
| `fund` | `tushare → akshare → local` |
| `macro` | `akshare → tushare → local` |
| `forex` | `akshare → yfinance → local` |

The chain ordering is intentionally biased toward no-key, lower-friction public endpoints first, and key-gated REST providers later.

### 6.2 Loader protocol and required data shape

Every loader implements:

```python
is_available() -> bool
fetch(codes, start_date, end_date, interval="1D", fields=None) -> dict[str, pandas.DataFrame]
```

The expected output is:

- key: symbol/code string;
- value: `DataFrame` indexed by `trade_date`/timestamp;
- required columns: `open`, `high`, `low`, `close`, `volume`;
- optional columns: amount, vwap, fundamentals, events, source-specific extras;
- normalized to ascending time order and generally timezone-naive;
- date range filtered to `start_date <= timestamp <= end_date`.

The shared loader boundary has:

- date-range validation;
- OHLC invariant validation: `high >= low`, `high` brackets open/close, `low` brackets open/close, and all OHLC prices are positive;
- bounded retry helpers for flaky APIs;
- optional local loader cache using Parquet metadata and DuckDB-style cache support, designed to be nonfatal if cache read/write fails.

### 6.3 Provider capability table

This table reflects the scanned implementation, not marketing documentation.

| Source | Markets in code | Auth / setup | Interval support | Main use | Important caveats |
|---|---|---|---|---|---|
| `tencent` | A-share | No key | Mostly daily/K-line public API | Preferred free A-share fallback start | Unofficial/public endpoint; endpoint behavior can change. |
| `mootdx` | A-share | Optional Python dependency / TCP quote access | Bars with pagination | A-share no-key fallback, intended to avoid HTTP CDN blocks | Dependency and quote-server availability matter. |
| `eastmoney` | A-share, US, HK | No key | K-line intervals via Eastmoney KLT mapping | Broad free public fallback | Public endpoint; throttling/rate-limit fragility. |
| `baostock` | A-share | Optional `ashare` extra; BaoStock login protocol but no paid token | Daily only in scanned loader | A-share free TCP-style backup | Requires dependency; daily only. |
| `akshare` | A-share, US, HK, macro, fund, futures, forex | No key | Source-specific; broad but uneven | Broad China/market data fallback | API wrappers change frequently; coverage depends on AkShare endpoints. |
| `tushare` | A-share, futures, fund | `TUSHARE_TOKEN` | `1D`, `1m`, `5m`, `15m`, `30m`, `1H` in loader mappings | Higher-quality China data; extra fields/fundamentals | Token required; some fields require Tushare points/permissions. |
| `yahoo` | US, HK | No key | Yahoo chart intervals | Preferred direct no-SDK US/HK fallback | Unofficial chart endpoint; may throttle/block. |
| `yfinance` | US, HK, crypto | No key | yfinance interval mappings | Equity/crypto fallback; engine routing recognizes it as global equity | SDK behavior can change; intraday history limits apply. |
| `stooq` | US equity | No key | Daily only | Free EOD backup | Daily only; symbol mapping limitations. |
| `sina` | US equity | No key | Daily only | US daily backup via Sina K-line | Daily only; unofficial JSONP endpoint. |
| `finnhub` | US equity | `FINNHUB_API_KEY` | Daily in loader | Key-gated US fallback | API quotas/plan limits. |
| `alphavantage` | US equity | `ALPHAVANTAGE_API_KEY` | Daily in loader | Key-gated US fallback | API quotas; daily only in implementation. |
| `tiingo` | US equity | `TIINGO_API_KEY` | Daily in loader | Key-gated US fallback | API quotas; daily only in implementation. |
| `fmp` | US equity | `FMP_API_KEY` | Daily in loader | Key-gated US fallback | API quotas; daily only in implementation. |
| `okx` | Crypto | No key for public spot candles | Crypto bar intervals | Preferred crypto default for `BTC-USDT` style symbols | Public endpoint; OKX symbol conventions matter. |
| `ccxt` | Crypto | No key for public exchange OHLCV; `CCXT_EXCHANGE` optional, default Binance | Exchange interval mappings | Exchange-general crypto fallback | Exchange availability, rate limits, proxy/env config. |
| `futu` | HK, A-share | Futu OpenD service; `FUTU_HOST`, `FUTU_PORT` | K-line intervals through Futu | Optional HK/A-share data path | Requires local OpenD and account/session setup. |
| `local` | All registered markets | Local config file `~/.vibe-trading/data-bridge/config.yaml` | Depends on files | Offline/private data bridge for CSV/Parquet/DuckDB | Explicit `local` never falls through to network; schema must match expected columns. |

### 6.4 Symbol-to-source auto routing

There are two related auto-routing systems:

1. **Agent market-data tool routing** in `agent/src/market_data.py`:
   - `local:` prefix → local;
   - A-share pattern like `000001.SZ` / `.SH` / `.BJ` → Tencent;
   - US pattern like `AAPL.US` → Yahoo;
   - HK pattern like `00700.HK` → Yahoo;
   - crypto hyphen pattern like `BTC-USDT` → OKX;
   - crypto slash pattern like `BTC/USDT` → CCXT;
   - otherwise → Tushare.

2. **Backtest `source: "auto"` routing** in `agent/backtest/runner.py`:
   - classifies codes by market type;
   - resolves a loader through the market-level fallback chain;
   - normalizes crypto slash/hyphen symbols depending on the selected loader;
   - tries runtime fallback sources if the first source returns an empty result.

For future research, prefer `source: "auto"` unless you are deliberately testing a specific provider. Auto mode reduces provider friction and also avoids some engine-routing surprises described later.

### 6.5 `get_market_data` / market-data tool behavior

The agent-facing data tool calls the same loader layer and returns JSON-safe records. Important details:

- default `max_rows = 250`;
- if fetched rows exceed `max_rows`, it returns a sampled/truncated view with metadata;
- the last bar is pinned in sampled results so current/recent data is not lost;
- unresolved symbols are returned under `_unresolved` rather than silently ignored;
- grouped source routing is used when `source="auto"`.

For strategy development, use the market-data tool to inspect shape and coverage, but do not confuse its truncated JSON preview with the full backtest data. The backtest runner fetches full frames for the requested dates.

### 6.6 Data enrichment paths

Vibe-Trading can use more than OHLCV in backtests, but enrichment is deliberately explicit.

#### `extra_fields`

`extra_fields` are passed to the Tushare loader on daily data. This is mainly intended for China A-share daily valuation/basic fields. Strategy files can then read these columns from the same `DataFrame`.

#### `fundamental_fields`

`fundamental_fields` triggers the Tushare fundamental provider in the base engine. The code enriches price frames with point-in-time statement/fundamental values. The strategy-generation skill documents fields such as:

- `income_total_revenue`;
- `income_n_income`;
- `balancesheet_total_hldr_eqy_exc_min_int`;
- `fina_indicator_roe`.

This path requires a valid `TUSHARE_TOKEN` and whatever Tushare permissions/points are needed for the requested fields.

#### `event_feeds`

`event_feeds` triggers RSSHub event enrichment. It requires `RSSHUB_BASE_URL`. The base engine calls the event provider and adds decayed event information, including an `event_score`, with defaults like `event_decay_lambda=0.1` and `event_lookback=30` unless overridden.

#### Alpha/factor panels

The Alpha Zoo and alpha-bench tools build wide panel data from loaders, then compute factor values, forward returns, IC series, and group equity.

#### Shadow Account price features

Shadow Account extraction can fetch historical price context as of each journal buy date. It is point-in-time by design: the extractor requests data ending at or before the buy date and uses only past bars to compute features such as RSI or prior returns.

---

## 7. Strategy creation and implementation

### 7.1 Standard strategy contract: `SignalEngine`

A normal daily/bar strategy is a Python file:

```text
<run_dir>/code/signal_engine.py
```

It defines:

```python
from typing import Dict
import pandas as pd

class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        ...
```

Input:

- `data_map`: dict mapping symbol → OHLCV `DataFrame`;
- each frame has a `DatetimeIndex` and at least `open/high/low/close/volume`;
- extra/fundamental/event columns are present only if configured and successfully loaded.

Output:

- dict mapping symbol → `pd.Series`;
- each series should align to the input frame index;
- values are clipped by the engine into `[-1, 1]`;
- interpretation is target exposure/weight signal before portfolio normalization:
  - `1.0` = full long signal;
  - `0.5` = half long;
  - `0.0` = flat;
  - `-1.0` = short signal if the market engine permits shorting.

The base engine then shifts all signals by one bar. This means today’s signal is executed on the next bar’s open, avoiding same-bar lookahead execution.

### 7.2 `config.json` contract

The runner validates a Pydantic schema with required fields:

```json
{
  "codes": ["000001.SZ"],
  "start_date": "2018-01-01",
  "end_date": "2025-12-31",
  "source": "auto",
  "interval": "1D",
  "engine": "daily"
}
```

Supported `interval` values:

```text
1m, 5m, 15m, 30m, 1H, 4H, 1D
```

Supported `engine` values:

```text
daily, options
```

The schema allows additional config keys; engines and tools use extras such as:

- `initial_cash`;
- `commission`;
- `slippage`;
- `benchmark`;
- `extra_fields`;
- `fundamental_fields`;
- `event_feeds`;
- `optimizer`;
- `optimizer_params`;
- `validation`;
- market-specific fee/margin/slippage settings;
- `rebalance_threshold` — opt-in mid-hold position resizing, see §8.3;
- `options_config` for the options engine.

### 7.3 Strategy safety checks

The runner validates `signal_engine.py` before import:

- no `from signal_engine import ...` self-import;
- top-level executable statements are rejected;
- top-level assignments must be literal-only — **note a real, non-obvious edge case, confirmed by direct testing**: the literal check (`_is_literal_node`) recognizes `ast.Constant`/`Tuple`/`List`/`Set`/`Dict` but not `ast.UnaryOp`, and Python parses a negative-number literal (e.g. `-0.43`) as `UnaryOp(USub, Constant(...))`, not a bare `Constant`. A top-level dict/list/tuple containing a negative number is therefore rejected even though it looks like plain data — encode sign separately (e.g. a non-negative code) and apply it inside `generate()`'s body instead, which has no such restriction;
- functions/classes are allowed;
- decorators are rejected in function/class definitions;
- class-level executable statements are rejected;
- `SignalEngine` must be instantiable without required `__init__` arguments;
- `SignalEngine.generate` must be callable.

This prevents import-time side effects in generated strategy files. It is not a full sandbox for arbitrary code inside method bodies. Strategy code still runs inside the Python process after import, so research runs should be treated as code execution.

Run directories are also constrained by `safe_run_dir`, which accepts only allowed run roots such as `agent/runs`, swarm runs, current-working-directory `runs`, and `~/.vibe-trading/...` run locations unless `VIBE_TRADING_ALLOWED_RUN_ROOTS` is configured.

### 7.4 Portfolio weight processing

After `generate()` returns raw signal series:

1. signals are clipped to `[-1, 1]`;
2. signals are shifted by one bar;
3. signals are reindexed to the unified date index;
4. close prices are forward-filled with a limit:
   - 5 bars for single-market;
   - 10 bars for cross-market, to tolerate calendar mismatches such as long holidays;
5. all-NaN symbols are dropped;
6. an optional optimizer may transform weights;
7. the final target-position matrix is normalized so `sum(abs(weights)) <= 1` for each bar.

This makes the framework naturally suited to **target-weight strategies**: momentum, mean reversion, rotation, multifactor ranking, volatility targeting, cross-market allocation, and long/short portfolios where the market engine permits shorting.

### 7.5 Portfolio optimizers

The repository includes optimizer modules under `agent/backtest/optimizers/`:

- `equal_volatility`;
- `risk_parity`;
- `mean_variance`;
- `max_diversification`.

Config pattern:

```json
{
  "optimizer": "risk_parity",
  "optimizer_params": {}
}
```

The base engine dynamically imports `backtest.optimizers.<name>.optimize`. Use only known in-repo optimizer names unless extending the package.

### 7.6 Options strategies

`engine: "options"` switches to `agent/backtest/engines/options_portfolio.py`.

Instead of returning target-weight series, the options signal engine returns a list of trade instructions. The options backtester:

1. loads underlying OHLCV data;
2. estimates volatility from historical underlying returns;
3. prices options with Black-Scholes;
4. optionally applies a simple IV smile adjustment;
5. supports European and a heuristic American early-exercise mode;
6. handles multi-leg open/close instructions;
7. marks open option positions to model value;
8. writes `equity.csv`, `trades.csv`, `greeks.csv`, `metrics.csv`, and run cards.

This is a theoretical options-pricing simulator, not a historical option-chain backtester. It synthesizes option prices from underlying prices and model assumptions.

### 7.7 Strategy generation workflows

Strategies can enter the system through several paths:

- **Manual implementation**: researcher writes `config.json` and `code/signal_engine.py`.
- **Agent skill**: `strategy-generate` guides the agent to create the config and code, syntax-check, run backtest, evaluate artifacts, and iterate.
- **Autopilot/hypothesis tooling**: tools can generate hypotheses, scaffold configs and signal engines, and link research runs to backtests.
- **Alpha Zoo strategies**: factors can be pulled from the registry and transformed into signals via multifactor/zoo strategy workflows.
- **Shadow Account codegen**: trade journals are converted into rules, then into generated strategy code.

---

## 8. Backtesting mechanics in detail

### 8.1 Runner responsibilities

`agent/backtest/runner.py` is the main backtest entrypoint. Its responsibilities are:

1. load `<run_dir>/config.json`;
2. validate required config fields and date order;
3. validate `source`, `interval`, and `engine`;
4. validate `run_dir` and `signal_engine.py` safety;
5. instantiate `SignalEngine`;
6. select and invoke data loaders;
7. sanitize OHLCV data;
8. determine effective source and annualization;
9. select engine type;
10. execute the selected engine;
11. allow the engine to write artifacts and metrics.

The runner supports both named-source and `auto` data modes. For named sources, it can try fallback loaders when a source is unavailable or returns no data, except for explicit `local`. For `auto`, it groups symbols by market and resolves each market independently.

### 8.2 Engine selection

The runner detects market types from symbol patterns and source names. Routing priority:

1. mixed market set → `CompositeEngine`;
2. futures symbols → China or global futures engine;
3. forex symbols → `ForexEngine`;
4. `okx`/`ccxt` source → `CryptoEngine`;
5. `tushare`/`akshare` source → China A engine unless US/HK symbols are detected;
6. `yfinance` source → global equity engine;
7. otherwise → crypto engine fallback.

Important limitation: the explicit non-auto sources `yahoo`, `stooq`, `sina`, and `eastmoney` are valid loaders, but the source-based engine routing has an explicit `yfinance` branch for global equity and otherwise falls back to `CryptoEngine`. In practice, `source: "auto"` avoids most of this because primary-source detection maps US/HK equities to the legacy global-equity path, but a manually configured `source: "yahoo"` single-market US/HK backtest deserves extra verification.

### 8.3 Base execution loop

The base engine implements bar-by-bar target-weight execution:

1. call `on_bar()` hooks for each symbol/date;
2. rebalance each symbol toward the target notional exposure;
3. use bar `open` for execution, falling back to close when open is unavailable;
4. check `can_execute()` for market constraints;
5. apply market-specific slippage;
6. round trade size according to market lot rules;
7. apply commissions/fees/taxes;
8. open or close positions (default), or optionally add-to/reduce an existing same-direction position (see below);
9. mark equity;
10. force-close all remaining positions at the final date with reason `end_of_backtest`.

**Default sizing is entry-locked, not continuously rebalanced — a real, previously-undocumented behavior confirmed by direct inspection of `_rebalance()`, not an assumption.** A position's size (quantity) is set once, on the day it opens, from whatever `target_notional` the signal engine's weight implies *at that moment*. While the target's sign (long/short/flat) stays the same on subsequent bars, the position is **not** resized to match each new bar's recomputed target weight — it is left exactly as-is until the sign changes (a full close) or the backtest ends. A signal engine that returns a smoothly-varying magnitude every bar (a vol scalar, a risk-parity weight, a regime dampener) is therefore only actually acting on the value it computed on entry day; every subsequent day's recomputation of that same magnitude is inert until the next direction flip. This is universal across every engine on this platform (no engine overrides `_rebalance()`). An opt-in escape hatch exists: setting `config["rebalance_threshold"]` (a float) enables add-to/reduce logic that resizes a same-direction position once its target weight drifts from its current implied weight by more than the threshold, blending cost basis on adds and realizing partial P&L on reduces. It defaults to unset/`None`, which preserves the entry-locked behavior above exactly — every existing strategy and test is unaffected unless this key is explicitly set. Whether enabling it helps or hurts a given strategy is not universal — for at least one validated strategy family it was tested and found sharply harmful (see `vibe_trading_research_findings.md` §43.3 and `CLAUDE.md`), because it lets a vol-target formula trim a position exactly as a favorable trend's own volatility rises.

This design is appropriate for bar-level systematic strategies. It does not model queue priority, bid/ask order book depth, intrabar stop/limit triggers, partial fills from volume participation, exchange outages, or broker-specific reject states except where simple rules are encoded.

### 8.4 Market engines and rules

#### China A-share engine

`ChinaAEngine` models:

- long-only retail-style trading;
- no shorting;
- T+1 sell restriction;
- price-limit checks using heuristic limits:
  - main board ≈ ±10%;
  - STAR/ChiNext ≈ ±20%;
  - Beijing ≈ ±30%;
- 100-share lot rounding;
- commission with minimum fee;
- sell-side stamp tax;
- transfer fee;
- simple slippage.

Strength: much more realistic than a generic equity engine for A-shares.  
Limitation: ST names, exact daily limit status, suspensions, auction mechanics, and exchange-specific microstructure are simplified.

#### Global equity engine

`GlobalEquityEngine` models US/HK-style equity behavior:

- T+0 style execution;
- long and short positions allowed by default;
- US fractional size rounding to 0.01 shares;
- HK 100-share lot rounding;
- HK stamp duty/levies/settlement style fees;
- zero/low default US commission;
- simple slippage.

Strength: good for US/HK bar-level long/short research.  
Limitation: no borrow availability/borrow fee model for shorts, no detailed corporate action handling beyond whatever the data source provides, no venue-level liquidity model.

#### Crypto engine

`CryptoEngine` models crypto/perpetual-like behavior:

- public crypto OHLCV via OKX/CCXT/yfinance/local;
- leverage/margin concepts;
- liquidation logic;
- funding-fee hooks using scheduled funding windows;
- simple fee/slippage model;
- long/short positions where configured/allowed.

Strength: better than generic equity logic for perpetual-like crypto systems.  
Limitation: not a full exchange matching or liquidation ladder simulator; funding assumptions need review for each use case.

#### Futures engines

There are separate China futures and global futures engines. They add:

- contract multipliers;
- margin concepts;
- futures-specific fee/commission behavior;
- symbol-market detection;
- futures-style PnL hooks.

Strength: suitable for initial futures strategy research.  
Limitation: exact exchange product specs, contract rolls, expiry handling, and tick-size rules may require custom verification before production-grade research.

#### Forex engine

`ForexEngine` models:

- FX/CFD-like spot exposure;
- lot sizing/pip conventions;
- swap/rollover hooks;
- Wednesday triple-swap logic;
- simple slippage.

Strength: useful for bar-level FX strategy prototypes.  
Limitation: broker-specific swaps, spreads, and liquidity vary heavily.

#### Composite engine

`CompositeEngine` is for mixed-market portfolios. It:

- creates market-rule delegates per symbol/market;
- uses one shared capital pool;
- delegates execution rules, lot rounding, commission, slippage, and PnL/margin logic;
- implements cross-market handling for crypto funding/liquidation, forex swaps, and A-share T+1 constraints in the shared portfolio context.

Strength: cross-asset allocation and mixed-market strategies are first-class.  
Limitation: cross-market cash/currency conversion is simplified; calendar alignment is forward-filled; precise broker-level multi-currency accounting is not modeled.

### 8.5 Benchmark behavior

If no explicit benchmark is configured, the base engine creates a simple benchmark return series from the mean returns of the strategy universe. If `benchmark` is set and is not `"auto"`, it calls benchmark resolution to fetch an external benchmark series and records benchmark metadata.

For serious research, explicitly set benchmarks where possible instead of relying on the equal-weight universe fallback.

---

## 9. Metrics and result artifacts

### 9.1 Core performance metrics

`agent/backtest/metrics.py` computes:

- `final_value`;
- `total_return`;
- `annual_return`;
- `max_drawdown`;
- `sharpe`;
- `calmar`;
- `sortino`;
- `win_rate`;
- `profit_loss_ratio`;
- `profit_factor`;
- `max_consecutive_loss`;
- `avg_holding_days` / holding bars;
- `trade_count`;
- `benchmark_return`;
- `excess_return`;
- `information_ratio`;
- `by_symbol` stats;
- `by_exit_reason` stats.

Annualization is based on bar frequency and source-specific trading-day assumptions. The code explicitly handles common sources such as Tushare/yfinance/akshare/mootdx/futu at 252 days and OKX/CCXT at 365 days. Sources not in the explicit map fall back to defaults, so annualized metrics for unusual provider/interval combinations should be reviewed.

### 9.2 Standard backtest artifacts

A normal daily/bar backtest writes:

| File | Contents |
|---|---|
| `artifacts/ohlcv_<code>.csv` | Normalized input OHLCV per symbol, including any enrichment columns. |
| `artifacts/equity.csv` | Strategy returns/equity/drawdown, benchmark equity, active return. |
| `artifacts/positions.csv` | Target position weights by timestamp and symbol. |
| `artifacts/trades.csv` | Entry/exit trade records: timestamp, code, side, price, qty, reason, PnL, holding period, return %. |
| `artifacts/metrics.csv` | One-row scalar metrics table. |
| `artifacts/validation.json` | Optional validation results if enabled. |
| `run_card.json` | Reproducibility card with config hash, strategy hash, data sources, metrics, artifacts, warnings. |
| `run_card.md` | Human-readable Markdown run card. |

The run card writer records SHA-256 hashes for `config.json`, `code/signal_engine.py`, and all discovered artifacts under the run directory. That makes it useful for audit trails and comparing backtest revisions.

### 9.3 Options artifacts

Options backtests write:

| File | Contents |
|---|---|
| `artifacts/ohlcv_<code>.csv` | Underlying price data. |
| `artifacts/equity.csv` | Equity/cash/positions value by date. |
| `artifacts/trades.csv` | Option open/close/exercise/expire records. |
| `artifacts/greeks.csv` | Portfolio delta/gamma/theta/vega and number of open positions. |
| `artifacts/metrics.csv` | Options performance metrics. |
| `run_card.json` / `run_card.md` | Reproducibility cards. |

---

## 10. Validation tests Vibe-Trading can run

Validation is optional through `config["validation"]` or can be run after the fact with the validation CLI against an existing run directory.

### 10.1 Monte Carlo trade-order test

Function: `monte_carlo_test`.

- Requires at least 3 trades.
- Shuffles realized trade PnL order across simulations.
- Compares actual Sharpe/drawdown to simulated distributions.
- Returns p-values and distribution summaries.

Main outputs:

- `actual_sharpe`;
- `actual_max_dd`;
- `p_value_sharpe`;
- `p_value_max_dd`;
- simulated Sharpe mean/std/p5/p95;
- number of simulations;
- number of trades.

Use it to ask: “Is this trade sequence unusually good relative to reshuffled trade outcomes?”

### 10.2 Bootstrap Sharpe confidence interval

Function: `bootstrap_sharpe_ci`.

- Requires at least 5 return observations.
- Resamples return observations with replacement.
- Produces an observed Sharpe and confidence interval.
- Reports probability that bootstrapped Sharpe is positive.

Use it to ask: “How uncertain is the Sharpe estimate under simple return resampling?”

### 10.3 Walk-forward analysis

Function: `walk_forward_analysis`.

- Requires enough bars for the requested number of windows.
- Splits the equity/trade history into sequential windows.
- Computes per-window return, Sharpe, drawdown, trades, and win rate.
- Reports consistency metrics.

Use it to ask: “Did the strategy work across time, or only in one lucky regime?”

### 10.4 What these validation tests do not prove

These tests are helpful diagnostics, not formal proof of out-of-sample profitability. They do not eliminate:

- data-snooping bias;
- multiple-testing bias;
- universe/survivorship bias;
- omitted transaction-cost effects;
- regime dependence;
- inaccurate provider data;
- overfitting from manual iteration.

For production research, combine them with strict train/test splits, out-of-sample windows, parameter freezes, randomized baselines, and independent data verification.

---

## 11. Alpha Zoo and factor research

### 11.1 Alpha Zoo inventory

The scanned registry loaded **456 alpha definitions** with zero load failures:

| Zoo | Count |
|---|---:|
| `gtja191` | 191 |
| `qlib158` | 154 |
| `alpha101` | 101 |
| `academic` | 10 |

Theme counts from metadata:

| Theme | Count |
|---|---:|
| volume | 190 |
| momentum | 175 |
| reversal | 91 |
| volatility | 65 |
| microstructure | 37 |
| quality | 3 |
| liquidity | 3 |
| value | 1 |
| sentiment | 1 |

Universe metadata counts:

| Universe | Count |
|---|---:|
| `equity_cn` | 355 |
| `equity_us` | 265 |
| `equity_hk` | 164 |

The registry schema can represent more universe types, but the loaded alpha metadata in this scan is primarily equity-oriented.

### 11.2 Factor registry design

Each alpha has metadata such as:

- `id`;
- nickname;
- theme list;
- LaTeX formula;
- required OHLCV columns;
- extra fields required;
- sector requirement flag;
- supported universe tags;
- frequency;
- decay horizon;
- minimum warmup bars;
- notes.

The registry does safe metadata extraction by AST-reading literal `__alpha_meta__` from zoo modules. It does not import every alpha module merely to read metadata. Computation is lazy: when an alpha is computed, the registry imports the corresponding zoo module and validates output shape/quality.

### 11.3 Factor operators

`agent/src/factors/base.py` provides wide-DataFrame operators for cross-sectional and time-series formula implementation, including:

- rank/scale;
- time-series rank;
- rolling correlation/covariance;
- rolling mean/std/min/max;
- rolling argmax/argmin;
- delta;
- decay linear;
- signed power;
- safe division;
- vwap.

The operator layer explicitly disallows problematic lookahead-like operations in some primitives, such as rejecting invalid negative delta horizons.

### 11.4 Factor analysis outputs

`factor_analysis_tool.py` takes factor and return CSVs and writes:

| Output | Meaning |
|---|---|
| `ic_series.csv` | Time series of daily cross-sectional IC values. |
| `ic_summary.json` | IC mean/std/IR/positive-ratio/count style summary. |
| `group_equity.csv` | Quantile-group equity curves. |

This is best used for cross-sectional alpha evaluation across a universe, not for single-symbol timing strategies.

### 11.5 Alpha Bench

`alpha_bench_tool.py` can benchmark Alpha Zoo factors on predefined universes:

- `csi300`;
- `sp500`;
- `btc-usdt`.

Implementation details:

- `csi300` uses Tushare index weights if `TUSHARE_TOKEN` is available, with fallback constituents.
- `sp500` uses current Wikipedia S&P 500 constituents, with a fallback large-cap list. This is explicitly survivorship-biased because it uses current constituents for historical tests.
- `btc-usdt` is recognized, but cross-sectional IC requires at least two instruments. A single BTC column cannot support cross-sectional IC, so the tool returns a clear unsupported/single-asset result.
- Results are rendered into CSP-safe HTML reports under `~/.vibe-trading/reports/alpha_bench_<timestamp>.html`.

### 11.6 Strict/random-control benchmarking

`bench_runner_strict.py` adds stricter diagnostics:

- random row-shuffled controls;
- paired comparison between alpha IC and random IC;
- optional out-of-sample splits;
- categorization of alpha status such as confirmed/weak/dead depending on metrics.

This is valuable for avoiding the trap of treating any positive IC as meaningful.

### 11.7 Alpha comparison

The compare runner/tool performs head-to-head alpha comparisons using common data and metrics. This is useful for pruning redundant factors or choosing between formula variants.

---

## 12. Shadow Account system

The Shadow Account subsystem converts real trade journals into an interpretable counterfactual strategy. It has four major stages.

### 12.1 Extraction

Tool: `extract_shadow_strategy`.

Inputs:

- trade journal path;
- optional `min_support`, default 3;
- optional `max_rules`, default 5.

Pipeline:

1. parse broker/trade journal records;
2. FIFO-pair BUY/SELL round trips;
3. filter profitable round trips;
4. engineer features;
5. cluster profitable trades with KMeans, auto-selecting roughly 2–5 clusters;
6. train shallow decision trees per cluster;
7. extract human-readable path rules;
8. produce immutable `ShadowRule` objects inside a `ShadowProfile`.

Journal-derived features always work offline:

- holding days;
- PnL percentage;
- entry hour/weekday;
- market.

Price-derived features are best effort and point-in-time:

- entry RSI-like features;
- prior 5-day return;
- price/momentum context.

If price fetches fail, the extractor degrades gracefully rather than fabricating data. It requires at least five profitable complete round trips to build a meaningful profile.

Outputs:

- `shadow_id`;
- profile text;
- source-market summary;
- profitable/total round-trip counts;
- typical holding days;
- rule preview;
- persisted profile under `~/.vibe-trading/shadow_accounts/`.

### 12.2 Code generation

The codegen module renders a normal `SignalEngine` from a Jinja template and validates it with `ast.parse` plus structural checks. It also renders a `config.json` and writes a backtest run directory.

This is important: Shadow Account backtests reuse the standard backtest machinery. They are not a separate simulator.

### 12.3 Shadow backtest

Tool: `run_shadow_backtest`.

The backtester:

- loads a stored shadow profile;
- selects representative symbols for requested markets, with liquid fallback baskets;
- renders a run directory under `~/.vibe-trading/shadow_runs/<shadow_id>`;
- invokes the same `backtest_tool.run_backtest` path;
- parses artifacts/metrics/equity;
- computes combined and per-market summaries;
- compares shadow PnL to real journal PnL if the journal is supplied;
- computes arithmetic attribution buckets.

Attribution fields include:

- missed signals PnL;
- noise trades PnL;
- early-exit PnL;
- late-exit PnL;
- overtrading PnL;
- counterfactual trade count.

These are arithmetic diagnostics, not causal proofs.

### 12.4 Shadow reports

Tool: `render_shadow_report`.

The reporter builds an HTML/PDF report from:

- `ShadowProfile`;
- `ShadowBacktestResult`;
- optional today’s signals.

It uses Jinja2 and WeasyPrint, with matplotlib charts where available. If chart/PDF rendering fails, it degrades to HTML-only rather than failing the entire workflow.

### 12.5 Shadow signal scanner

Tool: `scan_shadow_signals`.

The scanner evaluates stored shadow rules against recent OHLCV bars. It is deterministic and explicitly does not fabricate matches when data is absent. It supports features such as:

- momentum;
- price above moving average;
- volume ratio;
- RSI-like entry features.

This is useful as a research assistant for “what would my extracted strategy look at today?”, not as an autonomous trading signal service.

---

## 13. Tests the codebase can run

### 13.1 CI test command

The repository CI uses Python 3.11 and runs:

```bash
pip install -e ".[dev]"
pytest --ignore=agent/tests/e2e_backtest \
       --ignore=agent/tests/test_e2e_harness_v2.py \
       --cov=agent --cov-report=term-missing --cov-report=xml \
       --tb=short -q
```

It also runs syntax checks for key agent/backtest files and frontend build/tests.

### 13.2 Test suite coverage by category

Static classification of the 223 test files:

| Category | Approx. files | Examples of covered areas |
|---|---:|---|
| Tools | 29 | Market-data, backtest, factor analysis, alpha zoo/bench/compare, financial statements, filings, news/profile, sector/fund-flow/margin/northbound tools, file/doc/web tool security. |
| Data loaders/providers | 24 | Tushare, AkShare, BaoStock, Tencent, MootDX, Eastmoney, Yahoo/yfinance, Stooq, Sina, OKX, CCXT, key-gated providers, local loader, routing. |
| API/runtime/security/session | 23 | API routes, protected paths, sessions, auth/OAuth, root guards, frontend-related runtime behavior. |
| Swarm/multi-agent | 21 | DAG gating, grounding, presets, status hydration, worker reports, retry, output contracts. |
| Live connectors/safety | 18 | Advisory mode, mandates, order guards, kill switch, IBKR, Trading 212, connector defaults. |
| Agent/LLM/memory/goals | 18 | Provider behavior, memory, goals, context attribution. |
| Backtest/validation/engines | 14 | China A, global equity, crypto, futures, forex, metrics, validation CLI, run card, engine robustness. |
| CLI | 14 | CLI session, command routing, output behavior. |
| Factors/Alpha Zoo | 11 | Alpha samples, registry, purity/lookahead, strict bench, compare. |
| Shadow Account / journal | 4 | Journal parsing, extraction, backtest/reporting support. |
| Other | 47 | Autopilot, classification, consent, data routing, enforcement, research workflows, miscellaneous safeguards. |

### 13.3 My sandbox collection result

I attempted `PYTHONPATH=agent pytest --collect-only -q agent/tests` in the sandbox. It collected **4,227 tests** before 39 collection errors caused by missing package dependencies such as `yfinance` and other optional/runtime libraries. This does not indicate test failure of the repository; it indicates the uploaded code was inspected without installing its full dependency set in this environment.

### 13.4 What the tests imply

The test suite is broad and unusually security-aware for a research agent codebase. It specifically tests:

- loader availability and fallback behavior;
- provider-specific symbol/date normalization;
- strategy-runner safety constraints;
- path sandboxing;
- tool output contracts;
- market engine rules;
- validation logic;
- factor purity and lookahead prevention;
- alpha registry health;
- connector default-deny/read-only safety concepts;
- swarm/autopilot gating.

For future development, new strategy/research modules should add tests near the relevant subsystem rather than only relying on end-to-end backtests.

---

## 14. What Vibe-Trading is best set up to do

### 14.1 Best-fit research tasks

Vibe-Trading is strongest for:

1. **OHLCV-based systematic strategies**  
   Trend/momentum, moving-average systems, mean reversion, breakout, volatility filters, portfolio rotation, pairs/ranking, factor timing.

2. **Cross-sectional factor research**  
   Alpha Zoo IC testing, quantile portfolio analysis, random-control benchmarking, factor comparison.

3. **Cross-market allocation prototypes**  
   Mixed A-share/US/HK/crypto/futures/forex baskets through `CompositeEngine`.

4. **A-share-aware backtesting**  
   T+1, long-only, lot size, stamp tax, and price-limit simplifications make it more realistic than generic engines.

5. **Crypto/perpetual prototypes**  
   Funding/liquidation hooks and crypto-specific symbol routing are built in.

6. **Strategy ideation with reproducible artifacts**  
   Natural-language agent tooling creates conventional files and CSV/JSON outputs, not opaque hidden state.

7. **Trade-journal behavioral research**  
   Shadow Account can extract simple, interpretable rules from profitable historical behavior and test counterfactual variants.

8. **Research automation workflows**  
   Autopilot/swarm tooling, skills, and MCP tools support repeated research loops.

### 14.2 Less suitable tasks

Vibe-Trading is not best set up for:

- tick-level market making;
- limit-order-book execution modeling;
- exact intraday volume participation/queue simulation;
- broker-grade compliance accounting;
- precise futures roll construction without custom extension;
- historical options-chain backtesting from real option quotes;
- production trading without independent order/risk infrastructure;
- strategies requiring guaranteed institutional data quality from free/default providers;
- causal inference from trade journals.

---

## 15. Strengths

### 15.1 Broad default data-source coverage

The loader registry covers a wide range of markets and providers. The fallback chains are practical: they prioritize no-key public sources, then key-gated or optional providers, and provide local data bridging.

### 15.2 Clean strategy interface

The `SignalEngine.generate(data_map)` contract is simple, research-friendly, and compatible with manually written code and generated code. Most systematic strategies can be represented as target-weight series.

### 15.3 Multi-market execution engines

The engines encode meaningful differences across A-shares, global equities, crypto, futures, forex, and mixed portfolios. That is a major advantage over one-size-fits-all backtest examples.

### 15.4 Reproducible artifacts

Each backtest produces CSVs plus run-card JSON/Markdown with hashes. This is useful for research provenance and comparing strategy revisions.

### 15.5 Validation included

Monte Carlo, bootstrap, and walk-forward validation are integrated into the backtest output path, making robustness checks easier to standardize.

### 15.6 Large Alpha Zoo

A scanned load of 456 alphas across GTJA191, Qlib158, Alpha101, and academic factors provides a strong starting point for factor research and multifactor strategy development.

### 15.7 Safety-conscious tooling

The codebase includes path guards, AST checks for strategy imports, run-root restrictions, tool security tests, default-deny connector concepts, and many focused tests.

### 15.8 Shadow Account is differentiated

The trade-journal-to-strategy pipeline is unusual and useful. It bridges discretionary trading records and systematic rule extraction in a way that can produce testable artifacts.

---

## 16. Limitations and technical caveats

### 16.1 Data quality and provider stability

Many default sources are public/free/unofficial endpoints. They can:

- throttle;
- change response formats;
- block IPs;
- omit adjusted prices;
- have symbol quirks;
- differ in corporate-action handling;
- return sparse or delayed data.

For serious research, validate critical results across more than one provider or use `local` with curated data.

### 16.2 Provider coverage is uneven

Some providers support only daily data in the implementation. Some support only one market. Tushare-specific extras/fundamentals require `TUSHARE_TOKEN`. Alpha Vantage/Finnhub/Tiingo/FMP require keys and are daily-only in the scanned loaders.

### 16.3 Backtest execution is bar-level and simplified

The base engine models target rebalancing at bar open after signal shift. It does not simulate:

- tick path inside a bar;
- limit/stop order queues;
- partial fills based on volume;
- bid/ask spread dynamics beyond simple slippage;
- exchange halts beyond data gaps/price-limit checks;
- exact broker rejects.

### 16.4 Engine-routing edge case with explicit sources

Named global-equity public sources such as `yahoo`, `stooq`, `sina`, and `eastmoney` are valid loaders, but the runner’s engine selection only explicitly maps `yfinance` to `GlobalEquityEngine`; otherwise the fallback is `CryptoEngine`. Use `source: "auto"` or `source: "yfinance"` for US/HK equity backtests unless you verify the resulting engine behavior.

### 16.5 Annualization assumptions need review

Annualization tables explicitly handle common sources and intervals, but not every valid provider/source combination. If comparing strategies across providers/intervals, verify `bars_per_year` assumptions.

### 16.6 Strategy safety is not a complete sandbox

The AST validator prevents import-time side effects but does not make arbitrary generated code safe. `generate()` method bodies still execute. Treat strategy files as code.

### 16.7 Alpha Bench has known biases

- S&P 500 benchmark uses current constituents and is survivorship-biased.
- `btc-usdt` is single-asset and cannot support cross-sectional IC.
- CSI 300 quality improves with a Tushare token; fallbacks may be less exact.
- Factor IC is not the same as executable portfolio performance.

### 16.8 Shadow Account requires enough clean journal data

The extractor needs complete buy/sell round trips and at least five profitable examples. Sparse, messy, or unrepresentative journals will produce weak rules. Attribution is diagnostic, not causal.

### 16.9 Options engine is theoretical

It prices options using Black-Scholes and historical-volatility-derived IV estimates. This is useful for concept testing but not equivalent to backtesting historical listed options using real option-chain quotes, bid/ask spreads, expiries, and liquidity.

### 16.10 Local-file data bridge is powerful but schema-dependent

`local` can cover every market, but only if the user supplies properly normalized CSV/Parquet/DuckDB sources. It will not silently rescue a misconfigured local source by fetching remote data.

---

## 17. Recommended usage patterns for future research

### 17.1 Default strategy research template

Use this unless a strategy has special needs:

```json
{
  "source": "auto",
  "codes": ["AAPL.US", "MSFT.US", "NVDA.US"],
  "start_date": "2018-01-01",
  "end_date": "2025-12-31",
  "interval": "1D",
  "engine": "daily",
  "initial_cash": 1000000,
  "commission": 0.001,
  "benchmark": "SPY.US",
  "optimizer": null,
  "optimizer_params": {},
  "validation": {
    "monte_carlo": {"n_simulations": 1000},
    "bootstrap": {"n_bootstrap": 1000, "confidence": 0.95},
    "walk_forward": {"n_windows": 5}
  }
}
```

Recommended workflow:

1. inspect data coverage with `get_market_data`;
2. create `config.json` and `SignalEngine`;
3. run a short sanity backtest;
4. inspect `ohlcv`, `positions`, `trades`, and `equity` CSVs;
5. run longer backtest;
6. enable validation;
7. compare against explicit benchmark;
8. rerun using an alternate provider or `local` data for important results;
9. freeze parameters before out-of-sample testing.

### 17.2 A-share strategy template

Use:

```json
{
  "source": "auto",
  "codes": ["000001.SZ", "600519.SH"],
  "start_date": "2018-01-01",
  "end_date": "2025-12-31",
  "interval": "1D",
  "engine": "daily"
}
```

Notes:

- Auto usually begins with Tencent/MootDX/Eastmoney before Tushare.
- Use `TUSHARE_TOKEN` when you need Tushare daily_basic or fundamentals.
- Remember T+1, long-only, lot size, stamp-tax, and price-limit rules are modeled.

### 17.3 US/HK equity strategy template

Use `source: "auto"` or `source: "yfinance"`:

```json
{
  "source": "auto",
  "codes": ["AAPL.US", "MSFT.US", "00700.HK"],
  "start_date": "2019-01-01",
  "end_date": "2025-12-31",
  "interval": "1D",
  "engine": "daily"
}
```

For explicit named sources like `yahoo`, verify engine selection and artifacts carefully.

### 17.4 Crypto strategy template

Use hyphen symbols for OKX style:

```json
{
  "source": "auto",
  "codes": ["BTC-USDT", "ETH-USDT"],
  "start_date": "2021-01-01",
  "end_date": "2025-12-31",
  "interval": "1H",
  "engine": "daily"
}
```

Review crypto-specific config for leverage, margin, liquidation, and funding assumptions.

### 17.5 Factor research workflow

1. Pick alphas via `alpha_zoo_tool` by zoo/theme/universe.
2. Run factor analysis on prepared factor and return CSVs, or use alpha bench for predefined universes.
3. Require enough instruments for cross-sectional IC.
4. Compare to random controls/strict bench.
5. Convert promising factors into executable `SignalEngine` strategies.
6. Backtest with transaction costs and realistic universe construction.

### 17.6 Shadow Account workflow

1. Clean and import journal records.
2. Extract profile with `extract_shadow_strategy`.
3. Review the rules before trusting them.
4. Run shadow backtest across relevant markets.
5. Render the report.
6. Treat scanner output as research prompts, not production orders.

---

## 18. Output glossary

### Backtest CSVs

- **`ohlcv_<code>.csv`** — the data actually used after loader normalization/enrichment. Always inspect this first when results look strange.
- **`positions.csv`** — target weights after signal shift, fill, optimization, and normalization. This is the best file for debugging strategy logic.
- **`trades.csv`** — executed trades after market rules, fees, slippage, and lot sizing. Use this to debug whether signals are executable.
- **`equity.csv`** — realized strategy equity, drawdown, returns, benchmark equity, active return.
- **`metrics.csv`** — scalar summary for quick comparison.
- **`validation.json`** — robustness diagnostics when enabled.
- **`run_card.json/md`** — audit/reproducibility summary.

### Alpha/factor outputs

- **`ic_series.csv`** — daily factor IC values.
- **`ic_summary.json`** — factor-level IC statistics.
- **`group_equity.csv`** — quantile/portfolio group performance.
- **alpha bench HTML report** — summary of alpha performance and ranking.

### Shadow outputs

- **Shadow profile JSON/text** — extracted rule set and metadata.
- **Shadow run artifacts** — standard backtest outputs for generated shadow strategy.
- **Shadow report HTML/PDF** — narrative report with charts and attribution.
- **Scanner matches** — deterministic current-candidate list if recent data supports rule matches.

---

## 19. Concrete extension points

### 19.1 Add a new data provider

Implement a loader class under `agent/backtest/loaders/`:

```python
@register
class MyLoader:
    name = "my_source"
    markets = {"us_equity"}

    def is_available(self) -> bool:
        return True

    def fetch(self, codes, start_date, end_date, interval="1D", fields=None):
        return {code: df}
```

Then update:

- `VALID_SOURCES`;
- `_loader_modules`;
- `FALLBACK_CHAINS` for relevant markets;
- market-data tool enum if user-facing;
- tests for availability, normalization, edge cases, fallback.

### 19.2 Add a new strategy style

For normal target-weight strategies, no engine extension is needed. Write a new `SignalEngine`.

For a fundamentally different execution model, extend `BaseEngine` or add a new engine path:

- implement `can_execute`;
- implement `round_size`;
- implement `calc_commission`;
- implement `apply_slippage`;
- optionally override `on_bar`, PnL, margin, or execution loop;
- update runner engine routing;
- add tests.

### 19.3 Add a new factor

Add a zoo module with literal `__alpha_meta__` and a compute function compatible with the registry. Test:

- metadata loading;
- output shape;
- NaN/inf behavior;
- no lookahead;
- sample computation.

### 19.4 Add a new validation method

Add it to `agent/backtest/validation.py`, include config dispatch in `run_validation`, write JSON-safe outputs, and add tests on synthetic equity/trade data.

---

## 20. Practical “do this / avoid this” checklist

### Do this

- Use `source: "auto"` for first-pass research.
- Inspect `ohlcv_<code>.csv` and `positions.csv` on every new strategy family.
- Set explicit benchmarks for serious comparisons.
- Enable validation after initial strategy sanity checks.
- Use local curated data for high-stakes research.
- Test strategies out-of-sample after parameters are frozen.
- Compare factor results to random controls.
- Add tests when extending loaders, engines, or factor formulas.
- Keep strategy files simple and deterministic.

### Avoid this

- Do not treat free-provider backtests as final truth without verification.
- Do not optimize repeatedly on the same period and then trust validation p-values.
- Do not use single-asset factor IC analysis.
- Do not assume options results reflect real option-chain liquidity.
- Do not rely on explicit `source: "yahoo"`/`stooq` engine behavior without checking artifacts.
- Do not treat Shadow Account attribution as causal proof.
- Do not assume strategy AST checks make arbitrary generated code safe.

---

## 21. Bottom-line assessment

Vibe-Trading is a capable, research-oriented trading-strategy platform whose center of gravity is **agent-assisted systematic research with reproducible backtests**. The core backtest contract is simple enough to develop against directly, while the loader registry, market engines, Alpha Zoo, validation tools, and Shadow Account subsystem give it much broader coverage than a minimal backtesting library.

Its best use is to accelerate hypothesis generation, data inspection, strategy prototyping, factor screening, and comparative research. Its outputs are concrete and auditable: CSV artifacts, JSON metrics, validation files, and run cards. Its limitations are mostly the expected ones for a free-provider, bar-level research stack: data reliability, simplified execution, incomplete market microstructure, model-based options pricing, and overfitting risk.

For future strategy/research development, treat Vibe-Trading as a **fast, extensible research laboratory**. Use it to move from idea → data check → signal implementation → backtest → validation → factor comparison → report. For any result that matters, independently verify data, costs, benchmark choice, universe construction, and execution assumptions before treating the result as investment evidence.

### 21.1 Post-hoc accuracy check, after an extended hands-on research session (added 2026-07-01)

The claims above and throughout this document were checked against direct, repeated hands-on use of the `mcp__vibe-trading__*` MCP tools across a multi-session backtest research arc (`vibe_trading_research_findings.md`, ~43 sections). Honest assessment:

- **Held up exactly as documented**: the `run_dir` + `config.json` + `code/signal_engine.py` contract (§5, §7.1-7.2); `mcp__vibe-trading__backtest`'s interface (just a `run_dir`, returns metrics JSON plus artifact paths inline in a single synchronous call — no polling needed, unlike the swarm tool's async `get_run_result`); the 1-bar signal shift and final `sum(abs(weights)) <= 1.0` normalization (§7.4); engine auto-routing for `source: "auto"` (crypto and US-equity symbols both routed correctly every time); every metrics.csv field name (§9.1); the Monte Carlo/bootstrap/walk-forward validation outputs (§10); and the documented `source`-specific annualization behavior.
- **Found genuinely inaccurate, now corrected**: §8.3's execution-loop description (the "add/reduce" claim did not match any engine's actual code — see the update note at the top of this file and the corrected §8.3 text) and a real edge case in §7.3's safety-validator description (negative-number literals).
- **Not exercised this session, so not independently re-verified**: the Alpha Zoo/factor-analysis tooling (§11), Shadow Account (§12), and options engine (§16.9/§7.6) — this session's work was entirely backtest/loader/engine-focused. Treat those sections' accuracy as resting on the original repository scan only, not on fresh confirmation, until a future session actually exercises them.
- **One practical, non-documentation lesson**: `get_market_data` is accurate but token-heavy even for short (few-month) date ranges — prefer letting the backtest tool fetch data internally (it fetches full frames regardless) rather than pre-checking availability via `get_market_data` unless you specifically need to inspect raw values before committing to a backtest.
- For non-default provider configuration that the MCP tool itself has no parameter for (e.g. `CCXT_EXCHANGE=hyperliquid` to reach a specific exchange), invoking `agent/backtest/runner.py <run_dir>` directly via a scoped shell env var (documented in `CLAUDE.md`) worked exactly as described, repeatedly, with no surprises.
