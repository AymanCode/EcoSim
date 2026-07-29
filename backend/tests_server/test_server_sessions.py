import asyncio
import importlib
import random
import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server
from config import CONFIG, clone_config, use_config


def test_websocket_connections_receive_distinct_session_managers(monkeypatch):
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)

    with client.websocket_connect("/ws") as first_ws:
        first_session = first_ws.receive_json()
        with client.websocket_connect("/ws") as second_ws:
            second_session = second_ws.receive_json()

            assert first_session["type"] == "SESSION"
            assert second_session["type"] == "SESSION"
            assert first_session["sessionId"] != second_session["sessionId"]
            assert registry.get(first_session["sessionId"]) is not registry.get(second_session["sessionId"])


def test_session_registry_creates_isolated_managers_and_releases_them():
    registry = server.SessionRegistry(max_sessions=2)

    first_id, first_manager = registry.open_session()
    second_id, second_manager = registry.open_session()

    assert first_id != second_id
    assert first_manager is not second_manager

    first_manager.tick = 11
    second_manager.tick = 3

    assert registry.get(first_id).tick == 11
    assert registry.get(second_id).tick == 3

    registry.close_session(first_id)

    assert registry.get(first_id) is None
    assert registry.get(second_id) is second_manager


def test_session_managers_own_independent_config_and_random_streams():
    first = server.SimulationManager(session_id="first")
    second = server.SimulationManager(session_id="second")

    first.config.random_seed = 11
    first.config.llm.enable_llm_government = True
    second.config.random_seed = 22
    second.config.llm.enable_llm_government = False
    first._reset_random_state(11)
    second._reset_random_state(22)

    with first._random_scope():
        first_draw_a = (random.random(), float(np.random.random()))
    with second._random_scope():
        second_draw = (random.random(), float(np.random.random()))
    with first._random_scope():
        first_draw_b = (random.random(), float(np.random.random()))

    expected_python = random.Random(11)
    expected_numpy = np.random.RandomState(11)
    assert first.config is not second.config
    assert first.config.random_seed == 11
    assert second.config.random_seed == 22
    assert first.config.llm.enable_llm_government is True
    assert second.config.llm.enable_llm_government is False
    assert first_draw_a == (expected_python.random(), float(expected_numpy.random()))
    assert first_draw_b == (expected_python.random(), float(expected_numpy.random()))
    assert second_draw != first_draw_a


def test_config_proxy_routes_legacy_dict_updates_to_the_active_session():
    session_config = clone_config()
    default_seed = CONFIG.random_seed

    with use_config(session_config):
        CONFIG.__dict__.update({"random_seed": 9876})
        assert CONFIG.random_seed == 9876

    assert session_config.random_seed == 9876
    assert CONFIG.random_seed == default_seed


def test_package_and_legacy_config_imports_share_one_proxy():
    package_config = importlib.import_module("backend.config")

    assert package_config.CONFIG is CONFIG


def test_initializing_a_second_session_does_not_reconfigure_the_first():
    first = server.SimulationManager(session_id="first")
    second = server.SimulationManager(session_id="second")
    default_seed = CONFIG.random_seed

    first.initialize(
        {
            "num_households": 12,
            "num_firms": 1,
            "seed": 11,
            "enable_llm_government": True,
        }
    )
    second.initialize(
        {
            "num_households": 12,
            "num_firms": 1,
            "seed": 22,
            "enable_llm_government": False,
        }
    )

    assert first.config.random_seed == 11
    assert first.config.llm.enable_llm_government is True
    assert second.config.random_seed == 22
    assert second.config.llm.enable_llm_government is False
    assert CONFIG.random_seed == default_seed


def test_start_background_loop_reuses_active_task_instead_of_spawning_duplicate(monkeypatch):
    async def run_case():
        manager = server.SimulationManager()
        manager.economy = object()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def fake_run_loop():
            entered.set()
            await release.wait()

        monkeypatch.setattr(manager, "run_loop", fake_run_loop)

        first_started = manager.start_background_loop()
        await asyncio.wait_for(entered.wait(), timeout=1.0)
        first_task = manager.run_task
        manager.is_running = False

        second_started = manager.start_background_loop()

        assert first_started is True
        assert second_started is False
        assert manager.run_task is first_task
        assert manager.is_running is True

        release.set()
        await asyncio.wait_for(first_task, timeout=1.0)

    asyncio.run(run_case())
