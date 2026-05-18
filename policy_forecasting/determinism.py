"""Measure-not-fix determinism harness."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from policy_forecasting.config import arm_by_id
from policy_forecasting.sweep.wrapper import _backend_imports, run_single_policy


def hash_metric_rows(rows: list[dict[str, Any]]) -> str:
    """Hash the full per-tick row series with no rounding."""
    import hashlib

    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def replicate_delta_distribution(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, float]:
    """Compute absolute numeric replicate deltas across matched tick rows."""
    left_frame = pd.DataFrame(left).sort_values(["tick"]).reset_index(drop=True)
    right_frame = pd.DataFrame(right).sort_values(["tick"]).reset_index(drop=True)
    shared = min(len(left_frame), len(right_frame))
    if shared == 0:
        return {"count": 0, "max_abs_delta": float("nan"), "p95_abs_delta": float("nan"), "p99_abs_delta": float("nan")}
    left_frame = left_frame.iloc[:shared]
    right_frame = right_frame.iloc[:shared]
    numeric_cols = [
        col
        for col in left_frame.columns
        if col in right_frame.columns
        and col not in {"seed", "tick"}
        and pd.api.types.is_numeric_dtype(left_frame[col])
        and pd.api.types.is_numeric_dtype(right_frame[col])
    ]
    if not numeric_cols:
        return {"count": 0, "max_abs_delta": 0.0, "p95_abs_delta": 0.0, "p99_abs_delta": 0.0}
    deltas = (left_frame[numeric_cols].astype(float) - right_frame[numeric_cols].astype(float)).abs().to_numpy().ravel()
    return {
        "count": int(deltas.size),
        "max_abs_delta": float(np.max(deltas)),
        "p95_abs_delta": float(np.percentile(deltas, 95)),
        "p99_abs_delta": float(np.percentile(deltas, 99)),
    }


def _child_payload(args: argparse.Namespace) -> dict[str, Any]:
    _backend_imports()
    with contextlib.redirect_stdout(io.StringIO()):
        rows = run_single_policy(
            arm_by_id(args.arm),
            seed=args.seed,
            households=args.households,
            ticks=args.ticks,
            firms_per_category=args.firms_per_category,
            verbose=False,
        )
    return {"hash": hash_metric_rows(rows), "rows": rows}


def run_fresh_process(
    *,
    arm: str,
    seed: int,
    households: int,
    ticks: int,
    firms_per_category: int,
) -> dict[str, Any]:
    """Run one replicate in a fresh process with PYTHONHASHSEED=0."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "policy_forecasting.determinism",
        "--child",
        "--arm",
        arm,
        "--seed",
        str(seed),
        "--households",
        str(households),
        "--ticks",
        str(ticks),
        "--firms-per-category",
        str(firms_per_category),
    ]
    completed = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Replicate failed: {completed.stderr}")
    return json.loads(completed.stdout)


def measure_determinism(
    *,
    arm: str,
    seed: int,
    households: int,
    ticks: int,
    firms_per_category: int = 10,
) -> dict[str, Any]:
    """Run two fresh-process replicates and report hash equality plus noise floor."""
    first = run_fresh_process(
        arm=arm,
        seed=seed,
        households=households,
        ticks=ticks,
        firms_per_category=firms_per_category,
    )
    second = run_fresh_process(
        arm=arm,
        seed=seed,
        households=households,
        ticks=ticks,
        firms_per_category=firms_per_category,
    )
    return {
        "arm": arm,
        "seed": int(seed),
        "households": int(households),
        "ticks": int(ticks),
        "hash_equal": first["hash"] == second["hash"],
        "hashes": [first["hash"], second["hash"]],
        "replicate_delta_distribution": replicate_delta_distribution(first["rows"], second["rows"]),
        "interpretive_rule": (
            "Compare treatment effects against this replicate-delta noise band; "
            "do not subtract it as a correction."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure EcoSim run-to-run determinism.")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--arm", default="baseline")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.child:
        print(json.dumps(_child_payload(args), sort_keys=True, default=str))
        return 0
    report = measure_determinism(
        arm=args.arm,
        seed=args.seed,
        households=args.households,
        ticks=args.ticks,
        firms_per_category=args.firms_per_category,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
