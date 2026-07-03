"""CPD-1 Phase A acceptance gate: one full simulated day runs end-to-end --
signal -> tickets -> confirm -> ledger -> tracking report -- entirely on
fixture data (no network), per vibe_trading_deployment_plan_CPD1.md's Phase A
acceptance criteria.
"""

from __future__ import annotations

import sys

import pytest

from deployment import confirm, ledger, order_tickets, risk_rules, tracking_report, venue_specs
from deployment import tickets as tickets_mod
from deployment.tickets import find_ticket, read_tickets


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "live_ledger.csv")
    monkeypatch.setattr(ledger, "EQUITY_PATH", tmp_path / "equity_snapshots.csv")
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
            "M1": {
                "engine_sha256": "cafebabe",
                "effective_as_of": "2026-07-03",
                "stale": False,
                "targets": {
                    "SPY.US": {"prev_direction": 0, "direction": 1, "target_weight": 0.4, "flipped": True},
                    "GLD.US": {"prev_direction": 0, "direction": 0, "target_weight": 0.0, "flipped": False},
                },
            },
        },
    }


def test_simulated_day_end_to_end(monkeypatch, capsys, tmp_path):
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
    tix = order_tickets.build_tickets(state)
    assert len(tix) == 2  # BTC long open, SPY long open (SOL/GLD stay flat -> no ticket)
    tickets_mod.write_tickets(state["as_of_date"], tix)

    # 3. Confirm each ticket via the real CLI entry point.
    for t in tix:
        monkeypatch.setattr(
            sys, "argv",
            ["confirm.py", t.ticket_id, "--px", "1.0", "--qty", str(t.qty), "--fee", "0.1"],
        )
        confirm.main()
        out = capsys.readouterr().out
        assert "recorded LIVE fill" in out

    # 4. Ledger reflects both confirmed fills.
    ledger_df = ledger.read_ledger()
    assert len(ledger_df) == 2
    assert set(ledger_df["status"]) == {"confirmed"}
    assert ledger.current_position("BTC-USDT", "binance_spot") == pytest.approx(tix[0].qty)

    # 5. Risk checks run without crashing against the now-populated ledger.
    fired = risk_rules.run_risk_checks(state, notifier=risk_rules.alerts.NullNotifier())
    assert isinstance(fired, list)  # reconciliation reminder etc. may or may not fire; must not crash

    # 6. Tracking report runs against the fixture ledger + a fabricated paper equity curve.
    run_dir = tmp_path / "agent" / "runs" / "deploy_ZA4_20260703"
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "artifacts" / "equity.csv").write_text(
        "timestamp,equity\n2026-07-02,1000.0\n2026-07-03,1010.0\n"
    )
    out = tracking_report.build_report(
        since_date="2026-07-02", mark_prices={("BTC-USDT", "binance_spot"): 66000.0},
    )
    assert "divergence_pct" in out
    assert out["live_return_pct"] is not None
