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

SMALL = {"num_households": 60, "num_firms": 1, "seed": 7, "tracked_households": 8}


def _manager(monkeypatch, name, config=SMALL):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    manager = server.SimulationManager(session_id=name)
    manager.initialize(config)
    return manager


def _step(manager, n):
    for _ in range(n):
        with server.use_config(manager.config), manager._random_scope():
            manager.economy.step()
        manager.tick += 1


def _state(manager):
    return (
        [round(h.cash_balance, 9) for h in manager.economy.households],
        [h.employer_id for h in manager.economy.households],
        [round(f.cash_balance, 9) for f in manager.economy.firms],
        round(manager.economy.government.cash_balance, 9),
        manager._python_random_state,
        pickle.dumps(manager._numpy_random_state),
    )


def test_sample_size_follows_setup(monkeypatch):
    manager = _manager(monkeypatch, "a")
    assert len(manager.tracked_household_ids) == 8 == len(set(manager.tracked_household_ids))
    assert all(hid in manager.subject_histories for hid in manager.tracked_household_ids)


def test_browsing_households_never_changes_the_economy_or_the_session_rng(monkeypatch):
    quiet = _manager(monkeypatch, "quiet")
    busy = _manager(monkeypatch, "busy")
    for _ in range(6):
        _step(quiet, 1)
        _step(busy, 1)
        busy.track("reshuffle", None)
        busy.track("pin", busy.tracked_household_ids[0])
        outsider = next(h.household_id for h in busy.economy.households if h.household_id not in busy.tracked_household_ids)
        busy.track("follow", outsider)
    assert _state(quiet) == _state(busy)


def test_pin_survives_reshuffle_and_follow_evicts_oldest_unpinned(monkeypatch):
    manager = _manager(monkeypatch, "a")
    first = manager.tracked_household_ids[0]
    assert manager.track("pin", first)["pinned"] == [first]
    reply = manager.track("reshuffle", None)
    assert first in reply["tracked"] and len(reply["tracked"]) == 8
    outsider = next(h.household_id for h in manager.economy.households if h.household_id not in reply["tracked"])
    oldest_unpinned = next(hid for hid in reply["tracked"] if hid != first)
    reply = manager.track("follow", outsider)
    assert outsider in reply["tracked"] and oldest_unpinned not in reply["tracked"] and len(reply["tracked"]) == 8
    assert outsider in manager.subject_histories and oldest_unpinned not in manager.subject_histories


def test_follow_unknown_household_is_an_error_and_changes_nothing(monkeypatch):
    manager = _manager(monkeypatch, "a")
    before = list(manager.tracked_household_ids)
    try:
        manager.track("follow", 999_999)
    except ValueError as exc:
        assert "999999" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    assert manager.tracked_household_ids == before


def _rejects(manager, household_id):
    before = list(manager.tracked_household_ids)
    try:
        manager.track("follow", household_id)
    except ValueError as exc:
        assert "householdId must be an integer" in str(exc)
    else:
        raise AssertionError(f"expected ValueError for {household_id!r}")
    assert manager.tracked_household_ids == before


def test_household_id_must_be_a_finite_integer(monkeypatch):
    manager = _manager(monkeypatch, "a")
    for bad in (1.9, True, "7", float("inf"), float("nan")):
        _rejects(manager, bad)
    assert 3 in manager.economy.household_lookup
    reply = manager.track("follow", 3.0)
    assert 3 in reply["tracked"] and 3 in manager.subject_histories
    assert all(type(hid) is int for hid in reply["tracked"])


def test_pin_limit_is_eight(monkeypatch):
    manager = _manager(monkeypatch, "a", {**SMALL, "tracked_households": 10})
    for hid in manager.tracked_household_ids[:8]:
        manager.track("pin", hid)
    try:
        manager.track("pin", manager.tracked_household_ids[8])
    except ValueError as exc:
        assert "8" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_track_over_websocket_and_payment_fields_in_frames(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, {**SMALL, "horizon_ticks": 2}).get("type") == "SETUP_COMPLETE"
        ws.send_json({"command": "TRACK", "action": "reshuffle"})
        reply = until(ws, lambda m: m.get("type") == "TRACKED" or "error" in m)
        assert reply["type"] == "TRACKED" and len(reply["tracked"]) == 8
        ws.send_json({"command": "TRACK", "action": "follow", "householdId": 999_999})
        assert "error" in until(ws, lambda m: m.get("type") == "TRACKED" or "error" in m)
        ws.send_json({"command": "START"})
        frames = []

        def watch(msg):
            if "metrics" in msg:
                frames.append(msg)
            return msg.get("type") == "HORIZON_REACHED"

        until(ws, watch)
        frame = frames[-1]
        subjects = frame["metrics"]["trackedSubjects"]
        assert len(subjects) == 8
        assert {s["id"] for s in subjects} == set(reply["tracked"])
        assert all("rentArrears" in s and "leaseRenewalTick" in s for s in subjects)
        assert frame["metrics"]["pinnedHouseholdIds"] == []


def test_track_with_an_out_of_range_number_is_an_error_not_a_dropped_session(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, SMALL).get("type") == "SETUP_COMPLETE"
        ws.send_text('{"command": "TRACK", "action": "follow", "householdId": 1e309}')
        reply = until(ws, lambda m: m.get("type") == "TRACKED" or "error" in m)
        assert "householdId must be an integer" in reply["error"]
        ws.send_json({"command": "TRACK", "action": "reshuffle"})
        assert until(ws, lambda m: m.get("type") == "TRACKED" or "error" in m)["type"] == "TRACKED"


def test_frame_reports_arrears_and_the_lease_sentinel_only_for_renters(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, {**SMALL, "horizon_ticks": 2}).get("type") == "SETUP_COMPLETE"
        ws.send_json({"command": "TRACK", "action": "reshuffle"})
        tracked = until(ws, lambda m: m.get("type") == "TRACKED" or "error" in m)["tracked"]
        evicted_id, renter_id = tracked[0], tracked[1]
        manager = registry.get(session["sessionId"])
        economy = manager.economy
        # The legacy rental market re-matches every household each tick; hold it still so
        # the frame shows the fields exactly as set here.
        monkeypatch.setattr(economy, "_clear_housing_rental_market", lambda: None)
        landlord = next((f for f in economy.firms if (f.good_category or "").lower() == "housing"), economy.firms[0])
        evicted = economy.household_lookup[evicted_id]
        evicted.rent_arrears = 12.5
        evicted.renting_from_firm_id = None
        evicted.lease_renewal_tick = 52
        renter = economy.household_lookup[renter_id]
        renter.renting_from_firm_id = landlord.firm_id
        renter.lease_renewal_tick = 30
        ws.send_json({"command": "START"})
        frames = []

        def watch(msg):
            if "metrics" in msg:
                frames.append(msg)
            return msg.get("type") == "HORIZON_REACHED"

        until(ws, watch)
        subjects = {s["id"]: s for s in frames[-1]["metrics"]["trackedSubjects"]}
        assert subjects[evicted_id]["hasRental"] is False
        assert subjects[evicted_id]["rentArrears"] == 12.5
        assert subjects[evicted_id]["leaseRenewalTick"] == -1
        assert subjects[renter_id]["hasRental"] is True
        assert subjects[renter_id]["leaseRenewalTick"] == 30
