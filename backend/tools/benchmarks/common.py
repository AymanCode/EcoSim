"""Shared utilities for EcoSim benchmark CLIs."""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def parse_int_list(value: str | Sequence[int]) -> list[int]:
    """Parse a comma-separated list of positive integers."""
    if isinstance(value, (list, tuple)):
        result = [int(item) for item in value]
    else:
        raw_parts = str(value).split(",")
        result = []
        for raw in raw_parts:
            part = raw.strip()
            if not part:
                raise ValueError(f"Integer list contains an empty entry: {value!r}")
            result.append(int(part))

    if not result:
        raise ValueError("Integer list must contain at least one value")
    if any(item <= 0 for item in result):
        raise ValueError(f"Integer list values must be positive: {result!r}")
    return result


def parse_str_list(value: str | Sequence[str]) -> list[str]:
    """Parse a comma-separated list of non-empty strings."""
    if isinstance(value, (list, tuple)):
        result = [str(item).strip() for item in value]
    else:
        result = [part.strip() for part in str(value).split(",")]
    if not result or any(not item for item in result):
        raise ValueError(f"String list contains an empty entry: {value!r}")
    return result


def percentile(values: Iterable[float], pct: float) -> float:
    """Return a nearest-rank percentile from an iterable of numeric values."""
    sorted_values = sorted(float(value) for value in values)
    if not sorted_values:
        return 0.0
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    rank = max(1, math.ceil((pct / 100.0) * len(sorted_values)))
    return sorted_values[rank - 1]


def mean(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def sample_stdev(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if len(items) < 2:
        return 0.0
    avg = mean(items)
    return math.sqrt(sum((item - avg) ** 2 for item in items) / (len(items) - 1))


def confidence_interval_95(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if len(items) < 2:
        return 0.0
    return 1.96 * sample_stdev(items) / math.sqrt(len(items))


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "benchmark"


def build_run_id(prefix: str, parts: Mapping[str, Any]) -> str:
    encoded_parts = [slugify(prefix)]
    for key in sorted(parts):
        encoded_parts.append(f"{slugify(str(key))}-{slugify(str(parts[key]))}")
    return "-".join(encoded_parts)


@dataclass(frozen=True)
class BenchmarkPaths:
    """Filesystem locations for one benchmark run."""

    root: Path
    run_dir: Path

    @classmethod
    def create(cls, root: str | Path, kind: str, timestamp: str | None = None) -> "BenchmarkPaths":
        root_path = Path(root)
        timestamp = timestamp or dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
        base_name = f"{timestamp}-{slugify(kind)}"
        run_dir = root_path / base_name
        suffix = 1
        while run_dir.exists():
            suffix += 1
            run_dir = root_path / f"{base_name}-{suffix}"
        run_dir.mkdir(parents=True, exist_ok=False)
        return cls(root=root_path, run_dir=run_dir)


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def write_json(paths: BenchmarkPaths, stem: str, payload: Mapping[str, Any]) -> Path:
    path = paths.run_dir / f"{slugify(stem)}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=json_default), encoding="utf-8")
    return path


def write_rows_csv(paths: BenchmarkPaths, stem: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    path = paths.run_dir / f"{slugify(stem)}.csv"
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return path


def write_markdown(paths: BenchmarkPaths, stem: str, markdown: str) -> Path:
    path = paths.run_dir / f"{slugify(stem)}.md"
    path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_results_root() -> Path:
    return repo_root() / "benchmarks" / "results"


def _git_output(args: Sequence[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def collect_metadata(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Collect runtime metadata that makes benchmark claims reproducible."""
    metadata: dict[str, Any] = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commit": _git_output(["rev-parse", "--short", "HEAD"]) or "unknown",
        "git_dirty": bool(_git_output(["status", "--short"])),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "logical_cpu_count": os.cpu_count() or 0,
    }
    if extra:
        metadata.update(dict(extra))
    return metadata


def get_process_rss_mb() -> float | None:
    """Return current process RSS in MB when available without third-party packages."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            ctypes.windll.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if ok:
                return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            return None
        return None

    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return float(usage) / (1024.0 * 1024.0)
        return float(usage) / 1024.0
    except Exception:
        return None
