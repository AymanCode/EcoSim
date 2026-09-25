import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from experiments import HOUSEHOLD_BUDGET, MAX_ARMS, ExperimentError, ExperimentRegistry  # noqa: E402

WORLD = '{"seed": 7}'


def _reserve(registry, **overrides):
    params = dict(experiment_id="exp-1", arm_label="Town A", arm_count=2, households=1_000, session_id="s1",
                  owner="owner-1", world_key=WORLD)
    params.update(overrides)
    return registry.reserve(**params)


def test_per_arm_cap_splits_the_budget_evenly():
    registry = ExperimentRegistry()
    assert registry.per_arm_cap(1) == HOUSEHOLD_BUDGET
    assert registry.per_arm_cap(2) == 5_000
    assert registry.per_arm_cap(3) == 3_333
    assert registry.per_arm_cap(4) == 2_500


def test_single_arm_may_take_the_whole_budget():
    registry = ExperimentRegistry()
    reservation = _reserve(registry, arm_count=1, households=HOUSEHOLD_BUDGET)
    assert reservation.households == HOUSEHOLD_BUDGET
    assert registry.describe("exp-1")["households_reserved"] == HOUSEHOLD_BUDGET


def test_arm_over_cap_is_rejected_and_nothing_is_reserved():
    registry = ExperimentRegistry()
    with pytest.raises(ExperimentError, match="cap"):
        _reserve(registry, households=5_001)
    assert registry.describe("exp-1") is None


def test_duplicate_label_full_experiment_and_arm_count_mismatch_are_rejected():
    registry = ExperimentRegistry()
    _reserve(registry)
    with pytest.raises(ExperimentError, match="label"):
        _reserve(registry, session_id="s2")
    with pytest.raises(ExperimentError, match="arm count"):
        _reserve(registry, arm_label="Town B", arm_count=3, session_id="s2")
    _reserve(registry, arm_label="Town B", session_id="s2")
    with pytest.raises(ExperimentError, match="full"):
        _reserve(registry, arm_label="Town C", session_id="s3")
    with pytest.raises(ExperimentError, match="arms"):
        _reserve(registry, experiment_id="exp-2", arm_count=MAX_ARMS + 1, households=10, session_id="s9")


def test_second_owner_and_different_world_are_rejected():
    registry = ExperimentRegistry()
    _reserve(registry)
    with pytest.raises(ExperimentError, match="owner"):
        _reserve(registry, arm_label="Town B", session_id="s2", owner="someone-else")
    with pytest.raises(ExperimentError, match="world"):
        _reserve(registry, arm_label="Town B", session_id="s2", world_key='{"seed": 8}')
    assert registry.describe("exp-1")["arms"] == {"Town A": 1_000}


def test_release_frees_the_arm_and_removes_empty_experiments():
    registry = ExperimentRegistry()
    _reserve(registry)
    registry.release("s1")
    assert registry.describe("exp-1") is None
    registry.release("s1")  # idempotent


def _connect(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=4)
    experiments = ExperimentRegistry()
    monkeypatch.setattr(server, "session_registry", registry)
    monkeypatch.setattr(server, "experiment_registry", experiments)
    return TestClient(server.app), registry, experiments


def _until(ws, predicate, limit=200):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError(f"no matching message within {limit} messages")


def _setup(ws, **config):
    ws.send_json({"command": "SETUP", "config": config})
    return _until(ws, lambda msg: msg.get("type") == "SETUP_COMPLETE" or "error" in msg)


EXP = {"num_households": 30, "num_firms": 1, "seed": 7, "experiment_id": "exp-ws", "arm_label": "Town A",
       "arm_count": 2, "experiment_owner": "browser-1"}


def test_setup_reserves_echoes_and_a_failed_setup_leaves_nothing_runnable(monkeypatch):
    client, registry, experiments = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        reply = _setup(ws, **EXP)
        assert reply["type"] == "SETUP_COMPLETE", reply
        assert reply["config"]["experiment"] == {"id": "exp-ws", "armLabel": "Town A", "armCount": 2, "householdCap": 5_000}
        assert experiments.describe("exp-ws")["households_reserved"] == 30

        error = _setup(ws, **{**EXP, "num_households": 6_000})
        assert "error" in error and "cap" in error["error"]
        assert experiments.describe("exp-ws") is None
        manager = registry.get(session["sessionId"])
        assert manager.economy is None  # nothing runnable is left behind
        assert manager.experiment_id is None

        recovered = _setup(ws, **EXP)
        assert recovered["type"] == "SETUP_COMPLETE", recovered
        assert experiments.describe("exp-ws")["households_reserved"] == 30
        assert manager.economy is not None


def test_invalid_replacement_setup_releases_the_existing_reservation(monkeypatch):
    client, registry, experiments = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        assert _setup(ws, **EXP)["type"] == "SETUP_COMPLETE"
        assert experiments.describe("exp-ws")["households_reserved"] == 30

        error = _setup(ws, **{**EXP, "arm_count": 5})
        assert "error" in error
        assert experiments.describe("exp-ws") is None
        manager = registry.get(session["sessionId"])
        assert manager.economy is None
        assert manager.experiment_id is None


def test_failed_setup_closes_the_previous_warehouse_run_while_its_economy_exists(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    monkeypatch.setattr(server, "experiment_registry", ExperimentRegistry())
    manager = server.SimulationManager(session_id="warehouse-order")
    manager.initialize(dict(EXP))
    calls = []
    monkeypatch.setattr(manager, "_close_warehouse_run", lambda status: calls.append((status, manager.economy is not None)))

    with pytest.raises(ExperimentError, match="cap"):
        manager.initialize({**EXP, "num_households": 6_000})

    assert calls == [("stopped", True)]
    assert manager.economy is None
    assert manager.experiment_registry.describe("exp-ws") is None


def test_disconnect_releases_a_live_reservation(monkeypatch):
    client, _, experiments = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert _setup(ws, **EXP)["type"] == "SETUP_COMPLETE"
        assert experiments.describe("exp-ws")["households_reserved"] == 30
    assert experiments.describe("exp-ws") is None


def test_second_arm_must_share_the_world(monkeypatch):
    client, _, _ = _connect(monkeypatch)
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        first.receive_json()
        second.receive_json()
        assert _setup(first, **EXP)["type"] == "SETUP_COMPLETE"
        error = _setup(second, **{**EXP, "arm_label": "Town B", "seed": 8})
        assert "error" in error and "world" in error["error"]
        ok = _setup(second, **{**EXP, "arm_label": "Town B"})
        assert ok["type"] == "SETUP_COMPLETE"


def test_setup_without_experiment_fields_still_works(monkeypatch):
    client, _, _ = _connect(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        reply = _setup(ws, num_households=30, num_firms=1, seed=7)
        assert reply["type"] == "SETUP_COMPLETE"
        assert reply["config"]["experiment"] is None
