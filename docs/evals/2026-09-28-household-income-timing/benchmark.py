"""Reproduce or extend the paired household-income timing measurements.

Run from the repo with .venv/bin/python. --baseline points to economy.py
extracted from commit 17d5c0b; all other engine dependencies must be unchanged.
"""

import argparse
import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import platform
import random
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(args):
    sys.path.insert(0, str(ROOT / "backend"))
    from config import clone_config, use_config
    from economy import Economy as Candidate
    from tools.runners import run_large_simulation as runner

    spec = importlib.util.spec_from_file_location("timing_baseline_economy", args.baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    baseline = module.Economy
    config = clone_config()
    config.random_seed = 1337
    config.payment_sequence = "legacy"
    with use_config(config), contextlib.redirect_stdout(io.StringIO()):
        random.seed(1337)
        np.random.seed(1337)
        runner.Economy = baseline
        economy = runner.create_large_economy(args.households, 5)
        economy.performance_mode = args.mode == "performance"
        for _ in range(40):
            economy.step()
        economy.__class__ = baseline if args.worker == "baseline" else Candidate
        initial_firms = len(economy.firms)
        elapsed = []
        for _ in range(12):
            start = time.perf_counter_ns()
            economy.step()
            elapsed.append((time.perf_counter_ns() - start) / 1e6)
        rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            rss_bytes *= 1024
        payload = {
            "kind": args.worker, "households": args.households, "mode": args.mode,
            "ms": elapsed, "initial_firms": initial_firms,
            "final_firms": len(economy.firms), "rss_mb": rss_bytes / (1024 * 1024),
            "configuration": dataclasses.asdict(config),
        }
    print(json.dumps(payload))


def summarize(rows):
    rng = np.random.default_rng(937)
    summaries = []
    for size, mode in sorted({(r["households"], r["mode"]) for r in rows}):
        cell = [r for r in rows if r["households"] == size and r["mode"] == mode]
        baseline = sorted([r for r in cell if r["kind"] == "baseline"], key=lambda r: r["repeat"])
        candidate = sorted([r for r in cell if r["kind"] == "candidate"], key=lambda r: r["repeat"])
        assert [r["repeat"] for r in baseline] == [r["repeat"] for r in candidate]
        summary = {
            "households": size, "mode": mode, "pairs": len(baseline),
            "rss_baseline_mb": statistics.median(r["rss_mb"] for r in baseline),
            "rss_candidate_mb": statistics.median(r["rss_mb"] for r in candidate),
            "initial_firms": baseline[0]["initial_firms"],
            "final_firms_baseline": baseline[0]["final_firms"],
            "final_firms_candidate": candidate[0]["final_firms"],
        }
        for metric, percentile in [("median", 50), ("p95", 95)]:
            before = np.array([np.percentile(r["ms"], percentile) for r in baseline])
            after = np.array([np.percentile(r["ms"], percentile) for r in candidate])
            ratios = after / before - 1
            bootstrap = np.median(rng.choice(ratios, (10000, len(ratios)), replace=True), axis=1) * 100
            summary[metric] = {
                "baseline_ms": float(np.median(before)), "candidate_ms": float(np.median(after)),
                "paired_delta_pct": float(np.median(ratios) * 100),
                "ci95_pct": np.percentile(bootstrap, [2.5, 97.5]).tolist(),
            }
        summaries.append(summary)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("benchmark.json"))
    parser.add_argument("--append", action="store_true", help="Keep all samples and add pairs up to --repeats")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sizes", default="1000,10000")
    parser.add_argument("--modes", default="normal,performance")
    parser.add_argument("--worker", choices=["baseline", "candidate"])
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--mode", choices=["normal", "performance"], default="normal")
    args = parser.parse_args()
    args.baseline = args.baseline.resolve()
    if args.worker:
        return worker(args)

    identity = {
        "platform": platform.platform(), "python": platform.python_version(),
        "baseline_sha256": digest(args.baseline), "candidate_sha256": digest(ROOT / "backend/economy.py"),
    }
    report = json.loads(args.output.read_text()) if args.append else {**identity, "runs": []}
    for key, value in identity.items():
        if report[key] != value:
            raise ValueError(f"Cannot combine measurements with different {key}")
    report["benchmark_script_sha256"] = digest(Path(__file__))
    report["dependency_sha256"] = {
        path: digest(ROOT / path) for path in (
            "backend/agents.py", "backend/config.py", "backend/tools/runners/run_large_simulation.py",
        )
    }
    rows = report["runs"]
    for size in map(int, args.sizes.split(",")):
        for mode in args.modes.split(","):
            completed = [r["repeat"] for r in rows if r["households"] == size and r["mode"] == mode]
            for repeat in range(max(completed, default=-1) + 1, args.repeats):
                pair = []
                order = ["baseline", "candidate"] if repeat % 2 == 0 else ["candidate", "baseline"]
                for kind in order:
                    if digest(ROOT / "backend/economy.py") != identity["candidate_sha256"]:
                        raise ValueError("Engine changed during the benchmark")
                    command = [sys.executable, __file__, "--baseline", str(args.baseline),
                               "--worker", kind, "--households", str(size), "--mode", mode]
                    run = subprocess.run(command, capture_output=True, text=True, check=True)
                    row = json.loads(run.stdout)
                    row["repeat"] = repeat
                    pair.append(row)
                rows.extend(pair)
                report["summary"] = summarize(rows)
                args.output.write_text(json.dumps(report, indent=2) + "\n")
                print(size, mode, repeat, {r["kind"]: round(statistics.median(r["ms"]), 3) for r in pair}, flush=True)
    report["summary"] = summarize(rows)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
