"""Simulation throughput benchmark CLI.

Example:
    python -m backend.tools.benchmarks.run_sim_bench --households 1000,5000,10000 --ticks 80 --seeds 42,43,44 --profile
"""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import io
import pstats
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG
from tools.runners.run_large_simulation import create_large_economy

from .common import (
    BenchmarkPaths,
    build_run_id,
    collect_metadata,
    default_results_root,
    get_process_rss_mb,
    parse_int_list,
    write_json,
    write_markdown,
    write_rows_csv,
)
from .reporting import render_sim_summary, summarize_tick_rows


def _create_economy_quietly(num_households: int, firms_per_category: int, verbose: bool):
    if verbose:
        return create_large_economy(num_households, firms_per_category)
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(num_households, firms_per_category)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = int(seed)


def _phase_for_tick(tick_before: int, warmup_ticks: int, private_active_count: int, queued_firm_count: int) -> str:
    if tick_before < warmup_ticks:
        return "warmup"
    if private_active_count <= 0:
        return "post_warmup_baseline"
    if queued_firm_count > 0:
        return "private_firm_ramp"
    return "full_private_market"


def _profile_next_tick(economy, profile_path: Path, top_n: int) -> float:
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    economy.step()
    profiler.disable()
    elapsed = time.perf_counter() - started

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(top_n)
    profile_path.write_text(stream.getvalue(), encoding="utf-8")
    return elapsed


def run_sim_benchmark(
    *,
    households: list[int],
    seeds: list[int],
    ticks: int,
    warmup_ticks: int,
    firms_per_category: int,
    output_root: Path,
    profile: bool,
    profile_top: int,
    verbose: bool,
) -> dict[str, Any]:
    paths = BenchmarkPaths.create(output_root, "sim")
    tick_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    profile_paths: list[str] = []

    for household_count in households:
        for seed in seeds:
            _set_seed(seed)
            run_id = build_run_id("sim", {"households": household_count, "seed": seed})
            created_started = time.perf_counter()
            economy = _create_economy_quietly(household_count, firms_per_category, verbose=verbose)
            economy.warmup_ticks = warmup_ticks
            created_seconds = time.perf_counter() - created_started

            run_started = time.perf_counter()
            failed = False
            error = ""
            for _ in range(ticks):
                tick_before = int(economy.current_tick)
                step_started = time.perf_counter()
                try:
                    economy.step()
                except Exception as exc:  # pragma: no cover - surfaced in benchmark output
                    failed = True
                    error = f"{type(exc).__name__}: {exc}"
                    tick_rows.append(
                        {
                            "run_id": run_id,
                            "seed": seed,
                            "households": household_count,
                            "tick": tick_before,
                            "phase": "error",
                            "tick_duration_ms": round((time.perf_counter() - step_started) * 1000.0, 3),
                            "error": error,
                        }
                    )
                    break

                tick_duration_ms = (time.perf_counter() - step_started) * 1000.0
                private_active = sum(1 for firm in economy.firms if not getattr(firm, "is_baseline", False))
                queued_firms = len(getattr(economy, "queued_firms", []))
                unemployed = sum(1 for household in economy.households if not household.is_employed)
                tick_rows.append(
                    {
                        "run_id": run_id,
                        "seed": seed,
                        "households": household_count,
                        "firms_active": len(economy.firms),
                        "private_firms_active": private_active,
                        "firms_queued": queued_firms,
                        "tick": tick_before,
                        "tick_after": int(economy.current_tick),
                        "phase": _phase_for_tick(tick_before, warmup_ticks, private_active, queued_firms),
                        "tick_duration_ms": round(tick_duration_ms, 3),
                        "rss_mb": get_process_rss_mb(),
                        "unemployment_rate": round(unemployed / max(1, len(economy.households)), 6),
                        "error": "",
                    }
                )

            profile_elapsed = None
            if profile and not failed:
                profile_path = paths.run_dir / f"profile_{run_id}.txt"
                profile_elapsed = _profile_next_tick(economy, profile_path, profile_top)
                profile_paths.append(str(profile_path.relative_to(paths.run_dir)))

            run_elapsed = time.perf_counter() - run_started
            run_rows.append(
                {
                    "run_id": run_id,
                    "seed": seed,
                    "households": household_count,
                    "ticks_requested": ticks,
                    "ticks_completed": int(economy.current_tick),
                    "creation_seconds": round(created_seconds, 4),
                    "run_seconds": round(run_elapsed, 4),
                    "profile_seconds": round(profile_elapsed, 4) if profile_elapsed is not None else "",
                    "final_active_firms": len(economy.firms),
                    "final_queued_firms": len(getattr(economy, "queued_firms", [])),
                    "failed": failed,
                    "error": error,
                }
            )

    summary = summarize_tick_rows([row for row in tick_rows if not row.get("error")])
    metadata = collect_metadata(
        {
            "benchmark": "simulation-throughput",
            "households": households,
            "seeds": seeds,
            "ticks": ticks,
            "warmup_ticks": warmup_ticks,
            "firms_per_category": firms_per_category,
        }
    )
    markdown = render_sim_summary(metadata=metadata, summary=summary, profile_paths=profile_paths)

    tick_csv = write_rows_csv(paths, "tick_rows", tick_rows)
    run_csv = write_rows_csv(paths, "run_rows", run_rows)
    summary_md = write_markdown(paths, "summary", markdown)
    raw_json = write_json(
        paths,
        "raw",
        {
            "metadata": metadata,
            "summary": summary,
            "tick_rows": tick_rows,
            "run_rows": run_rows,
            "profile_paths": profile_paths,
            "artifacts": {
                "tick_csv": str(tick_csv.name),
                "run_csv": str(run_csv.name),
                "summary_md": str(summary_md.name),
            },
        },
    )
    return {
        "paths": paths,
        "metadata": metadata,
        "summary": summary,
        "tick_rows": tick_rows,
        "run_rows": run_rows,
        "artifacts": {
            "tick_csv": tick_csv,
            "run_csv": run_csv,
            "summary_md": summary_md,
            "raw_json": raw_json,
            "profiles": profile_paths,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark EcoSim simulation tick throughput.")
    parser.add_argument("--households", default="1000,5000,10000", help="Comma-separated household counts.")
    parser.add_argument("--ticks", type=int, default=80, help="Ticks per run.")
    parser.add_argument("--warmup-ticks", type=int, default=10, help="Warmup horizon used for phase labeling.")
    parser.add_argument("--seeds", default="42,43,44", help="Comma-separated random seeds.")
    parser.add_argument("--firms-per-category", type=int, default=10, help="Initial firms per category.")
    parser.add_argument("--profile", action="store_true", help="Profile one additional tick per run with cProfile.")
    parser.add_argument("--profile-top", type=int, default=30, help="Number of cProfile rows to write.")
    parser.add_argument("--output-root", type=Path, default=default_results_root(), help="Benchmark output root.")
    parser.add_argument("--verbose", action="store_true", help="Show economy construction logs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_sim_benchmark(
        households=parse_int_list(args.households),
        seeds=parse_int_list(args.seeds),
        ticks=args.ticks,
        warmup_ticks=args.warmup_ticks,
        firms_per_category=args.firms_per_category,
        output_root=args.output_root,
        profile=args.profile,
        profile_top=args.profile_top,
        verbose=args.verbose,
    )
    print(f"Wrote simulation benchmark artifacts to {result['paths'].run_dir}")
    print(f"p95 tick latency: {result['summary']['overall']['p95_ms']} ms")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
