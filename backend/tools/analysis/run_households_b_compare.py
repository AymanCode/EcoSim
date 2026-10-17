"""Seeded before/after run for the adaptive reservation wage (households B).

Arms: ``before`` (all household flags off, as on main), ``B``
(``adaptive_reservation_wage`` on) and ``AB`` (B plus PR3's
``buffer_stock_consumption``). Prints post-warmup metrics. ``--measure-f``
prints the median weekly job-finding rate of the ``before`` arm, the value
``job_finding_half_rate`` is derived from. ``--scale name=factor`` multiplies
one ``CONFIG.households`` value (tuples scale every element) for the
sensitivity sweep.

Usage (from backend/):
    PYTHONHASHSEED=0 python tools/analysis/run_households_b_compare.py
    PYTHONHASHSEED=0 python tools/analysis/run_households_b_compare.py --measure-f --arms before
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

ARMS = {"before": (False, False), "B": (True, False), "AB": (True, True)}


def run_arm(name: str, households: int, ticks: int) -> dict:
    """Run one arm and return post-warmup metrics.

    Completed spells are counted when an unemployed household finds a job.
    Spells still running at the end are reported as ``ongoing_mean``.
    """
    reservation_flag, buffer_flag = ARMS[name]
    CONFIG.households.adaptive_reservation_wage = reservation_flag
    CONFIG.households.buffer_stock_consumption = buffer_flag
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=households, num_firms_per_category=5)
    warmup = economy.warmup_ticks
    unemployment, wages, consumption, finding, reservation_gap = [], [], [], [], []
    spells, previous = [], {}
    for _ in range(ticks):
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        if economy.current_tick <= warmup:
            continue
        metrics = economy.get_economic_metrics()
        unemployment.append(metrics["unemployment_rate"])
        wages.append(metrics["mean_wage"])
        consumption.append(statistics.mean(h.last_consumption_spending for h in economy.households))
        rate = economy.job_finding_rate()
        if rate is not None:
            finding.append(rate)
        offers = sorted(economy.get_posted_wage_offers(include_baseline=True).values())
        res = [h.reservation_wage for h in economy.households if not h.is_employed and h.can_work]
        if offers and res:
            reservation_gap.append(statistics.median(res) / statistics.median(offers))
        for h in economy.households:
            was = previous.get(h.household_id, 0)
            if h.is_employed and was > 0:
                spells.append(was)
            previous[h.household_id] = 0 if h.is_employed else h.unemployment_duration
    ongoing = [h.unemployment_duration for h in economy.households if not h.is_employed and h.can_work]
    return {
        "arm": name,
        "unemp_mean": statistics.mean(unemployment),
        "spell_median": statistics.median(spells) if spells else 0.0,
        "spell_mean": statistics.mean(spells) if spells else 0.0,
        "share_gt26": sum(s > 26 for s in spells) / len(spells) if spells else 0.0,
        "ongoing_mean": statistics.mean(ongoing) if ongoing else 0.0,
        "f_median": statistics.median(finding) if finding else 0.0,
        "res_to_offer": statistics.median(reservation_gap) if reservation_gap else 0.0,
        "mean_wage": statistics.mean(wages),
        "consumption_mean": statistics.mean(consumption),
        "happy_median": statistics.median(h.happiness for h in economy.households),
        "runtime_s": time.perf_counter() - started,
    }


KEYS = ["arm", "unemp_mean", "spell_median", "spell_mean", "share_gt26", "ongoing_mean",
        "f_median", "res_to_offer", "mean_wage", "consumption_mean", "happy_median", "runtime_s"]


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
    parser.add_argument("--arms", default="before,B,AB")
    parser.add_argument("--scale", default=None)
    parser.add_argument("--measure-f", action="store_true")
    args = parser.parse_args()
    if args.scale:
        apply_scale(args.scale)
    print(f"seed={CONFIG.random_seed} households={args.households} ticks={args.ticks} scale={args.scale}")
    print(" | ".join(KEYS))
    for name in args.arms.split(","):
        row = run_arm(name, args.households, args.ticks)
        print(" | ".join(f"{row[k]:.4f}" if isinstance(row[k], float) else str(row[k]) for k in KEYS), flush=True)
        if args.measure_f and name == "before":
            print(f"median weekly job-finding rate (before arm): {row['f_median']:.4f}")


if __name__ == "__main__":
    main()
