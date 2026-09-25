"""Public setup contract for session-owned payment comparison arms."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import server
from config import CONFIG
from run_evidence import conditions


@pytest.mark.parametrize("field,bad", [
    ("payment_sequence", "tomorrow"),
    ("payment_care_mode", "guaranteed"),
    ("payment_assistance", "unlimited"),
    ("payment_firm_default_misses", 5),
    ("payment_annual_quote_shift", 0.06),
    ("payment_construction_unit_cost", 0),
])
def test_setup_rejects_unknown_payment_scenarios(field, bad):
    with pytest.raises(ValidationError):
        server.SetupConfig(**{field: bad})


def test_setup_sets_session_config_before_factory_and_keeps_other_session_legacy(monkeypatch):
    original = server.create_large_economy
    factory_seen = []

    def observed_factory(*args, **kwargs):
        factory_seen.append((CONFIG.payment_sequence, CONFIG.payment_care_mode, CONFIG.payment_assistance))
        return original(*args, **kwargs)

    monkeypatch.setattr(server, "create_large_economy", observed_factory)
    first = server.SimulationManager(session_id="scenario-first")
    second = server.SimulationManager(session_id="scenario-second")
    first.initialize({"num_households": 3, "num_firms": 1, "seed": 7,
                      "payment_sequence": "income_first", "payment_care_mode": "covered",
                      "payment_assistance": "care", "payment_lease_term_ticks": 26,
                      "payment_firm_default_misses": 12})
    second.initialize({"num_households": 3, "num_firms": 1, "seed": 7})
    assert factory_seen == [("income_first", "covered", "care"), ("legacy", "patient_pay", "reserve")]
    assert first.economy.payment_sequence == "income_first"
    assert second.economy.payment_sequence == "legacy"
    assert first.config.payment_assistance == "care"
    assert first.config.payment_lease_term_ticks == 26
    assert first.config.payment_firm_default_misses == 12
    assert second.config.payment_assistance == "reserve"
    assert CONFIG.payment_sequence == "legacy"
    execution = conditions(first.economy)["execution"]
    assert (execution["payment_sequence"], execution["payment_care_mode"], execution["payment_assistance"]) == (
        "income_first", "covered", "care"
    )
    assert execution["payment_parameters"]["payment_lease_term_ticks"] == 26
    assert execution["payment_parameters"]["payment_firm_default_misses"] == 12


def test_runtime_update_rejects_scenario_switch_without_mutation():
    manager = server.SimulationManager(session_id="scenario-lock")
    manager.initialize({"num_households": 3, "num_firms": 1, "payment_sequence": "income_first"})
    with pytest.raises(ValueError, match="fixed at SETUP"):
        asyncio.run(manager.update_config({"payment_sequence": "legacy"}))
    assert manager.economy.payment_sequence == "income_first"
    assert manager.pending_config_updates == []


def test_websocket_reports_selected_setup_and_recovers_from_rejected_config(monkeypatch):
    registry = server.SessionRegistry(max_sessions=1)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        assert session["type"] == "SESSION"
        ws.send_json({"command": "SETUP", "config": {
            "num_households": 3, "num_firms": 1, "seed": 3,
            "payment_sequence": "income_late", "payment_care_mode": "patient_pay",
            "payment_assistance": "rent",
        }})
        setup = ws.receive_json()
        assert setup["type"] == "SETUP_COMPLETE"
        assert setup["config"]["payment_sequence"] == "income_late"
        assert setup["config"]["payment_assistance"] == "rent"
        manager = registry.get(session["sessionId"])
        assert manager.config.payment_sequence == "income_late"
        ws.send_json({"command": "CONFIG", "config": {"payment_assistance": "care"}})
        assert "fixed at SETUP" in ws.receive_json()["error"]
        ws.send_json({"command": "STOP"})
        assert ws.receive_json()["type"] == "STOPPED"
