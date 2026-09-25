"""Record a whole WebSocket session (frame-2) to JSON Lines for backend-free frontend work.

Runs the FastAPI app in-process through Starlette's TestClient, sends SETUP and
START, replays scripted actions at given ticks, and writes every client command
and server message in wire order. Server errors are recorded, not fatal.

Every receive is bounded (``quiet_seconds`` per message, ``deadline_seconds`` for the
whole recording) with SIGALRM, so ``record`` must run on the main thread. On a
timeout the footer carries ``aborted`` with the reason and ``TimeoutError`` is raised.
STOP and FINISH are each sent at most once, scripted ones included.

    .venv/bin/python frontend-react/scripts/record_session.py --households 60 --ticks 24 \
        --out frontend-react/src/test/fixtures/session-compare-small.jsonl
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient  # noqa: E402

from backend import server  # noqa: E402


class _Stalled(Exception):
    """Raised from the SIGALRM handler when a receive outlives its bound."""


def record(*, setup: Dict[str, Any], ticks_to_run: Optional[int], actions: List[Dict[str, Any]], out_path: Path,
           deadline_seconds: float = 120.0, quiet_seconds: float = 30.0) -> Dict[str, Any]:
    pending = sorted(actions, key=lambda a: int(a["atTick"]))
    client = TestClient(server.app)
    stats = {"frames": 0, "bytesTotal": 0, "bytesMax": 0, "lastTick": 0, "errors": 0}
    seq = 0
    deadline_at = time.monotonic() + deadline_seconds
    bound = "quiet"  # which bound the armed timer enforces: "quiet" or "deadline"
    run_active = False
    terminal_error: Optional[str] = None  # set by a terminal server error, cleared by any later message
    stop_sent = False
    finish_sent = False
    aborted: Optional[str] = None

    def stall_reason() -> str:
        if bound == "deadline":
            reason = f"deadline {deadline_seconds:g} s exceeded"
        else:
            where = f"after tick {stats['lastTick']}" if stats["frames"] else "before the first tick frame"
            reason = f"no message within {quiet_seconds:g} s {where}"
        if terminal_error is not None:
            reason += f", following terminal server error: {terminal_error}"
        return reason

    def on_alarm(signum: int, frame: Any) -> None:
        raise _Stalled(stall_reason())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    previous_handler = signal.signal(signal.SIGALRM, on_alarm)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        with out_path.open("w", encoding="utf-8") as fh:
            def write(kind: str, **payload: Any) -> None:
                fh.write(json.dumps({"kind": kind, **payload}) + "\n")

            def send(ws, message: Dict[str, Any]) -> None:
                nonlocal seq, stop_sent, finish_sent
                command = message.get("command")
                if (command == "STOP" and (stop_sent or finish_sent)) or (command == "FINISH" and finish_sent):
                    return
                stop_sent = stop_sent or command == "STOP"
                finish_sent = finish_sent or command == "FINISH"
                seq += 1
                write("sent", seq=seq, message=message)
                ws.send_json(message)

            def receive(ws) -> Dict[str, Any]:
                nonlocal seq, run_active, terminal_error, bound
                remaining = deadline_at - time.monotonic()
                bound = "deadline" if remaining <= quiet_seconds else "quiet"
                if remaining <= 0:
                    raise _Stalled(stall_reason())
                signal.setitimer(signal.ITIMER_REAL, min(quiet_seconds, remaining))
                try:
                    message = ws.receive_json()
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                seq += 1
                terminal_error = None
                if "error" in message:
                    stats["errors"] += 1
                    text = str(message["error"])
                    if text.startswith("WebSocket error") or not run_active:
                        terminal_error = text
                if "metrics" in message and "tick" in message:
                    encoded = json.dumps(message, separators=(",", ":"))
                    stats["frames"] += 1
                    stats["bytesTotal"] += len(encoded)
                    stats["bytesMax"] = max(stats["bytesMax"], len(encoded))
                    stats["lastTick"] = int(message["tick"])
                    run_active = True
                if message.get("type") == "STARTED":
                    run_active = True
                elif message.get("type") in {"HORIZON_REACHED", "STOPPED", "FINISHED"}:
                    run_active = False
                write("message", seq=seq, message=message)
                return message

            write("header", schemaVersion="frame-2", setup=setup, recordedAt=datetime.now(timezone.utc).isoformat())
            try:
                with client.websocket_connect("/ws") as ws:
                    receive(ws)  # SESSION
                    send(ws, {"command": "SETUP", "config": setup})
                    msg = receive(ws)
                    while msg.get("type") != "SETUP_COMPLETE":
                        if "error" in msg:
                            raise RuntimeError(f"SETUP failed: {msg['error']}")
                        msg = receive(ws)
                    send(ws, {"command": "START"})
                    done = False
                    while not done:
                        msg = receive(ws)
                        if "metrics" in msg:
                            tick = int(msg["tick"])
                            while pending and int(pending[0]["atTick"]) <= tick:
                                action = dict(pending.pop(0))
                                action.pop("atTick", None)
                                send(ws, action)
                            if ticks_to_run is not None and tick >= ticks_to_run:
                                send(ws, {"command": "STOP"})
                        if msg.get("type") in {"HORIZON_REACHED", "STOPPED"}:
                            send(ws, {"command": "FINISH"})
                        if msg.get("type") == "FINISHED":
                            done = True
            except _Stalled as exc:
                aborted = str(exc)
            footer: Dict[str, Any] = dict(stats)
            if aborted is not None:
                footer["aborted"] = aborted
            write("footer", **footer)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
    if aborted is not None:
        raise TimeoutError(aborted)
    return dict(stats)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--households", type=int, default=60)
    parser.add_argument("--firms", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=24, help="horizon in ticks")
    parser.add_argument("--tracked", type=int, default=8)
    parser.add_argument("--initial-policy", default="{}", help="JSON lever vector")
    parser.add_argument("--experiment", default=None)
    parser.add_argument("--arm", default=None)
    parser.add_argument("--arms", type=int, default=1)
    parser.add_argument("--owner", default="recorder")
    parser.add_argument("--action", action="append", default=[], help='JSON like {"atTick":3,"command":"CONFIG","config":{...}}')
    parser.add_argument("--deadline", type=float, default=120.0, help="seconds allowed for the whole recording")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    setup: Dict[str, Any] = {
        "num_households": args.households, "num_firms": args.firms, "seed": args.seed,
        "horizon_ticks": args.ticks, "tracked_households": args.tracked,
        "initial_policy": json.loads(args.initial_policy), "enable_llm_government": False,
    }
    if args.experiment:
        setup.update({"experiment_id": args.experiment, "arm_label": args.arm or "Town A", "arm_count": args.arms,
                      "experiment_owner": args.owner})
    summary = record(setup=setup, ticks_to_run=None, actions=[json.loads(a) for a in args.action], out_path=Path(args.out),
                     deadline_seconds=args.deadline)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
