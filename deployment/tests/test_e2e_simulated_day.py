"""CPD-1 Phase A acceptance gate: one full simulated PAPER day runs
end-to-end -- signal -> tickets -> confirm -> ledger -> marking -> risk ->
tracking report -- entirely on fixture data (no network), per
vibe_trading_deployment_plan_CPD1.md's Phase A acceptance criteria, updated
2026-07-03 for the hardened flow (cpd1_lf profile, explicit paper mode,
marked equity, anchored tracking report).
"""

from __future__ import annotations

import sys

import pytest

from deployment import (
    confirm, ledger, marking, order_tickets, profiles, risk_rules,
    tracking_report, venue_specs,
)
from deployment import tickets as tickets_mod


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
    monkeypatch.setattr(marking, "MARKS_PATH", tmp_path / "equity_marks.csv")
    monkeypatch.setattr(tickets_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(tracking_report, "AGENT_DIR", tmp_path / "agent")


def _signal_state() -> dict:
    return {
        "as_of_date": "2026-07-03",
        "generated_at": "2026-07-03T00:00:00+00:00",
        "strategies": {
            "ZA4": {
                "engine_sha256": "deadbeef",
                "effective_as_of": "2026-07-03",
                "stale": False,
                "targets": {
                    "BTC-USDT": {"prev_direction": 0, "direction": 1, "target_weight": 0.3, "flipped": True},
                    "SOL-USDT": {"prev_direction": 0, "direction": 0, "target_weight": 0.0, "flipped": False},
                },
            },
            "M1LF": {
                "engine_sha256": "cafebabe",
                "effective_as_of": "2026-07-03",
                "stale": False,
                "targets": {
                    "SPY.US": {"prev_direction": 0, "direction": 1, "target_weight": 0.4, "flipped": True},
                    "GLD.US": {"prev_direction": 0, "direction": 0, "target_weight": 0.0, "flipped": False},
                },
            },
            # Shadow strategy present in the state -- must flow through
            # without producing tickets.
            "ZD2": {
                "engine_sha256": "beefcafe",
                "effective_as_of": "2026-07-03",
                "stale": False,
                "targets": {
                    "BTC-USDT": {"prev_direction": 0, "direction": -1, "target_weight": -0.3, "flipped": True},
                },
            },
        },
    }


def test_simulated_paper_day_end_to_end(monkeypatch, capsys, tmp_path):
    profile = profiles.PROFILES["cpd1_lf"]

    # 1. Seed starting equity so build_tickets has a sleeve base to size against.
    ledger.append_equity_snapshot(date="2026-07-02", venue="binance_spot", symbol_or_cash="cash", balance_usd=750.0)
    ledger.append_equity_snapshot(date="2026-07-02", venue="ibkr_ucits", symbol_or_cash="cash", balance_usd=1750.0)

    # 2. Signal -> tickets (venue_specs network calls mocked with fixture prices/filters;
    # ledger position lookups are real -- the fresh tmp_path ledger starts flat, so no
    # mocking needed there, which also lets step 4 below check the real post-confirm state).
    monkeypatch.setattr(venue_specs, "binance_spot_price", lambda sym: 65000.0)
    monkeypatch.setattr(
        venue_specs, "binance_spot_filters", lambda sym: {"step_size": 0.00001, "min_notional": 5.0},
    )
    monkeypatch.setattr(venue_specs, "macro_reference_price", lambda sym: 700.0)

    state = _signal_state()
    tix = order_tickets.build_tickets(state, profile=profile, paper=True)
    # BTC long open + SPY long open; SOL/GLD stay flat; shadow ZD2 emits nothing.
    assert len(tix) == 2
    assert {t.strategy for t in tix} == {"ZA4", "M1LF"}
    tickets_mod.write_tickets(state["as_of_date"], tix)

    # 3. Confirm each ticket via the real CLI entry point, in PAPER mode.
    for t in tix:
        monkeypatch.setattr(
            sys, "argv",
            ["confirm.py", t.ticket_id, "--paper",
             "--px", str(t.notional_usd / t.qty), "--qty", str(t.qty), "--fee", "0.1"],
        )
        confirm.main()
        out = capsys.readouterr().out
        assert "recorded PAPER fill" in out

    # 4. Ledger reflects both confirmed paper fills; the live book stays empty.
    ledger_df = ledger.read_ledger()
    assert len(ledger_df) == 2
    assert set(ledger_df["status"]) == {"confirmed"}
    assert ledger.current_position("BTC-USDT", "binance_spot", paper=True) == pytest.approx(tix[0].qty)
    assert ledger.current_position("BTC-USDT", "binance_spot", paper=False) == 0.0

    # 5. Mark the sleeves from fixture prices and append the daily risk row.
    positions = ledger.open_positions(paper=True)
    marks = marking.fetch_mark_prices(
        positions, fetch=lambda sym, venue: 66000.0 if sym == "BTC-USDT" else 700.0,
    )
    sleeve_equities = {}
    for sleeve in ("crypto", "macro"):
        valuation = marking.value_sleeve(sleeve, paper=True, mark_prices=marks, anchor_date="2026-07-02")
        sleeve_equities[sleeve] = valuation["equity"]
    marking.append_marks(date="2026-07-03", mode_paper=True, sleeve_equities=sleeve_equities)
    assert len(marking.equity_series(mode_paper=True)) == 1

    # 6. Risk checks (incl. the sleeve-drift tripwire) run against real state.
    fired = risk_rules.run_risk_checks(
        state, notifier=risk_rules.alerts.NullNotifier(), profile=profile,
        sleeve_equities=sleeve_equities, mode_paper=True,
    )
    assert isinstance(fired, list)  # reminders may fire; must not crash

    # 7. Tracking report: fabricated paper curves for BOTH deployed strategies,
    # profile-weighted composite, anchored at the seed snapshot.
    for strategy in ("ZA4", "M1LF"):
        run_dir = tmp_path / "agent" / "runs" / f"deploy_{strategy}_20260703"
        (run_dir / "artifacts").mkdir(parents=True)
        (run_dir / "artifacts" / "equity.csv").write_text(
            "timestamp,equity\n2026-07-02,1000.0\n2026-07-03,1010.0\n"
        )
    out = tracking_report.build_report(
        since_date="2026-07-02",
        mark_prices={("BTC-USDT", "binance_spot"): 66000.0, ("SPY.US", "ibkr_ucits"): 700.0},
        paper=True, profile=profile,
    )
    assert out["divergence_pct"] is not None
    assert out["live_return_pct"] is not None
    assert out["paper_return_pct"] == pytest.approx(1.0)  # both curves +1%, any weighting
