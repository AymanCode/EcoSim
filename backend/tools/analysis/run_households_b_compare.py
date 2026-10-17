"""Seeded before/after run for the adaptive reservation wage (households B).

Arms: ``before`` (flag off, as on main) and ``B`` (``adaptive_reservation_wage``
on). Prints post-warmup metrics, including, for B, the share of unemployed
households whose floor F (market-wide, so this is the share of weeks with
F above the minimum wage), the share of posted non-healthcare, non-housing
offers below F, and the share whose stored reservation wage (before the
plan's desperation discount and market clamp), sits above the minimum-wage
offer.
``--scale name=factor`` multiplies one ``CONFIG.households`` value (tuples
scale every element) for the sensitivity sweep.

Usage (from backend/):
    PYTHONHASHSEED=0 python tools/analysis/run_households_b_compare.py
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

KEYS = ["arm", "unemp_mean", "spell_median", "share_gt26", "consumption_mean", "f_median", "finding_ratio",
        "floor_above_minwage", "offers_below_floor", "res_above_minwage", "res_to_median_offer", "runtime_s"]


def run_arm(name: str, households: int, ticks: int) -> dict:
    """Run one arm; floor/ask shares are averaged over post-warmup ticks."""
    CONFIG.households.adaptive_reservation_wage = name == "B"
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=households, num_firms_per_category=5)
    warmup = economy.warmup_ticks
    unemployment, consumption, finding, ratios = [], [], [], []
    floor_above, below_floor, ask_above, ask_ratio, spells, previous = [], [], [], [], [], {}
    for _ in range(ticks):
        with contextlib.redirect_stdout(io.StringIO()):
            economy.step()
        if economy.current_tick <= warmup:
            continue
        metrics = economy.get_economic_metrics()
        unemployment.append(metrics["unemployment_rate"])
        consumption.append(statistics.mean(h.last_consumption_spending for h in economy.households))
        rate = economy.job_finding_rate()
        if rate is not None:
            finding.append(rate)
            ratios.append(rate / economy.normal_weekly_job_finding_rate())
        minimum = economy.government.get_minimum_wage()
        unemployed = [h for h in economy.households if not h.is_employed and h.can_work]
        offers = sorted(economy.get_posted_wage_offers(include_baseline=True).values())
        context = economy._reservation_context
        if unemployed and context is not None:
            floors = [h.adaptive_reservation_floor(context) for h in unemployed]
            floor_above.append(sum(f is not None and f > minimum + 1e-9 for f in floors) / len(unemployed))
            floor = floors[0]  # F is market-wide: the same for every household in a tick
            non_service = [o for fid, o in economy.get_posted_wage_offers(include_baseline=True).items()
                           if (getattr(economy.firm_lookup.get(fid), "good_category", "housing") or "").lower()
                           not in {"healthcare", "housing"}]
            if floor is not None and non_service:
                below_floor.append(sum(o < floor for o in non_service) / len(non_service))
        if unemployed and offers:
            asks = [h.reservation_wage for h in unemployed]
            ask_above.append(sum(a > minimum + 1e-9 for a in asks) / len(unemployed))
            ask_ratio.append(statistics.median(asks) / statistics.median(offers))
        for h in economy.households:
            was = previous.get(h.household_id, 0)
            if h.is_employed and was > 0:
                spells.append(was)
            previous[h.household_id] = 0 if h.is_employed else h.unemployment_duration
    return {
        "arm": name,
        "unemp_mean": statistics.mean(unemployment),
        "spell_median": statistics.median(spells) if spells else 0.0,
        "share_gt26": sum(s > 26 for s in spells) / len(spells) if spells else 0.0,
        "consumption_mean": statistics.mean(consumption),
        "f_median": statistics.median(finding) if finding else 0.0,
        "finding_ratio": statistics.median(ratios) if ratios else 0.0,
        "floor_above_minwage": statistics.mean(floor_above) if floor_above else float("nan"),
        "offers_below_floor": statistics.mean(below_floor) if below_floor else float("nan"),
        "res_above_minwage": statistics.mean(ask_above) if ask_above else 0.0,
        "res_to_median_offer": statistics.median(ask_ratio) if ask_ratio else 0.0,
        "runtime_s": time.perf_counter() - started,
    }


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
    parser.add_argument("--arms", default="before,B")
    parser.add_argument("--scale", default=None)
    args = parser.parse_args()
    if args.scale:
        apply_scale(args.scale)
    print(f"seed={CONFIG.random_seed} households={args.households} ticks={args.ticks} scale={args.scale}")
    print(" | ".join(KEYS))
    for name in args.arms.split(","):
        row = run_arm(name, args.households, args.ticks)
        print(" | ".join(f"{row[k]:.4f}" if isinstance(row[k], float) else str(row[k]) for k in KEYS), flush=True)


if __name__ == "__main__":
    main()
