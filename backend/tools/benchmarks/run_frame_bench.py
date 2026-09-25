"""Concurrent full-path frame benchmark: real uvicorn server, N websocket arms at once.

Measures per-frame bytes, tick compute time, projection time, serialization time
and inter-frame time per arm; checks the phase-1 gate for every arm; and asserts
that the session path reproduces the headless newcomer smoke runner for the same seed.

    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --seed 1337
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 1000 --ticks 260 --arms 2 --warehouse
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 5000 --ticks 52 --arms 2
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --households 2500 --ticks 52 --arms 4
    .venv/bin/python -m backend.tools.benchmarks.run_frame_bench --frame-profile legacy   # the old dashboard's frame

Every arm's SETUP carries ``frame_profile`` (``--frame-profile``, default ``lean``).

Exit codes: 0 when the phase gate passes (every arm within both budgets and the
equivalence check measured and matched); 2 for a matrix run with
``--skip-equivalence`` whose measured checks pass; 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from websockets.asyncio.client import connect  # noqa: E402

GATE_BYTES_P95 = 61_440
# The budget is defined at 40 tracked households; sent explicitly so a legacy-profile run (default 12) measures the same.
TRACKED_HOUSEHOLDS = 40
GATE_OVERHEAD_SHARE = 0.10
CHECKPOINTS = (13, 26, 52, 104, 156, 208, 260)
# Upper bound on messages read while waiting for SESSION, SETUP_COMPLETE or FINISHED.
MAX_CONTROL_MESSAGES = 2_000
# Frame fields every record needs; a frame missing one is an error, never a zero.
REQUIRED_FRAME_FIELDS = ("tick", "metrics.tickComputeMs", "projectionMs", "serializeMsPrev", "curated.peopleOutOfWorkPer100")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_server(*, warehouse: bool, sqlite_path: Path) -> Tuple[subprocess.Popen, str]:
    port = _free_port()
    env = dict(os.environ)
    env["ECOSIM_ENABLE_WAREHOUSE"] = "1" if warehouse else "0"
    env["ECOSIM_WAREHOUSE_BACKEND"] = "sqlite"
    env["ECOSIM_SQLITE_PATH"] = str(sqlite_path)
    env["ECOSIM_MAX_SESSIONS"] = "8"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    import urllib.request
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=1) as response:
                if response.status == 200:
                    return process, base_url
        except Exception:
            if process.poll() is not None:
                raise RuntimeError(f"server exited early: {process.stderr.read().decode(errors='replace')[-2000:]}")
            time.sleep(0.2)
    process.kill()
    raise RuntimeError("server did not become healthy within 30 s")


def stop_server(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _field(frame: Dict[str, Any], path: str) -> Any:
    node: Any = frame
    for part in path.split("."):
        if not isinstance(node, dict) or node.get(part) is None:
            return None
        node = node[part]
    return node


def _frame_record(label: str, raw: Any, frame: Dict[str, Any]) -> Dict[str, Any]:
    values = {}
    for path in REQUIRED_FRAME_FIELDS:
        value = _field(frame, path)
        if value is None:
            raise RuntimeError(f"{label}: frame at tick {frame.get('tick')} is missing {path}")
        values[path] = value
    return {
        "tick": int(values["tick"]),
        # UTF-8 bytes on the wire, the same measure as the server's frameBytesPrev.
        "bytes": len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw),
        "tickComputeMs": float(values["metrics.tickComputeMs"]),
        "projectionMs": float(values["projectionMs"]),
        "serializeMs": float(values["serializeMsPrev"]),
        "receivedAt": time.perf_counter(),
        "peopleOutOfWorkPer100": float(values["curated.peopleOutOfWorkPer100"]),
    }


async def _run_arm(ws_url: str, *, label: str, setup: Dict[str, Any], quiet_seconds: float,
                   deadline_seconds: float) -> List[Dict[str, Any]]:
    """Run one arm to its horizon and FINISH; every receive is bounded by a quiet period and a whole-arm deadline."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_seconds
    records: List[Dict[str, Any]] = []
    last_tick = 0

    def _deadline_error() -> RuntimeError:
        return RuntimeError(f"{label}: arm deadline of {deadline_seconds}s passed after tick {last_tick}")

    async def receive(ws: Any) -> Tuple[Any, Dict[str, Any]]:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise _deadline_error()
        wait = min(quiet_seconds, remaining)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=wait)
        except asyncio.TimeoutError:
            if wait < quiet_seconds:
                raise _deadline_error() from None
            raise RuntimeError(f"{label}: no message within {quiet_seconds}s after tick {last_tick}") from None
        msg = json.loads(raw)
        if "error" in msg:
            raise RuntimeError(f"{label}: server error after tick {last_tick}: {msg['error']}")
        return raw, msg

    async def await_type(ws: Any, wanted: str) -> None:
        for _ in range(MAX_CONTROL_MESSAGES):
            _raw, msg = await receive(ws)
            if msg.get("type") == wanted:
                return
        raise RuntimeError(f"{label}: no {wanted} within {MAX_CONTROL_MESSAGES} messages after tick {last_tick}")

    async with connect(ws_url, max_size=50_000_000, open_timeout=20) as ws:
        await await_type(ws, "SESSION")
        await ws.send(json.dumps({"command": "SETUP", "config": setup}))
        await await_type(ws, "SETUP_COMPLETE")
        await ws.send(json.dumps({"command": "START"}))
        while True:
            raw, msg = await receive(ws)
            if "metrics" in msg:
                records.append(_frame_record(label, raw, msg))
                last_tick = records[-1]["tick"]
            if msg.get("type") == "HORIZON_REACHED":
                break
        await ws.send(json.dumps({"command": "FINISH"}))
        await await_type(ws, "FINISHED")
    return records


def run_experiment(*, base_url: str, arms: List[Dict[str, Any]], households: int, ticks: int, seed: int,
                   warehouse: bool, quiet_seconds: float = 60.0, deadline_seconds: float = 1800.0,
                   frame_profile: str = "lean") -> Dict[str, List[Dict[str, Any]]]:
    ws_url = base_url.replace("http", "ws", 1) + "/ws"
    experiment_id = f"bench-{int(time.time())}"

    async def _all() -> Dict[str, List[Dict[str, Any]]]:
        tasks = []
        for arm in arms:
            setup = {
                "num_households": households, "num_firms": 5, "seed": seed, "horizon_ticks": ticks,
                "tracked_households": TRACKED_HOUSEHOLDS,
                "initial_policy": dict(arm.get("initial_policy") or {}), "enable_llm_government": False,
                "experiment_id": experiment_id, "arm_label": arm["label"], "arm_count": len(arms), "experiment_owner": "bench",
                "frame_profile": frame_profile,
            }
            tasks.append(_run_arm(ws_url, label=arm["label"], setup=setup, quiet_seconds=quiet_seconds,
                                  deadline_seconds=deadline_seconds))
        results = await asyncio.gather(*tasks)
        return {arm["label"]: records for arm, records in zip(arms, results)}

    return asyncio.run(_all())


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return float(ordered[index])


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        raise ValueError("summarize needs at least one frame")
    for record in records:
        value = record["tickComputeMs"]
        if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
            raise ValueError(f"tick {record.get('tick')}: tickComputeMs must be a finite positive number, got {value!r}")
    sizes = [float(r["bytes"]) for r in records]
    ticks_ms = [float(r["tickComputeMs"]) for r in records]
    proj_ms = [float(r["projectionMs"]) for r in records]
    ser_ms = [float(r.get("serializeMs", 0.0)) for r in records[1:]]  # first frame carries no previous value
    gaps = [(b["receivedAt"] - a["receivedAt"]) * 1000.0 for a, b in zip(records, records[1:])]
    tick_p50 = _percentile(ticks_ms, 50)
    proj_p50 = _percentile(proj_ms, 50)
    ser_p50 = _percentile(ser_ms, 50)
    return {
        "frames": len(records),
        "bytes": {"p50": _percentile(sizes, 50), "p95": _percentile(sizes, 95), "max": max(sizes) if sizes else 0.0},
        "tickComputeMs": {"p50": tick_p50, "p95": _percentile(ticks_ms, 95)},
        "projectionMs": {"p50": proj_p50, "p95": _percentile(proj_ms, 95), "shareOfTickP50": (proj_p50 / tick_p50) if tick_p50 else 0.0},
        "serializeMs": {"p50": ser_p50, "p95": _percentile(ser_ms, 95), "shareOfTickP50": (ser_p50 / tick_p50) if tick_p50 else 0.0},
        "interFrameMs": {"p50": _percentile(gaps, 50), "p95": _percentile(gaps, 95)},
    }


def equivalence(*, records_for_baseline: List[Dict[str, Any]], households: int, ticks: int, seed: int) -> Dict[str, Any]:
    """Compare the live session's unemployment with the headless smoke runner at shared checkpoints."""
    from backend.tools.benchmarks import run_newcomer_smoke

    baseline_arm = run_newcomer_smoke.resolve_arms(["baseline"])[0]
    smoke_rows, _meta = run_newcomer_smoke.run_arm(
        baseline_arm, seed=seed, households=households, ticks=ticks, firms_per_category=5, payment_sequence="legacy",
    )
    by_frame_tick = {r["tick"]: r["peopleOutOfWorkPer100"] for r in records_for_baseline}
    by_smoke_tick = {int(row["tick"]): float(row["unemployment_rate"]) * 100.0 for row in smoke_rows}
    checkpoints = [t for t in CHECKPOINTS if t <= ticks] or [ticks]
    rows = []
    for tick in checkpoints:
        session_value = by_frame_tick.get(tick)
        smoke_value = by_smoke_tick.get(tick - 1)  # smoke rows are stamped with the pre-step tick
        if smoke_value is None:
            raise RuntimeError(f"the smoke runner produced no row for tick {tick - 1} (frame tick {tick})")
        rows.append({"tick": tick, "session": session_value, "smoke": smoke_value,
                     "match": session_value is not None and abs(session_value - smoke_value) < 1e-6})
    return {"checkpoints": rows, "matches": all(r["match"] for r in rows)}


def gate(summaries: Dict[str, Dict[str, Any]], equivalence_result: Optional[Dict[str, Any]],
         require_equivalence: bool) -> Dict[str, Any]:
    """Check both budgets for every arm, and equivalence for the baseline arm.

    ``passed`` covers the measured checks only; ``phaseGate`` additionally needs the
    equivalence check measured and matched. A missing result counts as a failure when
    equivalence is required and as ``"skipped"`` when it is not.
    """
    arms: Dict[str, Dict[str, Any]] = {}
    for label, summary in summaries.items():
        overhead = summary["projectionMs"]["shareOfTickP50"] + summary["serializeMs"]["shareOfTickP50"]
        arms[label] = {
            "bytesP95": summary["bytes"]["p95"],
            "overheadShare": overhead,
            "bytesOk": summary["bytes"]["p95"] <= GATE_BYTES_P95,
            "overheadOk": overhead <= GATE_OVERHEAD_SHARE,
        }
    if equivalence_result is not None:
        equivalence_check: Any = bool(equivalence_result["matches"])
    else:
        equivalence_check = False if require_equivalence else "skipped"
    checks = {
        "bytesP95": bool(arms) and all(arm["bytesOk"] for arm in arms.values()),
        "overheadShare": bool(arms) and all(arm["overheadOk"] for arm in arms.values()),
        "equivalence": equivalence_check,
    }
    passed = all(value is True for value in checks.values() if value != "skipped")
    return {
        "checks": checks,
        "arms": arms,
        "failingArms": [label for label, arm in arms.items() if not (arm["bytesOk"] and arm["overheadOk"])],
        "passed": passed,
        "phaseGate": passed and checks["equivalence"] is True,
    }


def exit_code(verdict: Dict[str, Any]) -> int:
    """0: phase gate passed; 2: matrix run with equivalence skipped and measured checks passed; 1: failed."""
    if verdict["phaseGate"]:
        return 0
    if verdict["checks"]["equivalence"] == "skipped" and verdict["passed"]:
        return 2
    return 1


def _outcome(verdict: Dict[str, Any]) -> str:
    code = exit_code(verdict)
    if code == 0:
        return "phase gate passed (exit 0)"
    if code == 2:
        return "matrix run: measured checks passed, equivalence skipped, not a phase-gate result (exit 2)"
    failed = [name for name, value in verdict["checks"].items() if value is False]
    return f"failed: {', '.join(failed)} (exit 1)"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--arms", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--warehouse", action="store_true")
    parser.add_argument("--skip-equivalence", action="store_true")
    parser.add_argument("--frame-profile", choices=("lean", "legacy"), default="lean",
                        help="SETUP frame_profile for every arm (lean: the new client's frame; legacy: the old dashboard's)")
    parser.add_argument("--quiet", type=float, default=60.0, help="seconds an arm may go without a message")
    parser.add_argument("--deadline", type=float, default=1800.0, help="seconds an arm may run in total")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir or REPO_ROOT / "benchmarks" / "results" / "frame-bench" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    arms = [{"label": f"Town {chr(65 + i)}", "initial_policy": {} if i == 0 else {"benefit_level": "high"}} for i in range(args.arms)]

    process, base_url = launch_server(warehouse=args.warehouse, sqlite_path=out_dir / "bench.db")
    started = time.perf_counter()
    try:
        results = run_experiment(base_url=base_url, arms=arms, households=args.households, ticks=args.ticks,
                                 seed=args.seed, warehouse=args.warehouse, quiet_seconds=args.quiet,
                                 deadline_seconds=args.deadline, frame_profile=args.frame_profile)
    finally:
        stop_server(process)
    wall = time.perf_counter() - started

    per_arm = {label: summarize(records) for label, records in results.items()}
    equivalence_result = None if args.skip_equivalence else equivalence(
        records_for_baseline=results[arms[0]["label"]], households=args.households, ticks=args.ticks, seed=args.seed)
    verdict = gate(per_arm, equivalence_result, require_equivalence=not args.skip_equivalence)
    code = exit_code(verdict)
    report = {"households": args.households, "ticks": args.ticks, "arms": args.arms, "seed": args.seed,
              "warehouse": args.warehouse, "frameProfile": args.frame_profile, "wallClockSeconds": wall, "perArm": per_arm,
              "equivalence": equivalence_result, "gate": verdict, "exitCode": code}
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2))
    lines = [f"# Frame bench: {args.arms} arms x {args.households} households, {args.ticks} ticks, seed {args.seed}, "
             f"warehouse {'on' if args.warehouse else 'off'}, frame profile {args.frame_profile}", "",
             f"- wall clock: {wall:.1f} s", ""]
    for label, summary in per_arm.items():
        lines += [f"## {label}",
                  f"- bytes p50 / p95 / max: {summary['bytes']['p50']:.0f} / {summary['bytes']['p95']:.0f} / {summary['bytes']['max']:.0f}",
                  f"- tick compute ms p50 / p95: {summary['tickComputeMs']['p50']:.1f} / {summary['tickComputeMs']['p95']:.1f}",
                  f"- projection ms p50 / p95: {summary['projectionMs']['p50']:.2f} / {summary['projectionMs']['p95']:.2f}",
                  f"- serialize ms p50 / p95: {summary['serializeMs']['p50']:.2f} / {summary['serializeMs']['p95']:.2f}",
                  f"- inter-frame ms p50 / p95: {summary['interFrameMs']['p50']:.1f} / {summary['interFrameMs']['p95']:.1f}", ""]
    lines += ["## Gate"]
    for label, arm in verdict["arms"].items():
        lines += [f"- {label}: bytes p95 {arm['bytesP95']:.0f} (limit {GATE_BYTES_P95}, {'ok' if arm['bytesOk'] else 'over'}); "
                  f"overhead share of tick (p50) {arm['overheadShare']:.1%} (limit {GATE_OVERHEAD_SHARE:.0%}, "
                  f"{'ok' if arm['overheadOk'] else 'over'})"]
    lines += [f"- failing arms: {verdict['failingArms']}", f"- checks: {verdict['checks']}",
              f"- measured checks passed: {verdict['passed']}", f"- phase gate passed: {verdict['phaseGate']}",
              f"- result: {_outcome(verdict)}"]
    if equivalence_result:
        lines += ["", "## Equivalence with the headless smoke runner",
                  "| frame tick | session | smoke (tick-1) | match |", "|---|---|---|---|"]
        lines += [f"| {r['tick']} | {r['session']} | {r['smoke']} | {r['match']} |" for r in equivalence_result["checkpoints"]]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
