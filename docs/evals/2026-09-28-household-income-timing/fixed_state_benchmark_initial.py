"""Supplement the evolving-world benchmark with identical pre-tick states.

Uses 10,000 households at weeks 40 and 41, covering full choice refreshes
and cached shopping. Copying, garbage collection and warmup are not timed.
"""

import argparse
import contextlib
import copy
import gc
import importlib.util
import io
import json
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from benchmark import ROOT, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("fixed-state.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from config import clone_config, use_config
    from economy import Economy as Candidate
    from tools.runners import run_large_simulation as runner

    spec = importlib.util.spec_from_file_location("timing_fixed_baseline", args.baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    baseline = module.Economy
    rows = []
    summaries = []
    bootstrap_rng = np.random.default_rng(937)
    for mode in ["normal", "performance"]:
        config = clone_config()
        config.random_seed = 1337
        config.payment_sequence = "legacy"
        with use_config(config), contextlib.redirect_stdout(io.StringIO()):
            random.seed(1337)
            np.random.seed(1337)
            runner.Economy = baseline
            source = runner.create_large_economy(10000, 5)
            source.performance_mode = mode == "performance"
            for _ in range(40):
                source.step()
            for tick in [40, 41]:
                python_rng, numpy_rng = random.getstate(), np.random.get_state()
                cell = []
                for repeat in range(5):
                    order = ["baseline", "candidate"] if repeat % 2 == 0 else ["candidate", "baseline"]
                    for kind in order:
                        economy = copy.deepcopy(source)
                        economy.__class__ = baseline if kind == "baseline" else Candidate
                        random.setstate(python_rng)
                        np.random.set_state(numpy_rng)
                        gc.collect()
                        start = time.perf_counter_ns()
                        economy.step()
                        elapsed = (time.perf_counter_ns() - start) / 1e6
                        cell.append({"mode": mode, "tick": tick, "repeat": repeat, "kind": kind,
                                     "ms": elapsed, "initial_firms": len(source.firms),
                                     "final_firms": len(economy.firms)})
                        del economy
                rows.extend(cell)
                before = np.array([r["ms"] for r in cell if r["kind"] == "baseline"])
                after = np.array([r["ms"] for r in cell if r["kind"] == "candidate"])
                changes = after / before - 1
                bootstrap = np.median(bootstrap_rng.choice(changes, (10000, 5), replace=True), axis=1) * 100
                summaries.append({
                    "mode": mode, "tick": tick, "initial_firms": len(source.firms),
                    "baseline_ms": statistics.median(before), "candidate_ms": statistics.median(after),
                    "paired_delta_pct": float(np.median(changes) * 100),
                    "ci95_pct": np.percentile(bootstrap, [2.5, 97.5]).tolist(),
                })
                random.setstate(python_rng)
                np.random.set_state(numpy_rng)
                source.step()
        print(json.dumps(summaries[-2:]), flush=True)
    args.output.write_text(json.dumps({
        "baseline_sha256": digest(args.baseline), "candidate_sha256": digest(ROOT / "backend/economy.py"),
        "script_sha256": digest(Path(__file__)), "households": 10000,
        "seed": 1337, "runs": rows, "summary": summaries,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
