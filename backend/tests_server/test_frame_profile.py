import json
import pickle
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402

SMALL = {"num_households": 60, "num_firms": 1, "seed": 7, "tracked_households": 8, "horizon_ticks": 3}
DETAIL_KEYS = ("history", "traits", "expectedWageReason", "recentEvents")
FRAME2_KEYS = ("schemaVersion", "arm", "horizonTick", "curated", "firms", "firmsClosed", "events", "eventCounts",
               "projectionMs", "frameBytesPrev", "serializeMsPrev")


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _no_error(predicate):
    def check(msg):
        assert "error" not in msg, msg
        return predicate(msg)

    return check


def _run(client, registry, config, before_start=()):
    """SETUP, send *before_start* commands (returning their replies), START, and collect frames to the horizon."""
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        reply = setup(ws, config)
        assert reply.get("type") == "SETUP_COMPLETE", reply
        manager = registry.get(session["sessionId"])
        replies = []
        for command in before_start:
            message = command(manager) if callable(command) else command
            ws.send_json(message)
            replies.append(until(ws, _no_error(lambda m: m.get("type") == "TRACKED")))
        ws.send_json({"command": "START"})
        frames = []

        def watch(msg):
            if "metrics" in msg:
                frames.append(msg)
            return msg.get("type") == "HORIZON_REACHED"

        until(ws, _no_error(watch))
        return reply, replies, frames, manager


def _encoded_size(frame):
    return len(json.dumps(frame, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _state(manager):
    return (
        [h.cash_balance for h in manager.economy.households],
        [h.employer_id for h in manager.economy.households],
        manager.economy.government.cash_balance,
        manager._python_random_state,
        pickle.dumps(manager._numpy_random_state),
    )


def test_legacy_frames_keep_every_old_key(monkeypatch):
    client, registry = _client(monkeypatch)
    reply, _, frames, _ = _run(client, registry, {**SMALL, "frame_profile": "legacy"})
    assert reply["config"]["frame_profile"] == "legacy"
    assert [f["tick"] for f in frames] == [1, 2, 3]
    for frame in frames:
        assert frame["frameProfile"] == "legacy" and frame["schemaVersion"] == "frame-2"
        assert "trackedFirms" in frame["metrics"] and "firm_stats" in frame
        assert all(key in frame for key in FRAME2_KEYS)
        subjects = frame["metrics"]["trackedSubjects"]
        assert len(subjects) == 8
        assert all(key in subject for subject in subjects for key in DETAIL_KEYS)


def test_lean_frames_drop_subject_detail_tracked_firms_and_firm_stats(monkeypatch):
    client, registry = _client(monkeypatch)
    _, _, legacy_frames, _ = _run(client, registry, {**SMALL, "frame_profile": "legacy"})
    reply, _, frames, _ = _run(client, registry, {**SMALL, "frame_profile": "lean"})
    assert reply["config"]["frame_profile"] == "lean"
    legacy_fields = set(legacy_frames[-1]["metrics"]["trackedSubjects"][0]) - set(DETAIL_KEYS)
    assert [f["tick"] for f in frames] == [1, 2, 3]
    for frame in frames:
        assert frame["frameProfile"] == "lean" and frame["schemaVersion"] == "frame-2"
        assert "trackedFirms" not in frame["metrics"] and "firm_stats" not in frame
        assert all(key in frame for key in FRAME2_KEYS)
        subjects = frame["metrics"]["trackedSubjects"]
        assert len(subjects) == 8
        for subject in subjects:
            assert not [key for key in DETAIL_KEYS if key in subject], subject
            assert set(subject) == legacy_fields


def test_lean_pinned_subject_keeps_its_detail(monkeypatch):
    client, registry = _client(monkeypatch)
    pin = lambda manager: {"command": "TRACK", "action": "pin", "householdId": manager.tracked_household_ids[2]}  # noqa: E731
    _, replies, frames, manager = _run(client, registry, {**SMALL, "frame_profile": "lean"}, before_start=[pin])
    pinned = replies[0]["pinned"][0]
    assert replies[0]["profiles"] == {}
    for frame in frames:
        assert frame["metrics"]["pinnedHouseholdIds"] == [pinned]
        subjects = {s["id"]: s for s in frame["metrics"]["trackedSubjects"]}
        assert all(key in subjects[pinned] for key in DETAIL_KEYS)
        assert all(key not in s for hid, s in subjects.items() if hid != pinned for key in DETAIL_KEYS)
    # the pinned household's history is the one kept for every tracked household
    assert frames[-1]["metrics"]["trackedSubjects"][2]["history"]["cash"] == [
        {"tick": 1, "value": manager.subject_histories[pinned]["cash"][0]["value"]}]
    assert all(len(manager.subject_histories[hid]["cash"]) == 1 for hid in manager.tracked_household_ids)


def test_traits_travel_in_setup_complete_and_tracked_replies(monkeypatch):
    client, registry = _client(monkeypatch)
    _, _, legacy_frames, _ = _run(client, registry, {**SMALL, "frame_profile": "legacy"})
    legacy_traits = {str(s["id"]): s["traits"] for s in legacy_frames[0]["metrics"]["trackedSubjects"]}
    for profile in ("legacy", "lean"):
        with client.websocket_connect("/ws") as ws:
            session = until(ws, lambda m: m.get("type") == "SESSION")
            reply = setup(ws, {**SMALL, "frame_profile": profile})
            manager = registry.get(session["sessionId"])
            profiles = reply["trackedProfiles"]
            assert set(profiles) == {str(hid) for hid in manager.tracked_household_ids} and len(profiles) == 8
            assert profiles == legacy_traits  # same seed, same sample, same keys and values as legacy traits

            previous = set(manager.tracked_household_ids)
            ws.send_json({"command": "TRACK", "action": "reshuffle"})
            reshuffled = until(ws, _no_error(lambda m: m.get("type") == "TRACKED"))
            added = {str(hid) for hid in reshuffled["tracked"] if hid not in previous}
            assert added and set(reshuffled["profiles"]) == added
            assert all(set(traits) == set(next(iter(legacy_traits.values()))) for traits in reshuffled["profiles"].values())

            ws.send_json({"command": "TRACK", "action": "pin", "householdId": reshuffled["tracked"][0]})
            assert until(ws, _no_error(lambda m: m.get("type") == "TRACKED"))["profiles"] == {}
            ws.send_json({"command": "TRACK", "action": "unpin", "householdId": reshuffled["tracked"][0]})
            assert until(ws, _no_error(lambda m: m.get("type") == "TRACKED"))["profiles"] == {}

            outsider = next(h.household_id for h in manager.economy.households
                            if h.household_id not in manager.tracked_household_ids)
            ws.send_json({"command": "TRACK", "action": "follow", "householdId": outsider})
            followed = until(ws, _no_error(lambda m: m.get("type") == "TRACKED"))
            assert list(followed["profiles"]) == [str(outsider)]
            ws.send_json({"command": "TRACK", "action": "follow", "householdId": outsider})
            assert until(ws, _no_error(lambda m: m.get("type") == "TRACKED"))["profiles"] == {}


def test_lean_frame_is_smaller_than_legacy(monkeypatch):
    client, registry = _client(monkeypatch)
    _, _, legacy_frames, _ = _run(client, registry, {**SMALL, "frame_profile": "legacy"})
    _, _, lean_frames, _ = _run(client, registry, {**SMALL, "frame_profile": "lean"})
    assert legacy_frames[-1]["tick"] == lean_frames[-1]["tick"] == 3
    assert _encoded_size(lean_frames[-1]) < _encoded_size(legacy_frames[-1])


def test_profile_never_touches_the_economy_or_the_session_rng(monkeypatch):
    client, registry = _client(monkeypatch)
    _, _, _, legacy = _run(client, registry, {**SMALL, "frame_profile": "legacy"})
    _, _, _, lean = _run(client, registry, {**SMALL, "frame_profile": "lean"})
    assert legacy.tick == lean.tick == 3
    assert _state(legacy) == _state(lean)


def test_setup_defaults_are_the_legacy_profile_with_no_horizon_and_twelve_households():
    defaults = server.SetupConfig()
    assert defaults.frame_profile == "legacy"
    assert defaults.horizon_ticks is None and defaults.tracked_households is None


def test_legacy_setup_without_horizon_runs_on_and_samples_twelve(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        reply = setup(ws, {"num_households": 60, "num_firms": 1, "seed": 7})
        assert reply.get("type") == "SETUP_COMPLETE", reply
        assert reply["config"]["frame_profile"] == "legacy"
        assert reply["config"]["horizon_ticks"] is None and reply["config"]["tracked_households"] == 12
        manager = registry.get(session["sessionId"])
        assert manager.horizon_tick is None and len(manager.tracked_household_ids) == 12
        assert len(reply["trackedProfiles"]) == 12
        ws.send_json({"command": "START"})
        seen = []
        frame = until(ws, _no_error(lambda m: seen.append(m) or ("metrics" in m and m["tick"] >= 4)))
        assert not [m for m in seen if m.get("type") == "HORIZON_REACHED"]
        assert frame["horizonTick"] is None and frame["frameProfile"] == "legacy"
        assert len(frame["metrics"]["trackedSubjects"]) == 12
        ws.send_json({"command": "STOP"})
        until(ws, _no_error(lambda m: m.get("type") == "STOPPED"))
        assert not [m for m in seen if m.get("type") == "HORIZON_REACHED"]


def test_lean_setup_without_explicit_values_gets_horizon_260_and_forty_households(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        reply = setup(ws, {"num_households": 60, "num_firms": 1, "seed": 7, "frame_profile": "lean"})
        assert reply.get("type") == "SETUP_COMPLETE", reply
        assert reply["config"]["horizon_ticks"] == 260 and reply["config"]["tracked_households"] == 40
        manager = registry.get(session["sessionId"])
        assert manager.horizon_tick == 260 and len(manager.tracked_household_ids) == 40
        ws.send_json({"command": "START"})
        frame = until(ws, _no_error(lambda m: "metrics" in m))
        assert frame["horizonTick"] == 260 and len(frame["metrics"]["trackedSubjects"]) == 40
        ws.send_json({"command": "STOP"})
        until(ws, _no_error(lambda m: m.get("type") == "STOPPED"))

        explicit = setup(ws, {"num_households": 60, "num_firms": 1, "seed": 7, "frame_profile": "legacy",
                              "horizon_ticks": 9, "tracked_households": 5})
        assert explicit["config"]["horizon_ticks"] == 9 and explicit["config"]["tracked_households"] == 5
        assert manager.horizon_tick == 9 and len(manager.tracked_household_ids) == 5

        bad = setup(ws, {"num_households": 60, "num_firms": 1, "seed": 7, "frame_profile": "compact"})
        assert "frame_profile" in bad.get("error", ""), bad
