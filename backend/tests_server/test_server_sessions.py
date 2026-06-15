import asyncio
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server


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
