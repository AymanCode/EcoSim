import copy

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def _fresh_household(household_id: int = 1) -> HouseholdAgent:
    hh = HouseholdAgent(
        household_id=household_id,
        skills_level=0.6,
        age=35,
        cash_balance=2_000.0,
    )
    hh.met_housing_need = True
    hh.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
    return hh


def test_contract_food_drives_health_by_thresholds():
    """Contract E: Food proportionally drives health using the configured curved rule."""
    cfg = CONFIG.households
    baseline_health = 0.4

    def health_delta(food_units: float) -> float:
        hh = _fresh_household(10)
        hh.health = baseline_health
        hh.health_decay_rate = 0.0
        hh.food_consumed_this_tick = food_units
        hh.services_consumed_this_tick = 0.0
        hh.healthcare_consumed_this_tick = 0.0
        hh.update_wellbeing(government_happiness_multiplier=1.0)
        return hh.health - baseline_health

    low_delta = health_delta(0.0)
    mid_delta = health_delta(cfg.food_health_mid_threshold)
    high_delta = health_delta(cfg.food_health_high_threshold)

    def expected_food_effect(food_units: float) -> float:
        ratio = min(1.0, food_units / max(0.1, cfg.food_health_high_threshold))
        curved_ratio = ratio ** 0.6
        return curved_ratio * (cfg.food_health_high_boost + cfg.food_starvation_penalty) - cfg.food_starvation_penalty

    assert low_delta == pytest.approx(expected_food_effect(0.0), abs=1e-8)
    assert mid_delta == pytest.approx(expected_food_effect(cfg.food_health_mid_threshold), abs=1e-8)
    assert high_delta == pytest.approx(expected_food_effect(cfg.food_health_high_threshold), abs=1e-8)
    assert high_delta > mid_delta > low_delta


def test_contract_healthcare_consumption_restores_health_without_happiness_change():
    """Contract F: Completed healthcare visits restore health and do not raise happiness."""
    hh = _fresh_household(20)
    hh.health = 0.3
    hh.happiness = 0.42
    initial_happiness = hh.happiness
    # Force deterministic request and deterministic heal delta for this visit.
    hh.care_plan_anchor_tick = 0
    hh.care_plan_due_ticks = [0]
    hh.care_plan_heal_deltas = [0.2]

    healthcare_firm = FirmAgent(
        firm_id=1,
        good_name="Clinic",
        cash_balance=20_000.0,
        inventory_units=0.0,
        good_category="Healthcare",
        quality_level=6.0,
        wage_offer=40.0,
        price=15.0,
        expected_sales_units=100.0,
        production_capacity_units=500.0,
        productivity_per_worker=12.0,
        personality="moderate",
    )
    healthcare_firm.employees = [101, 102]
    healthcare_firm.healthcare_capacity_per_worker = 1.0
    government = GovernmentAgent(cash_balance=5_000.0)
    economy = Economy(households=[hh], firms=[healthcare_firm], government=government)
    economy._apply_random_shocks = lambda: None

    economy._enqueue_healthcare_requests()
    assert len(healthcare_firm.healthcare_queue) == 1

    sales = {}
    economy._process_healthcare_services(sales)

    expected_health = min(1.0, 0.3 + 0.2)
    assert hh.health == pytest.approx(expected_health, abs=1e-8)
    assert hh.happiness == pytest.approx(initial_happiness, abs=1e-8)
    assert hh.healthcare_consumed_this_tick == pytest.approx(1.0, abs=1e-8)
    assert len(hh.care_plan_due_ticks) == 0
    assert healthcare_firm.inventory_units == pytest.approx(0.0, abs=1e-8)
    assert sales[healthcare_firm.firm_id]["units_sold"] <= len(healthcare_firm.employees) * healthcare_firm.healthcare_capacity_per_worker


def test_contract_services_no_binary_happiness_boost_and_mercy_floor_pauses_decay():
    """Contract G: No binary services boost in wellbeing; mercy floor still pauses decay."""
    cfg = CONFIG.households

    low_hh = _fresh_household(30)
    low_hh.happiness = cfg.mercy_floor_threshold - 0.01
    low_hh.happiness_decay_rate = 0.1
    low_hh.services_consumed_this_tick = 0.0
    low_hh.update_wellbeing(government_happiness_multiplier=1.0)
    assert low_hh.happiness == pytest.approx(cfg.mercy_floor_threshold - 0.01, abs=1e-8)

    svc_hh = _fresh_household(31)
    svc_hh.happiness = 0.5
    svc_hh.happiness_decay_rate = 0.0
    svc_hh.services_consumed_this_tick = 1.0
    initial = svc_hh.happiness
    svc_hh.update_wellbeing(government_happiness_multiplier=1.0)
    assert svc_hh.happiness == pytest.approx(initial, abs=1e-8)


def test_contract_social_multiplier_per_tick_not_cumulative():
    """Contract H: Social multiplier is recomputed per tick and does not accumulate."""
    government = GovernmentAgent(cash_balance=5_000.0, social_investment_budget=750.0)

    multipliers = []
    for _ in range(3):
        government.invest_in_social_programs()
        multipliers.append(government.social_happiness_multiplier)

    assert all(m == pytest.approx(1.05, abs=1e-10) for m in multipliers)


def test_contract_morale_reacts_to_employment_housing_and_wages():
    """Contract I: Morale direction follows employment, housing, and wage satisfaction."""
    base = _fresh_household(40)
    base.morale = 0.5
    base.morale_decay_rate = 0.0
    base.employer_id = 1
    base.wage = 100.0
    base.expected_wage = 80.0
    base.met_housing_need = True

    employed_housed = copy.deepcopy(base)
    employed_housed.update_wellbeing(government_happiness_multiplier=1.0)
    delta_employed_housed = employed_housed.morale - 0.5
    assert delta_employed_housed > 0.0

    unemployed = copy.deepcopy(base)
    unemployed.employer_id = None
    unemployed.wage = 0.0
    unemployed.update_wellbeing(government_happiness_multiplier=1.0)
    delta_unemployed = unemployed.morale - 0.5
    assert delta_unemployed < 0.0

    employed_unhoused = copy.deepcopy(base)
    employed_unhoused.met_housing_need = False
    employed_unhoused.update_wellbeing(government_happiness_multiplier=1.0)
    delta_employed_unhoused = employed_unhoused.morale - 0.5
    assert delta_employed_unhoused < delta_employed_housed

    underpaid = copy.deepcopy(base)
    underpaid.wage = 50.0
    underpaid.expected_wage = 80.0
    underpaid.update_wellbeing(government_happiness_multiplier=1.0)
    delta_underpaid = underpaid.morale - 0.5
    assert delta_underpaid < delta_employed_housed


def test_contract_budget_redirect_rules(category_market_info):
    """Contract J: Food-shortage redirect adjusts and normalizes fractions."""
    base_fractions = {
        "food": 0.40,
        "housing": 0.30,
        "services": 0.30,
    }

    hh = _fresh_household(50)
    hh.food_consumed_last_tick = 0.0
    # Isolate food redirect behavior for deterministic expected fractions.
    hh.services_consumed_last_tick = hh.min_services_per_tick
    debug_food_shift = {}
    hh._plan_category_purchases(
        budget=100.0,
        firm_market_info=category_market_info,
        category_fraction_override=base_fractions,
        debug_category_fractions=debug_food_shift,
    )

    assert debug_food_shift["food"] == pytest.approx(0.805, abs=1e-8)
    assert debug_food_shift["housing"] == pytest.approx(0.195, abs=1e-8)
    assert debug_food_shift.get("services", 0.0) == pytest.approx(0.0, abs=1e-8)
    assert sum(debug_food_shift.values()) == pytest.approx(1.0, abs=1e-8)
    assert all(0.0 <= value <= 1.0 for value in debug_food_shift.values())


def test_contract_services_shortfall_redirect_rules(category_market_info):
    """Contract J2: Service shortfall redirect shifts some housing share to services."""
    base_fractions = {
        "food": 0.40,
        "housing": 0.40,
        "services": 0.20,
    }

    hh = _fresh_household(51)
    # Disable food shortfall branch so this test isolates service redirect behavior.
    hh.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
    hh.services_consumed_last_tick = 0.0
    hh.min_services_per_tick = 2.0
    debug_shift = {}

    hh._plan_category_purchases(
        budget=100.0,
        firm_market_info=category_market_info,
        category_fraction_override=base_fractions,
        debug_category_fractions=debug_shift,
    )

    assert debug_shift["services"] > base_fractions["services"]
    assert debug_shift["housing"] < base_fractions["housing"]
    assert debug_shift["food"] == pytest.approx(base_fractions["food"], abs=1e-8)
    assert sum(debug_shift.values()) == pytest.approx(1.0, abs=1e-8)
    assert all(0.0 <= value <= 1.0 for value in debug_shift.values())


def test_contract_services_are_non_storable_flow_consumption():
    """Contract G2: Service purchases should count this tick, but not persist in inventory."""
    hh = _fresh_household(52)
    hh.services_consumed_this_tick = 0.0

    hh.apply_purchases(
        purchases={"ServicesFirm": (2.0, 10.0)},
        firm_categories={"ServicesFirm": "services"},
    )

    assert hh.services_consumed_this_tick == pytest.approx(2.0, abs=1e-8)
    assert all("service" not in good.lower() for good in hh.goods_inventory.keys())

def test_contract_healthcare_queue_and_snapshot_contracts(tiny_economy_factory):
    """Contract K: Healthcare is excluded from goods snapshot and handled via queue."""
    economy = tiny_economy_factory(num_households=3, num_firms_per_category=1, include_healthcare=True, seed=333)
    snapshot = economy._build_category_market_snapshot()

    assert "healthcare" not in snapshot

    hh = economy.households[0]
    hh.health = 0.2
    hh.care_plan_due_ticks = [economy.current_tick]

    healthcare_firms = [f for f in economy.firms if f.good_category.lower() == "healthcare"]
    assert healthcare_firms, "Fixture expected at least one healthcare firm"
    healthcare_firm = healthcare_firms[0]
    healthcare_firm.employees = [1, 2]
    healthcare_firm.healthcare_capacity_per_worker = 1.0

    economy._enqueue_healthcare_requests()
    assert hh.household_id in healthcare_firm.healthcare_queue
    assert len(healthcare_firm.healthcare_queue) >= 0

    per_firm_sales = {}
    economy._process_healthcare_services(per_firm_sales)
    assert healthcare_firm.inventory_units == pytest.approx(0.0, abs=1e-8)
    assert 0.0 <= hh.health <= 1.0
