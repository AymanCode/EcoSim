"""Small business experiments with a funded, scripted customer.

Run: .venv/bin/python -m backend.tools.checks.run_business_scenarios
Custom: --case custom --cash 100 --initial-demand 20 --demand 20,20,80,80,0,0 --ticks 6

Demand is requested units, not guaranteed sales. Only this test harness replaces
household shopping; firm decisions, labor matching, production and settlement
use the current default engine. No production source changes are required.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import io
import json
import math
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG, get_config
from economy import Economy
from tools.checks.run_agent_scenarios import REPO_ROOT, format_cell, isolated_run, json_scalar


def _price_level(economy):
    prices = getattr(economy, "consumer_prices", None)
    return prices.level if prices is not None else 100.0


def _annual_inflation(economy):
    prices = getattr(economy, "consumer_prices", None)
    return prices.annual_rate if prices is not None else None


def _price_snapshot(economy):
    prices = getattr(economy, "consumer_prices", None)
    return prices.snapshot() if prices is not None else None


@dataclasses.dataclass(frozen=True)
class Settings:
    category: str = "Food"
    cash: float = 10000.0
    workers: int = 3
    population: int = 12
    job_seekers: int = 9
    wage: float = 40.0
    reservation_wage: float = 30.0
    price: float = 10.0
    capacity: float = 200.0  # Food: output ceiling; Services: worker slots.
    initial_demand: float = 30.0
    demand: tuple[float, ...] = (30.0,)
    ticks: int = 12
    bank_cash: float = 0.0
    buyer_cash: float = 1000000.0
    supply_shock_start: int = 0  # One-based week; zero disables the temporary shock.
    supply_shock_weeks: int = 0
    supply_multiplier: float = 1.0


class BusinessTestEconomy(Economy):
    """Test boundary only; imported by this CLI and its contract tests."""

    def _apply_random_shocks(self):
        week = self.current_tick - 17 + 1
        settings = self.scenario_settings
        active = settings.supply_shock_start <= week < settings.supply_shock_start + settings.supply_shock_weeks
        multiplier = settings.supply_multiplier if active else 1.0
        for firm in self.firms:
            firm.units_per_worker = self.base_productivity * multiplier

    def _maybe_create_new_firms(self):
        pass  # Keep one business so its response can be followed.

    def _enqueue_healthcare_requests(self):
        pass  # Worker health is a fixed labor-supply condition in this fixture.

    def _batch_update_wellbeing(self, happiness_multiplier):
        pass  # Avoid hunger/illness changing labor supply when buyers are external.

    def _plan_legacy_consumption_after_income(self, *args, **kwargs):
        return {h.household_id: {"household_id": h.household_id, "budget": 0.0,
                                "category_budgets": {}, "planned_purchases": {}}
                for h in self.households}

    def _clear_goods_market(self, household_consumption_plans, firms):
        firm = firms[0]
        supply = self._estimated_firm_market_supply(firm, current_tick_capacity=True)
        price = self._effective_market_price(firm, supply)
        affordable = self.requested_demand if price <= 0 else min(self.requested_demand, max(0.0, self.buyer_cash) / price)
        buyer_before = self.buyer_cash
        _, sales = super()._clear_goods_market({-1: {
            "household_id": -1, "budget": self.buyer_cash,
            "planned_purchases": {firm.firm_id: affordable},
        }}, firms)
        receipt = sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
        self.buyer_cash -= receipt["revenue"]
        self.market_trace = {
            "requested_units": self.requested_demand, "funded_order_units": affordable,
            "supply_units": supply, "units_sold": receipt["units_sold"],
            "unfilled_order_units": max(0.0, affordable - receipt["units_sold"]),
            "buyer_cash_before": buyer_before, "buyer_cash_after": self.buyer_cash,
            "buyer_paid": receipt["revenue"], "sale_price": price,
            "cash_before_sales": firm.cash_balance,
        }
        # The external customer pays the receipt once. Household purchase
        # settlement must not charge employees or deliver these goods again.
        return {}, sales


def validate(settings):
    if settings.category not in {"Food", "Services"}:
        raise ValueError("Choose Food or Services; housing and healthcare use different markets.")
    if not 1 <= settings.population <= 100 or not 0 <= settings.workers <= settings.population:
        raise ValueError("Use 1–100 households and a worker count within that population.")
    if not 0 <= settings.job_seekers <= settings.population - settings.workers:
        raise ValueError("Job seekers must fit in the population left after existing workers.")
    if not 1 <= settings.ticks <= 156 or not settings.demand or len(settings.demand) > settings.ticks:
        raise ValueError("Use 1–156 weeks and 1–ticks demand values; the final value repeats.")
    if (not math.isfinite(settings.supply_multiplier) or not 0 < settings.supply_multiplier <= 2
            or settings.supply_shock_start < 0 or settings.supply_shock_weeks < 0
            or (settings.supply_shock_weeks and not 1 <= settings.supply_shock_start <= settings.ticks)
            or settings.supply_shock_start + settings.supply_shock_weeks > settings.ticks + 1):
        raise ValueError("Supply shock needs a valid start/duration and a multiplier in (0, 2].")
    numbers = (settings.cash, settings.wage, settings.reservation_wage, settings.price, settings.capacity,
               settings.initial_demand, settings.bank_cash, settings.buyer_cash, *settings.demand)
    if any(not math.isfinite(x) or x < 0 for x in numbers):
        raise ValueError("Money, prices, capacity and demand must be finite, nonnegative numbers.")
    if settings.price <= 0 or settings.capacity <= 0:
        raise ValueError("Price and capacity must be positive.")
    if (max(settings.cash, settings.bank_cash, settings.buyer_cash) > 1e9
            or max(settings.wage, settings.reservation_wage, settings.price, settings.initial_demand, *settings.demand) > 1e6
            or settings.capacity > 10000):
        raise ValueError("Small-test limits: cash 1 billion; prices, wages and demand 1 million; capacity 10,000.")
    if settings.category == "Services" and not float(settings.capacity).is_integer():
        raise ValueError("Services capacity is a whole number of worker slots.")


def make_world(settings):
    CONFIG.time.warmup_ticks = 0
    CONFIG.llm.enable_llm_government = False
    CONFIG.modes.government_stabilizers = False
    CONFIG.government.auto_working_capital_backstop = False
    households = [HouseholdAgent(i + 1, cash_balance=100, skills_level=0.5, age=30)
                  for i in range(settings.population)]
    firm = FirmAgent(firm_id=1, good_name="TestProduct", good_category=settings.category,
                     cash_balance=settings.cash, wage_offer=settings.wage, price=settings.price,
                     inventory_units=0, production_capacity_units=settings.capacity,
                     expected_sales_units=settings.initial_demand, personality="moderate", is_baseline=False)
    # Constructor sampling is seeded. Explicit fixture inputs are applied afterward.
    firm.wage_offer = settings.wage
    firm.price = settings.price
    firm.age_in_ticks = 30
    firm.ceo_household_id = None
    firm.owners = []
    for index, household in enumerate(households):
        household.skills_level = 0.5
        household.expected_wage = settings.reservation_wage
        household.reservation_wage = settings.reservation_wage
        household.health = 0.8 if index < settings.workers + settings.job_seekers else 0.05
        household.happiness = household.morale = 0.8
        if index < settings.workers:
            household.employer_id = 1
            household.wage = settings.wage
            firm.employees.append(household.household_id)
            firm.actual_wages[household.household_id] = settings.wage
    workforce = settings.workers
    if settings.category == "Services":
        workforce = min(workforce, int(settings.capacity))
    prior_supply = min(firm._capacity_for_workers(workforce), settings.capacity) if settings.category == "Food" else firm._capacity_for_workers(workforce)
    prior_sales = min(settings.initial_demand, prior_supply)
    firm.last_units_produced = prior_supply
    firm.last_units_sold = prior_sales
    firm.last_revenue = prior_sales * settings.price
    firm.last_tick_total_costs = settings.workers * settings.wage
    firm.last_profit = firm.last_revenue - firm.last_tick_total_costs
    firm.smoothed_profit_margin = firm.last_profit / firm.last_revenue if firm.last_revenue > 0 else -1.0
    firm.sales_velocity_ema = prior_sales
    firm.last_sell_through_rate = prior_sales / prior_supply if prior_supply > 0 else 0.0
    government = GovernmentAgent(cash_balance=20000, unemployment_benefit_level=0, transfer_budget=0)
    government.unemployment_benefit_level = 0  # Apply after constructor policy defaults.
    bank = BankAgent(cash_reserves=settings.bank_cash) if settings.bank_cash > 0 else None
    economy = BusinessTestEconomy(households, [firm], government, bank=bank)
    economy.scenario_settings = settings
    economy.base_productivity = firm.units_per_worker
    economy.current_tick = 17  # Past warmup and away from the 50-week contract adjustment.
    economy.in_warmup = False
    economy.performance_mode = False
    economy.audit_log_enabled = True
    economy.buyer_cash = settings.buyer_cash
    economy.requested_demand = 0.0
    economy.market_trace = {}
    economy.last_tick_sales_units[1] = prior_sales
    economy.last_tick_sell_through_rate[1] = firm.last_sell_through_rate
    economy.last_tick_unmet_demand_by_firm[1] = max(0.0, settings.initial_demand - prior_sales)
    return economy


def snapshot(firm):
    return {
        "cash": firm.cash_balance, "workers": len(firm.employees), "employee_ids": list(firm.employees),
        "wage_offer": firm.wage_offer, "worker_contracts": dict(firm.actual_wages), "price": firm.price,
        "inventory": firm.inventory_units, "capital": firm.capital_stock,
        "capacity_limit": firm.production_capacity_units, "expected_sales": firm.expected_sales_units,
        "last_sales": firm.last_units_sold, "last_revenue": firm.last_revenue,
        "productive_capacity": firm._capacity_for_workers(
            min(len(firm.employees), int(firm.production_capacity_units))
            if firm.good_category == "Services" else len(firm.employees)),
    }


def run_experiment(name, settings, seed=1337):
    validate(settings)
    with isolated_run(seed), contextlib.redirect_stdout(io.StringIO()):
        economy = make_world(settings)
        firm = economy.firms[0]
        initial = snapshot(firm)
        configuration = dataclasses.asdict(get_config())
        rows, traces = [], []
        for index in range(settings.ticks):
            if not economy.firms:
                break
            before = snapshot(firm)
            economy.requested_demand = settings.demand[min(index, len(settings.demand) - 1)]
            economy.step()
            audit = economy._last_tick_audit
            plan = audit["firm_production_plans"][1]
            labor = audit["firm_labor_outcomes"][1]
            market = dict(economy.market_trace)
            after = snapshot(firm)
            paid_wages = sum(h.last_wage_income for h in economy.households)
            loans = ([dict(loan) for loan in economy.bank.active_loans
                      if loan.get("borrower_type") == "firm" and loan.get("borrower_id") == 1]
                     if economy.bank is not None else [])
            row = {
                "week": index + 1, "demand": market["requested_units"], "sold": firm.last_units_sold,
                "cash_before": before["cash"], "cash_after": firm.cash_balance,
                "hires_planned": plan["planned_hires_count"], "hired": len(labor.get("hired_households_ids", [])),
                "layoffs_planned": len(plan["planned_layoffs_ids"]), "laid_off": len(labor.get("confirmed_layoffs_ids", [])),
                "workers": len(firm.employees), "wage_offer_before": before["wage_offer"],
                "wage_offer_after": firm.wage_offer, "wages_paid": paid_wages,
                "mean_contract_after": sum(firm.actual_wages.values()) / max(1, len(firm.actual_wages)),
                "production": firm.last_units_produced, "capacity_limit": firm.production_capacity_units,
                "productive_capacity": after["productive_capacity"],
                "capital": firm.capital_stock, "inventory": firm.inventory_units,
                "price": market["sale_price"], "revenue": firm.last_revenue, "profit": firm.last_profit,
                "firm_open": bool(economy.firms),
                # The price index arrives with the inflation model; without it
                # the index stays at its 100 base and annual inflation is absent.
                "consumer_price_index": _price_level(economy),
                "annual_inflation": _annual_inflation(economy),
                "real_mean_wage": paid_wages / max(1, len(firm.employees)) * 100 / _price_level(economy),
            }
            trace = {
                "week": index + 1, "engine_tick": economy.current_tick - 1, "before": before, "after": after,
                "market": market, "production_plan": dict(plan), "labor_outcome": labor,
                "wage_plan": audit["firm_wage_plans"][1], "price_plan": audit["firm_price_plans"][1],
                "health_snapshot": audit["firm_health_snapshots"][1], "diagnostics": dict(firm.decision_diagnostics),
                "worker_receipts": {h.household_id: {"wage": h.last_wage_income, "employer": h.employer_id,
                                                     "contract": h.wage} for h in economy.households},
                "registered_firm_loans": loans, "firm_open": bool(economy.firms),
                "wages_paid": paid_wages, "payroll_cost": firm.last_tick_total_costs,
                "failed_hiring_reason": firm.last_tick_failed_match_reason,
                "unfilled_positions": firm.unfilled_positions_streak,
                "inflation": _price_snapshot(economy),
            }
            rows.append(row)
            traces.append(trace)
        checks = [
            ("Sales never exceed the funded order or real supply", all(t["market"]["units_sold"] <= min(t["market"]["funded_order_units"], t["market"]["supply_units"]) + 1e-8 for t in traces)),
            ("The external buyer pays the recorded sales revenue once", all(abs(t["market"]["buyer_cash_before"] - t["market"]["buyer_cash_after"] - t["market"]["buyer_paid"]) < 1e-7 for t in traces)),
            ("The firm's recorded revenue equals the external receipt", all(abs(t["after"]["last_revenue"] - t["market"]["buyer_paid"]) < 1e-7 for t in traces)),
            ("The buyer cannot spend beyond its opening funds", economy.buyer_cash >= -1e-7),
            ("Recorded payroll equals workers' gross wage receipts", all(abs(t["payroll_cost"] - t["wages_paid"]) < 1e-7 for t in traces)),
            ("Live employment links agree with the business roster", all(
                {hid for hid, h in t["worker_receipts"].items() if h["employer"] == 1} == set(t["after"]["employee_ids"])
                for t in traces if t["firm_open"])),
            ("Closing the firm releases its workers", all(
                all(h["employer"] != 1 for h in t["worker_receipts"].values())
                for t in traces if not t["firm_open"])),
            ("All numeric weekly observations are finite", all(math.isfinite(v) for r in rows for v in r.values() if isinstance(v, (int, float)))),
        ]
        findings = []
        if any(t["market"]["cash_before_sales"] < 0 for t in traces):
            findings.append("Cash goes negative before sales; legacy payroll is still paid even without enough opening funds.")
        if any(r["hires_planned"] > r["hired"] for r in rows):
            findings.append("Some requested hires are not filled; inspect the labor outcomes and failure reasons.")
        if any(r["demand"] == 0 and r["workers"] > 0 for r in rows):
            findings.append("The business retains workers during zero-demand weeks; retention floors and adjustment delays remain visible.")
        if any(t["market"]["unfilled_order_units"] > 1e-6 for t in traces) and after["capacity_limit"] <= initial["capacity_limit"]:
            findings.append("Unfilled demand did not raise the installed capacity limit during this run; inspect finance and expansion gates.")
        if any(t["after"]["wage_offer"] < t["before"]["wage_offer"] and t["after"]["worker_contracts"] == t["before"]["worker_contracts"] for t in traces):
            findings.append("A lower posted wage does not necessarily lower existing workers' contracts that week.")
        if settings.category == "Services" and len(rows) >= 5 and all(r["sold"] == 0 for r in rows):
            if max(t["diagnostics"].get("service_weak_demand_streak", 0) for t in traces) <= 1:
                findings.append("The Services weak-demand counter never advances beyond one despite repeated zero-sales weeks; this can delay headcount adjustments. Annual wage reviews have their own distress counter.")
        return {"name": name, "settings": dataclasses.asdict(settings), "initial": initial,
                "configuration": configuration, "rows": rows, "traces": traces,
                "checks": [{"description": label, "passed": passed} for label, passed in checks], "findings": findings}


def presets(ticks=12):
    base = Settings(ticks=ticks)
    def case(name, **kwargs):
        return name, dataclasses.replace(base, **kwargs)
    return {
        "cash": [case(f"cash_{cash}", cash=cash) for cash in (0, 120, 10000)] + [
            case("startup_no_cash", cash=0, workers=0, job_seekers=12, demand=(120,)),
            case("startup_funded", cash=10000, workers=0, job_seekers=12, demand=(120,))],
        "hiring": [case("hiring_available", initial_demand=120, demand=(120,)),
                   case("hiring_no_applicants", initial_demand=120, demand=(120,), job_seekers=0),
                   case("hiring_high_reservations", initial_demand=120, demand=(120,), reservation_wage=100)],
        "wages": [case("wages_rising_sales", initial_demand=10, demand=(100,)),
                  case("wages_falling_sales", initial_demand=100, demand=(5,)),
                  case("wages_competing_for_workers", initial_demand=120, demand=(120,), reservation_wage=100),
                  case("services_weak_sales_wages", category="Services", capacity=3, price=30,
                       wage=60, initial_demand=12, demand=(1,))],
        "capacity": [case("food_expansion", initial_demand=120, demand=(120,)),
                     case("services_expansion_funded", category="Services", capacity=3, initial_demand=100,
                          demand=(100,), price=30, bank_cash=100000),
                     case("services_expansion_no_bank", category="Services", capacity=3, initial_demand=100,
                          demand=(100,), price=30)],
        "low_demand": [case("no_sales", demand=(0,)), case("no_sales_no_cash", cash=0, demand=(0,)),
                       case("services_no_sales", category="Services", capacity=3, price=30,
                            wage=60, initial_demand=12, demand=(0,)),
                       case("demand_crash_then_recovery", demand=tuple(30.0 if i < 3 else 0.0 if i < 8 else 90.0 for i in range(ticks)))],
    }


def render_report(experiments, seed):
    checks = [c for e in experiments for c in e["checks"]]
    lines = ["# Business behaviour with controlled demand", "", f"Seed: {seed}. Default legacy rules, normal mode.", "",
             f"{sum(c['passed'] for c in checks)}/{len(checks)} harness/accounting checks passed across {len(experiments)} runs.", "",
             "Demand is a funded external customer's requested units, independent of household shopping. Actual sales remain limited by supply and buyer cash. Opening demand seeds one prior observation; later observations come from real sales and unfilled orders, with no look-ahead.", "",
             "Each run uses one private Food or Services firm and a small worker pool. Full engine weeks handle hiring, production, wages, taxes, credit (when enabled), investment and exit. Warmup, random shocks, new competitors, government stabilizers, household shopping and health/wellbeing changes are excluded to isolate business responses. Healthy nonemployees may search normally; unavailable workers start too ill to work. This is a controlled business test, not a calibrated closed town.", "",
             "Posted wages, existing contracts and wages actually paid are different. Food capacity limits output units; Services capacity counts worker slots. Capital stock and actual output are recorded separately. PASS checks verify the harness and affected receipts, not whether every business rule is desirable.", "",
             "## Summary", "", "| Run | Cash, start → end | Workers, start → end | Posted wage, start → end | Capacity limit, start → end | Closed? |",
             "| --- | --- | --- | --- | --- | --- |"]
    for exp in experiments:
        first, last = exp["initial"], exp["rows"][-1]
        pair = lambda a, b: f"{format_cell(a)} → {format_cell(b)}"
        lines.append(f"| {exp['name']} | {pair(first['cash'], last['cash_after'])} | {pair(first['workers'], last['workers'])} | {pair(first['wage_offer'], last['wage_offer_after'])} | {pair(first['capacity_limit'], last['capacity_limit'])} | {format_cell(not last['firm_open'])} |")
    lines += ["", "Intermediate rises and falls appear in the weekly tables below; matching start/end values can hide a temporary wage or demand change.", ""]
    for exp in experiments:
        s, rows = exp["settings"], exp["rows"]
        lines += [f"## {exp['name']}", "",
                  f"{s['category']}; opening business cash {s['cash']:g}; {s['workers']} workers; {s['job_seekers']} potential applicants in a population of {s['population']}; opening demand {s['initial_demand']:g}; weekly demand {s['demand']} (last value repeats); bank reserves {s['bank_cash']:g}.", "",
                  "### Money and demand", ""]
        for title, columns in [("", ("week", "demand", "sold", "cash_before", "cash_after", "revenue", "profit", "firm_open")),
                               ("Hiring and pay", ("week", "hires_planned", "hired", "layoffs_planned", "laid_off", "workers", "wage_offer_after", "mean_contract_after", "wages_paid")),
                               ("Production and capacity", ("week", "production", "capacity_limit", "productive_capacity", "capital", "inventory", "price"))]:
            if title:
                lines += [f"### {title}", ""]
            lines += ["| " + " | ".join(c.replace("_", " ") for c in columns) + " |", "| " + " | ".join("---" for c in columns) + " |"]
            lines += ["| " + " | ".join(format_cell(row[c]) for c in columns) + " |" for row in rows]
            lines.append("")
        lines += [f"- {'PASS' if c['passed'] else 'FAIL'}: {c['description']}." for c in exp["checks"]]
        lines += [""] + [f"**Observed:** {finding}" for finding in exp["findings"]] + [""]
    lines += ["## Raw evidence", "", "results.json contains starting settings, full config, source hashes, every weekly plan, labor outcomes, market receipts, worker contracts, firm diagnostics and registered firm loans. Infinite diagnostic runway when no payroll is due is encoded as the string Infinity; numeric weekly observations must remain finite. Some engine diagnostics can persist across ticks; the copied plans, receipts and states establish the current week's actions. Existing economy-wide accounting limitations are outside these checks.", ""]
    return "\n".join(lines)


def json_evidence(value):
    """Keep valid infinite runway diagnostics explicit without invalid JSON."""
    if isinstance(value, dict):
        return {key: json_evidence(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_evidence(item) for item in value]
    if isinstance(value, float) and math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", nargs="+", choices=[*presets(), "custom"])
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--ticks", type=int, default=12)
    parser.add_argument("--category", choices=["Food", "Services"], default="Food")
    parser.add_argument("--cash", type=float, default=10000)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--job-seekers", type=int, default=None)
    parser.add_argument("--wage", type=float, default=40)
    parser.add_argument("--reservation-wage", type=float, default=30)
    parser.add_argument("--price", type=float, default=10)
    parser.add_argument("--capacity", type=float, default=None)
    parser.add_argument("--initial-demand", type=float, default=30, help="Prior-week requested units; seeds history once")
    parser.add_argument("--demand", default="30", help="Comma-separated requested units by week; final value repeats")
    parser.add_argument("--bank-cash", type=float, default=0, help="Zero disables the bank; positive reserves enable normal lending")
    parser.add_argument("--buyer-cash", type=float, default=1000000)
    parser.add_argument("--supply-shock-start", type=int, default=0)
    parser.add_argument("--supply-shock-weeks", type=int, default=0)
    parser.add_argument("--supply-multiplier", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path)
    cli_args = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(cli_args)
    custom_flags = {"--category", "--cash", "--workers", "--population", "--job-seekers", "--wage",
                    "--reservation-wage", "--price", "--capacity", "--initial-demand", "--demand",
                    "--bank-cash", "--buyer-cash", "--supply-shock-start", "--supply-shock-weeks", "--supply-multiplier"}
    custom_requested = any(arg.split("=")[0] in custom_flags for arg in cli_args)
    if args.case is None:
        args.case = ["custom"] if custom_requested else list(presets())
    if custom_requested and "custom" not in args.case:
        parser.error("Custom starting conditions require --case custom; preset comparisons use fixed conditions.")
    args.case = list(dict.fromkeys(args.case))
    try:
        if not 0 <= args.seed < 2**32:
            raise ValueError("Seed must be between 0 and 2**32 - 1.")
        custom = Settings(category=args.category, cash=args.cash, workers=args.workers, population=args.population,
                          job_seekers=args.population - args.workers if args.job_seekers is None else args.job_seekers,
                          wage=args.wage, reservation_wage=args.reservation_wage, price=args.price,
                          capacity=(3 if args.category == "Services" else 200) if args.capacity is None else args.capacity,
                          initial_demand=args.initial_demand, demand=tuple(float(v.strip()) for v in args.demand.split(",")),
                          ticks=args.ticks, bank_cash=args.bank_cash, buyer_cash=args.buyer_cash,
                          supply_shock_start=args.supply_shock_start, supply_shock_weeks=args.supply_shock_weeks,
                          supply_multiplier=args.supply_multiplier)
        validate(custom)
        suites = presets(args.ticks)
        selected = [item for group in args.case for item in ([("custom", custom)] if group == "custom" else suites[group])]
        for _, settings in selected:
            validate(settings)
    except ValueError as error:
        parser.error(str(error))
    experiments = [run_experiment(name, settings, args.seed) for name, settings in selected]
    sources = ["backend/agents.py", "backend/economy.py", "backend/config.py", "backend/inflation.py",
               "backend/tools/checks/run_agent_scenarios.py", "backend/tools/checks/run_business_scenarios.py"]
    metadata = {"seed": args.seed, "groups": args.case,
                "source_sha256": {f: hashlib.sha256((REPO_ROOT / f).read_bytes()).hexdigest() for f in sources if (REPO_ROOT / f).exists()},
                "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()}
    output = args.output_dir or REPO_ROOT / "benchmarks/results/business-scenarios" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(json_evidence({"metadata": metadata, "experiments": experiments}), indent=2, allow_nan=False, default=json_scalar) + "\n")
    (output / "report.md").write_text(render_report(experiments, args.seed))
    for experiment in experiments:
        passed = all(c["passed"] for c in experiment["checks"])
        print(f"{'PASS' if passed else 'FAIL'} {experiment['name']}: {len(experiment['rows'])} complete weeks")
        for finding in experiment["findings"]:
            print(f"  OBSERVED: {finding}")
    print(f"Report: {(output / 'report.md').resolve()}")
    return 0 if all(c["passed"] for e in experiments for c in e["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
