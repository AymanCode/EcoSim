"""Interleave frozen baseline/candidate processes; retain ticks and workload.

Run from either source using the project virtualenv. Do not run CPU-heavy jobs
alongside this benchmark. The income-first arm changes economic behavior, so
its timing difference is a total observed cost, not a same-work algorithm cost.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import sys
import time


def digest_source(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "backend").rglob("*.py"))
            if "__pycache__" not in p.parts}


def worker(args):
    sys.path[:0] = [str(args.source / "backend"), str(args.source)]
    import numpy as np
    from config import clone_config, use_config
    from tools.runners.run_large_simulation import create_large_economy

    random.seed(args.seed)
    np.random.seed(args.seed)
    config = clone_config()
    config.random_seed = args.seed
    if hasattr(config, "payment_sequence"):
        config.payment_sequence = args.scenario
        config.payment_care_mode = "patient_pay"
        config.payment_assistance = "reserve"
    rows = []
    with use_config(config), contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(args.count, 10)
        economy.performance_mode = args.mode == "performance"
        economy.warmup_ticks = 5
        for tick in range(args.ticks):
            started = time.perf_counter_ns()
            economy.step()
            elapsed = (time.perf_counter_ns() - started) / 1e6
            rows.append({"tick": tick, "ms": elapsed,
                         "firms": len(economy.firms),
                         "employees": sum(len(f.employees) for f in economy.firms),
                         "care_queue": sum(len(f.healthcare_queue) for f in economy.firms),
                         "bank_loans": len(economy.bank.active_loans) if economy.bank else 0,
                         "wage_claims": len(getattr(economy, "payment_state", {}).get("wage_claims", {}))})
    sampled = [r["ms"] for r in rows if r["tick"] >= 10]
    result = {"source": str(args.source), "scenario": args.scenario,
              "households": args.count, "seed": args.seed, "mode": args.mode,
              "median_ms": statistics.median(sampled),
              "p95_ms": float(np.percentile(sampled, 95)),
              "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024),
              "ticks": rows}
    args.output.write_text(json.dumps(result, indent=2) + "\n")


def coordinator(args):
    args.output.mkdir(parents=True, exist_ok=True)
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    manifest = {"python": sys.version, "platform": platform.platform(),
                "cpu_count": os.cpu_count(), "ticks": args.ticks,
                "warmup_ticks": 5, "excluded_first_ticks": 10,
                "repeats": args.repeats, "seeds": args.seeds,
                "ordering": "Each block contains all arms; alternating forward/reverse order.",
                "workload_caveat": "income_first changes institutions and may change workload; compare candidate legacy separately",
                "sources": {key: digest_source(root) for key, root in roots.items()}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    runs = []
    block = 0
    for repeat in range(args.repeats):
        for count in args.counts:
            for mode in ("normal", "performance"):
                for seed in args.seeds:
                    arms = [("baseline", "legacy"), ("candidate", "legacy"), ("candidate", "income_first")]
                    if block % 2:
                        arms.reverse()
                    for source, scenario in arms:
                        name = f"r{repeat}-{count}-{mode}-s{seed}-{source}-{scenario}"
                        output = args.output / (name + ".json")
                        command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--source", str(roots[source]),
                                   "--scenario", scenario, "--count", str(count), "--mode", mode, "--seed", str(seed),
                                   "--ticks", str(args.ticks), "--output", str(output)]
                        subprocess.run(command, check=True, capture_output=True, text=True)
                        row = json.loads(output.read_text())
                        row.update(source_label=source, repeat=repeat, block=block, file=output.name)
                        runs.append({k: v for k, v in row.items() if k != "ticks"})
                        print(json.dumps({k: row[k] for k in ["file", "median_ms", "p95_ms", "peak_rss_mb"]}), flush=True)
                    block += 1
    summary = []
    for count in args.counts:
        for mode in ("normal", "performance"):
            matching = [r for r in runs if r["households"] == count and r["mode"] == mode]
            baseline = {r["block"]: r for r in matching if r["source_label"] == "baseline"}
            for scenario in ("legacy", "income_first"):
                candidates = [r for r in matching if r["source_label"] == "candidate" and r["scenario"] == scenario]
                item = {"households": count, "mode": mode, "scenario": scenario, "pairs": len(candidates)}
                for metric in ("median_ms", "p95_ms", "peak_rss_mb"):
                    changes = [100 * (r[metric] / baseline[r["block"]][metric] - 1) for r in candidates]
                    item[metric] = {"median_change_pct": statistics.median(changes), "min_change_pct": min(changes), "max_change_pct": max(changes)}
                item["all_pairs_within_5pct"] = all(r[metric] <= 1.05 * baseline[r["block"]][metric]
                                                   for r in candidates for metric in ("median_ms", "p95_ms"))
                summary.append(item)
    unchanged = {key: digest_source(root) == manifest["sources"][key] for key, root in roots.items()}
    result = {"source_unchanged": unchanged, "runs": runs, "summary": summary,
              "interpretation": "Range crossing +5% is not performance acceptance; no causal same-work claim for new behavior."}
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"source_unchanged": unchanged, "summary": summary}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", default="legacy")
    parser.add_argument("--counts", nargs="+", type=int, default=[1000, 10000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--count", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--mode", choices=["normal", "performance"])
    parser.add_argument("--ticks", type=int, default=50)
    args = parser.parse_args()
    worker(args) if args.worker else coordinator(args)


if __name__ == "__main__":
    main()
