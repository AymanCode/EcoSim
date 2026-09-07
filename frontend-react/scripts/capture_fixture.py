"""Capture one real WebSocket tick frame as a frontend test fixture.

Runs the FastAPI app in-process through Starlette's TestClient (no network,
no browser), launches a small economy, advances it to TARGET_TICK, and writes
the last frame to src/test/fixtures/frame.json. Usage, from the repo root:

    .venv/bin/python frontend-react/scripts/capture_fixture.py 60
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient  # noqa: E402

from backend import server  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "test" / "fixtures" / "frame.json"
TARGET_TICK = int(sys.argv[1]) if len(sys.argv) > 1 else 60
SETUP = {
    "num_households": 100, "num_firms": 5, "seed": 7, "wage_tax": 0.15, "profit_tax": 0.2,
    "enable_llm_government": False, "disable_stabilizers": False, "disabled_agents": [],
}


def main() -> None:
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        session = ws.receive_json()
        assert session["type"] == "SESSION", session
        ws.send_json({"command": "SETUP", "config": SETUP})
        msg = ws.receive_json()
        while msg.get("type") != "SETUP_COMPLETE":
            msg = ws.receive_json()
        ws.send_json({"command": "START"})
        last = None
        while True:
            msg = ws.receive_json()
            if "tick" in msg and "metrics" in msg:
                last = msg
                if msg["tick"] >= TARGET_TICK:
                    break
        ws.send_json({"command": "STOP"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(last, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(Path.cwd())} tick={last['tick']} metric keys={len(last['metrics'])} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
