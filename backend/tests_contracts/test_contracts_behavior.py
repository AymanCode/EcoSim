import copy

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from run_household_llm_tester import build_identity_block, build_tick_prompt, snapshot_household


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
    # Force deterministic request via the new episode-based model.
    hh.pending_healthcare_visits = 1
    hh.next_healthcare_request_tick = 0

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

    # New episode model: missing_health=0.7, 1 visit -> heal_delta=0.7 -> health=1.0
    assert hh.health > 0.3
    assert hh.health <= 1.0
    assert hh.happiness == pytest.approx(initial_happiness, abs=1e-8)
    assert hh.healthcare_consumed_this_tick == pytest.approx(1.0, abs=1e-8)
    assert healthcare_firm.inventory_units == pytest.approx(0.0, abs=1e-8)
    assert sales[healthcare_firm.firm_id]["units_sold"] <= len(healthcare_firm.employees) * healthcare_firm.healthcare_capacity_per_worker


def test_contract_wellbeing_mercy_floor_and_consumption_recovery():
    """Contract G: Mercy floor pauses natural decay; consumption gives incremental recovery.

    Services now contribute +0.0005/tick to happiness (not a large binary boost).
    Unemployment, food shortfall, and wealth loss each have small negative terms.
    The mercy floor stops natural decay from applying, but other signals still fire.
    """
    cfg = CONFIG.households

    # Mercy floor test: employed, all-needs-met household sitting just below mercy floor.
    # High decay rate to confirm it's suppressed. Positive terms should push happiness up.
    low_hh = _fresh_household(30)
    low_hh.happiness = cfg.mercy_floor_threshold - 0.01
    low_hh.happiness_decay_rate = 0.5  # Very high — mercy floor should neutralize this
    low_hh.employer_id = 1
    low_hh.wage = 100.0
    low_hh.expected_wage = 80.0
    low_hh.food_consumed_this_tick = cfg.food_health_high_threshold  # Well fed
    low_hh.services_consumed_this_tick = 1.0
    # met_housing_need = True from _fresh_household, last_tick_cash_start = 0 (no wealth loss)
    before = low_hh.happiness
    low_hh.update_wellbeing(government_happiness_multiplier=1.0)
    assert low_hh.happiness >= before, "Mercy floor should pause decay; positive recovery should apply"

    # Services recovery test: full-satisfaction employed household.
    # Happiness should rise by the incremental signal, not stay flat, not jump by a large amount.
    svc_hh = _fresh_household(31)
    svc_hh.happiness = 0.5
    svc_hh.happiness_decay_rate = 0.0
    svc_hh.employer_id = 1
    svc_hh.wage = 80.0
    svc_hh.expected_wage = 80.0
    svc_hh.food_consumed_this_tick = svc_hh.min_food_per_tick  # Met food need
    svc_hh.services_consumed_this_tick = 1.0
    # met_housing_need = True from _fresh_household, last_tick_cash_start = 0 (no wealth loss)
    initial = svc_hh.happiness
    svc_hh.update_wellbeing(government_happiness_multiplier=1.0)
    # All 4 positive conditions met: +0.0008 + 0.0005 + 0.0007 + 0.0005 = +0.0025 total
    # No decay (rate=0), no poverty, no shortfall, no unemployment, no wealth loss
    assert svc_hh.happiness > initial, "Full satisfaction should raise happiness"
    assert svc_hh.happiness < initial + 0.01, "Recovery should be incremental per tick, not a large one-shot boost"


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


def test_contract_batch_wellbeing_matches_per_agent_update_path():
    """Contract I2: Live batched wellbeing must match the richer per-agent path."""
    hh_batch = _fresh_household(45)
    hh_batch.happiness = 0.62
    hh_batch.morale = 0.58
    hh_batch.health = 0.71
    hh_batch.happiness_decay_rate = 0.01
    hh_batch.morale_decay_rate = 0.02
    hh_batch.health_decay_rate = 0.005
    hh_batch.employer_id = None
    hh_batch.wage = 0.0
    hh_batch.expected_wage = 90.0
    hh_batch.met_housing_need = False
    hh_batch.food_consumed_this_tick = 0.5
    hh_batch.services_consumed_this_tick = 0.0
    hh_batch.last_tick_cash_start = 1_000.0
    hh_batch.cash_balance = 700.0

    hh_single = copy.deepcopy(hh_batch)
    economy = Economy(
        households=[hh_batch],
        firms=[],
        government=GovernmentAgent(cash_balance=5_000.0),
    )

    economy._batch_update_wellbeing(happiness_multiplier=1.1)
    hh_single.update_wellbeing(government_happiness_multiplier=1.1)

    assert hh_batch.happiness == pytest.approx(hh_single.happiness, abs=1e-8)
    assert hh_batch.morale == pytest.approx(hh_single.morale, abs=1e-8)
    assert hh_batch.health == pytest.approx(hh_single.health, abs=1e-8)


def test_contract_healthcare_receipt_survives_batch_household_update():
    """Contract I3: Queue-based healthcare spend must persist into household purchase diagnostics."""
    hh = _fresh_household(46)
    hh.health = 0.3
    hh.pending_healthcare_visits = 1
    hh.next_healthcare_request_tick = 0

    healthcare_firm = FirmAgent(
        firm_id=2,
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
    healthcare_firm.employees = [201, 202]
    healthcare_firm.healthcare_capacity_per_worker = 1.0
    government = GovernmentAgent(cash_balance=5_000.0)
    economy = Economy(households=[hh], firms=[healthcare_firm], government=government)
    economy._apply_random_shocks = lambda: None

    economy._enqueue_healthcare_requests()
    economy._process_healthcare_services({})
    economy._batch_apply_household_updates(
        transfer_plan={hh.household_id: 0.0},
        wage_taxes={hh.household_id: 0.0},
        per_household_purchases={},
        good_category_lookup={},
    )

    assert hh.last_healthcare_units == pytest.approx(1.0, abs=1e-8)
    assert hh.last_healthcare_provider_id == healthcare_firm.firm_id
    assert "healthcare" in hh.last_purchase_breakdown
    assert hh.last_purchase_breakdown["healthcare"]["units"] == pytest.approx(1.0, abs=1e-8)
    assert hh.last_purchase_breakdown["healthcare"]["provider_id"] == healthcare_firm.firm_id


def test_contract_household_prompt_and_snapshot_use_grounded_unemployment_and_receipts():
    """Contract I4: Household prompt/logs should use unemployment framing and expose receipts."""
    hh = _fresh_household(47)
    hh.employer_id = None
    hh.wage = 0.0
    hh.unemployment_duration = 43
    hh.job_search_cooldown = 43
    hh.last_food_units = 2.0
    hh.last_food_spend = 20.0
    hh.last_services_units = 1.0
    hh.last_services_spend = 12.0
    hh.last_housing_units = 1.0
    hh.last_housing_spend = 40.0
    hh.last_healthcare_units = 1.0
    hh.last_healthcare_spend = 15.0
    hh.last_healthcare_provider_id = 9
    hh.healthcare_consumed_this_tick = 1.0
    hh.last_wage_income = 0.0
    hh.last_transfer_income = 30.0
    hh.last_dividend_income = 12.0
    hh.last_other_income = -4.0
    hh.education_active_this_tick = True
    hh.is_misc_beneficiary = True
    hh.owned_firm_ids = [2, 7]
    hh.last_dividend_firm_ids = [7]
    hh.last_tick_ledger = {
        "wage": 0.0,
        "transfers": 30.0,
        "stimulus": 20.0,
        "redistribution": 12.0,
        "dividends": 12.0,
        "goods": -72.0,
        "rent": -5.0,
        "healthcare": -15.0,
        "education": -100.0,
        "taxes": -4.0,
        "bank": 0.0,
        "other": 0.0,
        "net": -122.0,
    }
    hh.last_purchase_breakdown = {
        "food": {"units": 2.0, "spend": 20.0},
        "services": {"units": 1.0, "spend": 12.0},
        "healthcare": {"units": 1.0, "spend": 15.0, "provider_id": 9},
    }
    metrics = {
        "unemployment_rate": 0.4,
        "mean_wage": 55.0,
        "unemployment_benefit": 30.0,
        "mean_food_price": 8.0,
        "mean_housing_price": 14.0,
        "mean_services_price": 9.0,
        "total_firms": 12,
        "private_firms": 8,
    }

    identity = build_identity_block(hh)
    prompt = build_tick_prompt(hh, metrics, tick=12, prev_state=None)
    snapshot = snapshot_household(hh)

    assert "Won't switch jobs unless offered" not in identity
    assert "no switch threshold applies when unemployed" in identity
    assert "government benefit" not in prompt.lower()
    assert "Unemployment benefit: $30/tick" in prompt
    assert "searching every tick (unemployed — no cooldown)" in prompt
    assert "Healthcare:" in prompt
    assert "Purchase detail:" in prompt
    assert "Firm ownership: yes — owner of firms #2, #7" in prompt
    assert "Misc redistribution pool beneficiary: yes" in prompt
    assert "Education this tick: yes — spent $100 on skill building this tick" in prompt
    assert "Cash ledger:" in prompt
    assert "stimulus" in prompt
    assert "redistribution" in prompt
    assert "dividends" in prompt
    assert snapshot["last_healthcare_units"] == pytest.approx(1.0, abs=1e-8)
    assert snapshot["last_healthcare_provider_id"] == 9
    assert "last_purchase_breakdown" in snapshot
    assert "queued_healthcare_firm_id" in snapshot
    assert snapshot["last_dividend_income"] == pytest.approx(12.0, abs=1e-8)
    assert snapshot["education_active_this_tick"] is True
    assert snapshot["owned_firm_ids"] == [2, 7]
    assert snapshot["last_dividend_firm_ids"] == [7]
    assert snapshot["last_tick_ledger"]["education"] == pytest.approx(-100.0, abs=1e-8)


def test_contract_dividends_update_household_visibility_ledger():
    """Contract I5: Dividend payouts must surface in household visibility fields."""
    hh = _fresh_household(48)
    hh.reset_tick_ledger()
    firm = FirmAgent(
        firm_id=11,
        good_name="FoodCo",
        cash_balance=1_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=40.0,
        price=8.0,
        expected_sales_units=10.0,
        production_capacity_units=100.0,
        productivity_per_worker=10.0,
        personality="moderate",
    )
    firm.owners = [hh.household_id]
    firm.net_profit = 100.0
    firm.payout_ratio = 0.5
    firm.last_tick_total_costs = 0.0

    distributed = firm.distribute_profits({hh.household_id: hh})

    assert distributed == pytest.approx(50.0, abs=1e-8)
    assert hh.last_dividend_income == pytest.approx(50.0, abs=1e-8)
    assert hh.last_dividend_firm_ids == [firm.firm_id]
    assert hh.last_tick_ledger["dividends"] == pytest.approx(50.0, abs=1e-8)


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
    hh.pending_healthcare_visits = 2
    hh.next_healthcare_request_tick = 0

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
