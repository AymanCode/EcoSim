"""Summary math for the evidence panel: env, windows, scores, checks, escalation.

The worker measures. This module only aggregates finished runs, so it imports
nothing from the simulator.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# One line. "relative" until money-identity PR #57 merges, then "absolute".
MONEY_CHECK_MODE = "relative"
# One dust tolerance for both modes. A conserved stock over 312 weeks picks up
# about 1e-5 dollars of float error (measured on the O9 run). 1e-4 dollars is
# ten times that dust and a hundredth of a cent, so a real leak still fails.
# Scaling the cutoff to the money stock would hide a dollar on a multi-million stock.
DUST_TOLERANCE = 1e-4
# legacy still leaks until #57, so that sequence is reported and not failed.
# Every other sequence, including the baseline arm, must stay inside the dust tolerance.
REPORT_ONLY_SEQUENCES = frozenset({"legacy"})

UNEMPLOYMENT_BAND = (10.0, 40.0)
REAL_GDP_BASE_WEEKS = (11, 62)
ESCALATION_SEEDS = list(range(47, 55))
CANONICAL_SEEDS = list(range(42, 47))
WEEKS_PER_MONTH = 52.0 / 12.0

# Headline paired series that can escalate a 5-seed panel.
HEADLINE_KEYS = {
    "labor_force_unemployment_rate:mean",
    "real_gdp_paid:mean",
    "real_gdp:mean",
    "gdp:mean",
    "poverty_share:mean",
    "happiness:mean",
}

RATE_BOUNDS = {
    "labor_force_unemployment_rate": (0.0, 1.0),
    "unemployment_rate": (0.0, 1.0),
    "poverty_share": (0.0, 1.0),
    "extreme_poverty_share": (0.0, 1.0),
    "food_sufficient_share": (0.0, 1.0),
    "happiness": (0.0, 1.0),
    "health": (0.0, 1.0),
    "job_finding_rate": (0.0, 1.0),
    "happiness_le_005": (0.0, 1.0),
    "happiness_ge_095": (0.0, 1.0),
}

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", "benchmarks", ".mypy_cache"}

# Per-week state digest components, in the order a divergence is reported.
# evidence_panel_worker.STATE_COMPONENTS writes the same names.
STATE_COMPONENTS = ("households", "firms", "government", "bank", "loans", "payments", "rng")

# Comparability stamps. The reference environment is a GitHub-hosted Linux
# runner with the locked packages. A local run with the locked packages is
# labelled non-reference; --allow-nonref runs without them.
REFERENCE = "reference"
LOCAL_RUN = "non-reference (local or CI smoke)"
NOT_COMPARABLE = "NON-REFERENCE ENV, not comparable"
WITHIN_RUN_NOTE = (
    "Compare arms within this run only. GitHub-hosted runners differ in CPU model, so numbers "
    "from two runs, or from a local run, are not comparable even when every version stamp matches."
)
HOST_ENV_KEYS = ("GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion", "ECOSIM_PANEL_TIER")


def host_stamp(environ: dict[str, str]) -> dict[str, str | None]:
    """The CI runner variables that say where the panel ran. All None on a local machine."""
    return {key: environ.get(key) for key in HOST_ENV_KEYS}


def comparability_label(env_ok: bool, allow_nonref: bool, host: dict[str, Any], system: str) -> str:
    """``reference`` only on a GitHub-hosted Linux runner with the locked packages."""
    if allow_nonref or not env_ok:
        return NOT_COMPARABLE
    hosted = host.get("GITHUB_ACTIONS") == "true" and host.get("RUNNER_ENVIRONMENT") == "github-hosted"
    return REFERENCE if hosted and system == "Linux" and host.get("ECOSIM_PANEL_TIER") == "full" else LOCAL_RUN


def clip_default_windows(parts: list[tuple[int, int]], ticks: int) -> list[tuple[str, int, int]]:
    """Fit the default windows to a shorter run. ``--weeks 260`` drops 261-312 and clips 201-312."""
    windows = []
    for start, end in parts:
        if start > ticks:
            continue
        end = min(end, ticks)
        if start <= end:
            windows.append((f"{start}-{end}", start, end))
    if not windows:
        raise ValueError(f"No default window lies inside 1-{ticks}")
    return windows


def window_role(start: int) -> str:
    """Weeks 1-100 are reported and not judged. Windows that start at week 201 or later are judged."""
    if start >= 201:
        return "judged"
    if start == 1:
        return "reported, not judged"
    return "reported"


def band_distance_points(rate: float) -> float:
    """Points outside the 10-40% band. Zero inside. ``rate`` is a fraction."""
    unemployment = float(rate) * 100.0
    low, high = UNEMPLOYMENT_BAND
    return max(0.0, low - unemployment, unemployment - high)


def _sign(value: float) -> int:
    return (value > 0.0) - (value < 0.0)


def seed_carries_half(deltas: list[float]) -> bool:
    total = sum(deltas)
    if total == 0.0 or not deltas:
        return False
    return max(abs(value) for value in deltas) > 0.5 * abs(total)


def is_fragile(stats: dict[str, Any]) -> bool:
    """A paired result needs more seeds when the five-seed answer is not stable.

    Fragile when fewer than 4/5 seeds agree on the sign, the median and the mean
    disagree in sign, one seed carries more than half the summed delta, or
    leaving one seed out flips the sign.
    """
    deltas = list(stats.get("per_seed") or [])
    n = int(stats.get("n") or 0)
    if n < 5 or not deltas or not any(value != 0.0 for value in deltas):
        return False
    if max(int(stats.get("up") or 0), int(stats.get("down") or 0)) / n < 0.8:
        return True
    mean = float(stats.get("mean") or 0.0)
    median = float(stats.get("median") or 0.0)
    if _sign(mean) != 0 and _sign(median) != 0 and _sign(mean) != _sign(median):
        return True
    if seed_carries_half(deltas):
        return True
    if stats.get("loo_sign_stable") is False:
        return True
    return False


def escalation_reasons(summary: dict[str, Any], design: dict[str, Any], windows: list[tuple[str, int, int]]) -> list[str]:
    if list(design.get("seeds") or []) != CANONICAL_SEEDS:
        return []
    judged = {label for label, start, _end in windows if start >= 201}
    reasons = []
    for arm, by_sequence in (summary.get("comparisons") or {}).items():
        for sequence, by_window in by_sequence.items():
            for label, table in by_window.items():
                if label not in judged:
                    continue
                for key, stats in table.items():
                    if key in HEADLINE_KEYS and is_fragile(stats):
                        reasons.append(f"{arm} {sequence} {label} {key}")
    return reasons


def _category_totals(rows: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]]:
    units: dict[str, float] = {}
    revenue: dict[str, float] = {}
    for row in rows:
        for key, value in row.items():
            if value is None:
                continue
            if key.startswith("units__"):
                category = key[len("units__"):]
                units[category] = units.get(category, 0.0) + float(value)
            elif key.startswith("rev__"):
                category = key[len("rev__"):]
                revenue[category] = revenue.get(category, 0.0) + float(value)
    return units, revenue


def base_paid_prices(rows: list[dict[str, Any]], start: int = REAL_GDP_BASE_WEEKS[0], end: int = REAL_GDP_BASE_WEEKS[1]) -> tuple[dict[str, float], str]:
    """Category paid price (revenue / units) on the baseline arm.

    Weeks 11-62 are the first post-warmup year (warmup is 10 ticks). A run that
    never reaches week 11 uses every simulated week so a short panel still has a base.
    """
    chosen = [row for row in rows if start <= int(row["tick"]) <= end]
    label = f"{start}-{end}"
    if not chosen:
        chosen = list(rows)
        label = "all simulated weeks"
    units, revenue = _category_totals(chosen)
    prices = {
        category: revenue[category] / units[category]
        for category in units
        if units[category] > 0.0 and category in revenue
    }
    return prices, label


def paid_real_gdp(row: dict[str, Any], prices: dict[str, float]) -> float | None:
    if not prices:
        return None
    total = 0.0
    seen = False
    for category, price in prices.items():
        units = row.get(f"units__{category}")
        if units is None:
            continue
        total += float(units) * float(price)
        seen = True
    return total if seen else None


def attach_paid_real_gdp(results: list[dict[str, Any]], design: dict[str, Any]) -> dict[str, Any]:
    """Write ``real_gdp_paid`` onto every row from the baseline arm's base prices."""
    runs = {
        (run["spec"]["arm"], run["spec"]["payment_sequence"], run["spec"]["seed"]): run
        for run in results
        if not run["spec"].get("repeat")
    }
    bases: dict[str, Any] = {}
    for sequence in design["sequences"]:
        for seed in design["seeds"]:
            base = runs.get((design["baseline"], sequence, seed))
            if base is None:
                continue
            prices, label = base_paid_prices(base["rows"])
            bases[f"{sequence}|{seed}"] = {"window": label, "prices": prices}
            for arm in design["arms"]:
                run = runs.get((arm, sequence, seed))
                if run is None:
                    continue
                for row in run["rows"]:
                    row["real_gdp_paid"] = paid_real_gdp(row, prices)
            repeat = next((
                run for run in results
                if run["spec"].get("repeat")
                and run["spec"]["payment_sequence"] == sequence
                and run["spec"]["seed"] == seed
                and run["spec"]["arm"] == design["baseline"]
            ), None)
            if repeat is not None:
                for row in repeat["rows"]:
                    row["real_gdp_paid"] = paid_real_gdp(row, prices)
    return bases


def unemployment_report(results: list[dict[str, Any]], design: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Band distance on labour-force unemployment from week 201. The all-households rate is unjudged."""
    runs = {
        (run["spec"]["arm"], run["spec"]["payment_sequence"], run["spec"]["seed"]): run
        for run in results
        if not run["spec"].get("repeat")
    }
    scores: dict[str, Any] = {}
    warnings: list[str] = []
    for sequence in design["sequences"]:
        scores[sequence] = {}
        for arm in design["arms"]:
            distances = []
            levels = []
            dashboard = []
            for seed in design["seeds"]:
                run = runs.get((arm, sequence, seed))
                if run is None:
                    continue
                labour = [float(row["labor_force_unemployment_rate"]) for row in run["rows"] if int(row["tick"]) >= 201]
                all_households = [float(row["unemployment_rate"]) for row in run["rows"] if int(row["tick"]) >= 201]
                if not labour:
                    continue
                distances.append(statistics.fmean(band_distance_points(value) for value in labour))
                levels.append(statistics.fmean(labour) * 100.0)
                if all_households:
                    dashboard.append(statistics.fmean(all_households) * 100.0)
            if not distances:
                scores[sequence][arm] = None
                continue
            level = statistics.fmean(levels)
            record = {
                "band_distance_points": statistics.fmean(distances),
                "band_distance_median": statistics.median(distances),
                "labor_force_unemployment_pct": level,
                "below_band": level < UNEMPLOYMENT_BAND[0],
                "above_band": level > UNEMPLOYMENT_BAND[1],
                "all_households_unemployment_pct": statistics.fmean(dashboard) if dashboard else None,
                "all_households_judged": False,
                "warning": level < UNEMPLOYMENT_BAND[0] or level > UNEMPLOYMENT_BAND[1],
            }
            scores[sequence][arm] = record
            if arm == design["baseline"] and record["below_band"]:
                warnings.append(
                    f"{sequence}: baseline labour-force unemployment is {level:.1f}% over weeks 201+, "
                    "below the 10-40% band. Warning only; this does not fail the run. "
                    "The all-households figure is printed beside it and is not judged."
                )
            elif arm == design["baseline"] and record["above_band"]:
                warnings.append(
                    f"{sequence}: baseline labour-force unemployment is {level:.1f}% over weeks 201+, "
                    "above the 10-40% band. Warning only; this does not fail the run."
                )
    return scores, warnings


def first_divergence(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    """First week whose full-state digest differs, and which component moved."""
    digests_left = left.get("state_digests") or []
    digests_right = right.get("state_digests") or []
    for one, other in zip(digests_left, digests_right):
        if one.get("combined") == other.get("combined"):
            continue
        component = next(
            (name for name in STATE_COMPONENTS if one.get(name) != other.get(name)),
            "combined",
        )
        return {"tick": int(one.get("tick") or 0), "component": component}
    if len(digests_left) != len(digests_right):
        return {"tick": min(len(digests_left), len(digests_right)) + 1, "component": "length"}
    return None


def legacy_last_exit(run: dict[str, Any]) -> int | None:
    weeks = [int(row["tick"]) for row in run.get("rows") or [] if float(row.get("legacy_exits") or 0.0) > 0.0]
    return max(weeks) if weeks else None


def _final_drift(run: dict[str, Any] | None) -> float | None:
    if run is None:
        return None
    value = (run.get("money") or {}).get("final_drift")
    if value is None:
        return None
    return float(value)


def _drift_usable(drift: float | None) -> bool:
    return drift is not None and math.isfinite(drift)


def _money_failure(arm: str, sequence: str, seed: int, drift: float | None, base_drift: float | None, mode: str, reason: str) -> dict[str, Any]:
    return {
        "arm": arm, "payment_sequence": sequence, "seed": seed,
        "drift": drift, "baseline_drift": base_drift, "mode": mode, "reason": reason,
    }


def evaluate_money(results: list[dict[str, Any]], design: dict[str, Any]) -> dict[str, Any]:
    """Fail when an arm's money drift does not match the rule.

    Relative (default until #57): income_first and income_late must conserve,
    including the baseline arm, so a nightly main-only run fails if those
    sequences start leaking. Another arm on those sequences fails only when
    the baseline itself conserves and that arm leaks. legacy is report-only
    until #57. A NaN or inf drift fails in every mode and on every sequence.

    Absolute: every run's final drift is within ``DUST_TOLERANCE`` of zero.
    """
    mode = MONEY_CHECK_MODE
    tolerance = DUST_TOLERANCE
    baseline = design["baseline"]
    runs = {
        (run["spec"]["arm"], run["spec"]["payment_sequence"], run["spec"]["seed"]): run
        for run in results
        if not run["spec"].get("repeat")
    }
    sequences: dict[str, Any] = {}
    for sequence in design["sequences"]:
        base_drifts = [_final_drift(runs.get((baseline, sequence, seed))) for seed in design["seeds"] if (baseline, sequence, seed) in runs]
        usable = [value for value in base_drifts if _drift_usable(value)]
        conserves = bool(base_drifts) and len(usable) == len(base_drifts) and all(abs(value) <= tolerance for value in usable)
        finite_abs = [abs(value) for value in usable]
        sequences[sequence] = {
            "conserves": conserves,
            "must_conserve": sequence not in REPORT_ONLY_SEQUENCES,
            "baseline_max_abs_drift": max(finite_abs, default=None),
        }
    failures = []
    drift_gaps = []
    for arm in design["arms"]:
        for sequence in design["sequences"]:
            deltas = []
            must_conserve = sequence not in REPORT_ONLY_SEQUENCES
            for seed in design["seeds"]:
                run = runs.get((arm, sequence, seed))
                if run is None:
                    continue
                drift = _final_drift(run)
                base_drift = _final_drift(runs.get((baseline, sequence, seed)))
                if not _drift_usable(drift):
                    reason = "non-finite money drift" if drift is not None else "money drift unavailable"
                    failures.append(_money_failure(arm, sequence, seed, drift, base_drift, mode, reason))
                    continue
                if mode == "absolute":
                    if abs(drift) > tolerance:
                        failures.append(_money_failure(
                            arm, sequence, seed, drift, base_drift, mode,
                            "absolute drift outside the dust tolerance",
                        ))
                    continue
                is_baseline = arm == baseline
                new_leak = not is_baseline and sequences[sequence]["conserves"]
                if must_conserve and abs(drift) > tolerance and (is_baseline or new_leak):
                    reason = (
                        "baseline leak on a sequence that must conserve"
                        if is_baseline
                        else "new leak on a sequence the baseline conserves"
                    )
                    failures.append(_money_failure(arm, sequence, seed, drift, base_drift, mode, reason))
                if arm == baseline or not _drift_usable(base_drift):
                    continue
                deltas.append(drift - base_drift)
            if mode == "relative" and arm != baseline and deltas:
                drift_gaps.append({
                    "arm": arm,
                    "payment_sequence": sequence,
                    "baseline_conserves": sequences[sequence]["conserves"],
                    "median": statistics.median(deltas),
                    "mean": statistics.fmean(deltas),
                    "min": min(deltas),
                    "max": max(deltas),
                    "up": sum(1 for value in deltas if value > 0.0),
                    "n": len(deltas),
                    "per_seed": deltas,
                })
    return {
        "mode": mode,
        "tolerance": tolerance,
        "passed": not failures,
        "failures": failures,
        "sequences": sequences,
        "drift_gaps": drift_gaps,
    }


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def row_violations(row: dict[str, Any], extra_bounds: dict[str, tuple[float | None, float | None]] | None = None) -> list[dict[str, Any]]:
    violations = []
    tick = int(row.get("tick") or 0)
    for key, value in row.items():
        if key == "tick" or key.startswith("units__") or key.startswith("rev__"):
            continue
        if isinstance(value, float) and not math.isfinite(value):
            violations.append({"tick": tick, "metric": key, "value": None, "reason": "nonfinite"})
    for key, (low, high) in {**RATE_BOUNDS, **(extra_bounds or {})}.items():
        value = row.get(key)
        if value is None or not _finite(value):
            continue
        number = float(value)
        if low is not None and number < low - 1e-9:
            violations.append({"tick": tick, "metric": key, "value": number, "reason": f"below {low}"})
        if high is not None and number > high + 1e-9:
            violations.append({"tick": tick, "metric": key, "value": number, "reason": f"above {high}"})
    price = row.get("mean_price")
    if _finite(price) and float(price) < 0.0:
        violations.append({"tick": tick, "metric": "mean_price", "value": float(price), "reason": "negative price"})
    cpi = row.get("consumer_price_index")
    if _finite(cpi) and float(cpi) <= 0.0:
        violations.append({"tick": tick, "metric": "consumer_price_index", "value": float(cpi), "reason": "non-positive CPI"})
    return violations


def evaluate_bounds(results: list[dict[str, Any]], extra_bounds: dict[str, tuple[float | None, float | None]] | None = None) -> dict[str, Any]:
    violations = []
    for run in results:
        if run["spec"].get("repeat"):
            continue
        for row in run.get("rows") or []:
            for item in row_violations(row, extra_bounds):
                item["arm"] = run["spec"]["arm"]
                item["payment_sequence"] = run["spec"]["payment_sequence"]
                item["seed"] = run["spec"]["seed"]
                violations.append(item)
                if len(violations) >= 50:
                    return {"passed": False, "violations": violations, "truncated": True}
    return {"passed": not violations, "violations": violations, "truncated": False}


def check_failures(checks: dict[str, Any]) -> list[str]:
    reasons = []
    money = checks.get("money") or {}
    bounds = checks.get("bounds") or {}
    if money and not money.get("passed", True):
        reasons.append(f"money identity ({money.get('mode')})")
    if bounds and not bounds.get("passed", True):
        reasons.append("bounds or non-finite values")
    determinism = checks.get("determinism") or []
    if any(not item.get("identical", True) for item in determinism):
        reasons.append("determinism repeat")
    return reasons


def parse_lock_pins(text: str) -> dict[str, str]:
    pins = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower().replace("_", "-")] = version.strip()
    return pins


def compare_lock(pins: dict[str, str], versions: dict[str, str]) -> dict[str, Any]:
    """``versions`` maps canonical distribution name to the installed version."""
    missing = []
    mismatched = []
    for name, locked in sorted(pins.items()):
        installed = versions.get(name)
        if installed is None:
            missing.append(name)
        elif installed != locked:
            mismatched.append({"name": name, "lock": locked, "installed": installed})
    return {"pins": len(pins), "missing": missing, "mismatched": mismatched, "ok_packages": not missing and not mismatched}


def reference_python(implementation: str, version: str) -> bool:
    return implementation == "CPython" and version.startswith("3.11.")


def reference_decision(python_ok: bool, packages: dict[str, Any]) -> dict[str, Any]:
    ok = bool(python_ok and packages.get("ok_packages"))
    return {"ok": ok, "python_ok": python_ok, **packages}


def probe_installed_versions(python: str) -> dict[str, str]:
    """Distribution versions reported by the worker interpreter."""
    script = (
        "import json, importlib.metadata as md\n"
        "out = {}\n"
        "for dist in md.distributions():\n"
        "    name = (dist.metadata['Name'] or '').lower().replace('_', '-')\n"
        "    if name:\n"
        "        out[name] = dist.version\n"
        "print(json.dumps(out))\n"
    )
    completed = subprocess.run([python, "-c", script], capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def load_plugin_module(path: str):
    spec = importlib.util.spec_from_file_location(f"evidence_plugin_{Path(path).stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load metrics plugin {path!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "extra_metrics", None)):
        raise ValueError(f"Metrics plugin {path!r} must define extra_metrics(economy) -> dict")
    return module


def plugin_display(paths: list[str]) -> tuple[list[tuple[str, str, float, str, tuple[str, ...]]], dict[str, tuple[float | None, float | None]]]:
    """Metric rows and bounds declared by plugins. Unknown plugins stay mean-only."""
    rows = []
    bounds = {}
    for path in paths:
        module = load_plugin_module(path)
        for name, meta in (getattr(module, "METRICS", None) or {}).items():
            label, unit, aggregations, bound = meta
            scale = 100.0 if unit == "%" else 1.0
            key = f"x_{name}"
            rows.append((key, str(label), scale, "" if unit == "%" else str(unit), tuple(aggregations)))
            if bound:
                low = None if bound[0] is None else float(bound[0])
                high = None if len(bound) < 2 or bound[1] is None else float(bound[1])
                bounds[key] = (low, high)
    return rows, bounds


def plugin_summaries(paths: list[str], results: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for path in paths:
        module = load_plugin_module(path)
        summarize = getattr(module, "summarize", None)
        if callable(summarize):
            out[Path(path).name] = summarize(results)
    return out


def _link_or_copy(source: Path, target: Path) -> None:
    """Symlink ``target`` to ``source``; copy it where symlinks are not allowed.

    Windows refuses ``os.symlink`` without Developer Mode or admin rights
    (WinError 1314), so the mutation tree falls back to a copy there.
    """
    try:
        os.symlink(source, target)
    except (OSError, NotImplementedError):
        shutil.copy2(source, target)


def _overlay_tree(src: Path, dst: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".git")]
        relative = Path(dirpath).relative_to(src)
        (dst / relative).mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            target = dst / relative / name
            if not target.exists():
                _link_or_copy(Path(dirpath) / name, target)


def mutation_check(*, candidate_root: Path, main_root: Path, file_spec: str, tests: list[str], python: str) -> dict[str, Any]:
    """Revert ``FILE:L1-L2`` to ``main`` and require at least one named test to fail.

    The check passes when the reverted lines make a test fail. A test that still
    passes does not protect the line.
    """
    file_rel, sep, lines = file_spec.partition(":")
    start_text, dash, end_text = lines.partition("-")
    if not sep or not dash:
        raise ValueError(f"--mutate {file_spec!r} must look like path/file.py:10-12")
    start, end = int(start_text), int(end_text)
    if start < 1 or end < start:
        raise ValueError(f"--mutate line range {start}-{end} is not valid")
    candidate_file = candidate_root / file_rel
    main_file = main_root / file_rel
    if not candidate_file.is_file() or not main_file.is_file():
        raise ValueError(f"--mutate needs {file_rel} in both the candidate checkout and --root main")
    candidate_lines = candidate_file.read_text(encoding="utf-8").splitlines(keepends=True)
    main_lines = main_file.read_text(encoding="utf-8").splitlines(keepends=True)
    if end > len(candidate_lines) or end > len(main_lines):
        raise ValueError(f"--mutate {file_spec} extends past the end of the file")
    mutated = "".join(candidate_lines[: start - 1] + main_lines[start - 1: end] + candidate_lines[end:])
    tmp = Path(tempfile.mkdtemp(prefix="ecosim-mutate-"))
    try:
        _overlay_tree(candidate_root, tmp)
        target = tmp / file_rel
        if target.is_symlink() or target.exists():
            target.unlink()
        target.write_text(mutated, encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(tmp / "backend"), "PYTHONDONTWRITEBYTECODE": "1"}
        completed = subprocess.run(
            [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line", *tests],
            cwd=str(tmp), env=env, capture_output=True, text=True, timeout=600,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tail = (completed.stdout + "\n" + completed.stderr).strip().splitlines()[-20:]
    ok = completed.returncode != 0
    return {
        "ok": ok,
        "file": file_spec,
        "tests": list(tests),
        "returncode": completed.returncode,
        "detail": "at least one test failed after the revert" if ok else "reverting the lines did not fail any test",
        "output_tail": tail,
    }


def lock_sha256(path: Path) -> str | None:
    """sha256 of the lock with CRLF line endings read as LF.

    A Windows checkout with ``core.autocrlf`` and a Linux checkout of the same
    commit then stamp the same hash.
    """
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def format_reference_error(decision: dict[str, Any], version: str, implementation: str) -> str:
    parts = [f"Python {implementation} {version}"]
    mismatched = decision.get("mismatched") or []
    missing = decision.get("missing") or []
    if not decision.get("python_ok"):
        parts.append("not CPython 3.11")
    if mismatched:
        sample = ", ".join(f"{item['name']} lock {item['lock']} installed {item['installed']}" for item in mismatched[:6])
        parts.append(f"{len(mismatched)} version mismatch(es): {sample}")
    if decision.get("lock_error"):
        parts.append(str(decision["lock_error"]))
    if missing:
        parts.append(f"{len(missing)} lock pin(s) not installed: {', '.join(missing[:6])}")
    return (
        "Refusing to run: the evidence panel requires CPython 3.11 and the pins in backend/requirements.lock. "
        + "; ".join(parts)
        + ". Pass --allow-nonref to run anyway and stamp every output 'not comparable'."
    )
