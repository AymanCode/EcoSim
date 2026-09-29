import copy

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from tools.llm.run_household_llm_tester import build_identity_block, build_tick_prompt, snapshot_household


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


def _batch_wellbeing(hh: HouseholdAgent, multiplier: float = 1.0) -> None:
    """Run the live batched wellbeing update (Economy._batch_update_wellbeing) for one household."""
    economy = Economy(
        households=[hh],
        firms=[],
        government=GovernmentAgent(cash_balance=5_000.0),
    )
    economy._batch_update_wellbeing(happiness_multiplier=multiplier)


def test_contract_food_offsets_only_part_of_health_decay_by_thresholds():
    """Contract E: Food can offset only the configured share of natural health decay."""
    cfg = CONFIG.households
    baseline_health = 0.4
    decay = 0.02

    def health_delta(food_units: float) -> float:
        hh = _fresh_household(10)
        hh.health = baseline_health
        hh.health_decay_rate = decay
        hh.food_consumed_this_tick = food_units
        hh.services_consumed_this_tick = 0.0
        hh.healthcare_consumed_this_tick = 0.0
        _batch_wellbeing(hh, 1.0)
        return hh.health - baseline_health

    low_delta = health_delta(0.0)
    mid_delta = health_delta(cfg.food_health_mid_threshold)
    high_delta = health_delta(cfg.food_health_high_threshold)

    def expected_food_effect(food_units: float) -> float:
        ratio = min(1.0, food_units / max(0.1, cfg.food_health_high_threshold))
        curved_ratio = ratio ** 0.6
        raw_food_effect = (
            curved_ratio * (cfg.food_health_high_boost + cfg.food_starvation_penalty)
            - cfg.food_starvation_penalty
        )
        if raw_food_effect > 0.0:
            offset_ratio = min(1.0, raw_food_effect / max(cfg.food_health_high_boost, 1e-9))
            food_offset = decay * cfg.food_health_decay_offset_share * offset_ratio
            return food_offset - decay
        return raw_food_effect - decay

    assert low_delta == pytest.approx(expected_food_effect(0.0), abs=1e-8)
    assert mid_delta == pytest.approx(expected_food_effect(cfg.food_health_mid_threshold), abs=1e-8)
    assert high_delta == pytest.approx(expected_food_effect(cfg.food_health_high_threshold), abs=1e-8)
    assert high_delta > mid_delta > low_delta
    assert high_delta == pytest.approx(-(1.0 - cfg.food_health_decay_offset_share) * decay, abs=1e-8)


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


def test_contract_social_multiplier_does_not_scale_healthcare_healing():
    """Social spending is happiness-only; healthcare healing uses clinical heal amount."""
    hh = _fresh_household(21)
    hh.health = 0.5
    hh.cash_balance = 1_000.0
    hh.pending_visit_heal_delta = 0.1
    hh.queued_healthcare_firm_id = 2
    hh.healthcare_queue_enter_tick = 0

    healthcare_firm = FirmAgent(
        firm_id=2,
        good_name="Clinic",
        cash_balance=20_000.0,
        inventory_units=0.0,
        good_category="Healthcare",
        quality_level=6.0,
        wage_offer=40.0,
        price=0.0,
        expected_sales_units=100.0,
        production_capacity_units=500.0,
        productivity_per_worker=12.0,
        personality="moderate",
    )
    healthcare_firm.employees = [101]
    healthcare_firm.healthcare_capacity_per_worker = 1.0
    healthcare_firm.healthcare_queue = [hh.household_id]
    government = GovernmentAgent(cash_balance=5_000.0)
    government.social_happiness_multiplier = 1.15
    economy = Economy(households=[hh], firms=[healthcare_firm], government=government)

    economy._process_healthcare_services({})

    assert hh.health == pytest.approx(0.6, abs=1e-8)


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
    _batch_wellbeing(low_hh, 1.0)
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
    _batch_wellbeing(svc_hh, 1.0)
    # All 4 positive conditions met: +0.0008 + 0.0005 + 0.0007 + 0.0005 = +0.0025 total
    # No decay (rate=0), no poverty, no shortfall, no unemployment, no wealth loss
    assert svc_hh.happiness > initial, "Full satisfaction should raise happiness"
    assert svc_hh.happiness < initial + 0.01, "Recovery should be incremental per tick, not a large one-shot boost"


def test_contract_social_multiplier_is_policy_funded_and_decays():
    """Contract H: Social multiplier is funded by policy and decays when unfunded."""
    government = GovernmentAgent(cash_balance=5_000.0, social_investment_budget=750.0)

    multipliers = []
    for _ in range(3):
        government.invest_in_social_programs()
        multipliers.append(government.social_happiness_multiplier)

    assert all(m == pytest.approx(1.05, abs=1e-10) for m in multipliers)

    government.set_lever("social_spending", "none")
    spent = government.invest_in_social_programs()

    assert spent == pytest.approx(0.0)
    assert government.social_investment_budget == pytest.approx(0.0)
    assert government.social_happiness_multiplier < multipliers[-1]
    assert government.social_happiness_multiplier >= 1.0


def test_contract_infrastructure_multiplier_is_capped_and_decays():
    """B17: sustained infrastructure spending saturates at 1.15 and fades when it stops."""
    government = GovernmentAgent(cash_balance=10_000_000.0)
    government.set_lever("infrastructure_spending", "high")
    for _ in range(200):
        government.invest_in_infrastructure()
    assert government.infrastructure_productivity_multiplier == pytest.approx(1.15)

    government.set_lever("infrastructure_spending", "none")
    for _ in range(14):
        assert government.invest_in_infrastructure() == 0.0
    # The excess over 1.0 decays 5% a tick: 0.15 * 0.95**14 after 14 unfunded ticks.
    assert government.infrastructure_productivity_multiplier == pytest.approx(1.0 + 0.15 * 0.95 ** 14)
    for _ in range(400):
        government.invest_in_infrastructure()
    assert 1.0 <= government.infrastructure_productivity_multiplier < 1.0 + 1e-6


def test_contract_household_constructor_overrides_survive_personality_sampling():
    """B30: fields passed to HouseholdAgent are kept; only omitted fields are sampled."""
    base = dict(household_id=41, skills_level=0.5, age=30, cash_balance=100.0)
    default = HouseholdAgent(**base)
    custom = HouseholdAgent(
        **base,
        happiness=0.25,
        expected_wage=42.0,
        reservation_wage=20.0,
        price_expectation_alpha=0.5,
        saving_tendency=0.9,
        job_search_cooldown=3,
    )

    assert custom.happiness == 0.25
    assert custom.expected_wage == 42.0
    assert custom.reservation_wage == 20.0
    assert custom.price_expectation_alpha == 0.5
    assert custom.saving_tendency == 0.9
    assert custom.job_search_cooldown == 3
    # Derived from the supplied saving tendency, not a sampled one.
    assert custom.deposit_buffer_weeks == pytest.approx(3.0 + 7.0 * 0.9)
    # Omitted fields take the same draws as a default household.
    assert custom.morale == default.morale
    assert custom.spending_tendency == default.spending_tendency
    assert custom.min_services_per_tick == default.min_services_per_tick

    with pytest.raises(ValueError):
        HouseholdAgent(**base, price_expectation_alpha=1.5)
    with pytest.raises(ValueError):
        HouseholdAgent(**base, consumption_budget_share=2.0)


@pytest.mark.parametrize("supplied", [
    {"reservation_wage": 20.0, "expected_wage": 60.0},
    {"reservation_wage": 20.0},
    {"expected_wage": 5.0},
    {"savings_rate_target": 0.2},
])
def test_contract_household_overrides_leave_omitted_fields_at_default_draws(supplied):
    """B30: supplying fields never shifts the draws of omitted ones.

    Households 5, 6 and 7 hit the default reservation-wage adjustment (their
    sampled reservation wage is at or above the sampled expected wage, so a
    default household draws an extra factor); 1 and 2 do not.
    """
    from dataclasses import fields

    names = [f.name for f in fields(HouseholdAgent) if f.init and f.name not in supplied]
    for household_id in (1, 2, 5, 6, 7):
        base = dict(household_id=household_id, skills_level=0.5, age=30, cash_balance=100.0)
        default = HouseholdAgent(**base)
        custom = HouseholdAgent(**base, **supplied)
        for key, value in supplied.items():
            assert getattr(custom, key) == value
        if "expected_wage" in supplied and "reservation_wage" not in supplied:
            names_checked = [n for n in names if n != "reservation_wage"]  # derived from expected
            assert custom.reservation_wage < custom.expected_wage
        else:
            names_checked = names
        changed = [n for n in names_checked if getattr(custom, n) != getattr(default, n)]
        assert not changed, f"household {household_id}: supplying {sorted(supplied)} changed {changed}"


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
    _batch_wellbeing(employed_housed, 1.0)
    delta_employed_housed = employed_housed.morale - 0.5
    assert delta_employed_housed > 0.0

    unemployed = copy.deepcopy(base)
    unemployed.employer_id = None
    unemployed.wage = 0.0
    _batch_wellbeing(unemployed, 1.0)
    delta_unemployed = unemployed.morale - 0.5
    assert delta_unemployed < 0.0

    employed_unhoused = copy.deepcopy(base)
    employed_unhoused.met_housing_need = False
    _batch_wellbeing(employed_unhoused, 1.0)
    delta_employed_unhoused = employed_unhoused.morale - 0.5
    assert delta_employed_unhoused < delta_employed_housed

    underpaid = copy.deepcopy(base)
    underpaid.wage = 50.0
    underpaid.expected_wage = 80.0
    _batch_wellbeing(underpaid, 1.0)
    delta_underpaid = underpaid.morale - 0.5
    assert delta_underpaid < delta_employed_housed


def test_contract_batch_wellbeing_unemployed_unhoused_wealth_loss_with_social_multiplier():
    """Contract I2: Batched wellbeing for an unemployed, unhoused household losing cash, multiplier 1.1.

    Expected values were pinned from Economy._batch_update_wellbeing at d512de7, where
    this same setup was asserted equal (abs=1e-8) to the since-deleted per-agent
    HouseholdAgent.update_wellbeing.
    """
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

    economy = Economy(
        households=[hh_batch],
        firms=[],
        government=GovernmentAgent(cash_balance=5_000.0),
    )

    economy._batch_update_wellbeing(happiness_multiplier=1.1)

    assert hh_batch.happiness == pytest.approx(0.6068886959643153, abs=1e-8)
    assert hh_batch.morale == pytest.approx(0.49210845164609773, abs=1e-8)
    assert hh_batch.health == pytest.approx(0.6900713185890575, abs=1e-8)


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


@pytest.mark.llm
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
    assert "searching every tick" in prompt
    assert "no cooldown" in prompt
    assert "Healthcare:" in prompt
    assert "Purchase detail:" in prompt
    assert "Firm ownership: yes" in prompt
    assert "#2, #7" in prompt
    assert "Misc redistribution pool beneficiary: yes" in prompt
    assert "Education this tick: yes" in prompt
    assert "spent $100 on skill building this tick" in prompt
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


def test_contract_budget_redirect_rules():
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
        category_fraction_override=base_fractions,
        debug_category_fractions=debug_food_shift,
    )

    assert debug_food_shift["food"] == pytest.approx(0.805, abs=1e-8)
    assert debug_food_shift["housing"] == pytest.approx(0.195, abs=1e-8)
    assert debug_food_shift.get("services", 0.0) == pytest.approx(0.0, abs=1e-8)
    assert sum(debug_food_shift.values()) == pytest.approx(1.0, abs=1e-8)
    assert all(0.0 <= value <= 1.0 for value in debug_food_shift.values())


def test_contract_services_shortfall_redirect_rules():
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
    economy = Economy(
        households=[hh],
        firms=[],
        government=GovernmentAgent(cash_balance=5_000.0),
    )

    economy._batch_apply_household_updates(
        transfer_plan={hh.household_id: 0.0},
        wage_taxes={hh.household_id: 0.0},
        per_household_purchases={hh.household_id: {"ServicesFirm": (2.0, 10.0)}},
        good_category_lookup={"ServicesFirm": "services"},
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


def _turnaround_services_firm() -> FirmAgent:
    """A private Services firm with funded turnaround credit and validated demand."""
    firm = FirmAgent(
        firm_id=77,
        good_name="ServicesFirm77",
        cash_balance=100.0,
        inventory_units=0.0,
        good_category="Services",
        quality_level=5.0,
        wage_offer=20.0,
        price=100.0,
        expected_sales_units=20.0,
        production_capacity_units=20.0,
        productivity_per_worker=3.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1, 2, 3]
    firm.actual_wages = {1: 20.0, 2: 20.0, 3: 20.0}
    firm._invalidate_wage_bill_cache()
    firm.working_capital_support_ticks = 3
    firm.working_capital_hire_budget_workers = 2
    firm.last_tick_lost_sales_used_units = 10.0
    firm.last_working_capital_estimated_net_gain = 100.0
    return firm


def test_contract_turnaround_gate_reads_zero_inventory_and_margin_as_real_values():
    """B15: zero inventory weeks (every Services firm) and a 0.0 margin are real readings.

    Before the fix `getattr(..., 999.0) or 999.0` turned 0.0 inventory weeks into
    999 weeks and a 0.0 margin into -1.0, so the gate never allowed a Services
    turnaround.
    """
    from agents import FirmHealthSnapshot

    firm = _turnaround_services_firm()
    snapshot = FirmHealthSnapshot(
        cash_runway_ticks=1.0,
        smoothed_profit_margin=0.0,
        sell_through_rate=1.0,
        inventory_weeks=0.0,
        unfilled_positions_streak=0,
        worker_turnover_this_tick=0,
        survival_mode=True,
        burn_mode=False,
        category_wage_anchor_p75=20.0,
    )
    allowed, payload = firm._survival_turnaround_gate(snapshot)
    assert payload["inventory_weeks"] == 0.0
    assert payload["profit_margin"] == 0.0
    assert allowed is True

    plan = firm._plan_services_capacity_labor(snapshot)
    assert plan["planned_hires_count"] > 0
    assert firm.decision_diagnostics.get("survival_turnaround_hiring") is True


def test_contract_reservation_gap_raise_reads_zero_inventory_weeks_as_tight():
    """B15 (wage planner): 0.0 inventory weeks supports a reservation-gap wage raise.

    Before the fix `getattr(self, "inventory_weeks", 999.0) or 999.0` turned a
    firm's 0.0 inventory weeks (every Services firm, or a stocked-out goods
    firm) into 999 weeks, so that demand signal never counted.
    """
    from agents import FirmHealthSnapshot

    firm = _turnaround_services_firm()
    firm.working_capital_support_ticks = 0
    firm.working_capital_hire_budget_workers = 0
    firm.last_tick_lost_sales_used_units = 0.0
    firm.last_sell_through_rate = 0.5
    firm.inventory_weeks = 0.0
    firm.last_tick_planned_hires = 2
    firm.last_tick_actual_hires = 0
    firm.last_tick_failed_match_reason = "reservation_above_wage_offer"
    firm.last_tick_reservation_reject_count = 3
    firm.last_tick_median_rejected_reservation_wage = 30.0
    snapshot = FirmHealthSnapshot(
        cash_runway_ticks=50.0,
        smoothed_profit_margin=0.1,
        sell_through_rate=0.5,
        inventory_weeks=0.0,
        unfilled_positions_streak=0,
        worker_turnover_this_tick=0,
        survival_mode=False,
        burn_mode=False,
        category_wage_anchor_p75=20.0,
    )
    plan = firm.plan_wage(health_snapshot=snapshot, minimum_wage_floor=20.0)
    assert firm.decision_diagnostics.get("wage_raise_reason") == "reservation_blocked_vacancies"
    assert plan["wage_offer_next"] > 20.0


def test_contract_housing_labor_plan_is_stamped_on_the_firm():
    """B21: housing firms record their planned hires like every other planner branch.

    Before the fix the housing branch of plan_production_and_labor returned its
    plan without setting planned_hires_count, planned_layoffs_ids or
    last_tick_planned_hires, so housing vacancies were invisible to the code
    that reads those fields (unfilled-vacancy streaks, the wage planner's
    failed-hire check, sector vacancy totals).
    """
    firm = FirmAgent(
        firm_id=88,
        good_name="HousingFirm88",
        cash_balance=50_000.0,
        inventory_units=0.0,
        good_category="Housing",
        quality_level=5.0,
        wage_offer=30.0,
        price=150.0,
        expected_sales_units=10.0,
        production_capacity_units=20.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
        max_rental_units=20,
    )
    firm.planned_hires_count = 0
    firm.last_tick_planned_hires = 0
    plan = firm.plan_production_and_labor(last_tick_sales_units=0.0, total_households=100)

    assert plan["planned_hires_count"] > 0
    assert firm.planned_hires_count == plan["planned_hires_count"]
    assert firm.last_tick_planned_hires == plan["planned_hires_count"]
    assert firm.planned_layoffs_ids == plan["planned_layoffs_ids"]


def test_contract_destabilized_labor_plan_is_stamped_on_the_firm():
    """B21: the stabilization-disabled plan records its planned hires on the firm too."""
    firm = FirmAgent(
        firm_id=89,
        good_name="FoodFirm89",
        cash_balance=50_000.0,
        inventory_units=0.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=30.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=200.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.stabilization_disabled = True
    firm.planned_hires_count = 0
    firm.last_tick_planned_hires = 0
    plan = firm.plan_production_and_labor(last_tick_sales_units=0.0, total_households=100)

    assert plan["planned_hires_count"] > 0
    assert firm.planned_hires_count == plan["planned_hires_count"]
    assert firm.last_tick_planned_hires == plan["planned_hires_count"]


def _baseline_food_after_transition(inventory_units: float) -> FirmAgent:
    firm = FirmAgent(
        firm_id=90,
        good_name="BaselineFood90",
        cash_balance=1_000_000.0,
        inventory_units=inventory_units,
        good_category="Food",
        quality_level=5.0,
        wage_offer=20.0,
        price=5.0,
        expected_sales_units=2_000.0,
        production_capacity_units=5_000.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=True,
    )
    firm.baseline_production_quota = 500.0
    firm.baseline_food_post_warmup_transition_done = True
    firm.employees = list(range(1, 21))
    firm.actual_wages = {employee_id: 20.0 for employee_id in firm.employees}
    firm._invalidate_wage_bill_cache()
    return firm


def test_contract_baseline_food_liquidation_shrink_is_not_undone_by_demand_floor():
    """B18: a baseline Food firm in a liquidation tier keeps its shrunken headcount.

    Before the fix `if self.is_baseline: target_workers = max(target_workers,
    demand_workers)` ran after the inventory tiers and raised the target back
    to the demand-based headcount, so the tier's layoffs never happened.
    """
    firm = _baseline_food_after_transition(inventory_units=500.0 * 7.0)
    plan = firm.plan_production_and_labor(last_tick_sales_units=2_000.0, total_households=1_000)

    assert firm.decision_diagnostics["baseline_food_liquidation_tier"] == "liquidation"
    assert len(plan["planned_layoffs_ids"]) == 5  # 20 -> 10 target, capped at the baseline fire limit
    assert plan["planned_hires_count"] == 0


def test_contract_baseline_food_normal_tier_keeps_demand_floor():
    """B18: with inventory in the normal tier the demand-based floor still applies."""
    firm = _baseline_food_after_transition(inventory_units=0.0)
    firm.last_profit = 100.0
    firm.profit_ema = 100.0
    plan = firm.plan_production_and_labor(last_tick_sales_units=2_000.0, total_households=1_000)

    assert firm.decision_diagnostics["baseline_food_liquidation_tier"] == "normal"
    assert plan["planned_layoffs_ids"] == []


def test_contract_wage_offer_decays_toward_floor_above_nairu():
    """B20: in a labor surplus the wage offer falls at most max_wage_decrease_per_tick a tick.

    Before the fix, `unemployment_short_ma > nairu_threshold` returned the floor
    wage in one tick (60 -> 36 in this test), bypassing the per-tick decrease limit.
    """
    from agents import FirmHealthSnapshot

    firm = FirmAgent(
        firm_id=91,
        good_name="FoodFirm91",
        cash_balance=100_000.0,
        inventory_units=100.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=60.0,
        price=10.0,
        expected_sales_units=100.0,
        production_capacity_units=500.0,
        productivity_per_worker=10.0,
        personality="moderate",
        is_baseline=False,
    )
    firm.employees = [1, 2, 3]
    firm.actual_wages = {1: 60.0, 2: 60.0, 3: 60.0}
    firm._invalidate_wage_bill_cache()
    firm.last_revenue = 100_000.0
    snapshot = FirmHealthSnapshot(
        cash_runway_ticks=50.0,
        smoothed_profit_margin=0.2,
        sell_through_rate=0.9,
        inventory_weeks=1.0,
        unfilled_positions_streak=0,
        worker_turnover_this_tick=0,
        survival_mode=False,
        burn_mode=False,
        category_wage_anchor_p75=60.0,
    )
    nairu = CONFIG.firms.nairu_threshold
    plan = firm.plan_wage(
        health_snapshot=snapshot,
        unemployment_short_ma=nairu + 0.05,
        minimum_wage_floor=36.0,
    )
    expected = 60.0 * CONFIG.firms.max_wage_decrease_per_tick
    assert expected > 36.0
    assert plan["wage_offer_next"] == pytest.approx(expected)

    # Near the floor the decay stops at the floor.
    firm.wage_offer = 38.0
    plan = firm.plan_wage(
        health_snapshot=snapshot,
        unemployment_short_ma=nairu + 0.05,
        minimum_wage_floor=36.0,
    )
    assert plan["wage_offer_next"] == pytest.approx(36.0)


def test_contract_skill_growth_is_proportional_to_ticks_employed():
    """B31(a): the yearly skill grant counts the ticks actually worked.

    Before the fix, apply_labor_outcome granted 52 ticks of growth whenever 52
    calendar ticks had passed since the last grant, so a worker employed for
    one tick of the year got a full year's growth.
    """
    hh = _fresh_household(21)
    hh.skills_level = 0.5
    hh.skill_growth_rate = 0.001
    employed = {"employer_id": 1, "wage": 40.0, "employer_category": "Food"}
    unemployed = {"employer_id": None, "wage": 0.0, "employer_category": None}
    for tick in range(1, 53):
        hh.apply_labor_outcome(employed if tick > 42 else unemployed, current_tick=tick)
    # Employed on ticks 43-52 (10 ticks) when the grant fires at tick 52.
    assert hh.skills_level == pytest.approx(0.5 + 0.001 * (1.0 - 0.5) * 10)


def test_contract_initial_job_search_cooldown_is_at_least_one_tick():
    """B31(b): no household starts able to job-shop on every warmup tick.

    Cooldowns do not tick during warmup, so a household drawn at 0 was
    eligible for on-the-job search on every warmup tick.
    """
    cooldowns = [HouseholdAgent(household_id=i, skills_level=0.5, age=30, cash_balance=100.0).job_search_cooldown
                 for i in range(1, 1001)]
    assert min(cooldowns) >= 1
    assert max(cooldowns) <= 52
