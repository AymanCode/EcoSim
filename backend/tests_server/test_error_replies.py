"""Error replies over the WebSocket: validation text reaches the user, internal faults stay in the log."""

import logging
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402
from experiments import ExperimentError  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}
INTERNAL = "internal server error; details are in the server log"


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def test_client_error_passes_validation_text_and_hides_other_exceptions():
    try:
        server.SetupConfig(num_households=0)
    except ValidationError as exc:
        validation = exc
    assert server.client_error("SETUP failed", validation)["error"].startswith("SETUP failed: ")
    assert "num_households" in server.client_error("SETUP failed", validation)["error"]
    assert server.client_error("SETUP failed", ExperimentError("arm label 'A' is already taken")) == {
        "error": "SETUP failed: arm label 'A' is already taken"
    }
    assert server.client_error("START failed", KeyError("/home/runner/secret")) == {
        "error": f"START failed: {INTERNAL}",
        "code": "internal_error",
    }


def test_unknown_command_lists_valid_commands_in_sorted_order(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        until(ws, lambda m: m.get("type") == "SESSION")
        ws.send_json({"command": "NOPE"})
        reply = until(ws, lambda m: "error" in m)
    expected = sorted(server.VALID_COMMANDS)
    assert reply["validCommands"] == expected
    assert reply["error"] == f"Unknown command: NOPE. Valid: {', '.join(expected)}"


def test_setup_validation_failure_keeps_its_message(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        until(ws, lambda m: m.get("type") == "SESSION")
        reply = setup(ws, {**SMALL, "num_households": 0})
    assert reply["error"].startswith("SETUP failed: ") and "num_households" in reply["error"]
    assert "code" not in reply


def test_setup_internal_fault_is_logged_but_not_sent(monkeypatch, caplog):
    def broken_factory(*args, **kwargs):
        raise RuntimeError("cannot open /srv/private/ecosim.db")

    monkeypatch.setattr(server, "create_large_economy", broken_factory)
    client, _ = _client(monkeypatch)
    with caplog.at_level(logging.ERROR, logger=server.logger.name):
        with client.websocket_connect("/ws") as ws:
            until(ws, lambda m: m.get("type") == "SESSION")
            reply = setup(ws, SMALL)
    assert reply == {"error": f"SETUP failed: {INTERNAL}", "code": "internal_error"}
    logged = [r for r in caplog.records if r.getMessage().startswith("SETUP failed")]
    assert logged and logged[0].exc_info is not None
    assert "/srv/private/ecosim.db" in str(logged[0].exc_info[1])


def test_run_loop_crash_stops_the_run_logs_the_traceback_and_hides_the_text(monkeypatch, caplog):
    client, registry = _client(monkeypatch)
    with caplog.at_level(logging.ERROR, logger=server.logger.name):
        with client.websocket_connect("/ws") as ws:
            session = until(ws, lambda m: m.get("type") == "SESSION")
            assert setup(ws, SMALL)["type"] == "SETUP_COMPLETE"
            manager = registry.get(session["sessionId"])

            def broken_step():
                raise RuntimeError("tick failed at /srv/private/state")

            manager.economy.step = broken_step
            ws.send_json({"command": "START"})
            reply = until(ws, lambda m: "error" in m)
            assert manager.is_running is False
    assert reply == {"error": f"Simulation stopped: {INTERNAL}", "code": "internal_error"}
    logged = [r for r in caplog.records if r.getMessage().startswith("Simulation loop error")]
    assert logged and logged[0].exc_info is not None
    assert f"session={session['sessionId']}" in logged[0].getMessage()


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.addFilter(server.SessionLogFilter())
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_log_records_carry_the_session_id_into_the_tick_loop(monkeypatch):
    outside = logging.LogRecord("server", logging.INFO, __file__, 1, "outside a session", None, None)
    server.SessionLogFilter().filter(outside)
    assert outside.session == "-"

    collect = _Collect()
    previous_level = server.logger.level
    server.logger.setLevel(logging.INFO)
    server.logger.addHandler(collect)
    try:
        client, _ = _client(monkeypatch)
        with client.websocket_connect("/ws") as ws:
            session = until(ws, lambda m: m.get("type") == "SESSION")
            assert setup(ws, {**SMALL, "horizon_ticks": 1})["type"] == "SETUP_COMPLETE"
            ws.send_json({"command": "START"})
            until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
    finally:
        server.logger.removeHandler(collect)
        server.logger.setLevel(previous_level)
    # "Starting simulation loop" is logged by the background tick task, not the connection handler.
    loop_start = [r for r in collect.records if r.getMessage() == "Starting simulation loop"]
    assert loop_start and loop_start[0].session == session["sessionId"]
