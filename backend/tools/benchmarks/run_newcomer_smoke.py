"""Newcomer-scale policy-arm smoke run.

Runs matched-seed policy arms at the dashboard's default world size (1,000
households, five firms per category) for five simulated years and reports
whether each arm visibly separates from the baseline. It answers "would a
newcomer see two lines diverge on a five-year chart", not "is the effect
statistically significant"; the frozen, leakage-aware study remains
``policy_forecasting``.

Per-tick rows reuse the frozen manifest from
``policy_forecasting.sweep.wrapper.snapshot_manifest`` plus a few extra
columns read from ``Economy.get_economic_metrics()`` that the manifest does not
carry (firm count, homelessness, public-works firms and jobs, mean and median
wage).

Examples:
    python -m backend.tools.benchmarks.run_newcomer_smoke --seeds 1337,7
    python -m backend.tools.benchmarks.run_newcomer_smoke --arms baseline,benefit_high,min_wage_high \
        --payment-sequence income_first
    python -m backend.tools.benchmarks.run_newcomer_smoke --households 5000 --arms baseline

Outputs (default ``benchmarks/results/newcomer-smoke/<UTC timestamp>/``):
    <arm>_seed<seed>_<sequence>_hh<households>.csv       one row per tick
    <arm>_seed<seed>_<sequence>_hh<households>_meta.json  timing, payment marker, config
    run_meta.csv                                          one row per arm and seed
    summary.md                                            baseline motion and per-arm deltas
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from policy_forecasting.config import FROZEN_ARMS, PolicyArm, canonical_lever_json  # noqa: E402
from policy_forecasting.distress import DistressHistory  # noqa: E402
from policy_forecasting.sweep import wrapper  # noqa: E402
from policy_schema import POLICY_SCHEMA  # noqa: E402

from .common import (  # noqa: E402
    BenchmarkPaths,
    collect_metadata,
    parse_int_list,
    parse_str_list,
    repo_root,
    write_json,
    write_markdown,
    write_rows_csv,
)

PAYMENT_SEQUENCES: tuple[str, ...] = ("legacy", "income_first", "income_late")
PUBLIC_WORKS_ARM = PolicyArm("public_works_on", {"public_works": "on"})
ARM_CATALOG: dict[str, PolicyArm] = {arm.arm_id: arm for arm in (*FROZEN_ARMS, PUBLIC_WORKS_ARM)}
DEFAULT_ARMS: tuple[str, ...] = tuple(ARM_CATALOG)
DEFAULT_CHECKPOINTS: tuple[int, ...] = (52, 104, 156, 208, 260)
BASELINE_ARM_ID = "baseline"
MISSING_PAYMENT_COVERAGE = "<no coverage key>"

# Columns the frozen manifest does not carry, read straight from get_economic_metrics().
EXTRA_METRIC_KEYS: tuple[str, ...] = (
    "total_firms",
    "homeless_household_count",
    "public_works_firms",
    "public_works_jobs",
    "gov_public_works_jobs_authorized",
    "mean_wage",
    "median_wage",
    "median_price",
)

# (column, label, scale, decimals) used by the per-arm delta table.
DELTA_COLUMNS: tuple[tuple[str, str, float, int], ...] = (
    ("unemployment_rate", "Unemployment (pp)", 100.0, 1),
    ("mean_wage", "Mean wage", 1.0, 2),
    ("sector_price_food", "Food price", 1.0, 2),
    ("gov_cash", "Gov cash", 1.0, 0),
    ("mean_distress", "Distress", 1.0, 3),
    ("total_firms", "Firms", 1.0, 0),
    ("homeless_household_count", "Homeless", 1.0, 0),
    ("public_works_jobs", "PW jobs", 1.0, 0),
)


# --------------------------------------------------------------------------- arms


def validate_levers(levers: Mapping[str, Any]) -> None:
    """Reject levers or values outside the canonical action space in ``policy_schema``.

    Only membership and range are checked. ``max_step`` limits LLM proposals, not
    frozen experiment arms, which move straight to their target value.
    """
    for lever, value in levers.items():
        spec = POLICY_SCHEMA.get(lever)
        if spec is None:
            raise ValueError(f"Unknown policy lever {lever!r}")
        if isinstance(spec, dict):
            low, high = float(spec["min"]), float(spec["max"])
            if not low <= float(value) <= high:
                raise ValueError(f"{lever}={value!r} is outside [{low}, {high}]")
        elif value not in spec:
            raise ValueError(f"{lever}={value!r} is not one of {spec!r}")


def resolve_arms(arm_ids: Iterable[str]) -> list[PolicyArm]:
    """Look up arm names in the catalog and validate their levers."""
    arms: list[PolicyArm] = []
    for arm_id in arm_ids:
        arm = ARM_CATALOG.get(arm_id)
        if arm is None:
            raise ValueError(f"Unknown arm {arm_id!r}. Valid arms: {', '.join(ARM_CATALOG)}")
        validate_levers(arm.levers)
        arms.append(arm)
    return arms


# --------------------------------------------------------------------------- run


def output_stem(arm_id: str, seed: int, payment_sequence: str, households: int) -> str:
    return f"{arm_id}_seed{int(seed)}_{payment_sequence}_hh{int(households)}"


def _payment_marker(metrics: Mapping[str, Any]) -> tuple[str, Any]:
    payment = metrics.get("payment") or {}
    return payment.get("coverage", MISSING_PAYMENT_COVERAGE), payment.get("scenario")


def run_arm(
    arm: PolicyArm,
    *,
    seed: int,
    households: int,
    ticks: int,
    firms_per_category: int,
    payment_sequence: str = "legacy",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one arm and seed; return per-tick rows and a meta record.

    The run happens inside a cloned configuration context so the seed and
    payment sequence never leak into the process-default ``CONFIG``.
    """
    if payment_sequence not in PAYMENT_SEQUENCES:
        raise ValueError(f"payment_sequence must be one of {PAYMENT_SEQUENCES}, got {payment_sequence!r}")
    validate_levers(arm.levers)
    run_id = f"newcomer-smoke-{output_stem(arm.arm_id, seed, payment_sequence, households)}"
    levers_json = canonical_lever_json(arm.levers)

    with use_config(clone_config()):
        wrapper.set_run_seed(seed)
        # Economy reads payment_sequence once in __init__ and refuses a mid-run switch.
        CONFIG.payment_sequence = payment_sequence
        essential_spend = float(CONFIG.households.subsistence_min_cash)

        create_started = time.perf_counter()
        economy = wrapper.create_economy_quietly(households, firms_per_category, verbose=False)
        create_seconds = time.perf_counter() - create_started
        t0_coverage, _ = _payment_marker(economy.get_economic_metrics())
        wrapper.apply_policy(economy, arm)

        distress_history = DistressHistory()
        unemployment_history: deque[float] = deque(maxlen=8)
        gdp_history: deque[float] = deque(maxlen=4)
        rows: list[dict[str, Any]] = []
        started = time.perf_counter()
        for _ in range(ticks):
            economy.step()
            row = wrapper.snapshot_manifest(
                economy,
                run_id=run_id,
                policy_canonical=arm.policy_canonical,
                levers_json=levers_json,
                seed=seed,
                tick=int(economy.current_tick) - 1,
                distress_history=distress_history,
                unemployment_history=unemployment_history,
                gdp_history=gdp_history,
                essential_spend=essential_spend,
            )
            extra = economy.get_economic_metrics()
            for key in EXTRA_METRIC_KEYS:
                row[key] = extra.get(key, None)
            total_firms = row.get("total_firms") or 0
            distress_firms = float(row.get("n_burn_mode", 0.0) or 0.0) + float(row.get("n_survival_mode", 0.0) or 0.0)
            row["firm_distress_share"] = (distress_firms / total_firms) if total_firms else None
            rows.append(row)
        elapsed_seconds = time.perf_counter() - started
        final_coverage, final_scenario = _payment_marker(economy.get_economic_metrics())

    meta = {
        "run_id": run_id,
        "arm_id": arm.arm_id,
        "levers": dict(arm.levers),
        "policy_canonical": arm.policy_canonical,
        "seed": int(seed),
        "households": int(households),
        "firms_per_category": int(firms_per_category),
        "ticks_requested": int(ticks),
        "ticks_completed": len(rows),
        "payment_sequence_requested": payment_sequence,
        "payment_sequence_effective": str(getattr(economy, "payment_sequence", "?")),
        "payment_t0_coverage": t0_coverage,
        "payment_final_coverage": final_coverage,
        "payment_final_scenario": final_scenario,
        "payment_config": dict(getattr(economy, "payment_config_snapshot", {}) or {}),
        "create_seconds": round(create_seconds, 4),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "elapsed_definition": "step loop including per-tick snapshots; excludes economy creation",
        "status": "ok",
        "error": "",
    }
    return rows, meta


# --------------------------------------------------------------------------- summary


def _num(value: Any) -> float | None:
    """Coerce CSV or metric values to float; blanks, None and NaN become None."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _series(rows: Sequence[Mapping[str, Any]], column: str) -> list[float]:
    return [number for number in (_num(row.get(column)) for row in rows) if number is not None]


def _row_after(rows: Sequence[Mapping[str, Any]], ticks_elapsed: int) -> Mapping[str, Any] | None:
    """Row describing the state after ``ticks_elapsed`` steps (its ``tick`` column is N - 1)."""
    target = int(ticks_elapsed) - 1
    for row in rows:
        if _num(row.get("tick")) == target:
            return row
    return None


def effective_checkpoints(checkpoints: Sequence[int], ticks: int) -> list[int]:
    """Checkpoints that fall inside the run; the final tick when none do."""
    kept = [int(cp) for cp in checkpoints if 0 < int(cp) <= int(ticks)]
    return kept or [int(ticks)]


def baseline_motion(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
    """Range and end points of the headline series for one run."""
    unemployment = _series(rows, "unemployment_rate")
    firms = _series(rows, "total_firms")
    food = _series(rows, "sector_price_food")
    gov_cash = _series(rows, "gov_cash")
    distress = _series(rows, "mean_distress")
    homeless = _series(rows, "homeless_household_count")

    def first(values: list[float]) -> float | None:
        return values[0] if values else None

    def last(values: list[float]) -> float | None:
        return values[-1] if values else None

    return {
        "unemployment_min": min(unemployment, default=None),
        "unemployment_max": max(unemployment, default=None),
        "unemployment_final": last(unemployment),
        "firms_min": min(firms, default=None),
        "firms_max": max(firms, default=None),
        "firms_final": last(firms),
        # Ticks on which the active-firm count fell; several firms can exit on one tick.
        "firm_exit_ticks": float(sum(1 for prev, cur in zip(firms, firms[1:]) if cur < prev)),
        "food_price_start": first(food),
        "food_price_end": last(food),
        "gov_cash_start": first(gov_cash),
        "gov_cash_min": min(gov_cash, default=None),
        "gov_cash_final": last(gov_cash),
        "distress_start": first(distress),
        "distress_final": last(distress),
        "homeless_peak": max(homeless, default=None),
    }


def checkpoint_deltas(
    arm_rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    checkpoints: Sequence[int],
) -> list[dict[str, float | int | None]]:
    """Arm minus baseline for each delta column at each checkpoint (unscaled)."""
    deltas: list[dict[str, float | int | None]] = []
    for checkpoint in checkpoints:
        arm_row = _row_after(arm_rows, checkpoint)
        base_row = _row_after(baseline_rows, checkpoint)
        entry: dict[str, float | int | None] = {"checkpoint": int(checkpoint)}
        for column, _, _, _ in DELTA_COLUMNS:
            arm_value = _num(arm_row.get(column)) if arm_row else None
            base_value = _num(base_row.get(column)) if base_row else None
            entry[column] = (arm_value - base_value) if arm_value is not None and base_value is not None else None
        deltas.append(entry)
    return deltas


def _fmt(value: float | None, decimals: int = 2, *, signed: bool = False, scale: float = 1.0) -> str:
    if value is None:
        return "n/a"
    scaled = value * scale
    text = f"{scaled:+,.{decimals}f}" if signed else f"{scaled:,.{decimals}f}"
    return "0" if decimals == 0 and text in {"+0", "-0"} else text


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_motion_table(runs: Sequence[tuple[str, Sequence[Mapping[str, Any]]]]) -> list[str]:
    """Markdown table of ``baseline_motion`` for labelled runs."""
    lines = [
        "| Run | Unemployment min / max / final | Firms min / max / final | Firm-exit ticks "
        "| Food price start → end | Gov cash start / min / final | Distress start → final | Homeless peak |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, rows in runs:
        m = baseline_motion(rows)
        lines.append(
            f"| {label} "
            f"| {_pct(m['unemployment_min'])} / {_pct(m['unemployment_max'])} / {_pct(m['unemployment_final'])} "
            f"| {_fmt(m['firms_min'], 0)} / {_fmt(m['firms_max'], 0)} / {_fmt(m['firms_final'], 0)} "
            f"| {_fmt(m['firm_exit_ticks'], 0)} "
            f"| {_fmt(m['food_price_start'])} → {_fmt(m['food_price_end'])} "
            f"| {_fmt(m['gov_cash_start'], 0)} / {_fmt(m['gov_cash_min'], 0)} / {_fmt(m['gov_cash_final'], 0)} "
            f"| {_fmt(m['distress_start'], 3)} → {_fmt(m['distress_final'], 3)} "
            f"| {_fmt(m['homeless_peak'], 0)} |"
        )
    return lines


def render_delta_table(
    arm_runs: Sequence[tuple[str, int, Sequence[Mapping[str, Any]]]],
    baselines: Mapping[int, Sequence[Mapping[str, Any]]],
    checkpoints: Sequence[int],
) -> list[str]:
    """Markdown table of arm-minus-baseline deltas at each checkpoint, per arm and seed."""
    header = "| Arm | Seed | After tick | " + " | ".join(f"Δ {label}" for _, label, _, _ in DELTA_COLUMNS) + " |"
    lines = [header, "|---|---|---|" + "---|" * len(DELTA_COLUMNS)]
    for arm_id, seed, rows in arm_runs:
        baseline_rows = baselines.get(seed)
        if baseline_rows is None:
            lines.append(f"| {arm_id} | {seed} | n/a | " + " | ".join("no baseline" for _ in DELTA_COLUMNS) + " |")
            continue
        for entry in checkpoint_deltas(rows, baseline_rows, checkpoints):
            cells = [
                _fmt(entry[column], decimals, signed=True, scale=scale) for column, _, scale, decimals in DELTA_COLUMNS
            ]
            lines.append(f"| {arm_id} | {seed} | {entry['checkpoint']} | " + " | ".join(cells) + " |")
    return lines


def render_summary(
    results: Sequence[tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]],
    *,
    settings: Mapping[str, Any],
    environment: Mapping[str, Any],
    checkpoints: Sequence[int],
) -> str:
    """Render summary.md from (meta, rows) pairs."""
    ok = [(meta, rows) for meta, rows in results if meta.get("status") == "ok"]
    baselines = {int(meta["seed"]): rows for meta, rows in ok if meta["arm_id"] == BASELINE_ARM_ID}
    lines = [
        "# Newcomer smoke run",
        "",
        "Simulator-only evidence. Outcomes describe a synthetic economy, not a real-world forecast.",
        "",
        f"- Households: {settings['households']}; ticks: {settings['ticks']}; "
        f"firms per category: {settings['firms_per_category']}",
        f"- Seeds: {', '.join(str(seed) for seed in settings['seeds'])}; "
        f"payment sequence: `{settings['payment_sequence']}`",
        f"- Arms: {', '.join(f'`{arm}`' for arm in settings['arms'])}",
        f"- Commit: `{environment.get('commit', 'unknown')}` (dirty: {environment.get('git_dirty')}); "
        f"created {environment.get('created_at', 'unknown')}",
        "",
        "## Runs",
        "",
        "| Arm | Seed | Status | Ticks | Create s | Run s | Payment sequence | Payment coverage (final) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for meta, _ in results:
        lines.append(
            f"| {meta['arm_id']} | {meta['seed']} | {meta['status']} | {meta.get('ticks_completed', 0)} "
            f"| {_fmt(_num(meta.get('create_seconds')), 2)} | {_fmt(_num(meta.get('elapsed_seconds')), 1)} "
            f"| {meta.get('payment_sequence_effective', '?')} | {meta.get('payment_final_coverage', '')} |"
        )
    for meta, _ in results:
        if meta.get("status") != "ok":
            lines += ["", f"Failed: `{meta['arm_id']}` seed {meta['seed']}: {meta.get('error', '')}"]

    lines += [
        "",
        "## Baseline motion",
        "",
        "Firm-exit ticks counts ticks on which the active-firm count fell; several firms can exit on one tick.",
        "",
    ]
    if baselines:
        lines += render_motion_table([(f"baseline seed {seed}", rows) for seed, rows in sorted(baselines.items())])
    else:
        lines.append("No completed baseline arm in this run.")

    arm_runs = [(meta["arm_id"], int(meta["seed"]), rows) for meta, rows in ok if meta["arm_id"] != BASELINE_ARM_ID]
    lines += [
        "",
        "## Arm minus baseline at checkpoints",
        "",
        "Each checkpoint is the state after that many ticks (CSV `tick` column = checkpoint − 1). "
        "Unemployment deltas are percentage points; other columns are in their own units.",
        "",
    ]
    if arm_runs and baselines:
        lines += render_delta_table(arm_runs, baselines, checkpoints)
    elif arm_runs:
        lines.append("No completed baseline arm in this run, so deltas cannot be computed.")
    else:
        lines.append("No non-baseline arms in this run.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- CLI


def default_output_dir() -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    return repo_root() / "benchmarks" / "results" / "newcomer-smoke" / stamp


def run_smoke(
    *,
    arms: Sequence[PolicyArm],
    seeds: Sequence[int],
    households: int,
    ticks: int,
    firms_per_category: int,
    payment_sequence: str,
    checkpoints: Sequence[int],
    output_dir: Path,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run every arm for every seed, write per-arm CSV and meta files plus summary.md."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = BenchmarkPaths(root=output_dir, run_dir=output_dir)
    environment = collect_metadata({"benchmark": "newcomer-smoke"})
    settings = {
        "households": households,
        "ticks": ticks,
        "firms_per_category": firms_per_category,
        "seeds": list(seeds),
        "arms": [arm.arm_id for arm in arms],
        "payment_sequence": payment_sequence,
        "checkpoints": list(checkpoints),
    }
    results: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    artifacts: list[Path] = []
    for seed in seeds:
        for arm in arms:
            stem = output_stem(arm.arm_id, seed, payment_sequence, households)
            log(f"[newcomer-smoke] {arm.arm_id} seed={seed} sequence={payment_sequence} starting")
            started = time.perf_counter()
            try:
                rows, meta = run_arm(
                    arm,
                    seed=seed,
                    households=households,
                    ticks=ticks,
                    firms_per_category=firms_per_category,
                    payment_sequence=payment_sequence,
                )
            except Exception as exc:  # Surface the failure, keep the other arms running.
                traceback.print_exc()
                rows = []
                meta = {
                    "arm_id": arm.arm_id,
                    "levers": dict(arm.levers),
                    "seed": int(seed),
                    "households": households,
                    "firms_per_category": firms_per_category,
                    "ticks_requested": ticks,
                    "ticks_completed": 0,
                    "payment_sequence_requested": payment_sequence,
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            meta = {**meta, "environment": environment, "settings": settings}
            if rows:
                artifacts.append(write_rows_csv(paths, stem, rows))
            artifacts.append(write_json(paths, f"{stem}_meta", meta))
            results.append((meta, rows))
            log(
                f"[newcomer-smoke] {arm.arm_id} seed={seed} {meta['status']} in {meta['elapsed_seconds']:.1f}s "
                f"payment_coverage={meta.get('payment_final_coverage', '')!r}"
            )

    flat_keys = (
        "arm_id", "seed", "status", "households", "firms_per_category", "ticks_requested", "ticks_completed",
        "payment_sequence_requested", "payment_sequence_effective", "payment_t0_coverage", "payment_final_coverage",
        "payment_final_scenario", "create_seconds", "elapsed_seconds", "error",
    )
    flat_rows = [{key: meta.get(key, "") for key in flat_keys} for meta, _ in results]
    run_meta_csv = write_rows_csv(paths, "run_meta", flat_rows)
    summary_md = write_markdown(
        paths,
        "summary",
        render_summary(results, settings=settings, environment=environment, checkpoints=checkpoints),
    )
    return {
        "output_dir": output_dir,
        "results": results,
        "artifacts": [*artifacts, run_meta_csv, summary_md],
        "summary_md": summary_md,
        "failed": any(meta["status"] != "ok" for meta, _ in results),
    }


def _parse_seeds(value: str) -> list[int]:
    seeds = [int(part.strip()) for part in str(value).split(",") if part.strip()]
    if not seeds or any(seed < 0 for seed in seeds):
        raise argparse.ArgumentTypeError(f"--seeds needs non-negative integers, got {value!r}")
    return seeds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run newcomer-scale policy-arm smoke runs.")
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument(
        "--firms-per-category", type=int, default=5, help="Default matches the dashboard SetupConfig (5)."
    )
    parser.add_argument("--seeds", type=_parse_seeds, default=[1337], help="Comma-separated seeds.")
    parser.add_argument(
        "--arms",
        default=",".join(DEFAULT_ARMS),
        help=f"Comma-separated arm names. Available: {', '.join(ARM_CATALOG)}.",
    )
    parser.add_argument("--payment-sequence", choices=PAYMENT_SEQUENCES, default="legacy")
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="Default: benchmarks/results/newcomer-smoke/<UTC timestamp>/."
    )
    parser.add_argument(
        "--checkpoints",
        default=",".join(str(cp) for cp in DEFAULT_CHECKPOINTS),
        help="Comma-separated tick counts for the delta table.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.households <= 0 or args.ticks <= 0 or args.firms_per_category <= 0:
        parser.error("--households, --ticks and --firms-per-category must be positive")
    try:
        arms = resolve_arms(parse_str_list(args.arms))
        checkpoints = effective_checkpoints(parse_int_list(args.checkpoints), args.ticks)
    except ValueError as exc:
        parser.error(str(exc))
    result = run_smoke(
        arms=arms,
        seeds=args.seeds,
        households=args.households,
        ticks=args.ticks,
        firms_per_category=args.firms_per_category,
        payment_sequence=args.payment_sequence,
        checkpoints=checkpoints,
        output_dir=args.output_dir or default_output_dir(),
    )
    print(f"Wrote newcomer smoke artifacts to {result['output_dir']}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
