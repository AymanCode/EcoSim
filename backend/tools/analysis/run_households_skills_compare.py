"""Seeded before/after run for skills and training (households h1+h2).

Arms: ``before`` (household flags off, as on main), ``H``
(``skills_dynamics`` on) and ``AH`` (H plus PR3's
``buffer_stock_consumption``). Prints post-warmup metrics. ``--scale
name=factor`` multiplies one ``CONFIG.households`` value (tuples scale every
element) for the sensitivity sweep. ``--bench`` times the numpy skills update
against the same update written as a per-household Python loop.

Usage (from backend/):
    PYTHONHASHSEED=0 python tools/analysis/run_households_skills_compare.py
    PYTHONHASHSEED=0 python tools/analysis/run_households_skills_compare.py --arms H --bench
"""

import argparse
import contextlib
import io
import statistics
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
for _path in (BACKEND_ROOT, BACKEND_ROOT / "tools" / "runners"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from config import CONFIG  # noqa: E402
from run_large_simulation import create_large_economy  # noqa: E402

ARMS = {"before": (False, False), "H": (True, False), "AH": (True, True)}
KEYS = ["arm", "unemp_mean", "spell_median", "consumption_mean", "skill_mean_end", "skill_unemp_end",
        "low_skill_ever_hired", "never_hired", "training_weeks", "training_loans", "runtime_s"]


def loop_update(economy) -> None:
    """The h1 weekly update as a per-household loop (benchmark reference only)."""
    for h in economy.households:
        if h.employer_id is not None:
            h.skills_level = min(1.0, h.skills_level + h.learning_rate_annual / 52.0 * (1.0 - h.skills_level))
        else:
            h.skills_level = max(0.0, h.skills_level * (1.0 - h.skill_depreciation_annual / 52.0))


def run_arm(name: str, households: int, ticks: int, bench: bool) -> dict:
    """Run one arm and return post-warmup metrics.

    ``low_skill_ever_hired``: share of households with skill < 0.4 at the end
    of warmup that are employed at least once afterwards. ``never_hired``:
    share of all households never employed after warmup.
    """
    skills_flag, buffer_flag = ARMS[name]
    CONFIG.households.skills_dynamics = skills_flag
    CONFIG.households.buffer_stock_consumption = buffer_flag
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=households, num_firms_per_category=5)
    warmup = economy.warmup_ticks
    unemployment, consumption, spells = [], [], []
    previous, low_skill, ever = {}, set(), set()
    for _ in range(ticks):
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        if economy.current_tick == warmup:
            low_skill = {h.household_id for h in economy.households if h.skills_level < 0.4}
        if economy.current_tick <= warmup:
            continue
        metrics = economy.get_economic_metrics()
        unemployment.append(metrics["unemployment_rate"])
        consumption.append(statistics.mean(h.last_consumption_spending for h in economy.households))
        for h in economy.households:
            if h.is_employed:
                ever.add(h.household_id)
            was = previous.get(h.household_id, 0)
            if h.is_employed and was > 0:
                spells.append(was)
            previous[h.household_id] = 0 if h.is_employed else h.unemployment_duration
    runtime = time.perf_counter() - started
    unemployed = [h.skills_level for h in economy.households if not h.is_employed]
    row = {
        "arm": name,
        "unemp_mean": statistics.mean(unemployment),
        "spell_median": statistics.median(spells) if spells else 0.0,
        "consumption_mean": statistics.mean(consumption),
        "skill_mean_end": statistics.mean(h.skills_level for h in economy.households),
        "skill_unemp_end": statistics.mean(unemployed) if unemployed else 0.0,
        "low_skill_ever_hired": len(low_skill & ever) / len(low_skill) if low_skill else 0.0,
        "never_hired": 1.0 - len(ever) / len(economy.households),
        "training_weeks": economy.training_weeks_total,
        "training_loans": economy.training_loans_total,
        "runtime_s": runtime,
    }
    if bench and skills_flag:
        saved = [h.skills_level for h in economy.households]
        reps = 200
        t0 = time.perf_counter()
        for _ in range(reps):
            economy._batch_update_skills()
        t1 = time.perf_counter()
        for _ in range(reps):
            loop_update(economy)
        t2 = time.perf_counter()
        for h, s in zip(economy.households, saved):
            h.skills_level = s
        print(f"bench ({len(economy.households)} households, {reps} reps): numpy "
              f"{(t1 - t0) / reps * 1e3:.3f} ms/tick, loop {(t2 - t1) / reps * 1e3:.3f} ms/tick")
    return row


def apply_scale(spec: str) -> None:
    """Apply ``name=factor`` to ``CONFIG.households``."""
    name, factor = spec.split("=")
    value = getattr(CONFIG.households, name)
    factor = float(factor)
    if isinstance(value, tuple):
        setattr(CONFIG.households, name, tuple(v * factor for v in value))
    elif isinstance(value, int) and not isinstance(value, bool):
        setattr(CONFIG.households, name, max(1, round(value * factor)))
    else:
        setattr(CONFIG.households, name, value * factor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--arms", default="before,H,AH")
    parser.add_argument("--scale", default=None)
    parser.add_argument("--bench", action="store_true")
    args = parser.parse_args()
    if args.scale:
        apply_scale(args.scale)
    print(f"seed={CONFIG.random_seed} households={args.households} ticks={args.ticks} scale={args.scale}")
    print(" | ".join(KEYS))
    for name in args.arms.split(","):
        row = run_arm(name, args.households, args.ticks, args.bench)
        print(" | ".join(f"{row[k]:.4f}" if isinstance(row[k], float) else str(row[k]) for k in KEYS), flush=True)


if __name__ == "__main__":
    main()
