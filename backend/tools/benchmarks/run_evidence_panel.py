"""Standard paired evidence panel for PRs that change economic behavior.

One command runs every arm on every payment sequence and seed at the dashboard's
defaults, each run in its own process, and writes one table by tick window.
The O9 invocation is unchanged; the defaults below are what it picks up:

    python -m backend.tools.benchmarks.run_evidence_panel \\
        --arm main --root main ../main \\
        --arm off \\
        --arm on --set on households.skills_dynamics=True \\
        --baseline main --out benchmarks/results/pr51-panel

Defaults: 1,000 households, 5 firms per category, seeds 42-46 (escalating to
42-54 when a judged result is fragile), 312 ticks, windows 1-100 (reported, not
judged) / 101-200 / 201-312 (judged) / 261-312 (judged). ``--weeks 260`` still
selects a 260-tick run; the 261-312 window is then dropped and 201-312 is clipped.

``--set ARM section.field=value`` overrides a config field before the economy
is built. ``--set ARM lever.name=value`` applies a policy lever after it, and
``lever.name=value@START`` or ``@START..END`` applies it on that week and puts
the old value back after END. ``--off-set`` is ``--set off``. ``--sweep`` and
``--interact`` add the ±50% and a/b/a+b arms. ``--hook ARM k06_hold_pool`` keeps
the misc pool on the money stock. ``--metrics-plugin`` may be repeated.

Rerunning the same command reuses a finished run only if its settings, simulation
source, measuring code, worker Python and numpy, dependency lock and thread
settings are unchanged. The panel refuses to start unless the worker is CPython
3.11 and the installed packages match ``backend/requirements.lock``, unless
``--allow-nonref`` is set, which stamps every output as not comparable.

Outputs: ``panel.md``, ``panel.json``, ``evaluator.json``, ``window_values.csv``,
and ``runs/``.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from run_evidence import model_identity

from .common import BenchmarkPaths, default_results_root, parse_int_list, parse_str_list, repo_root
from .panel_summary import (
    CANONICAL_SEEDS,
    ESCALATION_SEEDS,
    MONEY_CHECK_MODE,
    WITHIN_RUN_NOTE,
    comparability_label,
    host_stamp,
    attach_paid_real_gdp,
    check_failures,
    clip_default_windows,
    compare_lock,
    escalation_reasons,
    evaluate_bounds,
    evaluate_money,
    first_divergence,
    format_reference_error,
    legacy_last_exit,
    load_plugin_module,
    lock_sha256,
    mutation_check,
    parse_lock_pins,
    plugin_display,
    plugin_summaries,
    probe_installed_versions,
    reference_decision,
    reference_python,
    unemployment_report,
    window_role,
)

WORKER = Path(__file__).with_name("evidence_panel_worker.py")
PAYMENT_SEQUENCES = ("income_first", "income_late", "legacy")
PYTHONHASHSEED = "0"
THREAD_ENV = {
    name: "1"
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
}
RUNTIME_PROBE = """
import json, os, platform, sys
from pathlib import Path
import numpy
cpu = platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER', 'unknown')
info = Path('/proc/cpuinfo')
if info.is_file():
    for line in info.read_text().splitlines():
        if line.startswith('model name'):
            cpu = line.partition(':')[2].strip()
            break
print(json.dumps({'python': platform.python_version(),
    'implementation': platform.python_implementation(), 'numpy': numpy.__version__,
    'executable': sys.executable, 'platform': platform.platform(),
    'system': platform.system(), 'machine': platform.machine(), 'cpu_model': cpu}))
"""
DEFAULT_WINDOWS = "1-100,101-200,201-312,261-312"
DEFAULT_TICKS = 312
ARM_NAME = re.compile(r"^[a-z0-9][a-z0-9._+-]*$")
LOCK_PATH = BACKEND_ROOT / "requirements.lock"

# (key, label, display scale, unit, aggregations). Shares are shown in percent,
# so their differences read in percentage points.
METRICS: tuple[tuple[str, str, float, str, tuple[str, ...]], ...] = (
    ("labor_force_unemployment_rate", "Unemployment, labour force", 100.0, "%", ("mean", "cv", "cv_detrended")),
    ("unemployment_rate", "Jobless, all households (dashboard)", 100.0, "%", ("mean",)),
    ("job_finding_rate", "Job-finding rate (U to E / U)", 100.0, "%", ("mean",)),
    ("layoffs_per_month", "Planned layoffs per month", 1.0, "people/month", ("mean",)),
    ("openings_per_unemployed", "Openings per unemployed", 1.0, "ratio", ("mean",)),
    ("real_gdp_paid", "Real GDP (units x base paid price)", 1.0, "$/wk", ("mean", "cv", "cv_detrended")),
    ("real_gdp", "Real GDP (GDP / CPI x 100)", 1.0, "$/wk", ("mean", "cv", "cv_detrended")),
    ("gdp", "Nominal GDP", 1.0, "$/wk", ("mean", "cv", "cv_detrended")),
    ("food_services_units_sold", "Food + Services units sold", 1.0, "units/wk", ("mean",)),
    ("consumer_price_index", "Consumer price index", 1.0, "index", ("mean", "cv", "cv_detrended")),
    ("mean_price", "Mean posted price", 1.0, "$", ("mean",)),
    ("fiscal_balance", "Fiscal balance (revenue - spending)", 1.0, "$/wk", ("mean", "min")),
    ("government_cash", "Treasury cash", 1.0, "$", ("mean", "min", "neg_share")),
    ("bond_buy", "Bond buy paid to misc pool (K06)", 1.0, "$/wk", ("mean",)),
    ("legacy_firms", "Legacy firms active", 1.0, "firms", ("mean",)),
    ("legacy_headcount", "Legacy firm headcount", 1.0, "people", ("mean",)),
    ("legacy_profit", "Legacy firm profit", 1.0, "$/wk", ("mean",)),
    ("legacy_exits", "Legacy firm exits", 1.0, "exits", ("sum",)),
    ("private_profit", "Private firm profit", 1.0, "$/wk", ("mean",)),
    ("private_firms", "Private firms", 1.0, "firms", ("mean",)),
    ("private_headcount", "Private firm headcount", 1.0, "people", ("mean",)),
    ("poverty_share", "Poverty (liquid < $200)", 100.0, "%", ("mean",)),
    ("extreme_poverty_share", "Extreme poverty (liquid < extreme line)", 100.0, "%", ("mean",)),
    ("food_sufficient_share", "Households eating minimum food", 100.0, "%", ("mean",)),
    ("happiness", "Happiness", 1.0, "index", ("mean", "cv", "cv_detrended")),
    ("happiness_median", "Happiness median", 1.0, "index", ("mean",)),
    ("happiness_p10", "Happiness p10", 1.0, "index", ("mean",)),
    ("happiness_p90", "Happiness p90", 1.0, "index", ("mean",)),
    ("happiness_le_005", "Happiness share <= 0.05", 100.0, "%", ("mean",)),
    ("happiness_ge_095", "Happiness share >= 0.95", 100.0, "%", ("mean",)),
    ("health", "Health", 1.0, "index", ("mean",)),
    ("food_unmet_demand", "Unmet Food demand", 1.0, "units/wk", ("mean",)),
    ("services_unmet_demand", "Unmet Services demand", 1.0, "units/wk", ("mean",)),
    *(
        (f"liquid_wealth_p{p}", f"Liquid wealth p{p}", 1.0, "$", ("mean",))
        for p in range(10, 100, 10)
    ),
)
AGGREGATION_LABELS = {
    "mean": "",
    "min": "min",
    "max": "max",
    "sum": "sum",
    "neg_share": "share of weeks below 0",
    "cv": "within-window CV (sd/|mean|)",
    "cv_detrended": "detrended CV (residual sd/|mean|)",
}


# --------------------------------------------------------------------------- windows and statistics


def parse_windows(text: str, ticks: int) -> list[tuple[str, int, int]]:
    """Parse ``1-100,101-200,201-`` into inclusive tick ranges; an open end means the last tick."""
    windows = []
    for part in parse_str_list(text):
        start_text, _, end_text = part.partition("-")
        start = int(start_text)
        end = int(end_text) if end_text.strip() else ticks
        if not 1 <= start <= end <= ticks:
            raise ValueError(f"Window {part!r} must lie within ticks 1-{ticks}")
        windows.append((f"{start}-{end}", start, end))
    return windows


def resolve_windows(text: str, ticks: int) -> list[tuple[str, int, int]]:
    """The default window list clips to ``--weeks`` / ``--ticks``. An explicit list stays strict."""
    if text != DEFAULT_WINDOWS:
        return parse_windows(text, ticks)
    parts = []
    for part in parse_str_list(text):
        start_text, _, end_text = part.partition("-")
        parts.append((int(start_text), int(end_text) if end_text.strip() else ticks))
    return clip_default_windows(parts, ticks)


def _detrended_cv(values: list[float]) -> float | None:
    """sd of the residual from a linear tick trend, divided by |mean|. Not the sd of the mean."""
    n = len(values)
    if n < 3:
        return None
    mean_y = statistics.fmean(values)
    if mean_y == 0.0:
        return None
    mean_x = (n - 1) / 2.0
    var_x = sum((index - mean_x) ** 2 for index in range(n))
    if var_x == 0.0:
        return None
    slope = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values)) / var_x
    residuals = [value - (mean_y + slope * (index - mean_x)) for index, value in enumerate(values)]
    return statistics.pstdev(residuals) / abs(mean_y)


def aggregate(values: list[float], how: str) -> float | None:
    if not values:
        return None
    if how == "mean":
        return statistics.fmean(values)
    if how == "min":
        return min(values)
    if how == "max":
        return max(values)
    if how == "sum":
        return sum(values)
    if how == "neg_share":
        return sum(1 for value in values if value < 0.0) / len(values)
    if how == "cv":
        avg = statistics.fmean(values)
        return statistics.pstdev(values) / abs(avg) if avg else None
    if how == "cv_detrended":
        return _detrended_cv(values)
    raise ValueError(f"Unknown aggregation {how!r}")


def metric_specs(rows: list[dict[str, Any]], plugin_rows: list[tuple[str, str, float, str, tuple[str, ...]]] | None = None):
    """The standard metrics plus plugin metrics. A plugin key with no METRICS entry is a mean."""
    declared = list(plugin_rows or [])
    known = {item[0] for item in declared}
    extra = sorted({key for row in rows for key in row if key.startswith("x_") and key not in known})
    fallback = tuple((key, f"{key[2:]} (plugin)", 1.0, "", ("mean",)) for key in extra)
    return (*METRICS, *declared, *fallback)


def window_values(
    rows: list[dict[str, Any]],
    windows: list[tuple[str, int, int]],
    plugin_rows: list[tuple[str, str, float, str, tuple[str, ...]]] | None = None,
) -> dict[str, dict[str, float | None]]:
    """Per window, each metric's aggregate over the ticks it covers. Keys are ``metric:aggregation``."""
    result: dict[str, dict[str, float | None]] = {}
    specs = metric_specs(rows, plugin_rows)
    for label, start, end in windows:
        inside = [row for row in rows if start <= int(row["tick"]) <= end]
        values: dict[str, float | None] = {}
        for key, _, _, _, aggregations in specs:
            series = [float(row[key]) for row in inside if row.get(key) is not None]
            for how in aggregations:
                values[f"{key}:{how}"] = aggregate(series, how)
        result[label] = values
    return result


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def paired_stats(deltas: list[float]) -> dict[str, Any]:
    """Summarize per-seed differences: mean, median, range, direction counts, leave-one-out sign."""
    n = len(deltas)
    if n == 0:
        return {"n": 0}
    mean = statistics.fmean(deltas)
    loo_stable = None
    if n >= 3:
        total = sum(deltas)
        loo_stable = all(_sign((total - value) / (n - 1)) == _sign(mean) for value in deltas)
    return {
        "n": n,
        "mean": mean,
        "median": statistics.median(deltas),
        "min": min(deltas),
        "max": max(deltas),
        "up": sum(1 for value in deltas if value > 0),
        "down": sum(1 for value in deltas if value < 0),
        "loo_sign_stable": loo_stable,
        "per_seed": deltas,
    }


# --------------------------------------------------------------------------- planning and running


def worker_env() -> dict[str, str]:
    return {**os.environ, "PYTHONHASHSEED": PYTHONHASHSEED, **THREAD_ENV}


def probe_runtime(python: str) -> dict[str, str]:
    """The worker interpreter's own versions, which can differ from the one running this script."""
    completed = subprocess.run(
        [python, "-c", RUNTIME_PROBE], env=worker_env(), capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout)


def _split_timed(value: str) -> tuple[str, dict[str, Any] | None]:
    raw, at, schedule = value.partition("@")
    if not at:
        return raw.strip(), None
    start_text, dots, end_text = schedule.partition("..")
    if not start_text.strip():
        raise ValueError(f"Timed lever {value!r} needs a start week, as 0.3@12 or 0.3@12..20")
    start = int(start_text)
    end = int(end_text) if dots and end_text.strip() else None
    if start < 1 or (end is not None and end < start):
        raise ValueError(f"Timed lever {value!r} has an invalid week range")
    return raw.strip(), {"start": start, "end": end}


def parse_assignments(pairs: list[list[str]], arms: list[str]) -> dict[str, dict[str, Any]]:
    """Split ``--set ARM key=value`` into config overrides, immediate levers and timed levers."""
    plan = {arm: {"config_overrides": {}, "levers": {}, "timed_levers": []} for arm in arms}
    for arm, assignment in pairs:
        if arm not in plan:
            raise ValueError(f"--set names unknown arm {arm!r}; declare it with --arm first")
        key, sep, value = assignment.partition("=")
        key = key.strip()
        if not sep or not key:
            raise ValueError(f"--set {arm} {assignment!r} must look like section.field=value or lever.name=value")
        if key == "payment_sequence" or key.endswith(".payment_sequence"):
            raise ValueError("payment_sequence is a panel dimension; use --sequences")
        if key.startswith("lever."):
            name = key[len("lever."):]
            raw, timing = _split_timed(value.strip())
            if timing is None:
                plan[arm]["levers"][name] = raw
            else:
                plan[arm]["timed_levers"].append({"name": name, "value": raw, **timing})
        else:
            plan[arm]["config_overrides"][key] = value.strip()
    return plan


def _numeric_field(config: Any, path: str) -> float:
    target = config
    parts = path.split(".")
    if len(parts) < 2:
        raise ValueError(f"--sweep {path!r} must name a section and field")
    for part in parts:
        if not hasattr(target, part):
            raise ValueError(f"--sweep unknown field {path!r}")
        target = getattr(target, part)
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        raise ValueError(f"--sweep needs a numeric field; {path} is {type(target).__name__}")
    return float(target)


def _format_scaled(value: float, factor: float) -> str:
    scaled = value * factor
    if scaled == int(scaled):
        return str(int(scaled)) if abs(scaled) < 1e15 else repr(scaled)
    return repr(scaled)


def _split_interact(text: str) -> tuple[str, str]:
    name, sep, assignment = text.partition(":")
    name = name.strip()
    if not sep or not name or "=" not in assignment:
        raise ValueError(f"--interact {text!r} must look like name:section.field=value")
    if not ARM_NAME.match(name):
        raise ValueError(f"--interact arm {name!r} must use lowercase letters, digits, '.', '_', '-' or '+'")
    return name, assignment.strip()


def expand_shorthand(args: argparse.Namespace) -> None:
    """Turn ``--off-set``, ``--sweep`` and ``--interact`` into arms and ``--set`` pairs."""
    from config import clone_config

    if args.off_set and "off" not in args.arm:
        args.arm.append("off")
    for item in list(args.off_set or []):
        args.set.append(["off", item])
    config = clone_config() if args.sweep else None
    for arm, field in list(args.sweep or []):
        base = _numeric_field(config, field)
        for factor, label in ((0.5, "x0.5"), (1.0, "x1"), (1.5, "x1.5")):
            name = f"{arm}-{label}"
            if name not in args.arm:
                args.arm.append(name)
            args.set.append([name, f"{field}={_format_scaled(base, factor)}"])
    for left, right in list(args.interact or []):
        left_name, left_set = _split_interact(left)
        right_name, right_set = _split_interact(right)
        both = f"{left_name}+{right_name}"
        for name in (left_name, right_name, both):
            if name not in args.arm:
                args.arm.append(name)
        args.set.append([left_name, left_set])
        args.set.append([right_name, right_set])
        args.set.append([both, left_set])
        args.set.append([both, right_set])


def plan_runs(
    args: argparse.Namespace,
    runtime: dict[str, str],
    seeds: list[int] | None = None,
    repeats: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arms = list(args.arm)
    if len(set(arms)) != len(arms) or any(ARM_NAME.match(arm) is None for arm in arms):
        raise ValueError(f"Arm names must be unique and use only lowercase letters, digits, '.', '_', '-', or '+': {arms}")
    baseline = args.baseline or arms[0]
    if baseline not in arms:
        raise ValueError(f"--baseline {baseline!r} is not one of the arms {arms}")
    sequences = parse_str_list(args.sequences)
    if not set(sequences) <= set(PAYMENT_SEQUENCES) or len(set(sequences)) != len(sequences):
        raise ValueError(f"--sequences must be distinct values from {PAYMENT_SEQUENCES}")
    seeds = parse_int_list(args.seeds) if seeds is None else list(seeds)
    if len(set(seeds)) != len(seeds):
        raise ValueError("--seeds must be distinct")
    do_repeats = args.determinism_check if repeats is None else repeats
    roots = {arm: repo_root() for arm in arms}
    for arm, path in args.root:
        if arm not in roots:
            raise ValueError(f"--root names unknown arm {arm!r}")
        roots[arm] = Path(path).resolve()
        if not (roots[arm] / "backend" / "economy.py").exists():
            raise ValueError(f"--root {arm} {path}: no backend/economy.py there")
    assignments = parse_assignments(args.set, arms)
    hooks = {arm: [] for arm in arms}
    for arm, name in list(args.hook or []):
        if arm not in hooks:
            raise ValueError(f"--hook names unknown arm {arm!r}")
        if name != "k06_hold_pool":
            raise ValueError(f"Unknown hook {name!r}. Known hooks: k06_hold_pool")
        hooks[arm].append(name)
    plugins = []
    for raw in list(args.metrics_plugin or []):
        path = str(Path(raw).resolve())
        if not Path(path).is_file():
            raise ValueError(f"--metrics-plugin {raw!r} is not a file")
        load_plugin_module(path)
        plugins.append(path)
    identities = {str(root): model_identity(root) for root in sorted(set(roots.values()), key=str)}
    plugin_hashes = [hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in plugins]

    def spec(arm: str, sequence: str, seed: int, repeat: bool = False) -> dict[str, Any]:
        root = str(roots[arm])
        return {
            "arm": arm,
            "repeat": repeat,
            "root": root,
            "source_sha256": identities[root]["source_sha256"],
            "payment_sequence": sequence,
            "seed": seed,
            "households": args.households,
            "firms_per_category": args.firms_per_category,
            "ticks": args.ticks,
            "config_overrides": assignments[arm]["config_overrides"],
            "levers": assignments[arm]["levers"],
            "timed_levers": assignments[arm]["timed_levers"],
            "hooks": list(hooks[arm]),
            "metrics_plugins": list(plugins),
            "metrics_plugin_sha256": list(plugin_hashes),
            "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "money_helper_sha256": hashlib.sha256(WORKER.with_name("panel_money.py").read_bytes()).hexdigest(),
            "pythonhashseed": PYTHONHASHSEED,
            "runtime": {
                "python": runtime["python"],
                "implementation": runtime["implementation"],
                "numpy": runtime["numpy"],
                # The venv that actually ran this arm, not the arm checkout's lock file.
                "requirements_lock_sha256": lock_sha256(LOCK_PATH),
                "thread_env": THREAD_ENV,
            },
        }

    specs = [spec(arm, sequence, seed) for sequence in sequences for arm in arms for seed in seeds]
    if do_repeats and seeds:
        specs += [spec(baseline, sequence, seeds[0], repeat=True) for sequence in sequences]
    design = {
        "arms": arms,
        "baseline": baseline,
        "sequences": sequences,
        "seeds": list(seeds),
        "roots": {arm: str(root) for arm, root in roots.items()},
        "assignments": assignments,
        "hooks": hooks,
        "model_identities": identities,
        "metrics_plugins": plugins,
        "escalated": False,
        "escalation_reasons": [],
    }
    return specs, design


def run_file(runs_dir: Path, spec: dict[str, Any]) -> Path:
    suffix = "-repeat" if spec["repeat"] else ""
    return runs_dir / f"{spec['arm']}-{spec['payment_sequence']}-s{spec['seed']}{suffix}.json"


def _load_cached(path: Path, spec: dict[str, Any]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return result if result.get("spec") == spec else None


def execute(specs: list[dict[str, Any]], runs_dir: Path, jobs: int, python: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run each spec in a fresh process (cached runs are reused) and collect results and failures."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    pending = []
    for spec in specs:
        cached = _load_cached(run_file(runs_dir, spec), spec)
        if cached is not None:
            results.append(cached)
        else:
            pending.append(spec)
    if results:
        print(f"[panel] reusing {len(results)} finished runs", flush=True)
    env = worker_env()

    def launch(spec: dict[str, Any]) -> tuple[dict[str, Any], subprocess.CompletedProcess]:
        out = run_file(runs_dir, spec)
        spec_path = out.with_suffix(".spec.json")
        spec_path.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
        completed = subprocess.run(
            [python, str(WORKER), str(spec_path), str(out)],
            cwd=spec["root"], env=env, capture_output=True, text=True,
        )
        return spec, completed

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(launch, spec) for spec in pending]
        for done, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            spec, completed = future.result()
            label = f"{spec['arm']} {spec['payment_sequence']} seed {spec['seed']}{' (repeat)' if spec['repeat'] else ''}"
            if completed.returncode == 0:
                result = json.loads(run_file(runs_dir, spec).read_text(encoding="utf-8"))
                results.append(result)
                print(f"[panel] {done}/{len(pending)} {label}: {result['elapsed_seconds']:.0f}s", flush=True)
            else:
                tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-12:]
                failures.append({"spec": spec, "returncode": completed.returncode, "stderr_tail": tail})
                print(f"[panel] {done}/{len(pending)} {label}: FAILED\n  " + "\n  ".join(tail), flush=True)
    return results, failures


# --------------------------------------------------------------------------- summary


def summarize(
    results: list[dict[str, Any]],
    design: dict[str, Any],
    windows: list[tuple[str, int, int]],
    plugin_rows: list[tuple[str, str, float, str, tuple[str, ...]]] | None = None,
    extra_bounds: dict[str, tuple[float | None, float | None]] | None = None,
) -> dict[str, Any]:
    baseline = design["baseline"]
    base_prices = attach_paid_real_gdp(results, design)
    main_runs = {(r["spec"]["arm"], r["spec"]["payment_sequence"], r["spec"]["seed"]): r for r in results if not r["spec"]["repeat"]}
    repeats = [r for r in results if r["spec"]["repeat"]]
    values = {key: window_values(run["rows"], windows, plugin_rows) for key, run in main_runs.items()}

    determinism = []
    for repeat in repeats:
        spec = repeat["spec"]
        original = main_runs.get((spec["arm"], spec["payment_sequence"], spec["seed"]))
        determinism.append({
            "payment_sequence": spec["payment_sequence"],
            "seed": spec["seed"],
            "identical": original is not None and original["fingerprint"] == repeat["fingerprint"],
        })

    checks: dict[str, Any] = {"determinism": determinism, "arms": {}}
    comparisons: dict[str, Any] = {}
    levels: dict[str, Any] = {}
    for sequence in design["sequences"]:
        for arm in design["arms"]:
            per_window = {}
            for label, _, _ in windows:
                keys = list(dict.fromkeys(
                    k for seed in design["seeds"] for k in values.get((arm, sequence, seed), {}).get(label, {})
                ))
                per_window[label] = {
                    key: statistics.fmean(vals) if (vals := [
                        values[(arm, sequence, seed)][label][key]
                        for seed in design["seeds"]
                        if (arm, sequence, seed) in values and values[(arm, sequence, seed)][label].get(key) is not None
                    ]) else None
                    for key in keys
                }
            levels.setdefault(sequence, {})[arm] = per_window

    for arm in design["arms"]:
        identical = []
        drift = []
        divergences = []
        exits = []
        for sequence in design["sequences"]:
            for seed in design["seeds"]:
                run = main_runs.get((arm, sequence, seed))
                base = main_runs.get((baseline, sequence, seed))
                if run is None:
                    continue
                last_exit = legacy_last_exit(run)
                if last_exit is not None:
                    exits.append({"payment_sequence": sequence, "seed": seed, "week": last_exit})
                if base is not None and arm != baseline:
                    same = run["fingerprint"] == base["fingerprint"]
                    identical.append(same)
                    if not same:
                        found = first_divergence(run, base)
                        if found is not None:
                            divergences.append({"payment_sequence": sequence, "seed": seed, **found})
                if run["money"]["final_drift"] is not None:
                    drift.append(run["money"]["final_drift"])
        earliest = min(divergences, key=lambda item: (item["tick"], item["payment_sequence"], item["seed"])) if divergences else None
        checks["arms"][arm] = {
            "identical_to_baseline": None if arm == baseline else {"identical": sum(identical), "runs": len(identical)},
            "money_final_drift_mean": statistics.fmean(drift) if drift else None,
            "money_final_drift_max_abs": max((abs(value) for value in drift), default=None),
            "first_divergence": earliest,
            "legacy_last_exit": exits,
        }
        if arm == baseline:
            continue
        for sequence in design["sequences"]:
            for label, _, _ in windows:
                keys = levels[sequence][baseline][label].keys()
                table = {}
                for key in keys:
                    deltas = []
                    for seed in design["seeds"]:
                        a = values.get((arm, sequence, seed), {}).get(label, {}).get(key)
                        b = values.get((baseline, sequence, seed), {}).get(label, {}).get(key)
                        if a is not None and b is not None:
                            deltas.append(a - b)
                    table[key] = paired_stats(deltas)
                comparisons.setdefault(arm, {}).setdefault(sequence, {})[label] = table

    scores, warnings = unemployment_report(results, design)
    checks["money"] = evaluate_money(results, design)
    checks["bounds"] = evaluate_bounds(results, extra_bounds)
    checks["warnings"] = warnings
    return {
        "levels": levels,
        "comparisons": comparisons,
        "checks": checks,
        "unemployment_scores": scores,
        "real_gdp_base_prices": base_prices,
        "window_values": {f"{arm}|{sequence}|{seed}": v for (arm, sequence, seed), v in values.items()},
    }


# --------------------------------------------------------------------------- report


def _fmt(value: float | None, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    magnitude = abs(value)
    # Three decimal places round a 1e-5 gap to 0. Keep tolerance-scale values visible.
    if magnitude != 0 and magnitude < 1e-3:
        return f"{value:{'+' if signed else ''}.3e}"
    digits = 0 if magnitude >= 1000 else 1 if magnitude >= 10 else 2 if magnitude >= 1 else 3
    text = f"{value:{'+' if signed else ''},.{digits}f}"
    return "0" if signed and float(text.replace(",", "")) == 0 else text


def _scale_for(key: str, plugin_rows: list[tuple[str, str, float, str, tuple[str, ...]]] | None = None) -> tuple[str, float, str]:
    metric, _, how = key.partition(":")
    for name, label, scale, unit, _ in (*METRICS, *(plugin_rows or ())):
        if name == metric:
            break
    else:
        label, scale, unit = f"{metric[2:]} (plugin)" if metric.startswith("x_") else metric, 1.0, ""
    if how in ("neg_share", "cv", "cv_detrended"):
        scale, unit = 100.0, "%"
    suffix = AGGREGATION_LABELS.get(how, how)
    return (f"{label}, {suffix}" if suffix else label), scale, unit


def _window_heading(label: str, windows: list[tuple[str, int, int]]) -> str:
    start = next((item[1] for item in windows if item[0] == label), None)
    if start is None:
        return label
    role = window_role(start)
    if role == "reported":
        return label
    return f"{label} ({role})"


def render_markdown(panel: dict[str, Any], windows: list[tuple[str, int, int]]) -> str:
    design, settings, summary = panel["design"], panel["settings"], panel["summary"]
    baseline = design["baseline"]
    plugin_rows = panel.get("plugin_rows") or []
    manifest = panel["manifest"]
    lines = ["# Evidence panel", ""]
    lines += [f"> **{manifest.get('comparability', 'non-reference')}**. {WITHIN_RUN_NOTE}", ""]
    lines += [
        f"`{manifest['command']}`",
        "",
        f"- **Setup:** {settings['households']:,} households, {settings['firms_per_category']} firms per category, "
        f"{settings['ticks']} ticks, seeds {', '.join(map(str, design['seeds']))} (one process per run, PYTHONHASHSEED={PYTHONHASHSEED}).",
        f"- **Reference env:** Python {manifest['worker_runtime']['python']} ({manifest['worker_runtime'].get('implementation', 'CPython')}), "
        f"numpy {manifest['worker_runtime']['numpy']}, requirements.lock sha256 `{manifest.get('requirements_lock_sha256')}`, "
        f"one numeric-library thread per run, PYTHONHASHSEED {PYTHONHASHSEED}. "
        f"Lock pins checked: {manifest.get('lock_pins_checked', 'n/a')}.",
        f"- **Host:** {manifest['worker_runtime'].get('platform', 'unknown')}; "
        f"CPU {manifest['worker_runtime'].get('cpu_model', 'unknown')}.",
        f"- **Evaluator:** `{manifest.get('evaluator', {}).get('commit', 'unknown')}` (tool checkout).",
        f"- **Comparability:** {manifest.get('comparability', 'non-reference')}. {WITHIN_RUN_NOTE}",
        f"- **Windows:** {', '.join(_window_heading(label, windows) for label in settings['windows'])}. **Baseline:** `{baseline}`.",
        f"- **Money check:** {MONEY_CHECK_MODE} (switch `MONEY_CHECK_MODE` in `panel_summary.py`; absolute after #57).",
    ]
    if design.get("escalated"):
        shown = design.get("escalation_reasons") or []
        preview = "; ".join(shown[:6])
        lines.append(f"- **Seeds escalated** from {', '.join(map(str, CANONICAL_SEEDS))} to include {', '.join(map(str, ESCALATION_SEEDS))} because: {preview}.")
    for arm in design["arms"]:
        identity = design["model_identities"][design["roots"][arm]]
        changes = {**design["assignments"][arm]["config_overrides"],
                   **{f"lever.{k}": v for k, v in design["assignments"][arm]["levers"].items()}}
        for timed in design["assignments"][arm].get("timed_levers") or []:
            end = "" if timed.get("end") is None else f"..{timed['end']}"
            changes[f"lever.{timed['name']}@{timed['start']}{end}"] = timed["value"]
        for hook in (design.get("hooks") or {}).get(arm) or []:
            changes[f"hook.{hook}"] = "on"
        change_text = ", ".join(f"`{k}={v}`" for k, v in sorted(changes.items())) or "no changes"
        dirty = " (uncommitted changes)" if identity.get("working_tree_dirty") else ""
        venv_lock = manifest.get("requirements_lock_sha256") or ""
        lines.append(
            f"- **`{arm}`:** {change_text}; commit `{(identity.get('commit') or 'unknown')[:10]}`{dirty}; "
            f"venv lock `{venv_lock}`."
        )
    lines += ["", "## Checks", "", "| Arm | Runs identical to baseline (state digest) | Unrecorded money drift at end (mean, max abs) | First divergent week |", "|---|---|---|---|"]
    for arm, check in summary["checks"]["arms"].items():
        ident = check["identical_to_baseline"]
        ident_text = "baseline" if ident is None else f"{ident['identical']}/{ident['runs']}"
        first = check.get("first_divergence")
        first_text = "baseline" if ident is None else ("none" if first is None else f"week {first['tick']} {first['component']} ({first['payment_sequence']} seed {first['seed']})")
        lines.append(
            f"| `{arm}` | {ident_text} | {_fmt(check['money_final_drift_mean'])}, {_fmt(check['money_final_drift_max_abs'])} | {first_text} |"
        )
    money = summary["checks"].get("money") or {}
    bounds = summary["checks"].get("bounds") or {}
    lines += [
        "",
        f"Money check ({money.get('mode', MONEY_CHECK_MODE)}, dust tolerance {money.get('tolerance')} dollars): "
        f"{'pass' if money.get('passed', True) else 'FAIL'} ({len(money.get('failures') or [])} runs).",
        f"Bounds and non-finite values: {'pass' if bounds.get('passed', True) else 'FAIL'} ({len(bounds.get('violations') or [])} shown).",
    ]
    if money.get("mode") == "relative":
        lines.append(
            "income_first and income_late must conserve, including the baseline arm. "
            "legacy is reported (median, k/n) and does not fail until #57. A non-finite drift always fails. "
            "Off = main is the state digest."
        )
    gaps = money.get("drift_gaps") or []
    if gaps:
        lines += [
            "",
            "| Sequence | Arm | Baseline | Drift minus baseline (median) | k/n up | mean |",
            "|---|---|---|---|---|---|",
        ]
        for gap in gaps:
            baseline_text = "conserves" if gap.get("baseline_conserves") else "leaks, not failed"
            lines.append(
                f"| {gap['payment_sequence']} | `{gap['arm']}` | {baseline_text} | "
                f"{_fmt(gap.get('median'), signed=True)} | {gap.get('up')}/{gap.get('n')} | {_fmt(gap.get('mean'), signed=True)} |"
            )
    det = summary["checks"]["determinism"]
    if det:
        same = sum(1 for item in det if item["identical"])
        status = "pass" if same == len(det) else "FAIL"
        lines += ["", f"Repeat of `{baseline}` seed {det[0]['seed']} on each sequence: {same}/{len(det)} identical ({status})."]
    for warning in summary["checks"].get("warnings") or []:
        lines += ["", f"Warning: {warning}"]
    lines += ["", "### Unemployment band (labour force, weeks 201+)", ""]
    lines.append("Distance is the mean over weeks 201+ of points outside 10-40% (0 inside). The all-households column is the dashboard figure and is not judged. A baseline outside the band is a warning, not a failure.")
    lines += ["", "| Sequence | Arm | Labour force % | Band distance (pts) | All households % (unjudged) |", "|---|---|---|---|---|"]
    any_score = False
    for sequence, by_arm in (summary.get("unemployment_scores") or {}).items():
        for arm, record in by_arm.items():
            if not record:
                continue
            any_score = True
            lines.append(
                f"| {sequence} | `{arm}` | {_fmt(record['labor_force_unemployment_pct'])} | "
                f"{_fmt(record['band_distance_points'])} | {_fmt(record['all_households_unemployment_pct'])} |"
            )
    if not any_score:
        lines.append("| | | n/a (run shorter than week 201) | | |")
    lines += ["", "### Legacy firms (report only)", ""]
    lines.append("Last week a legacy firm left the economy. Baseline firms are protected from the bankruptcy exit, so this is often none.")
    for arm, check in summary["checks"]["arms"].items():
        exits = check.get("legacy_last_exit") or []
        if not exits:
            lines.append(f"- `{arm}`: no legacy exit in these runs.")
            continue
        text = ", ".join(f"{item['payment_sequence']} seed {item['seed']} week {item['week']}" for item in exits[:12])
        lines.append(f"- `{arm}`: {text}.")
    lines += [
        "",
        "Each cell gives the baseline's level, then the paired difference (arm minus baseline): the mean over seeds, "
        "[min, max], the median, and how many seeds went up (k/n). Shares are in percent, so their differences are percentage points. "
        "**!** marks a mean whose sign flips when any one seed is left out. "
        "Within-window CV is the standard deviation of the weekly series divided by the absolute mean, not the standard deviation of the mean. "
        "Detrended CV removes a linear week trend first.",
    ]
    for arm, by_sequence in summary["comparisons"].items():
        ident = summary["checks"]["arms"][arm]["identical_to_baseline"]
        if ident["runs"] and ident["identical"] == ident["runs"]:
            lines += ["", f"## `{arm}` vs `{baseline}`", "", f"Identical on all {ident['runs']} runs: every per-week state digest matches, so every difference is zero."]
            continue
        for sequence in design["sequences"]:
            by_window = by_sequence.get(sequence, {})
            labels = [label for label in settings["windows"] if label in by_window]
            if not labels:
                continue
            lines += ["", f"## `{arm}` vs `{baseline}`: {sequence}", ""]
            headings = [_window_heading(label, windows) for label in labels]
            lines.append("| Metric | " + " | ".join(f"{label}: {baseline} | {label}: difference" for label in headings) + " |")
            lines.append("|---|" + "---|---|" * len(labels))
            for key in by_window[labels[0]]:
                name, scale, unit = _scale_for(key, plugin_rows)
                cells = []
                for label in labels:
                    level = summary["levels"][sequence][baseline][label].get(key)
                    stats = by_window[label][key]
                    cells.append(_fmt(None if level is None else level * scale))
                    if not stats.get("n"):
                        cells.append("n/a")
                        continue
                    flag = " **!**" if stats["loo_sign_stable"] is False else ""
                    cells.append(
                        f"{_fmt(stats['mean'] * scale, signed=True)} [{_fmt(stats['min'] * scale, signed=True)}, "
                        f"{_fmt(stats['max'] * scale, signed=True)}] median {_fmt(stats['median'] * scale, signed=True)} "
                        f"{stats['up']}/{stats['n']}{flag}"
                    )
                lines.append(f"| {name}{f' ({unit})' if unit else ''} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Definitions",
        "",
        "- **Unemployment, labour force:** unemployed and able to work, divided by employed plus those unemployed (`labor_force_unemployment_rate`). The 10-40% band uses this rate from week 201 on.",
        "- **Jobless, all households:** share of all households without a job, including those that cannot work (`compute_household_stats`). Printed next to the band and not judged.",
        "- **Band distance:** mean over weeks 201+ of max(0, 10 - u, u - 40) where u is the labour-force rate in percent. Zero inside the band.",
        "- **Real GDP (primary):** units sold times the baseline arm's paid price, same seed and sequence. Paid price is revenue / units over weeks 11-62 (the first post-warmup year; warmup is 10). A shorter run uses every simulated week.",
        "- **Real GDP (GDP / CPI):** nominal GDP (`gdp_this_tick`) divided by the posted consumer price index, times 100. Kept beside the primary series.",
        "- **Poverty:** share of households whose liquid wealth, cash + max(0, deposit), is below `households.poverty_threshold` ($200). Extreme uses `extreme_poverty_threshold`.",
        "- **Job-finding rate:** households who were labour-force unemployed at the start of the week and employed at the end, divided by that starting unemployed count.",
        "- **Planned layoffs per month:** firms' `planned_layoffs_ids` after the tick, times 52/12. This is the plan, not executed separations. **Openings per unemployed:** `planned_hires_count` divided by labour-force unemployed after the tick.",
        "- **Legacy firms:** `is_baseline` firms still active. Exits count firms that were legacy last week and are gone this week. Last-exit week is report only.",
        "- **Happiness tails:** median, p10, p90, and the shares at or below 0.05 and at or above 0.95.",
        "- **Within-window CV:** standard deviation of the weekly values in the window divided by the absolute mean. Detrended CV does that after a linear week trend is removed.",
        "- **Bond buy (K06):** the treasury's weekly bond purchase paid out through the misc pool. `--hook k06_hold_pool` leaves that pool on the money stock.",
        "- **Unrecorded money drift:** change in total money net of recorded outside money (the evaluator's `panel_money.total_money_net_of_injections`) from construction to the last tick.",
        "- **Runs identical:** per-week state digests (households, firms, government, bank, loans, payment-ledger totals, RNG) match. The row fingerprint is kept beside them and is not the identity check.",
        "- **Money check:** both modes use a 0.0001 dollar dust tolerance. Relative mode requires income_first and income_late, including the baseline, to conserve, and reports arm-minus-baseline drift (median, k/n) for legacy. Absolute mode requires every run's own drift inside that tolerance. A NaN or inf drift fails.",
    ]
    return "\n".join(lines) + "\n"


def render_short_summary(panel: dict[str, Any]) -> str:
    """Bounded CI/job-comment summary; detailed tables and raw runs stay in artifacts."""
    manifest, design = panel["manifest"], panel["design"]
    checks = panel["summary"]["checks"]
    reasons = check_failures(checks)
    if any(not item["ok"] for item in panel.get("mutations", [])):
        reasons.append("mutation check")
    lines = ["# Evidence panel summary", "", f"**{'FAIL' if reasons else 'PASS'}**; "
             f"{panel['settings']['ticks']} weeks, {len(design['seeds'])} seeds, "
             f"{len(design['sequences'])} payment sequences.", "",
             f"{manifest['comparability']}. {WITHIN_RUN_NOTE}", "",
             f"Host: {manifest['worker_runtime'].get('platform', 'unknown')}; "
             f"CPU: {manifest['worker_runtime'].get('cpu_model', 'unknown')}.",
             f"Evaluator commit: `{manifest.get('evaluator', {}).get('commit', 'unknown')}`."]
    for arm, check in checks["arms"].items():
        identity = check.get("identical_to_baseline")
        if identity:
            lines.append(f"- `{arm}` vs `{design['baseline']}`: "
                         f"{identity['identical']}/{identity['runs']} state digests identical.")
    if reasons:
        lines.append("- Failed checks: " + "; ".join(reasons))
    lines += ["", "Detailed panel, evaluator JSON and raw runs are in the workflow artifact."]
    return "\n".join(lines) + "\n"


def write_window_csv(path: Path, summary: dict[str, Any], comparability: str) -> None:
    rows = []
    for run_key, per_window in summary["window_values"].items():
        arm, sequence, seed = run_key.split("|")
        for label, values in per_window.items():
            rows.append({"arm": arm, "payment_sequence": sequence, "seed": seed, "window": label, **values})
    fields = sorted({key for row in rows for key in row}, key=lambda k: (k not in ("arm", "payment_sequence", "seed", "window"), k))
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(f"# comparability: {comparability}\n")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_evaluator(path: Path, panel: dict[str, Any], markdown: str) -> None:
    """One file for an AI evaluator: env, per-arm scores, and the panel. No combined score."""
    manifest = panel["manifest"]
    payload = {
        "comparability": manifest.get("comparability", "non-reference"),
        "comparison_scope": WITHIN_RUN_NOTE,
        "evaluator": manifest.get("evaluator"),
        "env": {
            "platform": manifest["worker_runtime"].get("platform"),
            "cpu_model": manifest["worker_runtime"].get("cpu_model"),
            "host": manifest.get("host"),
            "python": manifest["worker_runtime"]["python"],
            "implementation": manifest["worker_runtime"].get("implementation"),
            "numpy": manifest["worker_runtime"]["numpy"],
            "requirements_lock_sha256": manifest.get("requirements_lock_sha256"),
            "pythonhashseed": manifest.get("pythonhashseed"),
            "thread_env": manifest.get("thread_env"),
            "money_check_mode": MONEY_CHECK_MODE,
            "lock_pins_checked": manifest.get("lock_pins_checked"),
            "runtime_lock_ok": manifest.get("runtime_lock_ok"),
            "reference_ok": manifest.get("reference_ok"),
        },
        "unemployment_band": {
            "low_pct": 10,
            "high_pct": 40,
            "basis": "labor_force_unemployment_rate",
            "weeks": "201+",
            "distance": "mean of max(0, 10 - u, u - 40) percentage points",
            "all_households": "reported, not judged",
            "baseline_outside_band": "warning, not a failure",
        },
        "scores": panel["summary"].get("unemployment_scores"),
        "warnings": panel["summary"]["checks"].get("warnings"),
        "checks": {
            "money": panel["summary"]["checks"].get("money"),
            "bounds": panel["summary"]["checks"].get("bounds"),
            "determinism": panel["summary"]["checks"].get("determinism"),
            "arms": panel["summary"]["checks"].get("arms"),
        },
        "panel_markdown": markdown,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Paired evidence panel at the dashboard's defaults.")
    p.add_argument("--arm", action="append", required=True, help="Arm name (repeat). The first is the baseline unless --baseline.")
    p.add_argument("--set", action="append", nargs=2, default=[], metavar=("ARM", "KEY=VALUE"),
                   help="section.field=value, lever.name=value, or lever.name=value@WEEK or @WEEK..WEEK.")
    p.add_argument("--off-set", action="append", default=[], metavar="KEY=VALUE",
                   help="Same as --set off KEY=VALUE. Default-on PRs use this so the off arm is checked against main.")
    p.add_argument("--root", action="append", nargs=2, default=[], metavar=("ARM", "PATH"),
                   help="Run ARM from another checkout (default: this one).")
    p.add_argument("--baseline", help="Arm the others are compared with (default: the first --arm).")
    p.add_argument("--sequences", default=",".join(PAYMENT_SEQUENCES), help="Payment sequences, income_first first.")
    p.add_argument("--seeds", default="42,43,44,45,46")
    p.add_argument("--households", type=int, default=1000)
    p.add_argument("--firms-per-category", type=int, default=5)
    p.add_argument("--ticks", "--weeks", type=int, default=DEFAULT_TICKS, dest="ticks",
                   help="Tick count. --weeks is the same option. Default 312. --weeks 260 still runs.")
    p.add_argument("--windows", default=DEFAULT_WINDOWS,
                   help="Inclusive tick windows. The default list clips to --ticks; an explicit list does not.")
    p.add_argument("--metrics-plugin", action="append", default=[],
                   help="File defining extra_metrics(economy). Repeat for one plugin per owner. METRICS and summarize() are optional.")
    p.add_argument("--sweep", action="append", nargs=2, default=[], metavar=("ARM", "SECTION.FIELD"),
                   help="Add ARM-x0.5, ARM-x1 and ARM-x1.5 with the field at 0.5, 1 and 1.5 times its default.")
    p.add_argument("--interact", action="append", nargs=2, default=[], metavar=("A:K=V", "B:K=V"),
                   help="Add arms A, B and A+B.")
    p.add_argument("--hook", action="append", nargs=2, default=[], metavar=("ARM", "HOOK"),
                   help="Named read-only-to-money hook. k06_hold_pool keeps the misc pool from paying out.")
    p.add_argument("--mutate", action="append", default=[], metavar="FILE:L1-L2",
                   help="Revert these lines to --root main and require --mutate-tests to fail.")
    p.add_argument("--mutate-tests", action="append", default=[], metavar="PATH",
                   help="Pytest node id run by --mutate. The check passes when at least one test fails.")
    p.add_argument("--mutate-root", type=Path, help="Candidate checkout for mutation tests (default: tool checkout).")
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--no-determinism-check", dest="determinism_check", action="store_false",
                   help="Skip repeating the baseline's first seed on each sequence.")
    p.add_argument("--no-escalate", dest="escalate", action="store_false",
                   help="Do not add seeds 47-54 when a judged headline result is fragile.")
    p.add_argument("--allow-nonref", action="store_true",
                   help="Allow runtime/lock mismatches; all comparisons remain within this run only.")
    p.add_argument("--out", type=Path, help="Run folder (reused on rerun). Default: benchmarks/results/<timestamp>-evidence-panel.")
    p.add_argument("--python", default=sys.executable, help="Interpreter for the worker processes.")
    p.set_defaults(determinism_check=True, escalate=True)
    return p


def _reference_status(python: str) -> tuple[dict[str, str], dict[str, Any], str | None]:
    runtime = probe_runtime(python)
    if not LOCK_PATH.is_file():
        packages = {
            "pins": 0, "missing": [], "mismatched": [], "ok_packages": False,
            "lock_error": "backend/requirements.lock is missing",
        }
    else:
        pins = parse_lock_pins(LOCK_PATH.read_text(encoding="utf-8"))
        if not pins:
            packages = {
                "pins": 0, "missing": [], "mismatched": [], "ok_packages": False,
                "lock_error": "backend/requirements.lock has no pins",
            }
        else:
            versions = probe_installed_versions(python)
            packages = compare_lock(pins, versions)
    decision = reference_decision(reference_python(runtime.get("implementation", ""), runtime.get("python", "")), packages)
    return runtime, decision, lock_sha256(LOCK_PATH)


def _stamp_outputs(run_dir: Path, panel: dict[str, Any], markdown: str, windows: list[tuple[str, int, int]]) -> None:
    comparability = panel["manifest"].get("comparability", "reference")
    (run_dir / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "panel.md").write_text(markdown, encoding="utf-8")
    (run_dir / "summary.md").write_text(render_short_summary(panel), encoding="utf-8")
    write_evaluator(run_dir / "evaluator.json", panel, markdown)
    write_window_csv(run_dir / "window_values.csv", panel["summary"], comparability)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    expand_shorthand(args)
    windows = resolve_windows(args.windows, args.ticks)
    runtime, decision, digest = _reference_status(args.python)
    if not decision["ok"] and not args.allow_nonref:
        print(format_reference_error(decision, runtime.get("python", ""), runtime.get("implementation", "")), file=sys.stderr)
        return 2
    host = host_stamp(dict(os.environ))
    comparability = comparability_label(decision["ok"], args.allow_nonref, host, runtime.get("system", ""))
    if args.mutate and not args.mutate_tests:
        print("--mutate needs at least one --mutate-tests path", file=sys.stderr)
        return 2
    main_root = next((Path(path).resolve() for arm, path in args.root if arm == "main"), None)
    if args.mutate and main_root is None:
        print("--mutate needs --root main PATH (the checkout the lines revert to)", file=sys.stderr)
        return 2
    mutations = []
    for file_spec in args.mutate:
        mutations.append(mutation_check(
            candidate_root=(args.mutate_root or repo_root()).resolve(), main_root=main_root, file_spec=file_spec,
            tests=list(args.mutate_tests), python=args.python,
        ))
        print(f"[panel] mutation {file_spec}: {mutations[-1]['detail']}", flush=True)

    evaluator = model_identity(repo_root())
    specs, design = plan_runs(args, runtime)
    plugin_rows, extra_bounds = plugin_display(design["metrics_plugins"]) if design["metrics_plugins"] else ([], {})
    if args.out is not None:
        run_dir = args.out.resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = BenchmarkPaths.create(default_results_root(), "evidence-panel").run_dir
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    print(f"[panel] {len(specs)} runs, {args.jobs} at a time -> {run_dir}", flush=True)
    print(f"[panel] {comparability}. {WITHIN_RUN_NOTE}", flush=True)
    results, failures = execute(specs, run_dir / "runs", args.jobs, args.python)
    command = "python -m backend.tools.benchmarks.run_evidence_panel " + shlex.join(argv)

    def manifest(summary_time: str | None = None) -> dict[str, Any]:
        return {
            "command": command,
            "cwd": str(Path.cwd()),
            "started_at": started,
            "finished_at": summary_time or dt.datetime.now(dt.timezone.utc).isoformat(),
            "runner_python": sys.version.split()[0],
            "worker_runtime": runtime,
            "pythonhashseed": PYTHONHASHSEED,
            "thread_env": THREAD_ENV,
            "requirements_lock_sha256": digest,
            "lock_pins_checked": decision.get("pins"),
            "runtime_lock_ok": decision.get("ok"),
            "reference_ok": comparability == "reference",
            "comparability": comparability,
            "comparison_scope": WITHIN_RUN_NOTE,
            "host": host,
            "evaluator": evaluator,
            "money_check_mode": MONEY_CHECK_MODE,
        }

    panel: dict[str, Any] = {
        "manifest": manifest(),
        "settings": {
            "households": args.households,
            "firms_per_category": args.firms_per_category,
            "ticks": args.ticks,
            "windows": [label for label, _, _ in windows],
        },
        "design": design,
        "failures": failures,
        "mutations": mutations,
        "plugin_rows": plugin_rows,
    }
    if failures:
        (run_dir / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[panel] {len(failures)} runs failed; no table written. Details in {run_dir / 'panel.json'}", file=sys.stderr)
        return 1
    panel["summary"] = summarize(results, design, windows, plugin_rows, extra_bounds)
    if args.escalate:
        reasons = escalation_reasons(panel["summary"], design, windows)
        extra_seeds = [seed for seed in ESCALATION_SEEDS if seed not in design["seeds"]]
        if reasons and extra_seeds:
            print(f"[panel] escalating to seeds {extra_seeds[0]}-{extra_seeds[-1]} ({len(reasons)} fragile cells)", flush=True)
            extra_specs, _extra_design = plan_runs(args, runtime, seeds=extra_seeds, repeats=False)
            more, more_failures = execute(extra_specs, run_dir / "runs", args.jobs, args.python)
            results.extend(more)
            failures.extend(more_failures)
            panel["failures"] = failures
            if more_failures:
                (run_dir / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True), encoding="utf-8")
                print(f"[panel] {len(more_failures)} escalated runs failed; no table written.", file=sys.stderr)
                return 1
            design["seeds"] = list(design["seeds"]) + extra_seeds
            design["escalated"] = True
            design["escalation_reasons"] = reasons
            panel["summary"] = summarize(results, design, windows, plugin_rows, extra_bounds)
    panel["manifest"] = manifest()
    panel["plugin_summaries"] = plugin_summaries(design["metrics_plugins"], results) if design["metrics_plugins"] else {}
    markdown = render_markdown(panel, windows)
    _stamp_outputs(run_dir, panel, markdown, windows)
    reasons = check_failures(panel["summary"]["checks"])
    if any(not item["ok"] for item in mutations):
        reasons.append("mutation check")
    print(f"[panel] wrote {run_dir / 'panel.md'}", flush=True)
    if reasons:
        print("[panel] FAIL: " + "; ".join(reasons), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
