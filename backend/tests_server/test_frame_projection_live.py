import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import server  # noqa: E402
from _ws import setup, until  # noqa: E402

SMALL = {"num_households": 30, "num_firms": 1, "seed": 7}


def _client(monkeypatch):
    monkeypatch.setenv("ECOSIM_ENABLE_WAREHOUSE", "0")
    registry = server.SessionRegistry(max_sessions=2)
    monkeypatch.setattr(server, "session_registry", registry)
    return TestClient(server.app), registry


def _frames_until_horizon(ws):
    frames = []

    def watch(msg):
        if "metrics" in msg:
            frames.append(msg)
        return msg.get("type") == "HORIZON_REACHED"

    until(ws, watch)
    return frames


def test_reset_recomputes_cached_metrics_on_the_first_resumed_tick(monkeypatch):
    client, _ = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        until(ws, lambda m: m.get("type") == "SESSION")
        assert setup(ws, {**SMALL, "horizon_ticks": 7}).get("type") == "SETUP_COMPLETE"
        ws.send_json({"command": "START"})
        assert _frames_until_horizon(ws)[-1]["curated"]["wealthAsOfTick"] == 5
        ws.send_json({"command": "RESET"})
        until(ws, lambda m: m.get("type") == "RESET")
        ws.send_json({"command": "START"})
        first = until(ws, lambda m: "metrics" in m)
        assert first["tick"] == 1 and first["curated"]["wealthAsOfTick"] == 1
        until(ws, lambda m: m.get("type") == "HORIZON_REACHED")


def test_curated_bank_defaults_are_fresh_each_tick_while_wealth_is_stride_cached(monkeypatch):
    client, registry = _client(monkeypatch)
    with client.websocket_connect("/ws") as ws:
        session = until(ws, lambda m: m.get("type") == "SESSION")
        config = {**SMALL, "horizon_ticks": 6, "payment_sequence": "income_first"}
        assert setup(ws, config).get("type") == "SETUP_COMPLETE"
        # Count one more default every tick so a stride-cached count would visibly lag.
        economy = registry.get(session["sessionId"]).economy
        original_step = economy.step

        def step():
            original_step()
            state = economy.payment_state
            state["loan_default_history_total"] = int(state.get("loan_default_history_total", 0)) + 1

        monkeypatch.setattr(economy, "step", step)
        ws.send_json({"command": "START"})
        frames = _frames_until_horizon(ws)
    assert [f["tick"] for f in frames] == [1, 2, 3, 4, 5, 6]
    totals = [f["curated"]["bankDefaultsTotal"] for f in frames]
    assert totals == [f["metrics"]["payment"]["loans"]["defaults_total"] for f in frames]
    assert all(later > earlier for earlier, later in zip(totals, totals[1:]))
    assert [f["curated"]["wealthAsOfTick"] for f in frames] == [1, 1, 1, 1, 5, 5]
    assert len({f["curated"]["gini"] for f in frames[:4]}) == 1
    assert all(isinstance(f["curated"]["careDenials"], float) for f in frames)  # step() always reports it
