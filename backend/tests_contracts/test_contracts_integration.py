import math

import numpy as np
import pytest

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from tools.runners.run_large_simulation import create_large_economy


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


def _make_production_governor_firm(**overrides):
    base = {
        "firm_id": 930,
        "good_name": "GovernorFood",
        "cash_balance": 100_000.0,
        "inventory_units": 0.0,
        "good_category": "Food",
        "quality_level": 5.0,
        "wage_offer": 35.0,
        "price": 10.0,
        "expected_sales_units": 5.0,
        "production_capacity_units": 500.0,
        "productivity_per_worker": 20.0,
        "personality": "moderate",
        "is_baseline": False,
    }
    base.update(overrides)
    firm = FirmAgent(**base)
    firm.sales_expectation_alpha = 1.0
    firm.target_inventory_multiplier = 2.0
    firm.target_inventory_weeks = 2.0
    firm.units_per_worker = 50.0
    firm.capital_stock = 100.0
    firm.employees = [1, 2, 3]
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}
    firm.last_revenue = 1_000.0
    firm.last_profit = 500.0
    firm.revenue_ema = 1_000.0
    firm.profit_ema = 500.0
    for key, value in overrides.items():
        setattr(firm, key, value)
    return firm


def _make_service_flow_firm(**overrides):
    base = {
        "firm_id": 950,
        "good_name": "ServiceFlow",
        "cash_balance": 100_000.0,
        "inventory_units": 0.0,
        "good_category": "Services",
        "quality_level": 5.0,
        "wage_offer": 35.0,
        "price": 10.0,
        "expected_sales_units": 100.0,
        "production_capacity_units": 5.0,
        "productivity_per_worker": 7.0,
        "personality": "moderate",
        "is_baseline": False,
    }
    base.update(overrides)
    firm = FirmAgent(**base)
    firm.units_per_worker = CONFIG.firms.services_units_per_worker_range[1]
    firm.productivity_per_worker = firm.units_per_worker
    firm.capital_stock = 10_000.0
    firm.employees = list(range(1, 7))
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}
    firm.sales_expectation_alpha = 1.0
    firm.target_inventory_multiplier = 2.0
    firm.target_inventory_weeks = 2.0
    firm.last_revenue = 1_000.0
    firm.last_profit = 500.0
    firm.revenue_ema = 1_000.0
    firm.profit_ema = 500.0
    for key, value in overrides.items():
        setattr(firm, key, value)
    return firm


def test_contract_production_governor_stops_output_above_inventory_buffer():
    firm = _make_production_governor_firm(inventory_units=20.0)

    plan = firm.plan_production_and_labor(last_tick_sales_units=5.0)

    assert plan["planned_production_units"] == pytest.approx(0.0)
    assert firm.decision_diagnostics["production_governor_active"] is True
    assert firm.decision_diagnostics["production_governor_inventory_deficit"] == pytest.approx(-10.0)


def test_contract_production_governor_fills_only_inventory_deficit():
    firm = _make_production_governor_firm(inventory_units=7.0)

    plan = firm.plan_production_and_labor(last_tick_sales_units=5.0)

    assert plan["planned_production_units"] == pytest.approx(3.0)
    assert firm.decision_diagnostics["production_governor_target_inventory"] == pytest.approx(10.0)


def test_contract_production_governor_respects_capacity_limits():
    firm = _make_production_governor_firm(
        expected_sales_units=100.0,
        inventory_units=0.0,
        production_capacity_units=12.0,
    )

    plan = firm.plan_production_and_labor(last_tick_sales_units=100.0)

    effective_workers = (
        len(firm.employees)
        + plan["planned_hires_count"]
        - len(plan["planned_layoffs_ids"])
    )
    assert plan["planned_production_units"] <= firm.production_capacity_units
    assert plan["planned_production_units"] <= firm._capacity_for_workers(effective_workers) + 1e-9


def test_contract_production_governor_uses_final_inventory_cut_staffing():
    firm = _make_production_governor_firm(
        firm_id=931,
        expected_sales_units=20.0,
        inventory_units=50.0,
        price=0.1,
        wage_offer=100.0,
        production_capacity_units=10_000.0,
    )
    firm.target_inventory_multiplier = 10.0
    firm.employees = list(range(1, 21))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.max_fires_per_tick = 20
    firm.last_revenue = 5_000.0
    firm.last_profit = 3_000.0
    firm.revenue_ema = 5_000.0
    firm.profit_ema = 3_000.0

    plan = firm.plan_production_and_labor(last_tick_sales_units=20.0)

    effective_workers = (
        len(firm.employees)
        + plan["planned_hires_count"]
        - len(plan["planned_layoffs_ids"])
    )
    assert len(plan["planned_layoffs_ids"]) > 0
    assert plan["planned_production_units"] <= firm._capacity_for_workers(effective_workers) + 1e-9
    assert firm.decision_diagnostics["production_governor_max_possible_production"] == pytest.approx(
        min(firm._capacity_for_workers(effective_workers), firm.production_capacity_units)
    )


def test_contract_production_governor_skips_housing_and_healthcare():
    housing = _make_production_governor_firm(
        firm_id=932,
        good_name="GovernorHousing",
        good_category="Housing",
        inventory_units=20.0,
        production_capacity_units=20.0,
        max_rental_units=5,
    )
    housing.employees = [1, 2, 3, 4, 5]
    housing.actual_wages = {employee_id: 35.0 for employee_id in housing.employees}

    healthcare = _make_production_governor_firm(
        firm_id=933,
        good_name="GovernorHealthcare",
        good_category="Healthcare",
        inventory_units=0.0,
    )

    housing_plan = housing.plan_production_and_labor(last_tick_sales_units=5.0)
    healthcare_plan = healthcare.plan_production_and_labor(last_tick_sales_units=5.0)

    assert housing_plan["planned_production_units"] == pytest.approx(0.0)
    assert "production_governor_active" not in housing.decision_diagnostics
    assert healthcare_plan["planned_production_units"] == pytest.approx(0.0)
    assert "production_governor_active" not in healthcare.decision_diagnostics


def test_contract_services_capacity_obeys_units_per_worker_range():
    firm = _make_service_flow_firm(expected_sales_units=500.0, production_capacity_units=5.0)

    plan = firm.plan_production_and_labor(last_tick_sales_units=500.0, total_households=100)

    worker_slots = int(firm.production_capacity_units)
    max_units = worker_slots * CONFIG.firms.services_units_per_worker_range[1]
    assert firm.decision_diagnostics["services_target_workers"] == worker_slots
    assert plan["planned_hires_count"] == 0
    assert plan["planned_production_units"] <= max_units + 1e-9
    assert plan["planned_production_units"] > firm.production_capacity_units

    firm.apply_production_and_costs({"realized_production_units": 199.0, "other_variable_costs": 0.0})
    assert firm.last_units_produced <= len(firm.employees) * CONFIG.firms.services_units_per_worker_range[1] + 1e-9
    assert firm.inventory_units == pytest.approx(0.0)


def test_contract_services_capacity_units_are_employee_slots():
    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.employees = [1, 2]
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}

    plan = firm.plan_production_and_labor(last_tick_sales_units=0.0, total_households=100)

    assert firm.decision_diagnostics["services_target_workers"] == 5
    assert plan["planned_hires_count"] == 3
    assert plan["planned_production_units"] == pytest.approx(
        5 * CONFIG.firms.services_units_per_worker_range[1]
    )
    assert plan["planned_production_units"] > firm.production_capacity_units


def test_contract_large_runner_initializes_services_with_five_slots():
    economy = create_large_economy(num_households=100, num_firms_per_category=2)
    service_firms = [
        firm for firm in list(economy.firms) + list(economy.queued_firms)
        if firm.good_category == "Services"
    ]

    assert service_firms
    assert all(firm.production_capacity_units == pytest.approx(5.0) for firm in service_firms)
    assert all(firm.production_capacity_units not in {60_000.0, 100_000.0} for firm in service_firms)
    assert all(firm.inventory_units == pytest.approx(0.0) for firm in service_firms)


def test_contract_services_planned_hiring_stays_population_scaled():
    economy = create_large_economy(num_households=100, num_firms_per_category=2)
    service_firms = [
        firm for firm in list(economy.firms) + list(economy.queued_firms)
        if firm.good_category == "Services"
    ]

    assert service_firms
    for firm in service_firms:
        plan = firm.plan_production_and_labor(last_tick_sales_units=0.0, total_households=100)
        assert plan["planned_hires_count"] <= 5
        assert plan["planned_hires_count"] < 100


def test_contract_services_inventory_expires_after_sales():
    firm = _make_service_flow_firm(inventory_units=20.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}

    firm.apply_production_and_costs({"realized_production_units": 30.0, "other_variable_costs": 0.0})
    assert firm.last_units_produced == pytest.approx(30.0)
    assert firm.inventory_units == pytest.approx(0.0)

    firm.apply_sales_and_profit({"units_sold": 10.0, "revenue": 100.0, "profit_taxes_paid": 0.0})

    assert firm.inventory_units == pytest.approx(0.0)


def test_contract_services_market_inventory_is_current_tick_capacity_only():
    households = [
        HouseholdAgent(household_id=i, skills_level=0.5, age=30, cash_balance=1_000.0)
        for i in range(1, 11)
    ]
    firm = _make_service_flow_firm(inventory_units=200.0)
    firm.employees = list(range(1, 7))
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}
    firm.apply_production_and_costs({"realized_production_units": 30.0, "other_variable_costs": 0.0})
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=households, firms=[firm], government=government)
    plans = {
        household.household_id: {"planned_purchases": {firm.firm_id: 100.0}}
        for household in households
    }

    _, sales = economy._clear_goods_market(plans, [firm])

    assert firm.inventory_units == pytest.approx(0.0)
    assert sales[firm.firm_id]["units_sold"] == pytest.approx(30.0)
    assert economy.services_unmet_demand == pytest.approx(970.0)


def test_contract_economy_services_realized_production_keeps_worker_cap():
    households = [
        HouseholdAgent(household_id=i, skills_level=1.0, age=30, cash_balance=1_000.0)
        for i in range(1, 7)
    ]
    firm = _make_service_flow_firm()
    firm.employees = [household.household_id for household in households]
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}
    for household in households:
        household.employer_id = firm.firm_id
        household.wage = firm.wage_offer
        household.happiness = 1.0
        household.morale = 1.0
        household.health = 1.0
        household.category_experience[firm.good_category] = 52 * 20
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    government.infrastructure_productivity_multiplier = 10.0
    economy = Economy(households=households, firms=[firm], government=government)

    realized = economy._calculate_experience_adjusted_production(firm, planned_production_units=199.0)

    max_units = int(firm.production_capacity_units) * CONFIG.firms.services_units_per_worker_range[1]
    assert realized == pytest.approx(max_units)


def test_contract_economy_services_realized_production_keeps_worker_floor():
    households = [
        HouseholdAgent(household_id=i, skills_level=0.0, age=30, cash_balance=1_000.0)
        for i in range(1, 7)
    ]
    firm = _make_service_flow_firm()
    firm.employees = [household.household_id for household in households]
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}
    for household in households:
        household.employer_id = firm.firm_id
        household.wage = firm.wage_offer
        household.happiness = 0.0
        household.morale = 0.0
        household.health = 0.0
        household.category_experience[firm.good_category] = 0
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=households, firms=[firm], government=government)

    realized = economy._calculate_experience_adjusted_production(firm, planned_production_units=199.0)

    min_units = int(firm.production_capacity_units) * CONFIG.firms.services_units_per_worker_range[0]
    assert realized == pytest.approx(min_units)


def test_contract_services_skip_inventory_burn_mode_and_governor():
    firm = _make_service_flow_firm(
        expected_sales_units=10.0,
        inventory_units=1_000.0,
        production_capacity_units=5.0,
    )
    firm.high_inventory_streak = 20
    firm.low_inventory_streak = 20
    firm.burn_mode = True
    firm.decision_diagnostics["production_governor_active"] = True

    plan = firm.plan_production_and_labor(last_tick_sales_units=1.0)

    assert plan["planned_production_units"] <= 5.0 * CONFIG.firms.services_units_per_worker_range[1]
    assert plan["planned_production_units"] > firm.production_capacity_units
    assert firm.inventory_units == pytest.approx(0.0)
    assert firm.burn_mode is False
    assert "production_governor_active" not in firm.decision_diagnostics


def test_contract_services_pricing_uses_labor_capacity_floor():
    firm = _make_service_flow_firm(production_capacity_units=42.0)
    firm.wage_offer = 60.0
    firm.actual_wages = {employee_id: 60.0 for employee_id in firm.employees}
    firm.last_units_produced = 30.0
    firm.last_units_sold = 10.0

    price_plan = firm.plan_pricing(sell_through_rate=0.3, unemployment_rate=0.1, in_warmup=False)

    break_even = (len(firm.employees) * 60.0) / 30.0
    assert price_plan["price_next"] >= break_even
    assert firm.decision_diagnostics["pricing_reason"] == "services_labor_capacity"


def test_contract_services_pricing_low_capacity_floor_cases():
    low_capacity_firm = _make_service_flow_firm(price=1.0, production_capacity_units=2.0)
    low_capacity_firm.employees = [1, 2]
    low_capacity_firm.wage_offer = 40.0
    low_capacity_firm.actual_wages = {1: 40.0, 2: 40.0}
    low_capacity_firm.last_units_produced = 2.0
    low_capacity_firm.markup = 0.0

    low_capacity_plan = low_capacity_firm.plan_pricing(
        sell_through_rate=1.0,
        unemployment_rate=0.1,
        in_warmup=False,
    )

    assert low_capacity_plan["price_next"] >= 40.0

    high_capacity_firm = _make_service_flow_firm(price=1.0, production_capacity_units=7.0)
    high_capacity_firm.employees = [1]
    high_capacity_firm.wage_offer = 42.0
    high_capacity_firm.actual_wages = {1: 42.0}
    high_capacity_firm.last_units_produced = 7.0
    high_capacity_firm.markup = 0.0

    high_capacity_plan = high_capacity_firm.plan_pricing(
        sell_through_rate=1.0,
        unemployment_rate=0.1,
        in_warmup=False,
    )

    assert high_capacity_plan["price_next"] >= 6.0


def test_contract_services_market_clearing_uses_labor_floor_price():
    households = [
        HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0)
    ]
    firm = _make_service_flow_firm(price=1.0, production_capacity_units=2.0)
    firm.employees = [1, 2]
    firm.wage_offer = 40.0
    firm.actual_wages = {1: 40.0, 2: 40.0}
    firm.last_units_produced = 2.0
    firm.markup = 0.0
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=households, firms=[firm], government=government)
    plans = {1: {"planned_purchases": {firm.firm_id: 2.0}}}

    _, sales = economy._clear_goods_market(plans, [firm])

    assert sales[firm.firm_id]["units_sold"] == pytest.approx(2.0)
    assert sales[firm.firm_id]["revenue"] / sales[firm.firm_id]["units_sold"] >= 40.0
    assert firm.price >= 40.0


def test_contract_services_full_utilization_requests_slot_upgrade_after_five_ticks():
    from types import SimpleNamespace

    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.employees = list(range(1, 6))
    firm.actual_wages = {employee_id: 45.0 for employee_id in firm.employees}
    firm.cash_runway_ticks = math.inf
    firm.profit_ema = 200.0
    firm.last_profit = 200.0

    fake_econ = SimpleNamespace(services_unmet_demand_by_firm={firm.firm_id: 3.0})

    for tick in range(4):
        firm.last_units_produced = 10.0
        firm.last_units_sold = 9.5
        firm.last_sell_through_rate = 0.95
        assert firm.consider_service_infrastructure_upgrade(economy=fake_econ) is False
        assert firm.needs_service_infrastructure_loan is False
        assert firm.service_full_utilization_streak == tick + 1

    firm.last_units_produced = 10.0
    firm.last_units_sold = 9.5
    firm.last_sell_through_rate = 0.95
    assert firm.consider_service_infrastructure_upgrade(economy=fake_econ) is True
    assert firm.needs_service_infrastructure_loan is True
    assert firm.service_infrastructure_loan_amount == pytest.approx(7_000.0)


def test_contract_services_upgrade_not_requested_below_utilization_threshold():
    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.cash_runway_ticks = math.inf

    for _ in range(5):
        firm.last_units_produced = 10.0
        firm.last_units_sold = 9.0
        firm.last_sell_through_rate = 0.90
        assert firm.consider_service_infrastructure_upgrade() is False

    assert firm.service_full_utilization_streak == 0
    assert firm.needs_service_infrastructure_loan is False


def test_contract_services_upgrade_not_requested_in_survival_mode():
    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.cash_runway_ticks = math.inf
    firm.survival_mode = True

    for _ in range(5):
        firm.last_units_produced = 10.0
        firm.last_units_sold = 10.0
        firm.last_sell_through_rate = 1.0
        assert firm.consider_service_infrastructure_upgrade() is False

    assert firm.service_full_utilization_streak == 5
    assert firm.needs_service_infrastructure_loan is False


def test_contract_services_infrastructure_loan_adds_employee_slots_only():
    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.employees = list(range(1, 6))
    firm.actual_wages = {employee_id: 45.0 for employee_id in firm.employees}
    firm.cash_balance = 10_000.0
    firm.last_revenue = 1_000.0
    firm.revenue_ema = 1_000.0
    firm.last_units_produced = 16.0
    firm.needs_service_infrastructure_loan = True
    firm.service_infrastructure_loan_amount = 7_000.0
    bank = BankAgent(cash_reserves=100_000.0)
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=[], firms=[firm], government=government, bank=bank)
    before_output = firm.last_units_produced
    before_misc_revenue = economy.misc_firm_revenue

    economy._offer_service_infrastructure_loans()

    assert firm.production_capacity_units == pytest.approx(6.0)
    assert firm.last_units_produced == pytest.approx(before_output)
    assert firm.inventory_units == pytest.approx(0.0)
    assert firm.service_infrastructure_loan_remaining > 0.0
    assert firm.service_infrastructure_loan_payment_per_tick > 0.0
    assert bank.last_tick_new_loans == pytest.approx(7_000.0)
    assert economy.misc_firm_revenue > before_misc_revenue


def test_contract_services_debt_service_is_included_in_price_floor():
    firm = _make_service_flow_firm(price=1.0, production_capacity_units=5.0)
    firm.employees = [1, 2]
    firm.wage_offer = 40.0
    firm.actual_wages = {1: 40.0, 2: 40.0}
    firm.last_units_produced = 10.0
    firm.service_infrastructure_loan_payment_per_tick = 20.0
    firm.markup = 0.0

    price_plan = firm.plan_pricing(sell_through_rate=1.0, unemployment_rate=0.1, in_warmup=False)

    assert price_plan["price_next"] >= 10.0
    assert firm.decision_diagnostics["service_debt_service_for_pricing"] == pytest.approx(20.0)

    household = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0)
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=[household], firms=[firm], government=government)
    plans = {household.household_id: {"planned_purchases": {firm.firm_id: 10.0}}}

    _, sales = economy._clear_goods_market(plans, [firm])

    assert sales[firm.firm_id]["units_sold"] == pytest.approx(10.0)
    assert sales[firm.firm_id]["revenue"] / sales[firm.firm_id]["units_sold"] >= 10.0


def test_contract_services_weak_demand_wage_cut_is_fixed_amount():
    firm = _make_service_flow_firm(wage_offer=45.0, production_capacity_units=5.0)
    firm.last_units_produced = 10.0
    firm.last_units_sold = 7.0
    firm.last_profit = -1.0

    first = firm.plan_wage(in_warmup=False, minimum_wage_floor=36.0)
    assert first["wage_offer_next"] == pytest.approx(45.0)
    assert firm.service_weak_demand_streak == 1

    firm.last_profit = -2.0
    second = firm.plan_wage(in_warmup=False, minimum_wage_floor=36.0)
    assert second["wage_offer_next"] == pytest.approx(42.0)
    assert firm.service_weak_demand_streak == 2


def test_contract_services_weak_demand_wage_cut_respects_minimum_wage():
    firm = _make_service_flow_firm(wage_offer=37.0, production_capacity_units=5.0)
    firm.service_weak_demand_streak = 1
    firm.last_units_produced = 10.0
    firm.last_units_sold = 7.0
    firm.last_profit = -1.0

    wage_plan = firm.plan_wage(in_warmup=False, minimum_wage_floor=36.0)

    assert wage_plan["wage_offer_next"] == pytest.approx(36.0)


def test_contract_services_weak_demand_streak_resets_on_profit_or_strong_utilization():
    firm = _make_service_flow_firm(wage_offer=45.0, production_capacity_units=5.0)
    firm.service_weak_demand_streak = 2
    firm.last_units_produced = 10.0
    firm.last_units_sold = 7.0
    firm.last_profit = 1.0

    profitable_plan = firm.plan_wage(in_warmup=False, minimum_wage_floor=36.0)

    assert firm.service_weak_demand_streak == 0
    assert profitable_plan["wage_offer_next"] == pytest.approx(45.0)

    firm.service_weak_demand_streak = 2
    firm.last_units_produced = 10.0
    firm.last_units_sold = 9.0
    firm.last_profit = -1.0

    strong_plan = firm.plan_wage(in_warmup=False, minimum_wage_floor=36.0)

    assert firm.service_weak_demand_streak == 0
    assert strong_plan["wage_offer_next"] == pytest.approx(45.0)


def test_contract_services_weak_demand_headcount_last_resort_only_at_minimum_wage():
    firm = _make_service_flow_firm(wage_offer=36.0, production_capacity_units=5.0)
    firm.employees = [1, 2, 3, 4, 5]
    firm.actual_wages = {employee_id: 36.0 for employee_id in firm.employees}
    firm.service_weak_demand_streak = 4
    firm.cash_runway_ticks = math.inf
    firm.last_units_produced = 10.0
    firm.last_units_sold = 7.0
    firm.last_profit = -1.0

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=7.0,
        in_warmup=False,
        total_households=100,
        minimum_wage_floor=36.0,
    )

    assert firm.service_weak_demand_streak == 5
    assert len(plan["planned_layoffs_ids"]) == 1
    assert plan["planned_hires_count"] == 0

    above_minimum = _make_service_flow_firm(wage_offer=39.0, production_capacity_units=5.0)
    above_minimum.employees = [1, 2, 3, 4, 5]
    above_minimum.actual_wages = {employee_id: 39.0 for employee_id in above_minimum.employees}
    above_minimum.service_weak_demand_streak = 4
    above_minimum.cash_runway_ticks = math.inf
    above_minimum.last_units_produced = 10.0
    above_minimum.last_units_sold = 7.0
    above_minimum.last_profit = -1.0

    above_minimum_plan = above_minimum.plan_production_and_labor(
        last_tick_sales_units=7.0,
        in_warmup=False,
        total_households=100,
        minimum_wage_floor=36.0,
    )

    assert above_minimum.service_weak_demand_streak == 5
    assert above_minimum_plan["planned_layoffs_ids"] == []


def test_contract_household_services_purchase_is_direct_consumption():
    household = HouseholdAgent(household_id=42, skills_level=0.5, age=30, cash_balance=1_000.0)
    firm = _make_service_flow_firm()
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=[household], firms=[firm], government=government)

    economy._batch_apply_household_updates(
        transfer_plan={household.household_id: 0.0},
        wage_taxes={household.household_id: 0.0},
        per_household_purchases={household.household_id: {firm.good_name: (5.0, 2.0)}},
        good_category_lookup={firm.good_name: "services"},
    )

    assert household.services_consumed_this_tick == pytest.approx(5.0)
    assert household.last_services_units == pytest.approx(5.0)
    assert firm.good_name not in household.goods_inventory


def test_contract_food_inventory_still_accumulates_and_subtracts_sales():
    firm = _make_production_governor_firm(inventory_units=20.0)
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}

    firm.apply_production_and_costs({"realized_production_units": 30.0, "other_variable_costs": 0.0})
    assert firm.inventory_units == pytest.approx(50.0)

    firm.apply_sales_and_profit({"units_sold": 10.0, "revenue": 100.0, "profit_taxes_paid": 0.0})

    assert firm.inventory_units == pytest.approx(40.0)


def test_contract_healthcare_inventory_remains_non_storable():
    firm = _make_production_governor_firm(
        firm_id=951,
        good_name="HealthcareFlow",
        good_category="Healthcare",
        inventory_units=50.0,
    )
    firm.employees = [1, 2]
    firm.actual_wages = {employee_id: firm.wage_offer for employee_id in firm.employees}

    firm.apply_production_and_costs({"realized_production_units": 30.0, "other_variable_costs": 0.0})
    assert firm.inventory_units == pytest.approx(0.0)

    firm.apply_sales_and_profit({"units_sold": 10.0, "revenue": 100.0, "profit_taxes_paid": 0.0})

    assert firm.inventory_units == pytest.approx(0.0)


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

    # Diagnostics dict should be populated (labor system ran end-of-run).
    # Active hiring during the run is already asserted via post_warmup_hires > 0.
    diagnostics = economy.last_labor_diagnostics
    assert isinstance(diagnostics, dict) and len(diagnostics) > 0


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
        unemployment_short_ma=0.10,  # above NAIRU → Phillips Curve labor surplus path
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


def test_contract_pricing_cost_floor_uses_stable_throughput_for_tiny_production():
    firm = FirmAgent(
        firm_id=934,
        good_name="TinyProductionFood",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 1.0
    firm.capital_stock = 100.0
    firm.last_units_produced = 0.5
    firm.last_units_sold = 60.0  # sales_ratio=0.60 >= 0.50 → full_cost_floor_allowed=True

    price_plan = firm.plan_pricing(sell_through_rate=0.5, unemployment_rate=0.1, in_warmup=False)

    fixed_depreciation = (
        firm.capital_stock
        * CONFIG.firms.capital_depreciation_rate
        * CONFIG.firms.capital_cost_per_unit
    )
    expected_floor = (firm.unit_cost + fixed_depreciation / firm.expected_sales_units) * 1.05
    assert firm.decision_diagnostics["pricing_depreciation_denominator"] == pytest.approx(100.0)
    assert firm.decision_diagnostics["pricing_cost_floor"] == pytest.approx(expected_floor)
    assert price_plan["price_next"] == pytest.approx(expected_floor)
    assert price_plan["price_next"] < 50.0


def test_contract_pricing_cost_floor_cannot_raise_price_without_throughput():
    firm = FirmAgent(
        firm_id=935,
        good_name="NoThroughputFood",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=0.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 1.0
    firm.capital_stock = 100.0
    firm.last_units_produced = 0.5
    firm.last_units_sold = 0.0
    firm.expected_sales_units = 0.0

    price_plan = firm.plan_pricing(sell_through_rate=0.5, unemployment_rate=0.1, in_warmup=False)

    assert firm.decision_diagnostics["pricing_depreciation_denominator"] == pytest.approx(1.0)
    assert firm.decision_diagnostics["pricing_full_cost_floor_allowed"] == False
    assert firm.decision_diagnostics["pricing_cost_floor_applied"] == False


def test_contract_pricing_variable_floor_always_applies_even_when_market_rejects():
    """Variable cost floor (unit_cost * 1.05) always sets a minimum price, even with market rejection."""
    firm = FirmAgent(
        firm_id=936,
        good_name="RejectedFood",
        cash_balance=10_000.0,
        inventory_units=500.0,  # large inventory → inventory_available=True
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=100.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 0.01
    firm.last_units_produced = 10.0
    firm.last_units_sold = 10.0      # sales_ratio=0.10 < 0.35
    firm.last_revenue = 0.5          # revenue_ratio << 0.95

    price_plan = firm.plan_pricing(sell_through_rate=0.1, unemployment_rate=0.1, in_warmup=False)

    expected_variable_floor = firm.unit_cost * 1.05
    assert firm.decision_diagnostics["pricing_market_rejected"] == True
    assert firm.decision_diagnostics["pricing_full_cost_floor_allowed"] == False
    assert price_plan["price_next"] >= expected_variable_floor - 1e-9


def test_contract_pricing_full_floor_blocked_when_market_rejects():
    """Full depreciation floor NOT applied when market_rejected is True."""
    firm = FirmAgent(
        firm_id=937,
        good_name="RejectedFood2",
        cash_balance=10_000.0,
        inventory_units=500.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=50.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 0.01
    firm.capital_stock = 1000.0
    firm.last_units_produced = 10.0
    firm.last_units_sold = 10.0   # sales_ratio=0.10 < 0.35
    firm.last_revenue = 0.5        # revenue_ratio << 0.95

    price_plan = firm.plan_pricing(sell_through_rate=0.1, unemployment_rate=0.1, in_warmup=False)

    assert firm.decision_diagnostics["pricing_market_rejected"] == True
    assert firm.decision_diagnostics["pricing_full_cost_floor_allowed"] == False
    assert firm.decision_diagnostics["pricing_cost_floor_applied"] == False
    # Price must NOT be raised to full_cost_floor (which would be far above 50 with capital_stock=1000)
    assert price_plan["price_next"] < firm.decision_diagnostics["pricing_full_cost_floor"]


def test_contract_pricing_full_floor_applies_on_healthy_demand():
    """Full depreciation floor applied when sales_ratio >= 0.50 and no rejection streak."""
    firm = FirmAgent(
        firm_id=938,
        good_name="HealthyFood",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=5.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 0.01
    firm.capital_stock = 100.0
    firm.last_units_produced = 50.0
    firm.last_units_sold = 60.0   # sales_ratio=0.60 >= 0.50

    price_plan = firm.plan_pricing(sell_through_rate=0.9, unemployment_rate=0.1, in_warmup=False)

    assert firm.decision_diagnostics["pricing_market_rejected"] == False
    assert firm.decision_diagnostics["pricing_full_cost_floor_allowed"] == True
    assert price_plan["price_next"] >= firm.decision_diagnostics["pricing_full_cost_floor"] - 1e-9


def test_contract_pricing_rejection_streak_decays_after_recovery():
    """Streak initialized at 1 → decays to 0 when next tick is not market_rejected."""
    firm = FirmAgent(
        firm_id=939,
        good_name="RecoveringFood",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.unit_cost = 5.0
    firm.pricing_operating_unit_cost = 5.0
    firm.min_price = 0.01
    firm.capital_stock = 10.0
    firm.last_units_produced = 50.0
    firm.last_units_sold = 60.0   # sales_ratio=0.60 → not rejected
    firm.pricing_rejection_streak = 1  # pre-existing streak

    firm.plan_pricing(sell_through_rate=0.7, unemployment_rate=0.1, in_warmup=False)

    assert firm.decision_diagnostics["pricing_market_rejected"] == False
    assert firm.decision_diagnostics["pricing_rejection_streak"] == 0


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


# ---------------------------------------------------------------------------
# Task 3b: pricing_operating_unit_cost stable-throughput floor
# ---------------------------------------------------------------------------

def test_contract_pricing_operating_cost_stable_throughput_prevents_spike():
    """End-to-end: tiny realized production must NOT explode pricing_operating_unit_cost.

    Firm has wage_bill=400 but only produces 0.5 units.
    Without stable throughput, unit_cost = 400/0.5 = 800, floor = 840.
    With stable throughput = max(0.5, 100, 50, 1) = 100,
    pricing_operating_unit_cost = 400/100 = 4.0, floor = 4.2.
    """
    firm = FirmAgent(
        firm_id=940,
        good_name="TinyProdSpike",
        cash_balance=50_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    firm.actual_wages = {eid: 40.0 for eid in firm.employees}  # wage_bill = 400
    firm.last_units_sold = 50.0
    firm.capital_stock = 0.0  # no depreciation to isolate the test

    firm.apply_production_and_costs({"realized_production_units": 0.5, "other_variable_costs": 0.0})

    # stable_throughput = max(0.5, 100.0, 50.0, 1.0) = 100.0
    assert firm.pricing_operating_unit_cost == pytest.approx(400.0 / 100.0, rel=1e-6)
    # accounting unit_cost still explodes (that's intentional — different purpose)
    assert firm.unit_cost == pytest.approx(400.0 / 0.5, rel=1e-6)


def test_contract_pricing_floor_uses_operating_cost_not_accounting_cost():
    """End-to-end: plan_pricing variable floor = pricing_operating_unit_cost*1.05, not unit_cost*1.05.

    With tiny production, unit_cost explodes to 800 but pricing_operating_unit_cost stays at 4.0.
    Variable floor must be ~4.2, not ~840.
    """
    firm = FirmAgent(
        firm_id=941,
        good_name="FloorSeparation",
        cash_balance=50_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=300.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    firm.actual_wages = {eid: 40.0 for eid in firm.employees}  # wage_bill = 400
    firm.last_units_sold = 50.0
    firm.capital_stock = 0.0
    firm.min_price = 0.01
    firm.last_revenue = 1000.0  # avoid market_rejected

    firm.apply_production_and_costs({"realized_production_units": 0.5, "other_variable_costs": 0.0})
    price_plan = firm.plan_pricing(sell_through_rate=0.6, unemployment_rate=0.1, in_warmup=False)

    expected_var_floor = (400.0 / 100.0) * 1.05  # = 4.2
    assert firm.decision_diagnostics["pricing_variable_cost_floor"] == pytest.approx(expected_var_floor, rel=1e-6)
    # Price must not spike to accounting-based floor (~840)
    assert price_plan["price_next"] < 50.0


def test_contract_pricing_operating_unit_cost_no_employees_uses_floor():
    """Firm with zero employees has zero wage bill; pricing_operating_unit_cost = 0/max(...)=0."""
    firm = FirmAgent(
        firm_id=942,
        good_name="ZeroWageFirm",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=30.0,
        price=10.0,
        expected_sales_units=50.0,
        production_capacity_units=200.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = []
    firm.capital_stock = 0.0

    firm.apply_production_and_costs({"realized_production_units": 10.0, "other_variable_costs": 0.0})

    assert firm.pricing_operating_unit_cost == pytest.approx(0.0, abs=1e-9)


def test_contract_pricing_operating_cost_diagnostics_present():
    """plan_pricing diagnostics include all 3 new pricing_operating_* keys."""
    firm = FirmAgent(
        firm_id=943,
        good_name="DiagnosticsFirm",
        cash_balance=10_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=30.0,
        price=10.0,
        expected_sales_units=80.0,
        production_capacity_units=200.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.pricing_operating_unit_cost = 3.0
    firm.unit_cost = 5.0
    firm.min_price = 0.01
    firm.last_units_produced = 40.0
    firm.last_units_sold = 50.0
    firm.last_revenue = 500.0

    firm.plan_pricing(sell_through_rate=0.7, unemployment_rate=0.1, in_warmup=False)

    diag = firm.decision_diagnostics
    assert "pricing_operating_unit_cost" in diag
    assert "pricing_stable_cost_throughput" in diag
    assert "pricing_accounting_unit_cost" in diag
    assert diag["pricing_operating_unit_cost"] == pytest.approx(3.0, rel=1e-6)
    assert diag["pricing_accounting_unit_cost"] == pytest.approx(5.0, rel=1e-6)


# --- Services per-firm unmet demand & upgrade gating ----------------------


def _make_services_clearing_economy(firm_capacity: float = 2.0):
    """Build a tiny economy with one Services firm + one household for clearing tests."""
    households = [
        HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=10_000.0)
    ]
    firm = _make_service_flow_firm(production_capacity_units=firm_capacity)
    firm.employees = [101, 102]
    firm.actual_wages = {101: 40.0, 102: 40.0}
    firm.last_units_produced = firm_capacity
    firm.markup = 0.0
    government = GovernmentAgent(
        cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0
    )
    economy = Economy(households=households, firms=[firm], government=government)
    return economy, firm, households[0]


def test_contract_services_unmet_demand_aggregate_recorded_when_capacity_insufficient():
    economy, firm, _ = _make_services_clearing_economy(firm_capacity=2.0)
    plans = {1: {"planned_purchases": {firm.firm_id: 5.0}}}

    economy._clear_goods_market(plans, [firm])

    assert economy.services_unmet_demand == pytest.approx(3.0)


def test_contract_services_unmet_demand_recorded_per_firm_when_targeted_and_out_of_capacity():
    economy, firm, _ = _make_services_clearing_economy(firm_capacity=0.0)
    firm.last_units_produced = 0.0
    plans = {1: {"planned_purchases": {firm.firm_id: 4.0}}}

    economy._clear_goods_market(plans, [firm])

    assert economy.services_unmet_demand_by_firm.get(firm.firm_id) == pytest.approx(4.0)
    assert economy.services_unmet_demand == pytest.approx(4.0)


def test_contract_services_unmet_demand_records_only_partial_unfilled_when_targeted():
    economy, firm, _ = _make_services_clearing_economy(firm_capacity=2.0)
    plans = {1: {"planned_purchases": {firm.firm_id: 5.0}}}

    economy._clear_goods_market(plans, [firm])

    assert economy.services_unmet_demand_by_firm.get(firm.firm_id) == pytest.approx(3.0)


def test_contract_services_generic_category_unmet_demand_not_assigned_per_firm():
    economy, firm, _ = _make_services_clearing_economy(firm_capacity=2.0)
    # Generic good-name targeted purchase, not firm-id targeted.
    plans = {1: {"planned_purchases": {firm.good_name: 5.0}}}

    economy._clear_goods_market(plans, [firm])

    assert economy.services_unmet_demand == pytest.approx(3.0)
    assert economy.services_unmet_demand_by_firm.get(firm.firm_id, 0.0) == pytest.approx(0.0)


def test_contract_services_upgrade_blocked_when_firm_specific_unmet_demand_zero():
    from types import SimpleNamespace

    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.employees = list(range(1, 6))
    firm.actual_wages = {employee_id: 45.0 for employee_id in firm.employees}
    firm.cash_runway_ticks = math.inf
    firm.profit_ema = 200.0
    firm.last_profit = 200.0

    fake_econ = SimpleNamespace(services_unmet_demand_by_firm={})  # zero unmet

    for _ in range(6):
        firm.last_units_produced = 10.0
        firm.last_units_sold = 10.0
        firm.last_sell_through_rate = 1.0
        assert firm.consider_service_infrastructure_upgrade(economy=fake_econ) is False

    assert firm.service_full_utilization_streak >= 5
    assert firm.needs_service_infrastructure_loan is False


def test_contract_services_upgrade_triggers_when_utilization_and_firm_unmet_demand_present():
    from types import SimpleNamespace

    firm = _make_service_flow_firm(production_capacity_units=5.0)
    firm.employees = list(range(1, 6))
    firm.actual_wages = {employee_id: 45.0 for employee_id in firm.employees}
    firm.cash_runway_ticks = math.inf
    firm.profit_ema = 200.0
    firm.last_profit = 200.0

    fake_econ = SimpleNamespace(services_unmet_demand_by_firm={firm.firm_id: 2.5})

    for _ in range(4):
        firm.last_units_produced = 10.0
        firm.last_units_sold = 9.6
        firm.last_sell_through_rate = 0.96
        firm.consider_service_infrastructure_upgrade(economy=fake_econ)

    firm.last_units_produced = 10.0
    firm.last_units_sold = 9.6
    firm.last_sell_through_rate = 0.96
    assert firm.consider_service_infrastructure_upgrade(economy=fake_econ) is True
    assert firm.needs_service_infrastructure_loan is True
    assert firm.service_infrastructure_loan_amount == pytest.approx(7_000.0)


def test_contract_services_inventory_remains_zero_after_unmet_demand_clearing():
    economy, firm, _ = _make_services_clearing_economy(firm_capacity=2.0)
    plans = {1: {"planned_purchases": {firm.firm_id: 5.0}}}

    economy._clear_goods_market(plans, [firm])

    assert firm.inventory_units == pytest.approx(0.0)
