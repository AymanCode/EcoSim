"""Public works hires the headcount the government authorizes (bug 8).

Before the fix, ``Economy._ensure_public_works_capacity`` wrote a job count
into ``baseline_production_quota`` and the baseline planner read it as output
units (``0.8 * quota`` units at ~15+ units per worker), so 200 authorized jobs
became about 8 filled jobs. These tests pin the behavior a policy comparison
relies on: authorized jobs turn into hiring, the target follows the jobless
pool, and staff changes are paced by ``public_works_ramp_weeks``.
"""

import contextlib
import io

import pytest

from agents import FirmAgent
from config import CONFIG
from tests_contracts.factories import seed_everything
from tools.runners.run_large_simulation import create_large_economy


def _public_works_firm(target_jobs: int, staff: int) -> FirmAgent:
    firm = FirmAgent(
        firm_id=901,
        good_name="PublicWorks901",
        cash_balance=200_000.0,
        inventory_units=0.0,
        good_category="PublicWorks",
        quality_level=1.0,
        wage_offer=45.0,
        price=1.0,
        expected_sales_units=float(target_jobs),
        production_capacity_units=float(target_jobs * 2),
        units_per_worker=15.0,
        productivity_per_worker=15.0,
        personality="conservative",
        is_baseline=True,
        baseline_production_quota=float(target_jobs),
    )
    firm.employees = list(range(10_000, 10_000 + staff))
    firm.public_works_target_jobs = target_jobs
    return firm


def _set_jobless(economy, jobless: int) -> int:
    """Make exactly ``jobless`` working-age households unemployed; return labor force."""
    food = next(f for f in economy.firms if f.good_category == "Food")
    workers = [h for h in economy.households if h.can_work]
    for index, household in enumerate(workers):
        household.employer_id = None if index < jobless else food.firm_id
    return len(workers)


def test_planner_hires_toward_authorized_headcount(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_works_ramp_weeks", 8)
    firm = _public_works_firm(target_jobs=200, staff=0)

    plan = firm.plan_production_and_labor(0.0, total_households=1000)

    # ceil(200 / 8) = 25 hires this tick; the old path planned ~8 workers total.
    assert plan["planned_hires_count"] == 25
    assert plan["planned_layoffs_ids"] == []


def test_planner_releases_staff_at_ramp_pace_when_target_falls(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_works_ramp_weeks", 8)
    firm = _public_works_firm(target_jobs=0, staff=40)

    plan = firm.plan_production_and_labor(0.0, total_households=1000)

    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) == 5  # ceil(40 / 8)


def test_target_is_a_share_of_the_jobless_pool(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    labor_force = _set_jobless(economy, jobless=24)
    economy.government.set_lever("public_works", "on")

    economy._ensure_public_works_capacity(unemployment_rate=0.0)

    share = CONFIG.government.public_works_jobless_share
    ceiling = int(CONFIG.government.public_works_job_fraction * labor_force)
    expected = min(round(share * 24), ceiling)
    public = [f for f in economy.firms if f.good_category == "PublicWorks"]
    assert len(public) == 1
    assert public[0].public_works_target_jobs == expected
    assert economy.last_tick_gov_public_works_jobs_authorized == expected


def test_target_counts_public_works_staff_as_jobless_and_falls_with_private_hiring(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    _set_jobless(economy, jobless=24)
    economy.government.set_lever("public_works", "on")
    economy._ensure_public_works_capacity(unemployment_rate=0.0)
    firm = next(f for f in economy.firms if f.good_category == "PublicWorks")
    first_target = firm.public_works_target_jobs

    # Move the target headcount from unemployment onto public works: the pool,
    # and so the target, should not change.
    hired = [h for h in economy.households if h.can_work and not h.is_employed][:first_target]
    for household in hired:
        household.employer_id = firm.firm_id
    firm.employees = [h.household_id for h in hired]
    economy._ensure_public_works_capacity(unemployment_rate=0.0)
    assert firm.public_works_target_jobs == first_target

    # Private employers hire everyone else who was jobless: the target drops.
    food = next(f for f in economy.firms if f.good_category == "Food")
    for household in economy.households:
        if household.can_work and not household.is_employed:
            household.employer_id = food.firm_id
    economy._ensure_public_works_capacity(unemployment_rate=0.0)
    assert firm.public_works_target_jobs < first_target


def test_no_firm_is_capitalized_when_nobody_is_jobless(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    _set_jobless(economy, jobless=0)
    economy.government.set_lever("public_works", "on")
    cash_before = economy.government.cash_balance

    spent = economy._ensure_public_works_capacity(unemployment_rate=0.0)

    assert spent == 0.0
    assert economy.government.cash_balance == cash_before
    assert not [f for f in economy.firms if f.good_category == "PublicWorks"]


def test_authorized_jobs_become_filled_jobs_in_a_running_economy():
    seed_everything(42)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=300, num_firms_per_category=3)
    economy.government.cash_balance = max(economy.government.cash_balance, 400_000.0)
    economy.government.set_lever("public_works", "on")

    for _ in range(CONFIG.time.warmup_ticks + 2 * CONFIG.government.public_works_ramp_weeks):
        economy.step()

    firm = next(f for f in economy.firms if f.good_category == "PublicWorks")
    authorized = economy.last_tick_gov_public_works_jobs_authorized
    assert authorized > 0
    # Within one ramp step of the authorized headcount (the target can move
    # by a step between the authorization and the hiring in the same tick).
    assert abs(len(firm.employees) - authorized) <= firm.public_works_step_limit()


def test_flag_off_keeps_pre_fix_output_unit_planning(monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_works_headcount_planning_enabled", False)
    firm = _public_works_firm(target_jobs=200, staff=0)
    firm.public_works_target_jobs = 0

    plan = firm.plan_production_and_labor(0.0, total_households=1000, in_warmup=False)

    # The baseline planner reads the 200 as output units and asks for a
    # handful of workers, far below 200.
    assert 0 < plan["planned_hires_count"] < 20


def _funded_firm_with_staff(economy, staff: int):
    _set_jobless(economy, jobless=24)
    economy.government.set_lever("public_works", "on")
    economy._ensure_public_works_capacity(unemployment_rate=0.0)
    firm = next(f for f in economy.firms if f.good_category == "PublicWorks")
    jobless = [h for h in economy.households if h.can_work and not h.is_employed][:staff]
    for household in jobless:
        household.employer_id = firm.firm_id
    firm.employees = [h.household_id for h in jobless]
    firm.actual_wages = {h.household_id: 50.0 for h in jobless}
    firm._invalidate_wage_bill_cache()
    return firm


def test_treasury_covers_payroll_once_startup_capital_is_spent(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    firm = _funded_firm_with_staff(economy, staff=8)
    firm.public_works_target_jobs = 8  # no hires due: payroll is the current bill
    firm.cash_balance = 0.0
    economy.last_tick_gov_public_works_payroll_funding = 0.0
    gov_before = economy.government.cash_balance

    paid = economy._fund_public_works_payroll([firm])

    bill = 8 * 50.0
    # Firm holds this week's payroll plus one week ahead.
    assert firm.cash_balance == pytest.approx(2 * bill)
    # Every dollar the firm gained left the treasury and is on the books.
    assert paid == pytest.approx(2 * bill)
    assert gov_before - economy.government.cash_balance == pytest.approx(paid)
    assert economy.last_tick_gov_public_works_payroll_funding == pytest.approx(paid)


def test_payroll_funding_tops_up_without_accumulating(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    firm = _funded_firm_with_staff(economy, staff=8)
    firm.public_works_target_jobs = 8
    firm.cash_balance = 0.0
    economy._fund_public_works_payroll([firm])

    # Wages paid: the firm is back to one week ahead; the next transfer tops
    # up to the same level, not beyond it.
    firm.cash_balance -= 8 * 50.0
    paid = economy._fund_public_works_payroll([firm])

    assert paid == pytest.approx(8 * 50.0)
    assert firm.cash_balance == pytest.approx(2 * 8 * 50.0)
    # A firm that still has its startup capital gets nothing.
    firm.cash_balance = 150_000.0
    assert economy._fund_public_works_payroll([firm]) == 0.0


def test_payroll_funding_counts_as_government_spending_in_a_step():
    seed_everything(42)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(num_households=300, num_firms_per_category=3)
    economy.government.cash_balance = max(economy.government.cash_balance, 400_000.0)
    economy.government.set_lever("public_works", "on")
    for _ in range(CONFIG.time.warmup_ticks + 2):
        economy.step()
    firm = next(f for f in economy.firms if f.good_category == "PublicWorks")
    firm.cash_balance = 0.0  # startup capital spent

    economy.step()
    metrics = economy.get_economic_metrics()

    funded = metrics["gov_public_works_payroll_funding_this_tick"]
    assert funded > 0.0
    assert metrics["gov_spending_this_tick"] >= funded
    assert firm.cash_balance > 0.0  # no bankruptcy, no unfunded wages


def test_payroll_funding_flag_off_leaves_firm_on_startup_capital(tiny_economy_factory, monkeypatch):
    monkeypatch.setattr(CONFIG.government, "public_works_payroll_funding_enabled", False)
    economy = tiny_economy_factory(num_households=60, government_cash=300_000.0)
    firm = _funded_firm_with_staff(economy, staff=8)
    firm.cash_balance = 0.0
    gov_before = economy.government.cash_balance

    economy._ensure_public_works_capacity(unemployment_rate=0.0)

    assert economy.government.cash_balance == gov_before
    assert firm.cash_balance == 0.0
