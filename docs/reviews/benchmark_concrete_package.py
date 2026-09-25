"""Reproduce W05 timing using the repository's existing engine benchmark.

Run with the project virtualenv. --source-root can name the frozen baseline
archive or the candidate repository. Do not run heavy tests alongside timings.
"""

import argparse
import dataclasses
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--households", default="1000,10000")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--performance-mode", action="store_true")
    args = parser.parse_args()
    root = args.source_root.resolve()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "backend"))
    from config import get_config
    from backend.tools.benchmarks import run_sim_bench as bench

    original = bench.create_large_economy

    def factory(*positional, **kwargs):
        eco = original(*positional, **kwargs)
        eco.performance_mode = args.performance_mode
        return eco

    bench.create_large_economy = factory
    for repeat in range(args.repeats):
        result = bench.run_sim_benchmark(
            households=[int(v) for v in args.households.split(",")],
            seeds=[int(v) for v in args.seeds.split(",")],
            ticks=args.ticks,
            warmup_ticks=10,
            firms_per_category=10,
            output_root=args.output_root,
            profile=False,
            profile_top=30,
            verbose=False,
        )
        run_dir = result["paths"].run_dir
        (run_dir / "package-conditions.json").write_text(
            json.dumps(
                {
                    "performance_mode": args.performance_mode,
                    "repeat": repeat,
                    "source_root": str(root),
                    "effective_config": dataclasses.asdict(get_config()),
                    "per_run_seed": "Override effective_config.random_seed with each run_rows seed.",
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps({"mode": args.performance_mode, "repeat": repeat, "path": str(run_dir)}), flush=True)
        if any(row["failed"] for row in result["run_rows"]):
            raise SystemExit("Benchmark run failed; inspect raw evidence.")


if __name__ == "__main__":
    main()
