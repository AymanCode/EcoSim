"""Live dashboard WebSocket responsiveness probe.

This benchmark expects the FastAPI backend to already be running.

Example:
    python -m backend.tools.benchmarks.run_dashboard_bench --households 1000 --ticks 25
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import websockets

from .common import (
    BenchmarkPaths,
    collect_metadata,
    default_results_root,
    percentile,
    write_json,
    write_markdown,
    write_rows_csv,
)


async def _probe(
    *,
    url: str,
    households: int,
    firms_per_category: int,
    seed: int,
    ticks: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    async with websockets.connect(url, max_size=8 * 1024 * 1024, open_timeout=timeout_seconds) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "command": "SETUP",
                    "config": {
                        "num_households": households,
                        "num_firms": firms_per_category,
                        "seed": seed,
                        "enable_llm_government": False,
                    },
                }
            )
        )
        await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
        await websocket.send(json.dumps({"command": "START"}))

        last_received_at: float | None = None
        while len(rows) < ticks:
            raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            received_at = time.perf_counter()
            payload_bytes = len(raw.encode("utf-8"))
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "metrics" not in payload:
                continue
            metrics = payload.get("metrics", {})
            rows.append(
                {
                    "tick": payload.get("tick", len(rows)),
                    "payload_bytes": payload_bytes,
                    "interarrival_ms": round((received_at - last_received_at) * 1000.0, 3) if last_received_at else 0.0,
                    "backend_tick_compute_ms": float(metrics.get("tickComputeMs", 0.0) or 0.0),
                    "tracked_subjects": len(metrics.get("trackedSubjects", []) or []),
                    "tracked_firms": len(metrics.get("trackedFirms", []) or []),
                }
            )
            last_received_at = received_at

        await websocket.send(json.dumps({"command": "STOP"}))
    return rows


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    payloads = [float(row["payload_bytes"]) for row in rows]
    interarrival = [float(row["interarrival_ms"]) for row in rows if float(row["interarrival_ms"]) > 0]
    compute = [float(row["backend_tick_compute_ms"]) for row in rows]
    return {
        "tick_messages": len(rows),
        "p95_payload_bytes": percentile(payloads, 95),
        "p95_interarrival_ms": percentile(interarrival, 95),
        "p95_backend_tick_compute_ms": percentile(compute, 95),
        "mean_payload_bytes": round(sum(payloads) / len(payloads), 2) if payloads else 0.0,
    }


def _render_summary(metadata: dict[str, Any], summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# EcoSim Dashboard Responsiveness Benchmark",
            "",
            "## Runtime Context",
            "",
            f"- Commit: `{metadata.get('commit', 'unknown')}`",
            f"- Python: `{metadata.get('python', 'unknown')}`",
            f"- Platform: `{metadata.get('platform', 'unknown')}`",
            f"- WebSocket URL: `{metadata.get('url', 'unknown')}`",
            "",
            "## Results",
            "",
            f"- Tick messages: `{summary['tick_messages']}`",
            f"- p95 payload size: `{summary['p95_payload_bytes']} bytes`",
            f"- p95 message inter-arrival: `{summary['p95_interarrival_ms']} ms`",
            f"- p95 backend tick compute: `{summary['p95_backend_tick_compute_ms']} ms`",
            "",
            "## Resume Bullet Drafts",
            "",
            (
                "- Benchmarked live WebSocket dashboard responsiveness for EcoSim, measuring payload size, "
                "message cadence, and backend tick compute time under configurable agent loads."
            ),
        ]
    )


async def run_dashboard_benchmark(
    *,
    url: str,
    households: int,
    firms_per_category: int,
    seed: int,
    ticks: int,
    timeout_seconds: float,
    output_root: Path,
) -> dict[str, Any]:
    paths = BenchmarkPaths.create(output_root, "dashboard")
    rows = await _probe(
        url=url,
        households=households,
        firms_per_category=firms_per_category,
        seed=seed,
        ticks=ticks,
        timeout_seconds=timeout_seconds,
    )
    summary = _summarize(rows)
    metadata = collect_metadata(
        {
            "benchmark": "dashboard-websocket",
            "url": url,
            "households": households,
            "firms_per_category": firms_per_category,
            "seed": seed,
            "ticks": ticks,
        }
    )
    rows_csv = write_rows_csv(paths, "dashboard_rows", rows)
    summary_md = write_markdown(paths, "summary", _render_summary(metadata, summary))
    raw_json = write_json(paths, "raw", {"metadata": metadata, "summary": summary, "rows": rows})
    return {"paths": paths, "metadata": metadata, "summary": summary, "rows": rows, "artifacts": {"rows_csv": rows_csv, "summary_md": summary_md, "raw_json": raw_json}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe live EcoSim dashboard WebSocket responsiveness.")
    parser.add_argument("--url", default="ws://127.0.0.1:8002/ws")
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output-root", type=Path, default=default_results_root())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = asyncio.run(
        run_dashboard_benchmark(
            url=args.url,
            households=args.households,
            firms_per_category=args.firms_per_category,
            seed=args.seed,
            ticks=args.ticks,
            timeout_seconds=args.timeout_seconds,
            output_root=args.output_root,
        )
    )
    print(f"Wrote dashboard benchmark artifacts to {result['paths'].run_dir}")
    print(f"p95 backend tick compute: {result['summary']['p95_backend_tick_compute_ms']} ms")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
