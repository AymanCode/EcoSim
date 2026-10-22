"""Dashboard fiscal balance excludes public-debt financing (G1).

The frame's ``govProfit`` was the change in treasury cash, so a bank loan
that covered a deficit showed up as revenue. It is now the change in the net
position (cash minus public debt). The town receives that same net position
as ``curated.townHallCash``; no classic-dashboard financing fields are added.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402


def _manager(cash, debt=0.0, borrowed=0.0, repaid=0.0):
    manager = server.SimulationManager(session_id="fiscal-balance")
    gov = SimpleNamespace(cash_balance=cash, public_debt=debt,
                          last_tick_debt_borrowed=borrowed, last_tick_debt_repaid=repaid)
    manager.economy = SimpleNamespace(government=gov)
    return manager, gov


def test_borrowing_is_not_revenue():
    manager, gov = _manager(cash=0.0, debt=100_000.0)
    manager._treasury_flow_this_tick()
    # A week with a $5,243 deficit that the bank lends: cash ends where it began.
    gov.public_debt += 5_243.0
    gov.last_tick_debt_borrowed = 5_243.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(-5_243.0)
    assert flow["debt"] == pytest.approx(105_243.0)


def test_repayment_is_not_spending():
    manager, gov = _manager(cash=60_000.0, debt=100_000.0)
    manager._treasury_flow_this_tick()
    # A $2,000 surplus week; $50,000 of cash repays debt.
    gov.cash_balance += 2_000.0 - 50_000.0
    gov.public_debt -= 50_000.0
    gov.last_tick_debt_borrowed, gov.last_tick_debt_repaid = 0.0, 50_000.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(2_000.0)


def test_without_debt_it_is_the_change_in_cash_as_before():
    manager, gov = _manager(cash=10_000.0)
    manager._treasury_flow_this_tick()
    gov.cash_balance = -4_000.0
    flow = manager._treasury_flow_this_tick()
    assert flow["fiscal_balance"] == pytest.approx(-14_000.0)
    assert flow["debt"] == pytest.approx(4_000.0)  # unlent negative cash still counts as debt


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _metric_frames(ws):
    frames = []

    def watch(msg):
        if "metrics" in msg:
            frames.append(msg)
        return msg.get("type") == "HORIZON_REACHED"

    until(ws, watch, seconds=120)
    return frames


def test_default_levers_omit_financing_keys_for_30_ticks(monkeypatch):
    """Flag on, dashboard levers untouched: neither financing key is in any frame."""
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, {
            "num_households": 40,
            "num_firms": 2,
            "seed": 42,
            "horizon_ticks": 30,
            "payment_sequence": "legacy",
        }).get("type") == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        manager.config.government.public_debt_enabled = True
        ws.send_json({"command": "START"})
        frames = _metric_frames(ws)
    assert len(frames) == 30
    for frame in frames:
        assert "govBorrowed" not in frame["metrics"]
        assert "govRepaid" not in frame["metrics"]
    assert manager.economy.government.public_debt == 0.0


@pytest.mark.parametrize("debt_on", [False, True])
def test_town_lean_frames_show_net_position_without_classic_financing_fields(monkeypatch, debt_on):
    """An actual bank-financed legacy deficit must still show as money owed in town."""
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, {
            "num_households": 40,
            "num_firms": 2,
            "seed": 44,
            "horizon_ticks": 12,
            "frame_profile": "lean",
            "payment_sequence": "legacy",
        }).get("type") == "SETUP_COMPLETE"
        manager = registry.get(session["sessionId"])
        manager.config.government.public_debt_enabled = debt_on
        gov = manager.economy.government
        gov.cash_balance = 0.0
        gov.set_lever("benefit_level", "crisis")
        gov.set_lever("infrastructure_spending", "high")
        gov.set_lever("technology_spending", "high")
        gov.set_lever("social_spending", "high")
        ws.send_json({"command": "START"})
        frames = _metric_frames(ws)
    assert len(frames) == 12
    assert all("govBorrowed" not in frame["metrics"] and "govRepaid" not in frame["metrics"] for frame in frames)
    assert any(frame["curated"]["townHallCash"] < 0.0 for frame in frames)
    assert frames[-1]["curated"]["townHallCash"] == pytest.approx(gov.cash_balance - gov.public_debt)
    if debt_on:
        assert gov.public_debt > 0.0
        assert gov.cash_balance >= 0.0  # coins alone would hide the debt
    else:
        assert gov.public_debt == 0.0
        assert frames[-1]["curated"]["townHallCash"] == gov.cash_balance  # main's formula
