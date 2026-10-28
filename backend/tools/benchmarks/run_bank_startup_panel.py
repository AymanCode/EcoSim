"""Run the predeclared frozen bank-startup panel with at most two workers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def tree_hash(root):
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
            files[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def main():
    artifact = Path(sys.argv[1]).resolve()
    roots = {"old": artifact / "baseline", "new": artifact / "candidate-v5"}
    for p in (artifact / "cases", artifact / "specs", artifact / "logs"):
        p.mkdir(parents=True, exist_ok=True)
    worker = roots["new"] / "backend/tools/benchmarks/bank_startup_panel_worker.py"
    hashes = {name: tree_hash(path) for name, path in roots.items()}
    manifest = {"source_files_sha256": hashes, "worker": str(worker),
                "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
                "python": sys.version, "platform": platform.platform(), "pythonhashseed": "0",
                "workers": 2, "households": 1000, "firms_per_category": 5, "ticks": 140,
                "windows_inclusive": [[60, 80], [104, 140]], "seeds": [4242, 101, 777],
                "sequences": ["income_first", "income_late"], "benefits": ["neutral", "high"],
                "baseline_zip_sha256": hashlib.sha256((artifact / "baseline-b233cd7.zip").read_bytes()).hexdigest()}
    (artifact / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    cases = []
    for sequence in manifest["sequences"]:
        for benefit in manifest["benefits"]:
            for seed in manifest["seeds"]:
                for version in ("old", "new"):
                    name = f"{sequence}-{benefit}-{seed}-{version}"
                    cases.append((name, version, sequence, benefit, seed, version == "new"))
    cases += [("income_first-neutral-4242-old-replay", "old", "income_first", "neutral", 4242, False),
              ("income_first-neutral-4242-new-flag-off", "new", "income_first", "neutral", 4242, False)]
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    def one(case):
        name, version, sequence, benefit, seed, enabled = case
        sp = {"root": str(roots[version]), "seed": seed, "households": 1000,
              "firms_per_category": 5, "payment_sequence": sequence, "enabled": enabled,
              "benefit": benefit, "ticks": 140}
        path = artifact / "specs" / (name + ".json")
        path.write_text(json.dumps(sp, indent=2), encoding="utf-8")
        if tree_hash(roots[version]) != hashes[version]:
            raise RuntimeError(f"Source changed before {name}")
        with (artifact / "logs" / (name + ".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, str(worker), str(path), str(artifact / "cases" / (name + ".json"))],
                                    stdout=log, stderr=subprocess.STDOUT, env=env, check=False)
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}); see {log.name}")
        if tree_hash(roots[version]) != hashes[version]:
            raise RuntimeError(f"Source changed during {name}; preserve incomplete evidence")
        return name
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, c) for c in cases]
        for done in as_completed(futures):
            print("completed", done.result(), flush=True)
    print("all cases complete", flush=True)


if __name__ == "__main__":
    main()
