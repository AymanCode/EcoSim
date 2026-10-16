"""Validate the benchmark's artifacts; its CLI alone does not fail on run errors."""

import hashlib
import json
from pathlib import Path
import sys


def verify(root: Path) -> dict:
    raw_files = list(root.glob("*/raw.json"))
    if len(raw_files) != 1:
        raise ValueError("Expected exactly one benchmark output directory")
    raw = raw_files[0]
    payload = json.loads(raw.read_text())
    runs = payload["run_rows"]
    if len(runs) != 3 or {r["seed"] for r in runs} != {42, 43, 44}:
        raise ValueError("Expected exactly three seeded runs: 42, 43, 44")
    for run in runs:
        if run["failed"] is not False or run["error"]:
            raise ValueError(f"Benchmark failed: {run}")
        if (run["households"], run["ticks_requested"], run["ticks_completed"]) != (1000, 80, 80):
            raise ValueError(f"Incomplete or unexpected workload: {run}")
    rows = payload["tick_rows"]
    if len(rows) != 240 or any(row.get("error") for row in rows):
        raise ValueError("Expected 240 error-free tick records")
    checksums = {}
    for name in ("raw.json", "tick_rows.csv", "run_rows.csv", "summary.md"):
        path = raw.parent / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty artifact: {name}")
        checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"verified": True, "runs": runs, "total_ticks": len(rows), "sha256": checksums}


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
