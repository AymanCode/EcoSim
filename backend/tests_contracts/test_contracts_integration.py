import math

import numpy as np
import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def test_contract_no_spiral_collapse_under_baseline(tiny_economy_factory):
    """Contract L: Short baseline run should stay numerically and behaviorally sane."""
    economy = tiny_economy_factory(
        num_households=12,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=444,
        government_cash=80_000.0,
    )

    for _ in range(15):
        economy.step()

    health = np.array([h.health for h in economy.households], dtype=float)
    happiness = np.array([h.happiness for h in economy.households], dtype=float)
    morale = np.array([h.morale for h in economy.households], dtype=float)

    assert np.mean(health) > 0.1
    assert np.mean(happiness) > 0.1
    assert np.mean(morale) > 0.1

    assert np.isfinite(health).all()
    assert np.isfinite(happiness).all()
    assert np.isfinite(morale).all()

    unemployment_rate = sum(1 for h in economy.households if not h.is_employed) / len(economy.households)
    assert unemployment_rate < 1.0

    for firm in economy.firms:
        assert firm.price > 0.0
        assert math.isfinite(firm.price)
        assert math.isfinite(firm.wage_offer)
        assert math.isfinite(firm.cash_balance)


def test_contract_healthcare_demand_appears_when_health_is_low(tiny_economy_factory):
    """Contract M: Low-health households generate more healthcare service demand."""
    economy = tiny_economy_factory(
        num_households=10,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=False,
        disable_shocks=True,
        seed=555,
    )

    low_ids = {h.household_id for h in economy.households[:5]}
    high_ids = {h.household_id for h in economy.households[5:]}

    for household in economy.households:
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        if household.household_id in low_ids:
            household.health = 0.1
            # Force low-health households to have pending visits (new episode model).
            household.pending_healthcare_visits = 3
            household.next_healthcare_request_tick = 0
        else:
            household.health = 0.95
            # Healthy households should not request care this tick.
            household.pending_healthcare_visits = 0
            household.next_healthcare_request_tick = economy.current_tick + 999

    healthcare_firms = [f for f in economy.firms if f.good_category.lower() == "healthcare"]
    assert healthcare_firms
    for firm in healthcare_firms:
        firm.employees = list(range(1000 + firm.firm_id, 1004 + firm.firm_id))
        firm.healthcare_capacity_per_worker = 2.0

    economy._enqueue_healthcare_requests()

    low_requested = sum(
        1 for household in economy.households
        if household.household_id in low_ids and household.queued_healthcare_firm_id is not None
    )
    high_requested = sum(
        1 for household in economy.households
        if household.household_id in high_ids and household.queued_healthcare_firm_id is not None
    )

    assert low_requested > 0
    assert low_requested > high_requested

    per_firm_sales = {}
    economy._process_healthcare_services(per_firm_sales)
    total_completed = sum(f.healthcare_completed_visits_last_tick for f in healthcare_firms)
    total_capacity = sum(len(f.employees) * f.healthcare_capacity_per_worker for f in healthcare_firms)
    assert total_completed <= total_capacity + 1e-8


def test_contract_firm_survival_mode_behaviors():
    """Contract N: Survival mode engages and blocks R&D/dividends under distress."""
    firm = FirmAgent(
        firm_id=900,
        good_name="StressFirm",
        cash_balance=100.0,
        inventory_units=300.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=100.0,
        price=10.0,
        expected_sales_units=200.0,
        production_capacity_units=400.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )

    # Give the firm a known run-rate so it is below the 2-week runway threshold.
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.last_revenue = 0.0

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        total_households=30,
    )

    assert firm.survival_mode is True
    assert len(plan["planned_layoffs_ids"]) > 0
    assert plan["planned_hires_count"] == 0
    assert plan["planned_production_units"] <= firm.production_capacity_units * 0.1 + 1e-9

    # In survival mode, R&D and dividends should be halted.
    rd_spend = firm.apply_rd_and_quality_update(revenue=1_000.0)
    assert rd_spend == 0.0

    owner = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0)
    firm.net_profit = 5_000.0
    firm.owners = [1]
    paid = firm.distribute_profits({1: owner})
    assert paid == 0.0


def test_contract_post_warmup_labor_market_remains_active(tiny_economy_factory):
    """Contract O: After warmup (tick > 52), non-healthcare labor matching still produces hires."""
    economy = tiny_economy_factory(
        num_households=180,
        num_firms_per_category=3,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=777,
        government_cash=120_000.0,
    )
    # Small economies need active stabilisation — set levers that
    # replicate what the old auto-stabilisers would have done.
    economy.government.set_lever("benefit_level", "high")
    economy.government.set_lever("public_works", "on")

    post_warmup_hires = 0
    for _ in range(70):
        economy.step()
        if economy.current_tick > 52:
            post_warmup_hires += sum(
                int(getattr(firm, "last_tick_actual_hires", 0))
                for firm in economy.firms
                if (firm.good_category or "").lower() != "healthcare"
            )

    assert economy.current_tick >= 70
    assert economy.in_warmup is False

    # A hard failure mode is "everyone can work but matching never hires".
    work_capable = [h for h in economy.households if h.can_work]
    employed_capable = sum(1 for h in work_capable if h.is_employed)
    assert employed_capable > 0
    assert post_warmup_hires > 0

    # Diagnostics should still indicate active seekers (not a dead labor market).
    diagnostics = economy.last_labor_diagnostics
    assert diagnostics.get("labor_seekers_total", 0.0) > 0.0


def test_contract_private_startups_bootstrap_small():
    firm = FirmAgent(
        firm_id=910,
        good_name="BootstrapFood",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=35.0,
        price=12.0,
        expected_sales_units=40.0,
        production_capacity_units=300.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        total_households=40,
    )

    assert 0 <= plan["planned_hires_count"] <= 2


def test_contract_unprofitable_private_firm_does_not_expand_staff():
    firm = FirmAgent(
        firm_id=911,
        good_name="LossMaker",
        cash_balance=500.0,
        inventory_units=400.0,
        good_category="Food",
        quality_level=4.0,
        wage_offer=40.0,
        price=6.0,
        expected_sales_units=60.0,
        production_capacity_units=400.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1, 2, 3, 4, 5]
    firm.actual_wages = {employee_id: 40.0 for employee_id in firm.employees}
    firm.last_revenue = 30.0
    firm.last_units_sold = 5.0

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=5.0,
        in_warmup=False,
        total_households=40,
    )

    assert plan["planned_hires_count"] == 0
    assert len(plan["planned_layoffs_ids"]) > 0


def test_contract_private_wage_ratchet_does_not_spike_from_one_worker_revenue():
    firm = FirmAgent(
        firm_id=914,
        good_name="AnchorFood",
        cash_balance=8_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=8.0,
        expected_sales_units=80.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1]
    firm.actual_wages = {1: 40.0}
    firm.last_revenue = 1_200.0
    firm.last_profit = 700.0
    firm.last_tick_planned_hires = 1
    firm.last_tick_actual_hires = 0

    snapshot = firm.refresh_health_snapshot(sell_through_rate=1.0, category_wage_anchor_p75=45.0)
    wage_plan = firm.plan_wage(
        unemployment_rate=0.05,
        unemployment_benefit=30.0,
        in_warmup=False,
        health_snapshot=snapshot,
    )

    assert wage_plan["wage_offer_next"] <= 46.0
    assert wage_plan["wage_offer_next"] < 100.0


def test_contract_profitable_stockout_private_firm_scales_hiring_faster():
    firm = FirmAgent(
        firm_id=917,
        good_name="StockoutFood",
        cash_balance=25_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=45.0,
        price=10.0,
        expected_sales_units=110.0,
        production_capacity_units=600.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.target_inventory_weeks = 4.0
    firm.employees = list(range(1, 9))
    firm.actual_wages = {employee_id: 45.0 for employee_id in firm.employees}
    firm.last_revenue = 1_600.0
    firm.last_profit = 450.0

    snapshot = firm.refresh_health_snapshot(sell_through_rate=1.0, category_wage_anchor_p75=50.0)
    default_hire_cap = max(firm.max_hires_per_tick, math.ceil(len(firm.employees) * 0.25))
    plan = firm.plan_production_and_labor(
        last_tick_sales_units=120.0,
        in_warmup=False,
        total_households=200,
        health_snapshot=snapshot,
    )

    assert plan["updated_expected_sales"] >= 180.0
    assert plan["planned_hires_count"] > default_hire_cap


def test_contract_private_wage_ratchet_stops_raising_when_above_category_p75_and_still_unfilled():
    firm = FirmAgent(
        firm_id=918,
        good_name="TightLaborFood",
        cash_balance=18_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=80.0,
        price=9.0,
        expected_sales_units=140.0,
        production_capacity_units=500.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = list(range(1, 7))
    firm.actual_wages = {employee_id: 80.0 for employee_id in firm.employees}
    firm.last_revenue = 1_200.0
    firm.last_profit = 250.0
    firm.last_tick_planned_hires = 3
    firm.last_tick_actual_hires = 0
    firm.unfilled_positions_streak = firm._vacancy_patience_ticks()

    snapshot = firm.refresh_health_snapshot(sell_through_rate=1.0, category_wage_anchor_p75=70.0)
    wage_plan = firm.plan_wage(
        unemployment_rate=0.10,
        unemployment_benefit=30.0,
        in_warmup=False,
        health_snapshot=snapshot,
    )

    assert wage_plan["wage_offer_next"] <= firm.wage_offer


def test_contract_category_newspaper_signal_uses_employer_sector():
    household = HouseholdAgent(household_id=42, skills_level=0.5, age=30, cash_balance=500.0)
    household.employer_id = 10
    household.wage = 45.0
    household.job_search_cooldown = 0

    no_switch_plan = household.plan_labor_supply(
        mean_posted_wage=90.0,
        category_posted_wages={"Food": 46.0, "Housing": 90.0},
        employer_category="Food",
    )
    switch_plan = household.plan_labor_supply(
        mean_posted_wage=46.0,
        category_posted_wages={"Food": 60.0},
        employer_category="Food",
    )

    assert no_switch_plan["job_switching"] is False
    assert switch_plan["job_switching"] is True


def test_contract_private_price_adjustment_scales_with_inventory_severity():
    mild = FirmAgent(
        firm_id=915,
        good_name="MildGlut",
        cash_balance=5_000.0,
        inventory_units=260.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=80.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    severe = FirmAgent(
        firm_id=916,
        good_name="SevereGlut",
        cash_balance=5_000.0,
        inventory_units=480.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=80.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    mild.target_inventory_weeks = 2.0
    severe.target_inventory_weeks = 2.0
    mild.price_adjustment_rate = 0.1
    severe.price_adjustment_rate = 0.1
    mild.min_price = 1.0
    severe.min_price = 1.0

    mild_snapshot = mild.refresh_health_snapshot(sell_through_rate=0.3, category_wage_anchor_p75=45.0)
    severe_snapshot = severe.refresh_health_snapshot(sell_through_rate=0.3, category_wage_anchor_p75=45.0)
    mild_price = mild.plan_pricing(0.3, unemployment_rate=0.1, in_warmup=False, health_snapshot=mild_snapshot)
    severe_price = severe.plan_pricing(0.3, unemployment_rate=0.1, in_warmup=False, health_snapshot=severe_snapshot)

    assert mild_price["price_next"] < mild.price
    assert severe_price["price_next"] < severe.price
    assert severe_price["price_next"] < mild_price["price_next"]


def test_contract_low_cash_three_worker_private_firm_enters_survival_mode_and_stops_hiring():
    firm = FirmAgent(
        firm_id=913,
        good_name="ThreeWorkerStressFirm",
        cash_balance=90.0,
        inventory_units=250.0,
        good_category="Food",
        quality_level=4.0,
        wage_offer=50.0,
        price=6.0,
        expected_sales_units=25.0,
        production_capacity_units=120.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.age_in_ticks = 8
    firm.employees = [1, 2, 3]
    firm.actual_wages = {employee_id: 50.0 for employee_id in firm.employees}
    firm.last_revenue = 40.0
    firm.last_units_sold = 4.0

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=4.0,
        in_warmup=False,
        total_households=20,
    )

    assert firm.survival_mode is True
    assert plan["planned_hires_count"] == 0
    assert plan["planned_production_units"] <= firm.production_capacity_units * 0.1 + 1e-9


@pytest.mark.xfail(
    reason="Known issue: survival mode hard-floors private firms at min_skeleton_workers=3, so a 3-worker distressed firm keeps everyone.",
    strict=True,
)
def test_contract_low_cash_three_worker_private_firm_should_lay_off_on_step():
    households = [
        HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0),
        HouseholdAgent(household_id=2, skills_level=0.5, age=31, cash_balance=1_000.0),
        HouseholdAgent(household_id=3, skills_level=0.5, age=32, cash_balance=1_000.0),
        HouseholdAgent(household_id=4, skills_level=0.5, age=33, cash_balance=1_000.0),
    ]
    for household_id in (1, 2, 3):
        households[household_id - 1].employer_id = 1
        households[household_id - 1].wage = 50.0

    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    firm = FirmAgent(
        firm_id=1,
        good_name="ThreeWorkerStepProbe",
        cash_balance=90.0,
        inventory_units=250.0,
        good_category="Food",
        quality_level=4.0,
        wage_offer=50.0,
        price=6.0,
        expected_sales_units=25.0,
        production_capacity_units=120.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.age_in_ticks = 8
    firm.employees = [1, 2, 3]
    firm.actual_wages = {employee_id: 50.0 for employee_id in firm.employees}
    firm.last_revenue = 40.0
    firm.last_units_sold = 4.0

    economy = Economy(households=households, firms=[firm], government=government)
    economy._apply_random_shocks = lambda: None
    economy.current_tick = economy.warmup_ticks
    economy.in_warmup = False

    economy.step()

    assert firm.survival_mode is True
    assert len(firm.employees) < 3


def test_contract_bailouts_require_explicit_policy_choice():
    households = [
        HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0),
        HouseholdAgent(household_id=2, skills_level=0.5, age=31, cash_balance=1_000.0),
    ]
    government = GovernmentAgent(cash_balance=50_000.0)
    firm = FirmAgent(
        firm_id=912,
        good_name="DistressedFood",
        cash_balance=100.0,
        inventory_units=200.0,
        good_category="Food",
        quality_level=4.5,
        wage_offer=50.0,
        price=8.0,
        expected_sales_units=50.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.age_in_ticks = 6
    firm.employees = [10, 11, 12]
    firm.actual_wages = {employee_id: 50.0 for employee_id in firm.employees}
    firm.last_revenue = 20.0

    economy = Economy(households=households, firms=[firm], government=government)

    economy._execute_bailouts()
    assert firm.government_loan_principal == pytest.approx(0.0)

    government.set_lever("bailout_policy", "all")
    government.set_lever("bailout_budget", 5_000)
    economy._execute_bailouts()

    assert firm.government_loan_principal > 0.0
    assert firm.government_loan_principal <= 5_000.0
    assert government.bailout_cycle_disbursed > 0.0


def test_contract_fiscal_pressure_clamps_surplus_floor_and_can_trigger_penalty(tiny_economy_factory):
    economy = tiny_economy_factory(
        num_households=20,
        num_firms_per_category=1,
        include_healthcare=False,
        baseline_firms=True,
        disable_shocks=True,
        seed=991,
        government_cash=80_000.0,
    )

    economy.last_tick_revenue = {1: 1_000.0}
    for _ in range(20):
        economy._update_budget_pressure(revenue=2_000.0, spending=0.0)

    assert economy.government.fiscal_pressure == pytest.approx(-0.15)

    for _ in range(5):
        economy._update_budget_pressure(revenue=0.0, spending=1_000.0)

    assert economy.government.fiscal_pressure > 0.05
    assert economy.government.spending_efficiency < 1.0


def test_contract_public_works_capitalization_counts_as_treasury_spending(tiny_economy_factory):
    economy = tiny_economy_factory(
        num_households=20,
        num_firms_per_category=1,
        include_healthcare=False,
        baseline_firms=True,
        disable_shocks=True,
        seed=992,
        government_cash=300_000.0,
    )

    economy.government.set_lever("public_works", "on")
    economy.step()
    metrics = economy.get_economic_metrics()

    assert economy.last_tick_gov_public_works_capitalization > 0.0
    assert metrics["gov_public_works_capitalization_this_tick"] == pytest.approx(
        economy.last_tick_gov_public_works_capitalization
    )
    assert economy.government.last_tick_spending >= economy.last_tick_gov_public_works_capitalization


def test_contract_bond_purchases_count_as_government_spending(tiny_economy_factory):
    economy = tiny_economy_factory(
        num_households=20,
        num_firms_per_category=1,
        include_healthcare=False,
        baseline_firms=True,
        disable_shocks=True,
        seed=993,
        government_cash=120_000.0,
    )

    economy.step()
    metrics = economy.get_economic_metrics()

    assert economy.last_tick_gov_bond_purchases > 0.0
    assert metrics["gov_bond_purchases_this_tick"] == pytest.approx(
        economy.last_tick_gov_bond_purchases
    )
    assert economy.government.last_tick_spending >= economy.last_tick_gov_bond_purchases
