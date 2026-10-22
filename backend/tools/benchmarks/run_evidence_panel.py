"""Standard paired evidence panel for PRs that change economic behavior.

One command runs every arm on every payment sequence and seed at the dashboard's
defaults, each run in its own process, and writes one table by tick window:
the baseline level, the paired difference (mean, [min, max] across seeds, how
many seeds moved up) and a mark when leaving one seed out flips the sign. It
also checks that arms without changes reproduce the baseline exactly, that a
repeated run is identical, and how much unrecorded money each arm creates.

Compare a PR's flag against its own flag-off state, and its flag-off state
against ``main`` (a second checkout, e.g. ``git worktree add ../main origin/main``):

    python -m backend.tools.benchmarks.run_evidence_panel \\
        --arm main --root main ../main \\
        --arm off \\
        --arm on --set on households.skills_dynamics=True \\
        --baseline main --out benchmarks/results/pr51-panel

``--set ARM section.field=value`` overrides a config field before the economy
is built; ``--set ARM lever.<name>=value`` applies a policy lever after it, as
the dashboard's opening policy does. Rerunning the same command reuses a finished
run only if its settings, simulation source, measuring code, worker Python and
numpy versions, dependency lock and thread settings are unchanged, so a changed
``--windows`` only re-aggregates. ``--metrics-plugin FILE`` adds a mechanism's own measure: FILE
defines ``extra_metrics(economy) -> dict[str, float]``, called after each tick.

Outputs in the run folder: ``panel.md`` (the table to paste in a PR),
``panel.json`` (everything, including the manifest and per-seed values),
``window_values.csv`` and ``runs/`` (per-tick rows for each run).
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

from .common import BenchmarkPaths, default_results_root, parse_int_list, parse_str_list, repo_root, slugify

WORKER = Path(__file__).with_name("evidence_panel_worker.py")
PAYMENT_SEQUENCES = ("income_first", "income_late", "legacy")
PYTHONHASHSEED = "0"
# One thread per worker: parallel runs don't oversubscribe the cores, and numeric
# library threading can't change summation order from one machine to another.
THREAD_ENV = {
    name: "1"
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
}
RUNTIME_PROBE = (
    "import json, platform, sys, numpy; print(json.dumps({'python': platform.python_version(), "
    "'implementation': platform.python_implementation(), 'numpy': numpy.__version__, 'executable': sys.executable}))"
)

# (key, label, display scale, unit, aggregations). Shares are shown in percent,
# so their differences read in percentage points.
METRICS: tuple[tuple[str, str, float, str, tuple[str, ...]], ...] = (
    ("labor_force_unemployment_rate", "Unemployment, labour force", 100.0, "%", ("mean",)),
    ("unemployment_rate", "Jobless, all households (dashboard)", 100.0, "%", ("mean",)),
    ("real_gdp", "Real GDP (GDP / CPI x 100)", 1.0, "$/wk", ("mean",)),
    ("gdp", "Nominal GDP", 1.0, "$/wk", ("mean", "cv")),
    ("food_services_units_sold", "Food + Services units sold", 1.0, "units/wk", ("mean",)),
    ("consumer_price_index", "Consumer price index", 1.0, "index", ("mean",)),
    ("mean_price", "Mean posted price", 1.0, "$", ("mean",)),
    ("fiscal_balance", "Fiscal balance (revenue - spending)", 1.0, "$/wk", ("mean", "min")),
    ("government_cash", "Treasury cash", 1.0, "$", ("mean", "min", "neg_share")),
    ("bond_buy", "Bond buy paid to misc pool (K06)", 1.0, "$/wk", ("mean",)),
    ("private_profit", "Private firm profit", 1.0, "$/wk", ("mean",)),
    ("private_firms", "Private firms", 1.0, "firms", ("mean",)),
    ("poverty_share", "Poverty (liquid < poverty line)", 100.0, "%", ("mean",)),
    ("extreme_poverty_share", "Extreme poverty (liquid < extreme line)", 100.0, "%", ("mean",)),
    ("food_sufficient_share", "Households eating minimum food", 100.0, "%", ("mean",)),
    ("happiness", "Happiness", 1.0, "index", ("mean",)),
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
    "neg_share": "share of weeks below 0 (%)",
    "cv": "volatility (sd / mean, %)",
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


def aggregate(values: list[float], how: str) -> float | None:
    if not values:
        return None
    if how == "mean":
        return statistics.fmean(values)
    if how == "min":
        return min(values)
    if how == "neg_share":
        return sum(1 for value in values if value < 0.0) / len(values)
    if how == "cv":
        avg = statistics.fmean(values)
        return statistics.pstdev(values) / abs(avg) if avg else None
    raise ValueError(f"Unknown aggregation {how!r}")


def metric_specs(rows: list[dict[str, Any]]) -> list[tuple[str, str, float, str, tuple[str, ...]]]:
    """The standard metrics plus any plugin metrics (``x_`` prefix) present in the rows."""
    extra = sorted({key for row in rows for key in row if key.startswith("x_")})
    return [*METRICS, *((key, f"{key[2:]} (plugin)", 1.0, "", ("mean",)) for key in extra)]


def window_values(rows: list[dict[str, Any]], windows: list[tuple[str, int, int]]) -> dict[str, dict[str, float | None]]:
    """Per window, each metric's aggregate over the ticks it covers. Keys are ``metric:aggregation``."""
    result: dict[str, dict[str, float | None]] = {}
    specs = metric_specs(rows)
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


def lock_sha256(root: Path) -> str | None:
    lock = root / "backend" / "requirements.lock"
    return hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None


def parse_assignments(pairs: list[list[str]], arms: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    """Split ``--set ARM key=value`` into config overrides and policy levers per arm."""
    plan = {arm: {"config_overrides": {}, "levers": {}} for arm in arms}
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
            plan[arm]["levers"][key[len("lever."):]] = value.strip()
        else:
            plan[arm]["config_overrides"][key] = value.strip()
    return plan


def plan_runs(args: argparse.Namespace, runtime: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arms = list(args.arm)
    if len(set(arms)) != len(arms) or any(slugify(arm) != arm for arm in arms):
        raise ValueError(f"Arm names must be unique and use only lowercase letters, digits, '.', '_' or '-': {arms}")
    baseline = args.baseline or arms[0]
    if baseline not in arms:
        raise ValueError(f"--baseline {baseline!r} is not one of the arms {arms}")
    sequences = parse_str_list(args.sequences)
    if not set(sequences) <= set(PAYMENT_SEQUENCES) or len(set(sequences)) != len(sequences):
        raise ValueError(f"--sequences must be distinct values from {PAYMENT_SEQUENCES}")
    seeds = parse_int_list(args.seeds)
    if len(set(seeds)) != len(seeds):
        raise ValueError("--seeds must be distinct")
    roots = {arm: repo_root() for arm in arms}
    for arm, path in args.root:
        if arm not in roots:
            raise ValueError(f"--root names unknown arm {arm!r}")
        roots[arm] = Path(path).resolve()
        if not (roots[arm] / "backend" / "economy.py").exists():
            raise ValueError(f"--root {arm} {path}: no backend/economy.py there")
    assignments = parse_assignments(args.set, arms)
    plugin = str(Path(args.metrics_plugin).resolve()) if args.metrics_plugin else None
    identities = {str(root): model_identity(root) for root in sorted(set(roots.values()), key=str)}

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
            "metrics_plugin": plugin,
            "metrics_plugin_sha256": hashlib.sha256(Path(plugin).read_bytes()).hexdigest() if plugin else None,
            # A changed worker measures differently, so its finished runs are not reused.
            "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "pythonhashseed": PYTHONHASHSEED,
            # Part of the cache key: a finished run is reused only under the same
            # interpreter, numpy, dependency lock and thread settings.
            "runtime": {
                "python": runtime["python"],
                "implementation": runtime["implementation"],
                "numpy": runtime["numpy"],
                "requirements_lock_sha256": lock_sha256(roots[arm]),
                "thread_env": THREAD_ENV,
            },
        }

    specs =[spec(arm, sequence, seed) for sequence in sequences for arm in arms for seed in seeds]
    if args.determinism_check:
        specs += [spec(baseline, sequence, seeds[0], repeat=True) for sequence in sequences]
    design = {
        "arms": arms,
        "baseline": baseline,
        "sequences": sequences,
        "seeds": seeds,
        "roots": {arm: str(root) for arm, root in roots.items()},
        "assignments": assignments,
        "model_identities": identities,
        "metrics_plugin": plugin,
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


def summarize(results: list[dict[str, Any]], design: dict[str, Any], windows: list[tuple[str, int, int]]) -> dict[str, Any]:
    baseline = design["baseline"]
    main_runs = {(r["spec"]["arm"], r["spec"]["payment_sequence"], r["spec"]["seed"]): r for r in results if not r["spec"]["repeat"]}
    repeats = [r for r in results if r["spec"]["repeat"]]
    values = {key: window_values(run["rows"], windows) for key, run in main_runs.items()}

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
                # Keys keep the METRICS order (window_values builds them in that order).
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
        for sequence in design["sequences"]:
            for seed in design["seeds"]:
                run = main_runs.get((arm, sequence, seed))
                base = main_runs.get((baseline, sequence, seed))
                if run is None:
                    continue
                if base is not None and arm != baseline:
                    identical.append(run["fingerprint"] == base["fingerprint"])
                if run["money"]["final_drift"] is not None:
                    drift.append(run["money"]["final_drift"])
        checks["arms"][arm] = {
            "identical_to_baseline": None if arm == baseline else {"identical": sum(identical), "runs": len(identical)},
            "money_final_drift_mean": statistics.fmean(drift) if drift else None,
            "money_final_drift_max_abs": max((abs(value) for value in drift), default=None),
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

    return {
        "levels": levels,
        "comparisons": comparisons,
        "checks": checks,
        "window_values": {f"{arm}|{sequence}|{seed}": v for (arm, sequence, seed), v in values.items()},
    }


# --------------------------------------------------------------------------- report


def _fmt(value: float | None, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    magnitude = abs(value)
    digits = 0 if magnitude >= 1000 else 1 if magnitude >= 10 else 2 if magnitude >= 1 else 3
    text = f"{value:{'+' if signed else ''},.{digits}f}"
    return "0" if signed and float(text.replace(",", "")) == 0 else text


def _scale_for(key: str) -> tuple[str, float, str]:
    metric, _, how = key.partition(":")
    for name, label, scale, unit, _ in METRICS:
        if name == metric:
            break
    else:
        label, scale, unit = f"{metric[2:]} (plugin)", 1.0, ""
    if how in ("neg_share", "cv"):
        scale, unit = 100.0, "%"
    suffix = AGGREGATION_LABELS.get(how, how)
    return (f"{label}, {suffix}" if suffix else label), scale, unit


def render_markdown(panel: dict[str, Any]) -> str:
    design, settings, summary = panel["design"], panel["settings"], panel["summary"]
    baseline = design["baseline"]
    lines = [
        "# Evidence panel",
        "",
        f"`{panel['manifest']['command']}`",
        "",
        f"- **Setup:** {settings['households']:,} households, {settings['firms_per_category']} firms per category, "
        f"{settings['ticks']} ticks, seeds {', '.join(map(str, design['seeds']))} (one process per run, PYTHONHASHSEED={PYTHONHASHSEED}).",
        f"- **Worker runtime:** Python {panel['manifest']['worker_runtime']['python']}, "
        f"numpy {panel['manifest']['worker_runtime']['numpy']}, one numeric-library thread per run.",
        f"- **Windows:** {', '.join(label for label in settings['windows'])}. **Baseline:** `{baseline}`.",
    ]
    for arm in design["arms"]:
        identity = design["model_identities"][design["roots"][arm]]
        changes = {**design["assignments"][arm]["config_overrides"],
                   **{f"lever.{k}": v for k, v in design["assignments"][arm]["levers"].items()}}
        change_text = ", ".join(f"`{k}={v}`" for k, v in sorted(changes.items())) or "no changes"
        dirty = " (uncommitted changes)" if identity.get("working_tree_dirty") else ""
        lines.append(f"- **`{arm}`:** {change_text}; commit `{(identity.get('commit') or 'unknown')[:10]}`{dirty}.")
    lines += ["", "## Checks", "", "| Arm | Runs identical to baseline | Unrecorded money drift at end (mean, max abs) |", "|---|---|---|"]
    for arm, check in summary["checks"]["arms"].items():
        ident = check["identical_to_baseline"]
        ident_text = "baseline" if ident is None else f"{ident['identical']}/{ident['runs']}"
        lines.append(f"| `{arm}` | {ident_text} | {_fmt(check['money_final_drift_mean'])}, {_fmt(check['money_final_drift_max_abs'])} |")
    det = summary["checks"]["determinism"]
    if det:
        same = sum(1 for d in det if d["identical"])
        lines += ["", f"Repeat of `{baseline}` seed {det[0]['seed']} on each sequence: {same}/{len(det)} identical."]
    lines += [
        "",
        "Each cell gives the baseline's level, then the paired difference (arm minus baseline): the mean over seeds, "
        "[min, max], and how many seeds went up. Shares are in percent, so their differences are percentage points. "
        "**!** marks a mean whose sign flips when any one seed is left out, so read the median and the range instead.",
    ]
    for arm, by_sequence in summary["comparisons"].items():
        ident = summary["checks"]["arms"][arm]["identical_to_baseline"]
        if ident["runs"] and ident["identical"] == ident["runs"]:
            lines += ["", f"## `{arm}` vs `{baseline}`", "", f"Identical on all {ident['runs']} runs: every per-tick row hashes the same, so every difference is zero."]
            continue
        for sequence in design["sequences"]:
            by_window = by_sequence.get(sequence, {})
            labels = [label for label in settings["windows"] if label in by_window]
            if not labels:
                continue
            lines += ["", f"## `{arm}` vs `{baseline}`: {sequence}", ""]
            lines.append("| Metric | " + " | ".join(f"{label}: {baseline} | {label}: difference" for label in labels) + " |")
            lines.append("|---|" + "---|---|" * len(labels))
            for key in by_window[labels[0]]:
                name, scale, unit = _scale_for(key)
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
                        f"{_fmt(stats['max'] * scale, signed=True)}] {stats['up']}/{stats['n']} up{flag}"
                    )
                lines.append(f"| {name}{f' ({unit})' if unit else ''} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Definitions",
        "",
        "- **Unemployment, labour force:** jobless households among those that can work (`labor_force_unemployment_rate`).",
        "- **Jobless, all households:** share of all households without a job, including those that cannot work (`compute_household_stats`, the dashboard's figure).",
        "- **Real GDP:** nominal GDP (`gdp_this_tick`, a sales proxy) divided by the engine's posted consumer price index, times 100.",
        "- **Poverty:** share of households whose liquid wealth (cash plus bank deposits) is below `households.poverty_threshold`; extreme uses `extreme_poverty_threshold`.",
        "- **Households eating minimum food:** 1 minus `food_insecure_share` (food eaten last tick at least the household's minimum).",
        "- **Bond buy (K06):** the treasury's weekly bond purchase paid out through the misc pool; check it before crediting a GDP or household change to a policy.",
        "- **Unrecorded money drift:** change in total money net of recorded outside money (`total_money_net_of_injections`) from construction to the last tick.",
        "- **Runs identical:** per-tick panel rows hash the same at full precision.",
    ]
    return "\n".join(lines) + "\n"


def write_window_csv(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for run_key, per_window in summary["window_values"].items():
        arm, sequence, seed = run_key.split("|")
        for label, values in per_window.items():
            rows.append({"arm": arm, "payment_sequence": sequence, "seed": seed, "window": label, **values})
    fields = sorted({key for row in rows for key in row}, key=lambda k: (k not in ("arm", "payment_sequence", "seed", "window"), k))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Paired evidence panel at the dashboard's defaults.")
    p.add_argument("--arm", action="append", required=True, help="Arm name (repeat). The first is the baseline unless --baseline.")
    p.add_argument("--set", action="append", nargs=2, default=[], metavar=("ARM", "KEY=VALUE"),
                   help="section.field=value (config, before build) or lever.name=value (policy, after build).")
    p.add_argument("--root", action="append", nargs=2, default=[], metavar=("ARM", "PATH"),
                   help="Run ARM from another checkout (default: this one).")
    p.add_argument("--baseline", help="Arm the others are compared with (default: the first --arm).")
    p.add_argument("--sequences", default=",".join(PAYMENT_SEQUENCES), help="Payment sequences, income_first first.")
    p.add_argument("--seeds", default="42,43,44,45,46")
    p.add_argument("--households", type=int, default=1000)
    p.add_argument("--firms-per-category", type=int, default=5)
    p.add_argument("--ticks", type=int, default=260)
    p.add_argument("--windows", default="1-100,101-200,201-", help="Inclusive tick windows; an open end means the last tick.")
    p.add_argument("--metrics-plugin", help="File defining extra_metrics(economy) -> dict[str, float].")
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--no-determinism-check", dest="determinism_check", action="store_false",
                   help="Skip repeating the baseline's first seed on each sequence.")
    p.add_argument("--out", type=Path, help="Run folder (reused on rerun). Default: benchmarks/results/<timestamp>-evidence-panel.")
    p.add_argument("--python", default=sys.executable, help="Interpreter for the worker processes.")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    windows = parse_windows(args.windows, args.ticks)
    runtime = probe_runtime(args.python)
    specs, design = plan_runs(args, runtime)
    if args.out is not None:
        run_dir = args.out.resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = BenchmarkPaths.create(default_results_root(), "evidence-panel").run_dir
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    print(f"[panel] {len(specs)} runs, {args.jobs} at a time -> {run_dir}", flush=True)
    results, failures = execute(specs, run_dir / "runs", args.jobs, args.python)
    command = "python -m backend.tools.benchmarks.run_evidence_panel " + shlex.join(argv)
    panel = {
        "manifest": {
            "command": command,
            "cwd": str(Path.cwd()),
            "started_at": started,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "runner_python": sys.version.split()[0],
            "worker_runtime": runtime,
            "pythonhashseed": PYTHONHASHSEED,
            "thread_env": THREAD_ENV,
        },
        "settings": {
            "households": args.households,
            "firms_per_category": args.firms_per_category,
            "ticks": args.ticks,
            "windows": [label for label, _, _ in windows],
        },
        "design": design,
        "failures": failures,
    }
    if failures:
        (run_dir / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[panel] {len(failures)} runs failed; no table written. Details in {run_dir / 'panel.json'}", file=sys.stderr)
        return 1
    panel["summary"] = summarize(results, design, windows)
    (run_dir / "panel.json").write_text(json.dumps(panel, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "panel.md").write_text(render_markdown(panel), encoding="utf-8")
    write_window_csv(run_dir / "window_values.csv", panel["summary"])
    print(f"[panel] wrote {run_dir / 'panel.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
