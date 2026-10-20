"""One-arm panel for sticky posted prices, on top of the Services markup flag.

Seeded with regression_snapshot._set_seed. Each arm is its own process.
The Services target-markup flag is set explicitly so a sticky run can sit
on the held-markup rule.

    python -m backend.tools.benchmarks.sticky_price_panel --seed 42 --ticks 260 \\
        --sticky on --ratchet on --arm sticky --out sticky.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.benchmarks.regression_snapshot import _set_seed  # noqa: E402
from tools.benchmarks.services_markup_panel import observe  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

# A posted price has changed when it moves by at least this fraction.
# One definition, used for durations, sizes and reversals.
PRICE_CHANGE_EPS = 1e-4
SPELL_CATEGORIES = ("Food", "Services", "Healthcare")


def _scale_pair(pair, factor: float):
    low, high = float(pair[0]) * factor, float(pair[1]) * factor
    return (low, high)


def _track_prices(economy, previous, spells):
    for firm in economy.firms:
        if firm.is_baseline:
            continue
        category = str(firm.good_category)
        if category not in SPELL_CATEGORIES:
            continue
        price = float(firm.price)
        tick = int(economy.current_tick)
        prior = previous.get(firm.firm_id)
        if prior is None:
            previous[firm.firm_id] = {
                "price": price,
                "tick": tick,
                "direction": None,
                "category": category,
                "interval": float(firm.price_review_interval()) if firm.uses_sticky_prices(False) else None,
            }
            continue
        old = prior["price"]
        if old <= 0.0 or abs(price / old - 1.0) < PRICE_CHANGE_EPS:
            continue
        size = price / old - 1.0
        direction = 1 if size > 0.0 else -1
        spells.append({
            "firm_id": int(firm.firm_id),
            "category": category,
            "tick": tick,
            "weeks": tick - int(prior["tick"]),
            "size": size,
            "reversal": prior["direction"] is not None and direction != prior["direction"],
            "interval": prior["interval"],
        })
        prior["price"] = price
        prior["tick"] = tick
        prior["direction"] = direction


def run(args: argparse.Namespace) -> dict:
    with use_config(clone_config()):
        _set_seed(args.seed)
        CONFIG.payment_sequence = args.payment_sequence
        CONFIG.firms.services_target_markup_held = args.ratchet == "on"
        CONFIG.firms.sticky_prices_enabled = args.sticky == "on"
        CONFIG.firms.sticky_price_cap_compounds = args.cap_mode == "compound"
        if args.interval_scale != 1.0:
            firms = CONFIG.firms
            firms.price_review_weeks_food = _scale_pair(firms.price_review_weeks_food, args.interval_scale)
            firms.price_review_weeks_services = _scale_pair(firms.price_review_weeks_services, args.interval_scale)
            firms.price_review_weeks_healthcare = _scale_pair(
                firms.price_review_weeks_healthcare, args.interval_scale
            )
        if args.gap_scale != 1.0:
            CONFIG.firms.price_review_gap_scale *= args.gap_scale
        if args.knee_scale != 1.0:
            CONFIG.firms.price_review_inflation_knee *= args.knee_scale
        if args.slope_scale != 1.0:
            CONFIG.firms.price_review_inflation_slope *= args.slope_scale
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(args.households, args.firms_per_category)
        if args.price_cap != "none":
            economy.government.price_stabilization_target = args.price_cap_target
            economy.government.price_stabilization_level = args.price_cap
        rows = []
        spells = []
        previous = {}
        t0 = time.perf_counter()
        for _ in range(args.ticks):
            economy.step()
            row = observe(economy)
            annual = economy.consumer_prices.annual_rate
            row["cpi_annual"] = None if annual is None else float(annual)
            row["social_multiplier"] = float(economy.government.social_happiness_multiplier)
            rows.append(row)
            _track_prices(economy, previous, spells)
        elapsed = time.perf_counter() - t0
    return {
        "meta": {
            "seed": args.seed,
            "ticks": args.ticks,
            "households": args.households,
            "firms_per_category": args.firms_per_category,
            "payment_sequence": args.payment_sequence,
            "sticky": args.sticky,
            "ratchet": args.ratchet,
            "cap_mode": args.cap_mode,
            "price_cap": args.price_cap,
            "price_cap_target": args.price_cap_target,
            "interval_scale": args.interval_scale,
            "gap_scale": args.gap_scale,
            "knee_scale": args.knee_scale,
            "slope_scale": args.slope_scale,
            "arm": args.arm,
            "seconds": round(elapsed, 3),
            "seconds_per_tick": round(elapsed / max(args.ticks, 1), 4),
            "price_change_eps": PRICE_CHANGE_EPS,
        },
        "rows": rows,
        "spells": spells,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=5)
    parser.add_argument("--payment-sequence", default="legacy")
    parser.add_argument("--sticky", choices=("off", "on"), default="off")
    parser.add_argument("--ratchet", choices=("off", "on"), default="on")
    parser.add_argument("--cap-mode", choices=("compound", "review"), default="compound")
    parser.add_argument("--price-cap", choices=("none", "soft", "strict"), default="none")
    parser.add_argument("--price-cap-target", default="services")
    parser.add_argument("--interval-scale", type=float, default=1.0)
    parser.add_argument("--gap-scale", type=float, default=1.0)
    parser.add_argument("--knee-scale", type=float, default=1.0)
    parser.add_argument("--slope-scale", type=float, default=1.0)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload))
    meta = payload["meta"]
    print(
        f"wrote {args.out} arm={meta['arm']} seed={meta['seed']} "
        f"ticks={meta['ticks']} sec={meta['seconds']} s/tick={meta['seconds_per_tick']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
