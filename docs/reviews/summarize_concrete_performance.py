"""Archive and summarize the completed W05 benchmark recordings."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics


def percentile(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * p / 100) - 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    dest = args.repo / "docs/reviews/evidence/performance"
    dest.mkdir(parents=True, exist_ok=True)
    records = []
    groups = {}
    for mode, suffix in [("normal", "results"), ("performance", "performance-results")]:
        for version in ["baseline", "candidate"]:
            completed = sorted((args.raw_root / f"{version}-{suffix}").glob("*/package-conditions.json"))
            assert len(completed) == 2, (mode, version, len(completed))
            combined = []
            runs = []
            repeat_stats = []
            for repeat, conditions_path in enumerate(completed):
                conditions = json.loads(conditions_path.read_text())
                data = json.loads((conditions_path.parent / "raw.json").read_text())
                assert all(not r["failed"] and r["ticks_completed"] == 100 for r in data["run_rows"])
                assert len(data["tick_rows"]) == 100 * len(data["run_rows"])
                assert conditions["performance_mode"] == (mode == "performance")
                data["package_conditions"] = conditions
                path = dest / f"{mode}-{version}-repeat{repeat}.json"
                path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                records.append(
                    {"path": str(path.relative_to(args.repo)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                )
                combined.extend(data["tick_rows"])
                runs.extend(data["run_rows"])
                repeat_stats.append(
                    {
                        str(n): {
                            "p50_ms": percentile(
                                [r["tick_duration_ms"] for r in data["tick_rows"] if r["households"] == n], 50
                            ),
                            "p95_ms": percentile(
                                [r["tick_duration_ms"] for r in data["tick_rows"] if r["households"] == n], 95
                            ),
                        }
                        for n in [1000, 10000]
                    }
                )
            groups[f"{mode}:{version}"] = {
                "peak_process_rss_mb": max(r["rss_mb"] for r in combined),
                "repeats": repeat_stats,
                "cells": {
                    str(n): {
                        "ticks": len([r for r in combined if r["households"] == n]),
                        "p50_ms": percentile([r["tick_duration_ms"] for r in combined if r["households"] == n], 50),
                        "p95_ms": percentile([r["tick_duration_ms"] for r in combined if r["households"] == n], 95),
                        "mean_ms": statistics.mean(r["tick_duration_ms"] for r in combined if r["households"] == n),
                        "phase_counts": dict(Counter(r["phase"] for r in combined if r["households"] == n)),
                        "final_firms": [r["final_active_firms"] for r in runs if r["households"] == n],
                        "run_seconds": [r["run_seconds"] for r in runs if r["households"] == n],
                    }
                    for n in [1000, 10000]
                },
            }
    comparisons = []
    for mode in ["normal", "performance"]:
        for n in [1000, 10000]:
            base, cand = [groups[f"{mode}:{version}"]["cells"][str(n)] for version in ["baseline", "candidate"]]
            comparisons.append(
                {
                    "mode": mode,
                    "households": n,
                    "baseline_p50_ms": base["p50_ms"],
                    "candidate_p50_ms": cand["p50_ms"],
                    "p50_change_percent": 100 * (cand["p50_ms"] / base["p50_ms"] - 1),
                    "baseline_p95_ms": base["p95_ms"],
                    "candidate_p95_ms": cand["p95_ms"],
                    "p95_change_percent": 100 * (cand["p95_ms"] / base["p95_ms"] - 1),
                    "mean_change_percent": 100 * (cand["mean_ms"] / base["mean_ms"] - 1),
                }
            )
    engine_files = [
        "backend/agents.py",
        "backend/economy.py",
        "backend/config.py",
        "backend/policy_schema.py",
        "backend/tools/runners/run_large_simulation.py",
        "backend/tools/benchmarks/run_sim_bench.py",
        "backend/tools/benchmarks/common.py",
        "backend/tools/benchmarks/reporting.py",
    ]
    identity = {
        version: {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in engine_files}
        for version, root in [("baseline", args.raw_root / "baseline"), ("candidate", args.repo)]
    }
    result = {
        "baseline_commit": "4f693890b5f133c2c6c1dcbec9b1ec91ced97b46",
        "engine_files_sha256": identity,
        "conditions": {
            "normal_seeds": [42, 43, 44],
            "performance_seeds": [42],
            "repeats": 2,
            "ticks": 100,
            "households": [1000, 10000],
            "firms_per_category": 10,
            "warmup_ticks": 10,
            "budget_percent": 5,
            "memory_semantics": "Process high-water RSS, not isolated per-population live memory.",
        },
        "groups": groups,
        "comparisons": comparisons,
        "raw_artifacts": records,
    }
    output = args.repo / "docs/reviews/evidence/ECONOMIC_CONCRETE_PERFORMANCE.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"comparisons": comparisons, "memory_mb": {k: v["peak_process_rss_mb"] for k, v in groups.items()}},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
