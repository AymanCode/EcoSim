"""Small, repeatable household and business experiments, without an LLM.

Run from the repository root:
    .venv/bin/python -m backend.tools.checks.run_agent_scenarios

The isolated cases exercise real simulation phases with explicit starting states.
The small-town case uses the normal world factory and complete Economy.step calls.
Passing a check describes a current mechanism; it does not endorse its economics.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent  # noqa: E402
from config import CONFIG, clone_config, use_config  # noqa: E402
from economy import Economy  # noqa: E402
from tools.runners.run_large_simulation import create_large_economy  # noqa: E402


@contextlib.contextmanager
def isolated_run(seed):
    """Restore both global RNG streams and the context-local configuration."""
    python_state, numpy_state = random.getstate(), np.random.get_state()
    config = clone_config()
    config.random_seed = seed
    config.payment_sequence = "legacy"
    random.seed(seed)
    np.random.seed(seed)
    try:
        with use_config(config):
            yield
    finally:
        random.setstate(python_state)
        np.random.set_state(numpy_state)


def small_world(seed, *, cash=100.0, deposits=0.0, category="Food", workers=1):
    """Explicit fixtures, not a calibrated town. Each variant starts afresh."""
    random.seed(seed)
    np.random.seed(seed)
    households = [HouseholdAgent(i + 1, skills_level=0.5, age=30, cash_balance=cash)
                  for i in range(workers)]
    firm = FirmAgent(
        firm_id=1, good_name="Shop", good_category=category, cash_balance=10_000.0,
        inventory_units=10.0 if category == "Food" else 0.0, price=10.0,
        wage_offer=40.0, expected_sales_units=40.0, quality_level=5.0,
        production_capacity_units=200.0, productivity_per_worker=12.0,
        personality="moderate", is_baseline=False,
        max_rental_units=1 if category == "Housing" else 0,
    )
    bank = BankAgent(cash_reserves=10_000.0)
    government = GovernmentAgent(cash_balance=20_000.0, unemployment_benefit_level=30.0,
                                 transfer_budget=0.0, wage_tax_rate=0.15, profit_tax_rate=0.20)
    for household in households:
        household.employer_id = firm.firm_id
        household.wage = household.expected_wage = 40.0
        household.health = 0.8
        household.spending_tendency = household.frugality = 1.0
        household.savings_drawdown_rate = 0.02
        household.subsistence_min_cash = 50.0
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        household.bank_deposit = deposits
        bank.accept_deposit(household.household_id, deposits)
        firm.employees.append(household.household_id)
        firm.actual_wages[household.household_id] = household.wage
    firm.age_in_ticks = 30
    firm.last_revenue = 400.0
    firm.last_profit = 100.0
    firm.last_units_sold = firm.sales_velocity_ema = 40.0
    return Economy(households, [firm], government, bank=bank)


def shopping_plan(economy):
    return economy._batch_plan_consumption(
        {}, economy._build_category_market_snapshot(), economy._build_good_category_lookup(),
        unemployment_rate=0.0, unemployment_benefit=30.0,
    )[1]


def result(case_id, question, scope, rows, checks, findings=()):
    return {"id": case_id, "question": question, "scope": scope, "rows": rows,
            "checks": [{"description": name, "passed": bool(passed)} for name, passed in checks],
            "findings": list(findings)}


def household_budget(seed):
    rows = []
    for label, cash, deposits in (("broke", 0, 0), ("tight", 10, 0), ("buffer", 100, 0),
                                  ("comfortable", 1000, 0), ("savings only", 0, 100)):
        economy = small_world(seed, cash=cash, deposits=deposits)
        plan = shopping_plan(economy)
        rows.append({"case": label, "cash": cash, "deposits": deposits, "wage_due": 40,
                     "shopping_budget": plan["budget"],
                     "planned_goods_cost": sum(economy.firm_lookup[fid].price * qty
                                               for fid, qty in plan["planned_purchases"].items())})
    return result("household_budget", "What can a household plan to buy at different cash levels?",
                  "Isolated pre-income batch planner; same worker, traits and food shop. In the complete default tick, shopping now waits for income. Budget is a ceiling, not spending.",
                  rows, [("Zero cash and deposits produce a zero shopping budget", rows[0]["shopping_budget"] == 0),
                         ("More cash permits at least as much budget in these cases",
                          all(a["shopping_budget"] <= b["shopping_budget"] for a, b in zip(rows[:3], rows[1:4]))),
                         ("Deposits can support the planned budget", rows[4]["shopping_budget"] > 0),
                         ("Every budget stays within cash plus 90% of deposits",
                          all(r["shopping_budget"] <= r["cash"] + 0.9 * r["deposits"] + 1e-8 for r in rows))],
                  [])


def household_credit(seed):
    rows = []
    for label, score, debt, reserves in (("eligible", .5, 0, 10000), ("poor credit", .2, 0, 10000),
                                        ("existing debt", .5, 200, 10000), ("empty bank", .5, 0, 0)):
        economy = small_world(seed, cash=0)
        household = economy.households[0]
        economy.bank.cash_reserves = reserves
        economy.bank.household_credit_scores[1] = score
        household.consumption_loan_remaining = debt
        plan = shopping_plan(economy)
        household.maybe_request_consumption_loan(economy.bank)
        economy._offer_consumption_loans()
        funded_plan = shopping_plan(economy)
        rows.append({"case": label, "credit_score": score, "old_debt": debt,
                     "shopping_budget_before_loan": plan["budget"], "loan_cash_received": household.cash_balance,
                     "debt_after": household.consumption_loan_remaining,
                     "shopping_budget_after_loan": funded_plan["budget"]})
    return result("household_credit", "Does having no cash guarantee a loan?",
                  "Actual request and funding phases, with before/after planning probes. The default tick now makes its shopping decision after this funding. No repayment yet.",
                  rows, [("Eligible household receives a loan", rows[0]["loan_cash_received"] == 200),
                         ("Credit, debt and bank funding gates can each prevent a loan",
                          all(r["loan_cash_received"] == 0 for r in rows[1:])),
                         ("Approved credit supports a positive same-week shopping budget",
                          rows[0]["shopping_budget_after_loan"] > 0)])


def household_payday(seed):
    economy = small_world(seed, cash=0)
    # Start beyond warmup and its transition; keep the complete tick unmodified.
    economy.current_tick = economy.warmup_ticks + 7
    economy.in_warmup = False
    with contextlib.redirect_stdout(io.StringIO()):
        economy.step()
    household = economy.households[0]
    borrowed = sum(loan["principal"] for loan in economy.bank.active_loans
                   if loan["borrower_type"] == "household" and loan["borrower_id"] == 1
                   and loan.get("subtype") == "consumption")
    rows = [{"cash_before": 0, "wages_received": household.last_wage_income,
             "consumption_loan_received": borrowed, "goods_spending": household.last_consumption_spending,
             "food_eaten": household.food_consumed_this_tick, "cash_after": household.cash_balance,
             "cash_change_not_itemized": unitemized_cash_change(household)}]
    return result("household_payday", "Can new wages and credit fund shopping in the same complete week?",
                  "One household, one food business and a bank; actual Economy.step after warmup. All other tick rules remain active, including policy changes and redistribution, so final cash includes more than the displayed wages and loan.",
                  rows, [("The worker actually receives wages and emergency credit", household.last_wage_income > 0 and borrowed > 0),
                         ("The household buys goods that week", household.last_consumption_spending > 0),
                         ("The household eats food that week", household.food_consumed_this_tick > 0)],
                  ["The default household cash ledger omits some movements, including consumption-loan proceeds and recycled capital spending. Actual cash changes exceed the sum of itemized flows in this case."]
                  if abs(unitemized_cash_change(household)) > 1e-8 else [])


def household_benefits(seed):
    rows = []
    for label, employed, cash in (("employed but broke", True, 0), ("unemployed and broke", False, 0),
                                   ("unemployed with savings", False, 1000)):
        economy = small_world(seed, cash=cash)
        transfers = economy.government.plan_transfers([
            {"household_id": 1, "is_employed": employed, "cash_balance": cash}])
        rows.append({"case": label, "cash": cash, "employed": employed, "benefit_planned": transfers.get(1, 0)})
    return result("household_benefits", "Who gets unemployment benefits when money is tight?",
                  "Actual government transfer planner; $30 base benefit and zero extra top-up budget. Planning only; cash has not been paid yet.",
                  rows, [("Employment excludes this unemployment benefit", rows[0]["benefit_planned"] == 0),
                         ("Both unemployed households qualify for the base benefit",
                          rows[1]["benefit_planned"] == rows[2]["benefit_planned"] == 30)])


def household_rent(seed):
    rows = []
    for label, cash, deposits in (("broke", 0, 0), ("short", 10, 0), ("funded", 100, 0), ("savings", 0, 100)):
        economy = small_world(seed, cash=cash, deposits=deposits, category="Housing")
        household, landlord = economy.households[0], economy.firms[0]
        landlord.price = household.monthly_rent = 20.0  # Despite the field name, rent is weekly.
        landlord.current_tenants = [1]
        household.renting_from_firm_id = 1
        household.owns_housing = True
        before = landlord.cash_balance
        economy._clear_housing_rental_market()
        rows.append({"case": label, "cash_before": cash, "deposits_before": deposits,
                     "rent_paid": landlord.cash_balance - before, "cash_after": household.cash_balance,
                     "deposits_after": household.bank_deposit, "housed_after": household.renting_from_firm_id is not None})
    return result("household_rent", "What happens if the household cannot pay this week's rent?",
                  "Actual rental phase; one occupied unit at $20/week, $40 weekly wage, balances as shown at rent collection, no cheaper alternative.",
                  rows, [("Insufficient liquid funds end the tenancy", all(not r["housed_after"] for r in rows[:2])),
                         ("Cash or funded deposit withdrawal can cover rent", all(r["housed_after"] for r in rows[2:])),
                         ("Rent received equals the household's cash and deposit loss",
                          all(abs(r["cash_before"] + r["deposits_before"] - r["cash_after"] - r["deposits_after"] - r["rent_paid"]) < 1e-8 for r in rows))],
                  ["The rental rule still has immediate eviction when rent cannot be paid. Wages now arrive before this phase in a complete default week; a cheaper available home could also change its outcome."])


def household_debt(seed):
    rows = []
    for cash in (0, 5, 20):
        economy = small_world(seed, cash=cash)
        household, bank = economy.households[0], economy.bank
        # Existing $100 loan; proceeds were spent before this phase fixture begins.
        loan = bank.originate_loan("household", 1, 100.0, 0.0, 10)
        loan["subtype"] = "consumption"
        household.consumption_loan_remaining = 100.0
        household.consumption_loan_payment_per_tick = 10.0
        reserves_before = bank.cash_reserves
        economy._collect_bank_loan_repayments()
        rows.append({"cash_before": cash, "scheduled_payment": 10,
                     "paid": cash - household.cash_balance, "bank_received": bank.cash_reserves - reserves_before,
                     "cash_after": household.cash_balance, "remaining_debt": loan["remaining"],
                     "missed_payments": loan.get("missed_payments", 0), "credit_after": bank.get_household_credit_score(1)})
    return result("household_debt", "What if there is only enough money for part of a loan payment?",
                  "Actual registered-loan collection; $10 due and remaining cash as shown. Wages now arrive before this phase in a complete default week.",
                  rows, [("Collection cannot take more cash than the borrower has", all(r["cash_after"] >= 0 for r in rows)),
                         ("Borrower payments reach the bank", all(abs(r["paid"] - r["bank_received"]) < 1e-8 for r in rows)),
                         ("Unpaid contractual balances remain outstanding", all(abs(100 - r["paid"] - r["remaining_debt"]) < 1e-8 for r in rows))],
                  ["In the default collector, a partial positive payment improves credit and does not count as a missed payment. That is a rule to review."] if rows[1]["missed_payments"] == 0 and rows[1]["credit_after"] > .5 else [])


def household_health(seed):
    rows = []
    for label, health, food in (("no food", .8, 0), ("fed", .8, 5), ("too ill to work", .05, 0)):
        economy = small_world(seed, cash=0)
        household = economy.households[0]
        household.employer_id = None
        household.wage = 0
        household.health = health
        household.food_consumed_this_tick = food
        household.last_tick_cash_start = 0
        labor = household.plan_labor_supply(30, mean_posted_wage=40)
        economy._batch_update_wellbeing(1.0)
        rows.append({"case": label, "health_before": health, "food_eaten": food,
                     "health_after": household.health, "looking_for_work": labor["searching_for_job"]})
    return result("household_health", "How do hunger and poor health affect the household?",
                  "Actual labor plan and batch wellbeing update; unemployed household, no treatment in this isolated phase.",
                  rows, [("No food damages health more than adequate food", rows[0]["health_after"] < rows[1]["health_after"]),
                         ("Very poor health prevents job search", not rows[2]["looking_for_work"]),
                         ("Healthy unemployed household searches", rows[0]["looking_for_work"])])


def business_demand(seed):
    rows = []
    for sales in (0, 40):
        economy = small_world(seed, workers=2)
        firm = economy.firms[0]
        plan = firm.plan_production_and_labor(sales, total_households=24, minimum_wage_floor=20)
        rows.append({"last_week_sales_units": sales, "cash": firm.cash_balance,
                     "inventory": firm.inventory_units, "expected_sales_now": firm.expected_sales_units,
                     "planned_production": plan["planned_production_units"],
                     "planned_hires": plan["planned_hires_count"], "planned_layoffs": len(plan["planned_layoffs_ids"])})
    return result("business_demand", "Does a business change its plan when customers disappear?",
                  "Actual food-firm planner; two workers, same cash, inventory, traits and previous expectations. Only completed sales change.",
                  rows, [("Lost sales lower expected demand", rows[0]["expected_sales_now"] < rows[1]["expected_sales_now"]),
                         ("No sales reduce planned production", rows[0]["planned_production"] < rows[1]["planned_production"])])


def business_payroll(seed):
    rows = []
    for cash in (0, 40, 100):
        economy = small_world(seed, workers=2)
        firm = economy.firms[0]
        firm.cash_balance = cash
        household_cash = sum(h.cash_balance for h in economy.households)
        firm.apply_production_and_costs({"realized_production_units": 0.0})
        economy._batch_apply_household_updates({}, {}, {}, frozen_wages={1: 40, 2: 40})
        received = sum(h.cash_balance for h in economy.households) - household_cash
        rows.append({"business_cash_before": cash, "payroll_due": 80,
                     "business_cash_after": firm.cash_balance, "workers_received": received})
    return result("business_payroll", "What happens when a business cannot afford payroll?",
                  "Actual production-cost and household-income phases; two retained workers at $40 each, no sales or taxes in this fixture.",
                  rows, [("The business debit equals workers' receipts", all(abs(r["business_cash_before"] - r["business_cash_after"] - r["workers_received"]) < 1e-8 for r in rows))],
                  ["The default payroll path pays the full wage bill and permits negative business cash. Zero cash does not by itself stop wages in this phase."] if rows[0]["business_cash_after"] < 0 else [])


def business_exit(seed):
    rows = []
    threshold = CONFIG.market.bankruptcy_threshold
    for label, cash, baseline in (("zero cash", 0, False), ("below exit threshold", threshold - 1, False),
                                   ("protected baseline", threshold - 1, True)):
        economy = small_world(seed)
        firm, household = economy.firms[0], economy.households[0]
        firm.cash_balance = cash
        firm.is_baseline = baseline
        if baseline:
            economy.government.register_baseline_firm("Food", 1)
        economy._handle_firm_exits()
        rows.append({"case": label, "cash": cash, "exit_threshold": threshold,
                     "business_survives": bool(economy.firms), "worker_keeps_job": household.is_employed})
    return result("business_exit", "When does a business close, and what happens to its worker?",
                  "Actual exit phase; zero-cash streak starts at zero. Baseline is an exit-protection flag, not public ownership.",
                  rows, [("Zero cash alone does not cause immediate exit", rows[0]["business_survives"]),
                         ("An unprotected firm below the threshold closes and releases its worker",
                          not rows[1]["business_survives"] and not rows[1]["worker_keeps_job"]),
                         ("Registered baseline firm is protected from this exit rule", rows[2]["business_survives"])])


def unitemized_cash_change(household):
    flows = household.last_tick_ledger
    return flows.get("net", 0.0) - sum(value for key, value in flows.items() if key != "net")


def small_town(seed, households=24, ticks=24):
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=households, num_firms_per_category=1)
        initial_firms = len(economy.firms)
        rows, traces = [], []
        for week in range(1, ticks + 1):
            economy.step()
            hhs = [{"id": h.household_id, "cash": h.cash_balance, "deposits": h.bank_deposit,
                    "employer": h.employer_id, "food_eaten": h.food_consumed_this_tick,
                    "health": h.health, "housed": h.renting_from_firm_id is not None,
                    "consumption_debt": h.consumption_loan_remaining,
                    "flows": dict(h.last_tick_ledger),
                    "cash_change_not_itemized": unitemized_cash_change(h)} for h in economy.households]
            firms = [{"id": f.firm_id, "category": f.good_category, "baseline": f.is_baseline,
                      "cash": f.cash_balance, "workers": list(f.employees), "price": f.price,
                      "sales": f.last_revenue, "inventory": f.inventory_units,
                      "survival_mode": f.survival_mode} for f in economy.firms]
            traces.append({"week": week, "households": hhs, "businesses": firms})
            rows.append({"week": week, "employed": sum(h["employer"] is not None for h in hhs),
                         "households": len(hhs), "housed": sum(h["housed"] for h in hhs),
                         "mean_food_eaten": sum(h["food_eaten"] for h in hhs) / len(hhs),
                         "negative_household_cash": sum(h["cash"] < -1e-8 for h in hhs),
                         "businesses": len(firms), "negative_business_cash": sum(f["cash"] < -1e-8 for f in firms)})
    finite = all(np.isfinite(h[key]) for t in traces for h in t["households"]
                 for key in ("cash", "deposits", "food_eaten", "health", "consumption_debt"))
    rosters_match = all(
        {h["id"] for h in t["households"] if h["employer"] == f["id"]} == set(f["workers"])
        for t in traces for f in t["businesses"]
    ) and all(h["employer"] is None or h["employer"] in {f["id"] for f in t["businesses"]}
              for t in traces for h in t["households"])
    findings = []
    if any(r["negative_household_cash"] for r in rows):
        findings.append("This complete town run produced negative household cash. Inspect the weekly household flows before changing a spending rule.")
    if any(r["negative_business_cash"] for r in rows):
        findings.append("This complete town run produced negative business cash.")
    data = result("small_town", "Do the actors work together through complete weeks?",
                  f"Normal world factory and full ticks: {households} households, {initial_firms} initial firms, {ticks} weeks. Default warmup, shocks, bank, policy and entry rules remain active. This tiny town is not a calibration sample.",
                  rows, [("All household measurements remain finite", finite),
                         ("Business rosters agree with household employers", rosters_match),
                         ("Health remains within zero and one", all(0 <= h["health"] <= 1 for t in traces for h in t["households"]))], findings)
    data["traces"] = traces
    return data


CASES = {fn.__name__: fn for fn in (household_budget, household_credit, household_payday, household_benefits, household_rent, household_debt,
                                   household_health, business_demand, business_payroll, business_exit, small_town)}


def run_suite(case_ids, *, seed=1337, households=24, ticks=24):
    results = []
    for case_id in case_ids:
        with isolated_run(seed):
            kwargs = {"households": households, "ticks": ticks} if case_id == "small_town" else {}
            results.append(CASES[case_id](seed, **kwargs))
    return results


def format_cell(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|")


def json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Unsupported observation type: {type(value).__name__}")


def render_report(results, seed):
    checks = [c for case in results for c in case["checks"]]
    findings = [f for case in results for f in case["findings"]]
    lines = ["# Small household and business experiments", "",
             f"Seed: {seed}. Payment rules: `legacy` (the current default). No LLM needed.", "",
             f"{sum(c['passed'] for c in checks)}/{len(checks)} mechanism checks passed; {len(findings)} observations need review.", "",
             "Passing describes the current program. It does not mean the economic rule is desirable or the town is calibrated.", "",
             "The focused cases call the same phases as the simulation with explicit starting states. The payday case and small town also run complete weeks.", ""]
    for case in results:
        lines += [f"## {case['question']}", "", case["scope"], ""]
        columns = list(case["rows"][0])
        lines += ["| " + " | ".join(c.replace("_", " ") for c in columns) + " |",
                  "| " + " | ".join("---" for _ in columns) + " |"]
        lines += ["| " + " | ".join(format_cell(row[c]) for c in columns) + " |" for row in case["rows"]]
        lines += [""] + [f"- {'PASS' if c['passed'] else 'FAIL'}: {c['description']}." for c in case["checks"]]
        if case["findings"]:
            lines += [""] + [f"**Review:** {finding}" for finding in case["findings"]]
        lines += [""]
    lines += ["## Scope", "", "These fixtures cover money, benefits, emergency borrowing, rent, debt, hunger, job eligibility, demand, payroll and closure. They do not yet isolate healthcare funding, skill matching, business borrowing, taxes, dividends or the two named payment sequences. The JSON includes household and business traces for every small-town week. The cash_change_not_itemized field reports the gap between actual cash changes and recorded flow categories; the default ledger is incomplete.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", nargs="+", choices=tuple(CASES), default=list(CASES))
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--households", type=int, default=24, help="Small-town population, from 12 to 100")
    parser.add_argument("--ticks", type=int, default=24, help="Small-town weeks, from 1 to 52")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if not 12 <= args.households <= 100 or not 1 <= args.ticks <= 52:
        parser.error("Use 12–100 households and 1–52 ticks for these small experiments.")
    if not 0 <= args.seed < 2**32:
        parser.error("Seed must be between 0 and 2**32 - 1.")
    output = args.output_dir or REPO_ROOT / "benchmarks/results/agent-scenarios" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    results = run_suite(args.case, seed=args.seed, households=args.households, ticks=args.ticks)
    sources = ["backend/agents.py", "backend/economy.py", "backend/config.py",
               "backend/tools/runners/run_large_simulation.py", "backend/tools/checks/run_agent_scenarios.py"]
    metadata = {"seed": args.seed, "payment_sequence": "legacy", "cases": args.case,
                "households": args.households, "ticks": args.ticks,
                "source_sha256": {p: hashlib.sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in sources}}
    for key, command in (("commit", ["git", "rev-parse", "HEAD"]), ("working_tree", ["git", "status", "--short"])):
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        metadata[key] = completed.stdout.strip() if completed.returncode == 0 else "unavailable"
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps({"metadata": metadata, "results": results}, indent=2, allow_nan=False, default=json_scalar) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(results, args.seed), encoding="utf-8")
    for case in results:
        passed = all(check["passed"] for check in case["checks"])
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {case['question']}")
        for finding in case["findings"]:
            print(f"  REVIEW: {finding}")
    print(f"Report: {(output / 'report.md').resolve()}")
    print(f"Raw observations: {(output / 'results.json').resolve()}")
    return 0 if all(c["passed"] for case in results for c in case["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
