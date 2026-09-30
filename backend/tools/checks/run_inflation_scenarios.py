"""Small inflation experiments: python -m backend.tools.checks.run_inflation_scenarios."""

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import io
import json
from pathlib import Path

from backend.tools.checks import run_business_scenarios as business
from backend.tools.checks.run_agent_scenarios import isolated_run, small_world, shopping_plan, REPO_ROOT
from config import InflationConfig
from inflation import ConsumerPriceIndex, WageReview


def controlled_prices(annual, cash, *, seed):
    """Decision fixture: fixed finances isolate price measurement and pay review."""
    with isolated_run(seed):
        economy = small_world(seed)
        firm = economy.firms[0]
        firm.wage_offer = 40
        firm.actual_wages = {1: 40}
        firm.last_revenue, firm.last_profit = 1000, 100
        index = ConsumerPriceIndex({"food": 1})
        review = WageReview(0, 100, -52)
        rows = []
        for tick in range(105):
            firm.price = 10 * (1 + annual) ** (tick / 52)
            firm.cash_balance = cash  # Exogenous decision input; no claim of full settlement.
            index.observe(tick, [firm])
            plan = review.plan(firm, index, tick, InflationConfig(), 36)
            firm.wage_offer = plan["wage_offer_next"]
            firm.actual_wages[1] *= plan["contract_factor"]
            rows.append({"week": tick, "index": index.level, "annual_inflation": index.annual_rate,
                         "nominal_wage": firm.actual_wages[1],
                         "real_wage": firm.actual_wages[1] * 100 / index.level,
                         "review": plan["review_reason"]})
        return {"annual_price_path": annual, "cash_input": cash, "rows": rows}


def purchasing_power(seed):
    rows = []
    for price in (10, 11, 20):
        with isolated_run(seed):
            economy = small_world(seed)
            household, firm = economy.households[0], economy.firms[0]
            firm.price = price
            household.category_weights = {"food": 1}
            plan = shopping_plan(economy)
            rows.append({"price": price, "budget": plan["budget"],
                         "units": sum(plan["planned_purchases"].values())})
    return rows


def run(seed):
    base = business.Settings(ticks=105, initial_demand=90, demand=(90,), cash=50000)
    experiments = [business.run_experiment(name, settings, seed) for name, settings in (
        ("control", base),
        ("temporary_demand", dataclasses.replace(base, demand=(90,) * 12 + (180,) * 8 + (90,))),
        ("temporary_supply", dataclasses.replace(base, supply_shock_start=13, supply_shock_weeks=8, supply_multiplier=.5)),
    )]
    controlled = [controlled_prices(rate, cash, seed=seed)
                  for rate, cash in ((0, 10000), (.05, 10000), (.05, 320), (-.05, 10000))]
    power = purchasing_power(seed)
    checks = {
        "market_receipts_supply_and_payroll": all(c["passed"] for e in experiments for c in e["checks"]),
        "first_year_unavailable_before_week_52": all(r["annual_inflation"] is None for r in controlled[1]["rows"][:52]),
        "healthy_firm_reviews_at_52_and_104": [r["week"] for r in controlled[1]["rows"] if r["review"] == "annual_inflation_raise"] == [52, 104],
        "five_percent_prices_receive_five_percent_review": abs(controlled[1]["rows"][52]["nominal_wage"] - 42) < 1e-8,
        "cash_limit_blocks_raise": controlled[2]["rows"][-1]["nominal_wage"] == 40,
        "deflation_does_not_cut_nominal_pay": controlled[3]["rows"][-1]["nominal_wage"] == 40,
        "doubling_food_price_halves_quantity": abs(power[0]["units"] / 2 - power[2]["units"]) < 1e-8,
        "flat_prices_hold_pay": controlled[0]["rows"][-1]["nominal_wage"] == 40,
    }
    return {"seed": seed, "checks": checks, "purchasing_power": power,
            "controlled_price_decisions": controlled, "market_experiments": experiments}


def render(result):
    lines = ["# Small inflation scenarios", "",
             f"Seed {result['seed']}. Checks: {sum(result['checks'].values())}/{len(result['checks'])}.", "",
             "## What the controlled price cases establish", "",
             "These are decision fixtures with fixed financial inputs and an imposed price path. They isolate measurement and pay rules; they do not claim those prices emerge from a complete town or that wages settle here. Full-step contract/payroll integration is tested separately.", "",
             "| Annual price path | Cash available at review | Wage at week 52 | Wage at week 104 | Real wage at week 104 |", "|---|---:|---:|---:|---:|"]
    for case in result["controlled_price_decisions"]:
        a, b = case["rows"][52], case["rows"][104]
        lines.append(f"| {case['annual_price_path']:.0%} | {case['cash_input']:.2f} | {a['nominal_wage']:.2f} | {b['nominal_wage']:.2f} | {b['real_wage']:.2f} |")
    lines += ["", "## Market-generated prices under temporary shocks", "",
              "Each case runs real engine weeks for one Food firm and 12 households with a funded external buyer. Demand doubles in weeks 13–20, or labor productivity halves in weeks 13–20, then returns to its original input. Prices, hiring, production, loans, capital and firm survival respond through their normal rules. Households do not shop in these business-isolation cases. These are sector experiments, not aggregate inflation estimates; only Food (35% of the basket) has matched quotes.", "",
              "| Case | Weeks completed | Week 12 sale price | Week 20 sale price | Final sale price | Final workers | Final price index |", "|---|---:|---:|---:|---:|---:|---:|"]
    for case in result["market_experiments"]:
        rows = case["rows"]
        a, b, z = rows[min(11, len(rows)-1)], rows[min(19, len(rows)-1)], rows[-1]
        lines.append(f"| {case['name']} | {len(rows)} | {a['price']:.2f} | {b['price']:.2f} | {z['price']:.2f} | {z['workers']} | {z['consumer_price_index']:.2f} |")
    lines += ["", "## Purchasing power", "", "| Food price | Same shopping budget | Planned units |", "|---:|---:|---:|"]
    for row in result["purchasing_power"]:
        lines.append(f"| {row['price']:.2f} | {row['budget']:.2f} | {row['units']:.4f} |")
    lines += ["", "## Checks", ""] + [f"- {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result["checks"].items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if not 0 <= args.seed < 2**32:
        parser.error("Seed must be between 0 and 2**32 - 1")
    with contextlib.redirect_stdout(io.StringIO()):
        result = run(args.seed)
    sources = ["backend/inflation.py", "backend/economy.py", "backend/agents.py", "backend/config.py",
               "backend/tools/checks/run_business_scenarios.py", "backend/tools/checks/run_inflation_scenarios.py"]
    result["source_sha256"] = {p: hashlib.sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in sources}
    output = args.output_dir or REPO_ROOT / "benchmarks/results/inflation-scenarios" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(business.json_evidence(result), indent=2, allow_nan=False) + "\n")
    (output / "report.md").write_text(render(result))
    print(f"{sum(result['checks'].values())}/{len(result['checks'])} checks passed; report: {output / 'report.md'}")
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
