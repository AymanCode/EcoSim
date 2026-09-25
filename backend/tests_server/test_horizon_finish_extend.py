import asyncio
import functools
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}


def _client(monkeypatch, warehouse="0"):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", warehouse)
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _until(ws, predicate, **kw):
    """Bounded ``until`` that fails on any error message instead of skipping past it."""

    def check(msg):
        assert "error" not in msg, msg
        return predicate(msg)

    return until(ws, check, **kw)


def _session(ws):
    return _until(ws, lambda m: m.get("type") == "SESSION")


def _setup(ws, config):
    reply = setup(ws, config)
    assert reply.get("type") == "SETUP_COMPLETE", reply
    return reply


def test_loop_pauses_at_horizon_then_finish_and_extend_resume(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        setup_reply = _setup(ws, {**SMALL, "horizon_ticks": 3})
        assert setup_reply["config"]["horizon_ticks"] == 3
        ws.send_json({"command": "START"})
        reached = _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 3
        manager = registry.get(session["sessionId"])
        assert manager.tick == 3 and manager.is_running is False

        ws.send_json({"command": "FINISH"})
        finished = _until(ws, lambda m: m.get("type") == "FINISHED")
        assert finished["tick"] == 3 and finished["analysisReady"] is False and finished["runId"] is None
        assert finished["drained"] == 0
        assert manager.economy is not None

        ws.send_json({"command": "EXTEND", "ticks": 2})
        extended = _until(ws, lambda m: m.get("type") == "EXTENDED")
        assert extended["horizonTick"] == 5 and extended["resumed"] is True
        reached = _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 5


def test_extend_mid_run_raises_horizon_without_an_early_notification(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, {**SMALL, "horizon_ticks": 12})
        ws.send_json({"command": "START"})
        _until(ws, lambda m: "metrics" in m and m["tick"] >= 1)
        ws.send_json({"command": "EXTEND", "ticks": 3})
        seen = []
        extended = _until(ws, lambda m: seen.append(m) or m.get("type") == "EXTENDED")
        assert extended["horizonTick"] == 15
        reached = _until(ws, lambda m: seen.append(m) or m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 15
        assert [m for m in seen if m.get("type") == "HORIZON_REACHED"] == [reached]
        assert registry.get(session["sessionId"]).is_running is False


def test_finish_before_setup_and_extend_with_bad_ticks_are_errors(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        _session(ws)
        ws.send_json({"command": "FINISH"})
        assert "FINISH failed" in until(ws, lambda m: True).get("error", "")
        _setup(ws, SMALL)
        # Python's json accepts Infinity; it must be rejected, not crash the session.
        ws.send_text('{"command": "EXTEND", "ticks": Infinity}')
        assert "EXTEND failed" in until(ws, lambda m: True).get("error", "")
        for bad in (0, 5201, "soon", "3", True, 2.7, None):
            ws.send_json({"command": "EXTEND", "ticks": bad})
            reply = until(ws, lambda m: True)
            assert "EXTEND failed" in reply.get("error", ""), (bad, reply)


def test_finish_drains_queued_config_and_sends_receipts_before_finished(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, SMALL)
        manager = registry.get(session["sessionId"])
        manager.pending_config_updates.append(("queued-at-finish", {"benefitLevel": "high"}))
        ws.send_json({"command": "FINISH"})
        before_finished = []
        finished = _until(ws, lambda m: before_finished.append(m) or m.get("type") == "FINISHED")
        receipts = [m for m in before_finished if m.get("type") == "CONFIG_APPLIED"]
        assert [r["actionId"] for r in receipts] == ["queued-at-finish"]
        assert receipts[0]["applied"] == {"benefit_level": "high"}
        assert finished["drained"] == 1
        assert manager.pending_config_updates == []
        assert manager.economy.government.benefit_level == "high"


class _ExtendOnHorizonSocket:
    """Fake websocket that sends EXTEND while the loop is suspended delivering HORIZON_REACHED."""

    def __init__(self):
        self.manager = None
        self.messages = []

    async def send_json(self, msg):
        self.messages.append(msg)
        if msg.get("type") == "HORIZON_REACHED" and msg["tick"] == 3:
            self.manager.extend(2)
        await asyncio.sleep(0)


def test_extend_arriving_while_horizon_notice_is_in_flight_keeps_the_loop_running(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id="extend-race")
    manager.initialize({**SMALL, "horizon_ticks": 3})
    socket = _ExtendOnHorizonSocket()
    socket.manager = manager

    async def run():
        manager.active_websocket = socket
        manager.start_background_loop()
        await asyncio.wait_for(manager.run_task, timeout=30)

    asyncio.run(run())
    notices = [m for m in socket.messages if m.get("type") == "HORIZON_REACHED"]
    assert [m["tick"] for m in notices] == [3, 5]
    assert manager.tick == 5 and manager.is_running is False


class _FinishDuringReceiptSocket:
    """Fake websocket: FINISH is handled while the loop is suspended sending a CONFIG receipt."""

    def __init__(self, manager):
        self.manager = manager
        self.messages = []
        self.finish_task = None

    async def send_json(self, msg):
        self.messages.append(msg)
        if msg.get("type") == "CONFIG_APPLIED" and self.finish_task is None:
            self.finish_task = asyncio.create_task(self.manager.finish())
            await asyncio.sleep(0)  # FINISH runs up to its first await while this send is suspended


def test_finish_is_a_hard_boundary_when_it_lands_during_a_config_receipt(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id="finish-boundary")
    manager.initialize(SMALL)
    socket = _FinishDuringReceiptSocket(manager)

    async def run():
        manager.active_websocket = socket
        manager.pending_config_updates.append(("queued-before-first-tick", {"benefitLevel": "high"}))
        manager.start_background_loop()
        loop_task = manager.run_task
        await asyncio.wait_for(loop_task, timeout=30)
        return await asyncio.wait_for(socket.finish_task, timeout=30)

    receipts, finished = asyncio.run(run())
    frames = [m for m in socket.messages if "metrics" in m]
    assert finished["tick"] == 0 and manager.tick == 0, (finished, manager.tick)
    assert [m["tick"] for m in frames if m["tick"] > finished["tick"]] == []
    assert receipts == [] and finished["drained"] == 0  # the loop applied it at the boundary
    assert manager.economy.government.benefit_level == "high"


def test_finish_mid_run_replies_only_after_the_loop_has_exited(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, SMALL)
        manager = registry.get(session["sessionId"])
        ws.send_json({"command": "START"})
        _until(ws, lambda m: "metrics" in m and m["tick"] >= 2)
        ws.send_json({"command": "FINISH"})
        finished = _until(ws, lambda m: m.get("type") == "FINISHED")
        assert manager.run_task is None or manager.run_task.done()
        assert manager.tick == finished["tick"]
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high"}})
        after = []
        _until(ws, lambda m: after.append(m) or m.get("type") == "CONFIG_APPLIED")
        assert [m for m in after if "metrics" in m] == []


def test_stop_waits_for_the_loop_before_replying(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, SMALL)
        manager = registry.get(session["sessionId"])
        ws.send_json({"command": "START"})
        _until(ws, lambda m: "metrics" in m and m["tick"] >= 1)
        ws.send_json({"command": "STOP"})
        _until(ws, lambda m: m.get("type") == "STOPPED")
        assert manager.run_task is None or manager.run_task.done()
        stopped_at = manager.tick
        ws.send_json({"command": "CONFIG", "config": {"benefitLevel": "high"}})
        _until(ws, lambda m: m.get("type") == "CONFIG_APPLIED")
        assert manager.tick == stopped_at


class _StubbornLoop:
    """Stand-in tick loop that never ends on its own and ignores its first *refusals* cancellations.

    Setting ``released`` lets it return within one poll, so a failing test cannot leave it hanging.
    """

    def __init__(self, refusals):
        self.refusals = refusals
        self.released = False

    async def __call__(self):
        while not self.released:
            try:
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                if self.released or self.refusals == 0:
                    raise
                self.refusals -= 1


class _WarehouseRecorder:
    def __init__(self):
        self.calls = []

    def update_run_status(self, run_id, **kwargs):
        self.calls.append(("update_run_status", run_id, kwargs))

    def persist_flush_bundle(self, **kwargs):
        self.calls.append(("persist_flush_bundle", kwargs))


def _block_loop(monkeypatch, manager, refusals):
    stub = _StubbornLoop(refusals)
    monkeypatch.setattr(manager, "run_loop", stub)
    monkeypatch.setattr(manager, "wait_loop_stopped", functools.partial(manager.wait_loop_stopped, timeout=0.05))
    return stub


def _manager_with_blocked_loop(monkeypatch, refusals):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id=f"blocked-loop-{refusals}")
    manager.initialize(SMALL)
    manager.enable_warehouse = True
    manager.warehouse_manager = _WarehouseRecorder()
    manager.warehouse_run_id = "run_fake"
    return manager, _block_loop(monkeypatch, manager, refusals)


def test_finish_fails_without_finalizing_when_the_loop_will_not_stop(monkeypatch):
    manager, stub = _manager_with_blocked_loop(monkeypatch, refusals=1)
    manager.pending_config_updates.append(("left-queued", {"benefitLevel": "high"}))

    async def run():
        manager.start_background_loop()
        task = manager.run_task
        try:
            await asyncio.sleep(0)
            with pytest.raises(RuntimeError, match="simulation loop did not stop within the timeout"):
                await manager.finish()
            assert not task.done()
        finally:
            stub.released = True
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)

    asyncio.run(run())
    assert manager.run_finalized is False
    assert manager.warehouse_manager.calls == []
    assert manager.pending_config_updates == [("left-queued", {"benefitLevel": "high"})]


def test_finish_cancels_a_loop_that_outlives_the_wait_then_finalizes(monkeypatch):
    manager, stub = _manager_with_blocked_loop(monkeypatch, refusals=0)

    async def run():
        manager.start_background_loop()
        task = manager.run_task
        try:
            await asyncio.sleep(0)
            receipts, finished = await manager.finish()
            return task.cancelled(), finished
        finally:
            stub.released = True
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)

    cancelled_before_reply, finished = asyncio.run(run())
    assert cancelled_before_reply is True
    assert finished["type"] == "FINISHED" and finished["analysisReady"] is True
    assert [call[0] for call in manager.warehouse_manager.calls] == ["update_run_status"]
    assert manager.warehouse_manager.calls[0][2]["status"] == "completed"
    assert manager.run_finalized is True


def test_stop_fails_without_draining_when_the_loop_will_not_stop(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, SMALL)
        manager = registry.get(session["sessionId"])
        stub = _block_loop(monkeypatch, manager, refusals=1)
        try:
            ws.send_json({"command": "START"})
            _until(ws, lambda m: m.get("type") == "STARTED")
            manager.pending_config_updates.append(("left-queued", {"benefitLevel": "high"}))
            ws.send_json({"command": "STOP"})
            reply = until(ws, lambda m: True)
            assert reply == {"error": "STOP failed: simulation loop did not stop within the timeout"}
            assert manager.pending_config_updates == [("left-queued", {"benefitLevel": "high"})]
            assert manager.run_task is not None and not manager.run_task.done()
        finally:
            stub.released = True


class _ReopenFails:
    def reopen_run(self, run_id):
        raise RuntimeError("database is locked")


class _CannotReopen:
    pass


@pytest.mark.parametrize("warehouse", [_ReopenFails(), _CannotReopen()], ids=["raises", "missing-method"])
def test_failed_reopen_keeps_the_run_finished_and_nothing_resumes(monkeypatch, warehouse):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, {**SMALL, "horizon_ticks": 3})
        manager = registry.get(session["sessionId"])
        manager.warehouse_manager = warehouse
        manager.warehouse_run_id = "run_fake"
        manager.run_finalized = True

        ws.send_json({"command": "EXTEND", "ticks": 2})
        reply = until(ws, lambda m: True)
        assert reply.get("error") == "EXTEND failed: could not reopen the finished warehouse run", reply
        assert manager.run_finalized is True and manager.horizon_tick == 3
        assert manager.is_running is False and manager.run_task is None

        ws.send_json({"command": "START"})
        reply = until(ws, lambda m: True)
        assert reply.get("error") == "START failed: could not reopen the finished warehouse run", reply
        assert manager.run_finalized is True and manager.is_running is False and manager.run_task is None


def test_reset_clears_horizon_notice_and_finalized_flag(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, {**SMALL, "horizon_ticks": 2})
        manager = registry.get(session["sessionId"])
        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        manager.run_finalized = True
        ws.send_json({"command": "RESET"})
        _until(ws, lambda m: m.get("type") == "RESET")
        assert manager.horizon_notified is False and manager.run_finalized is False
        ws.send_json({"command": "START"})
        reached = _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        assert reached["tick"] == 2


class _RecordingCursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))


class _RecordingConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def cursor(self):
        return _RecordingCursor(self.calls)

    def commit(self):
        self.commits += 1


def test_postgres_reopen_run_clears_end_state_and_commits():
    from data.postgres_manager import PostgresDatabaseManager

    manager = object.__new__(PostgresDatabaseManager)
    manager.conn = _RecordingConnection()
    manager.reopen_run("run_x")
    [(sql, params)] = manager.conn.calls
    assert sql.startswith("UPDATE simulation_runs SET status = 'running'")
    for clause in ("ended_at = NULL", "termination_reason = NULL", "analysis_ready = FALSE", "WHERE run_id = %s"):
        assert clause in sql
    assert params == ("run_x",) and manager.conn.commits == 1


def _runs(client):
    return client.get("/warehouse/runs?limit=5").json()["runs"]


def test_sqlite_lifecycle_finish_extend_finish_and_disconnect(monkeypatch, tmp_path):
    monkeypatch.setenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite")
    monkeypatch.setenv("ECOSIM_SQLITE_PATH", str(tmp_path / "lifecycle.db"))
    client, registry = _client(monkeypatch, warehouse="1")
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, {**SMALL, "horizon_ticks": 2})
        manager = registry.get(session["sessionId"])
        run_id = manager.warehouse_run_id
        assert run_id
        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        ws.send_json({"command": "FINISH"})
        finished = _until(ws, lambda m: m.get("type") == "FINISHED")
        assert finished["analysisReady"] is True and finished["runId"] == run_id
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "completed" and row["analysis_ready"] in (True, 1)

        ws.send_json({"command": "EXTEND", "ticks": 2})
        _until(ws, lambda m: m.get("type") == "EXTENDED")
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "running" and row["analysis_ready"] in (False, 0)
        assert row["ended_at"] is None and row["termination_reason"] is None
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        ws.send_json({"command": "FINISH"})
        _until(ws, lambda m: m.get("type") == "FINISHED")
        assert manager.warehouse_run_id == run_id
    # disconnect after FINISH must not downgrade the completed run
    row = next(r for r in _runs(client) if r["run_id"] == run_id)
    assert row["status"] == "completed" and row["analysis_ready"] in (True, 1) and row["total_ticks"] == 4


def test_start_after_finish_reopens_the_warehouse_run(monkeypatch, tmp_path):
    monkeypatch.setenv("ECOSIM_WAREHOUSE_BACKEND", "sqlite")
    monkeypatch.setenv("ECOSIM_SQLITE_PATH", str(tmp_path / "start-after-finish.db"))
    client, registry = _client(monkeypatch, warehouse="1")
    with client.websocket_connect("/ws") as ws:
        session = _session(ws)
        _setup(ws, {**SMALL, "horizon_ticks": 2})
        manager = registry.get(session["sessionId"])
        run_id = manager.warehouse_run_id
        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")
        ws.send_json({"command": "FINISH"})
        assert _until(ws, lambda m: m.get("type") == "FINISHED")["analysisReady"] is True
        assert next(r for r in _runs(client) if r["run_id"] == run_id)["status"] == "completed"

        ws.send_json({"command": "START"})
        _until(ws, lambda m: m.get("type") == "STARTED")
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "running" and row["analysis_ready"] in (False, 0)
        assert row["ended_at"] is None and row["termination_reason"] is None
        assert manager.run_finalized is False
        # START at the horizon answers with the horizon notice again instead of silently stopping.
        assert _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")["tick"] == 2

        ws.send_json({"command": "EXTEND", "ticks": 1})
        assert _until(ws, lambda m: m.get("type") == "HORIZON_REACHED")["tick"] == 3
        ws.send_json({"command": "FINISH"})
        assert _until(ws, lambda m: m.get("type") == "FINISHED")["analysisReady"] is True
        row = next(r for r in _runs(client) if r["run_id"] == run_id)
        assert row["status"] == "completed" and row["total_ticks"] == 3
