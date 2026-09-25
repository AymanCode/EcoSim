import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "frontend-react" / "scripts"
for path in (SCRIPTS, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import record_session  # noqa: E402


def test_recorder_writes_header_sent_messages_errors_and_footer(tmp_path, monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    out = tmp_path / "session.jsonl"
    summary = record_session.record(
        setup={"num_households": 30, "num_firms": 1, "seed": 7, "horizon_ticks": 5, "tracked_households": 4,
               "experiment_id": "exp-rec", "arm_label": "Town A", "arm_count": 1, "experiment_owner": "test"},
        ticks_to_run=None,
        actions=[{"atTick": 2, "command": "TRACK", "action": "reshuffle"},
                 {"atTick": 2, "command": "TRACK", "action": "follow", "householdId": 999_999},
                 {"atTick": 3, "command": "CONFIG", "config": {"benefitLevel": "high"}}],
        out_path=out,
    )
    lines = [json.loads(line) for line in out.read_text().splitlines()]
    assert lines[0]["kind"] == "header" and lines[0]["schemaVersion"] == "frame-2"
    assert lines[-1]["kind"] == "footer" and lines[-1]["frames"] == 5 and lines[-1]["errors"] == 1
    sent = [line["message"]["command"] for line in lines if line["kind"] == "sent"]
    assert sent[:2] == ["SETUP", "START"] and "TRACK" in sent and "CONFIG" in sent and sent[-1] == "FINISH"
    received = [line["message"] for line in lines if line["kind"] == "message"]
    types = [m.get("type") for m in received]
    assert "SETUP_COMPLETE" in types and "TRACKED" in types and "HORIZON_REACHED" in types and "FINISHED" in types
    assert any("error" in m for m in received)
    assert "CONFIG_APPLIED" in types
    frames = [m for m in received if "metrics" in m]
    assert [f["tick"] for f in frames] == [1, 2, 3, 4, 5]
    assert frames[0]["schemaVersion"] == "frame-2" and "curated" in frames[0] and "firms" in frames[0]
    assert summary["frames"] == 5 and summary["bytesMax"] > 0 and summary["errors"] == 1

    wire = lines[1:-1]
    assert [line["seq"] for line in wire] == list(range(1, len(wire) + 1))

    def frame_pos(tick):
        return next(i for i, line in enumerate(wire)
                    if line["kind"] == "message" and "metrics" in line["message"] and line["message"]["tick"] == tick)

    track_pos = [i for i, line in enumerate(wire) if line["kind"] == "sent" and line["message"]["command"] == "TRACK"]
    config_pos = [i for i, line in enumerate(wire) if line["kind"] == "sent" and line["message"]["command"] == "CONFIG"]
    assert len(track_pos) == 2 and all(frame_pos(2) < i < frame_pos(3) for i in track_pos)
    assert len(config_pos) == 1 and frame_pos(3) < config_pos[0] < frame_pos(4)

    sizes = [len(json.dumps(f, separators=(",", ":"))) for f in frames]
    footer = lines[-1]
    assert (footer["frames"], footer["bytesTotal"], footer["bytesMax"]) == (len(sizes), sum(sizes), max(sizes))
    assert summary == {key: value for key, value in footer.items() if key != "kind"}


BLOCK = object()


class _StubSocket:
    """Replays scripted server messages; once they run out (or at BLOCK) it sleeps like a silent server."""

    def __init__(self, script, delay=0.0):
        self.script = list(script)
        self.delay = delay
        self.sent = []

    def send_json(self, message):
        self.sent.append(message)

    def receive_json(self):
        if self.delay:
            time.sleep(self.delay)
        if not self.script or self.script[0] is BLOCK:
            time.sleep(5)
            raise AssertionError("the recorder should have timed out")
        item = self.script.pop(0)
        return item() if callable(item) else item


def _stub_client(monkeypatch, socket):
    class StubClient:
        def __init__(self, app):
            pass

        @contextmanager
        def websocket_connect(self, path):
            yield socket

    monkeypatch.setattr(record_session, "TestClient", StubClient)


def _frame(tick):
    return {"tick": tick, "metrics": {}, "schemaVersion": "frame-2"}


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


SESSION = {"type": "SESSION", "sessionId": "stub"}
SETUP_COMPLETE = {"type": "SETUP_COMPLETE", "config": {}}
STARTED = {"type": "STARTED"}


def test_recorder_stall_writes_aborted_footer_and_raises(tmp_path, monkeypatch):
    _stub_client(monkeypatch, _StubSocket([SESSION, SETUP_COMPLETE, _frame(1), BLOCK]))
    out = tmp_path / "stall.jsonl"
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="no message within 0.5 s after tick 1"):
        record_session.record(setup={}, ticks_to_run=None, actions=[], out_path=out,
                              deadline_seconds=1.0, quiet_seconds=0.5)
    assert time.monotonic() - started < 3
    footer = _read(out)[-1]
    assert footer["kind"] == "footer" and footer["frames"] == 1 and footer["lastTick"] == 1
    assert "no message within 0.5 s" in footer["aborted"]


def test_recorder_deadline_bounds_a_session_that_never_finishes(tmp_path, monkeypatch):
    frames = (lambda tick=tick: _frame(tick) for tick in range(1, 10_000))
    _stub_client(monkeypatch, _StubSocket([SESSION, SETUP_COMPLETE, *frames], delay=0.1))
    out = tmp_path / "deadline.jsonl"
    with pytest.raises(TimeoutError, match="deadline 1 s exceeded"):
        record_session.record(setup={}, ticks_to_run=None, actions=[], out_path=out,
                              deadline_seconds=1.0, quiet_seconds=0.5)
    footer = _read(out)[-1]
    assert footer["kind"] == "footer" and footer["aborted"] == "deadline 1 s exceeded" and footer["frames"] >= 1


@pytest.mark.parametrize("script, error", [
    ([SESSION, SETUP_COMPLETE, STARTED, _frame(1), {"type": "HORIZON_REACHED", "tick": 1},
      {"error": "FINISH failed: boom"}], "FINISH failed: boom"),
    ([SESSION, SETUP_COMPLETE, STARTED, _frame(1), {"error": "WebSocket error: boom"}], "WebSocket error: boom"),
])
def test_recorder_names_a_terminal_server_error_when_the_session_then_stalls(tmp_path, monkeypatch, script, error):
    _stub_client(monkeypatch, _StubSocket([*script, BLOCK]))
    out = tmp_path / "terminal.jsonl"
    with pytest.raises(TimeoutError, match="terminal server error"):
        record_session.record(setup={}, ticks_to_run=None, actions=[], out_path=out,
                              deadline_seconds=5.0, quiet_seconds=0.3)
    footer = _read(out)[-1]
    assert footer["errors"] == 1 and footer["aborted"].endswith(f"following terminal server error: {error}")


def test_recorder_sends_stop_and_finish_once(tmp_path, monkeypatch):
    socket = _StubSocket([SESSION, SETUP_COMPLETE, STARTED, _frame(1), _frame(2),
                          {"type": "HORIZON_REACHED", "tick": 2}, {"type": "STOPPED"},
                          {"type": "FINISHED", "tick": 2, "drained": 0}, BLOCK])
    _stub_client(monkeypatch, socket)
    out = tmp_path / "once.jsonl"
    summary = record_session.record(setup={}, ticks_to_run=1,
                                    actions=[{"atTick": 2, "command": "STOP"}, {"atTick": 2, "command": "FINISH"}],
                                    out_path=out, deadline_seconds=5.0, quiet_seconds=0.5)
    lines = _read(out)
    sent = [line["message"]["command"] for line in lines if line["kind"] == "sent"]
    assert sent == ["SETUP", "START", "STOP", "FINISH"]
    assert [m["command"] for m in socket.sent] == sent
    assert lines[-2]["kind"] == "message" and lines[-2]["message"]["type"] == "FINISHED"
    assert lines[-1]["kind"] == "footer" and "aborted" not in lines[-1] and summary["frames"] == 2


@pytest.mark.parametrize("argv, profile", [([], "lean"), (["--frame-profile", "legacy"], "legacy")])
def test_recorder_cli_sends_the_frame_profile_lean_by_default(tmp_path, monkeypatch, argv, profile):
    captured = {}

    def fake_record(**kwargs):
        captured.update(kwargs)
        return {"frames": 0}

    monkeypatch.setattr(record_session, "record", fake_record)
    assert record_session.main(["--out", str(tmp_path / "s.jsonl"), *argv]) == 0
    assert captured["setup"]["frame_profile"] == profile
