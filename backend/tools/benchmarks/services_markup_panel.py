"""Paired-seed panel for the Services target-markup flag.

One process, one arm. Seeded with regression_snapshot._set_seed.
Writes per-tick series and a per-tick state hash. The flag defaults off;
pass --flag on to hold each Services firm's sampled target markup.

    python -m backend.tools.benchmarks.services_markup_panel --seed 42 --ticks 260 --flag off --arm off --out off.json
    python -m backend.tools.benchmarks.services_markup_panel --seed 42 --ticks 260 --flag on --arm on --out on.json
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config import CONFIG, clone_config, use_config  # noqa: E402
from tools.benchmarks.regression_snapshot import _set_seed  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402

CATEGORIES = ("Food", "Housing", "Services", "Healthcare", "PublicWorks")


def _r(value: float) -> str:
    return f"{float(value):.6f}"


def state_hash(economy) -> str:
    """Order-stable hash of posted prices, markups, cash, jobs and household stocks."""
    parts: list[str] = [
        str(int(economy.current_tick)),
        _r(economy.government.cash_balance),
        _r(getattr(economy, "external_injection_total", 0.0)),
    ]
    bank = getattr(economy, "bank", None)
    parts.append(_r(bank.cash_reserves if bank is not None else 0.0))
    for firm in sorted(economy.firms, key=lambda f: f.firm_id):
        parts.append(
            "|".join((
                str(int(firm.firm_id)),
                str(firm.good_category),
                "1" if firm.is_baseline else "0",
                _r(firm.price),
                _r(firm.markup),
                _r(firm.cash_balance),
                _r(firm.inventory_units),
                _r(firm.wage_offer),
                str(len(firm.employees)),
                _r(firm.last_units_sold),
                _r(firm.last_revenue),
                _r(firm.last_profit),
                _r(firm.last_tick_total_costs),
            ))
        )
    for household in sorted(economy.households, key=lambda h: h.household_id):
        parts.append(
            "|".join((
                str(int(household.household_id)),
                _r(household.cash_balance),
                _r(household.bank_deposit),
                _r(household.happiness),
                _r(household.health),
                str(household.employer_id),
                _r(household.wage),
                _r(household.food_consumed_this_tick),
            ))
        )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _empty_cat() -> dict[str, float]:
    return {cat: 0.0 for cat in CATEGORIES}


def observe(economy) -> dict:
    households = economy.households
    n = len(households)
    employed = 0
    can_work = 0
    lf_unemployed = 0
    happy = 0.0
    food_ok = 0
    poor = 0
    extreme = 0
    wealth = np.empty(n, dtype=np.float64)
    for i, household in enumerate(households):
        is_employed = bool(household.is_employed)
        if is_employed:
            employed += 1
        if household.can_work:
            can_work += 1
            if not is_employed:
                lf_unemployed += 1
        happy += float(household.happiness)
        if float(household.food_consumed_this_tick) + 1e-12 >= float(household.min_food_per_tick):
            food_ok += 1
        liquid = float(household.cash_balance) + max(0.0, float(household.bank_deposit))
        wealth[i] = liquid
        if liquid < 100.0:
            extreme += 1
        if liquid < 200.0:
            poor += 1

    wealth.sort()
    decile_means = []
    for decile in range(10):
        start = int(n * decile / 10)
        stop = int(n * (decile + 1) / 10)
        decile_means.append(float(wealth[start:stop].mean()) if stop > start else 0.0)

    units = _empty_cat()
    revenue = _empty_cat()
    books = _empty_cat()
    posted_sum = _empty_cat()
    posted_n = {cat: 0 for cat in CATEGORIES}
    private_profit = 0.0
    private_revenue = 0.0
    private_cost = 0.0
    private_units = 0.0
    private_profit_cat = _empty_cat()
    private_revenue_cat = _empty_cat()
    private_cost_cat = _empty_cat()
    private_units_cat = _empty_cat()
    services_markup_sum = 0.0
    services_markup_n = 0
    services_markup_min = None
    services_markup_max = None

    for firm in economy.firms:
        cat = str(firm.good_category)
        if cat not in units:
            units[cat] = 0.0
            revenue[cat] = 0.0
            books[cat] = 0.0
            posted_sum[cat] = 0.0
            posted_n[cat] = 0
            private_profit_cat[cat] = 0.0
            private_revenue_cat[cat] = 0.0
            private_cost_cat[cat] = 0.0
            private_units_cat[cat] = 0.0
        sold = float(firm.last_units_sold)
        gdp_rev = float(economy.last_tick_revenue.get(firm.firm_id, 0.0))
        book_rev = float(firm.last_revenue)
        cost = float(firm.last_tick_total_costs)
        profit = float(firm.last_profit)
        units[cat] += sold
        revenue[cat] += gdp_rev
        books[cat] += book_rev
        posted_sum[cat] += float(firm.price)
        posted_n[cat] += 1
        if not firm.is_baseline:
            private_profit += profit
            private_revenue += book_rev
            private_cost += cost
            private_units += sold
            private_profit_cat[cat] += profit
            private_revenue_cat[cat] += book_rev
            private_cost_cat[cat] += cost
            private_units_cat[cat] += sold
            if cat == "Services":
                markup = float(firm.markup)
                services_markup_sum += markup
                services_markup_n += 1
                services_markup_min = markup if services_markup_min is None else min(services_markup_min, markup)
                services_markup_max = markup if services_markup_max is None else max(services_markup_max, markup)

    posted = {
        cat: (posted_sum[cat] / posted_n[cat] if posted_n[cat] else 0.0)
        for cat in posted_sum
    }
    gdp = float(sum(economy.last_tick_revenue.values()))
    cpi = float(economy.consumer_prices.level)
    return {
        "tick": int(economy.current_tick),
        "gdp": gdp,
        "unemployment": (lf_unemployed / can_work) if can_work else 0.0,
        "jobless_population": ((n - employed) / n) if n else 0.0,
        "happiness": happy / n if n else 0.0,
        "cpi": cpi,
        "gov_cash": float(economy.government.cash_balance),
        "poverty": poor / n if n else 0.0,
        "extreme_poverty": extreme / n if n else 0.0,
        "food_sufficiency": food_ok / n if n else 0.0,
        "wealth_decile_means": decile_means,
        "units": units,
        "gdp_revenue": revenue,
        "book_revenue": books,
        "posted_price": posted,
        "private_profit": private_profit,
        "private_revenue": private_revenue,
        "private_cost": private_cost,
        "private_units": private_units,
        "private_profit_cat": private_profit_cat,
        "private_revenue_cat": private_revenue_cat,
        "private_cost_cat": private_cost_cat,
        "private_units_cat": private_units_cat,
        "services_markup_mean": (services_markup_sum / services_markup_n) if services_markup_n else 0.0,
        "services_markup_min": 0.0 if services_markup_min is None else services_markup_min,
        "services_markup_max": 0.0 if services_markup_max is None else services_markup_max,
        "services_markup_n": services_markup_n,
        "baseline_services_markup_mean": _baseline_services_markup(economy),
        "money_net": _money_net(economy),
        "hash": state_hash(economy),
    }


def _baseline_services_markup(economy) -> float:
    values = [
        float(firm.markup)
        for firm in economy.firms
        if firm.is_baseline and str(firm.good_category) == "Services"
    ]
    return sum(values) / len(values) if values else 0.0


def _money_net(economy) -> float:
    """Same stock as tests_contracts.conftest.total_money_net_of_injections."""
    bank = getattr(economy, "bank", None)
    reserves = float(bank.cash_reserves) if bank is not None else 0.0
    stock = (
        sum(float(h.cash_balance) for h in economy.households)
        + sum(float(f.cash_balance) for f in economy.firms)
        + sum(float(f.cash_balance) for f in getattr(economy, "queued_firms", []))
        + float(economy.government.cash_balance)
        + float(getattr(economy, "misc_firm_revenue", 0.0))
        + reserves
    )
    return stock - float(getattr(economy, "external_injection_total", 0.0))


def run(args: argparse.Namespace) -> dict:
    with use_config(clone_config()):
        _set_seed(args.seed)
        CONFIG.payment_sequence = args.payment_sequence
        if args.flag == "on":
            CONFIG.firms.services_target_markup_held = True
        elif args.flag != "off":
            raise SystemExit(f"flag must be on or off, got {args.flag!r}")
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(args.households, args.firms_per_category)
        if args.markup_scale != 1.0:
            for firm in list(economy.firms) + list(getattr(economy, "queued_firms", [])):
                if str(firm.good_category) == "Services":
                    firm.markup = max(0.0, float(firm.markup) * args.markup_scale)
        rows = []
        t0 = time.perf_counter()
        for _ in range(args.ticks):
            economy.step()
            rows.append(observe(economy))
        elapsed = time.perf_counter() - t0
    return {
        "meta": {
            "seed": args.seed,
            "ticks": args.ticks,
            "households": args.households,
            "firms_per_category": args.firms_per_category,
            "payment_sequence": args.payment_sequence,
            "flag": args.flag,
            "markup_scale": args.markup_scale,
            "arm": args.arm,
            "seconds": round(elapsed, 3),
            "seconds_per_tick": round(elapsed / max(args.ticks, 1), 4),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--households", type=int, default=1000)
    parser.add_argument("--firms-per-category", type=int, default=10)
    parser.add_argument("--payment-sequence", default="legacy")
    parser.add_argument("--flag", choices=("off", "on"), default="off")
    parser.add_argument("--markup-scale", type=float, default=1.0)
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
