import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def _new_household(household_id: int, cash_balance: float = 2_000.0, health: float = 0.85) -> HouseholdAgent:
    hh = HouseholdAgent(
        household_id=household_id,
        skills_level=0.5,
        age=30,
        cash_balance=cash_balance,
    )
    hh.health = health
    hh.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
    return hh


def _new_healthcare_firm(firm_id: int = 1, price: float = 15.0) -> FirmAgent:
    return FirmAgent(
        firm_id=firm_id,
        good_name="Clinic",
        cash_balance=30_000.0,
        inventory_units=0.0,
        good_category="Healthcare",
        quality_level=6.0,
        wage_offer=40.0,
        price=price,
        expected_sales_units=80.0,
        production_capacity_units=500.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )


def test_contract_queue_request_is_not_duplicated_for_same_household(fixed_seed):
    """Healthcare contract: queueing is idempotent while household is already queued."""
    patient = _new_household(household_id=1, health=0.30)
    patient.pending_healthcare_visits = 2
    patient.next_healthcare_request_tick = 0

    doctor = _new_household(household_id=2, health=0.90)
    doctor.medical_training_status = "doctor"
    doctor.medical_doctor_capacity_cap = 2.0
    doctor.skills_level = 0.0

    firm = _new_healthcare_firm()
    government = GovernmentAgent(cash_balance=20_000.0)
    economy = Economy(households=[patient, doctor], firms=[firm], government=government)
    economy._apply_random_shocks = lambda: None

    # Override seeded staffing to this explicit deterministic setup.
    firm.employees = [doctor.household_id]
    doctor.employer_id = firm.firm_id
    doctor.wage = firm.wage_offer

    economy._enqueue_healthcare_requests()
    economy._enqueue_healthcare_requests()

    assert firm.healthcare_queue.count(patient.household_id) == 1
    assert patient.queued_healthcare_firm_id == firm.firm_id


def test_contract_sick_doctors_are_prioritized_in_healthcare_queue(fixed_seed):
    """Healthcare contract: doctors below threshold are moved to front of queue."""
    healthy_doctor = _new_household(household_id=10, health=0.85)
    healthy_doctor.medical_training_status = "doctor"

    sick_doctor = _new_household(household_id=11, health=0.40)
    sick_doctor.medical_training_status = "doctor"

    patient = _new_household(household_id=12, health=0.25)

    firm = _new_healthcare_firm()
    government = GovernmentAgent(cash_balance=20_000.0)
    economy = Economy(households=[healthy_doctor, sick_doctor, patient], firms=[firm], government=government)

    firm.healthcare_queue = [healthy_doctor.household_id, patient.household_id, sick_doctor.household_id]
    economy._prioritize_healthcare_queue(firm)

    assert firm.healthcare_queue[0] == sick_doctor.household_id
    assert firm.healthcare_queue[1:] == [healthy_doctor.household_id, patient.household_id]


def test_contract_completed_visits_respect_capacity_and_no_inventory(fixed_seed):
    """Healthcare contract: completed visits are capped by doctor capacity and inventory stays zero."""
    doctor_a = _new_household(household_id=1, health=0.9)
    doctor_a.medical_training_status = "doctor"
    doctor_a.medical_doctor_capacity_cap = 2.0
    doctor_a.skills_level = 0.0  # 2.0 visits

    doctor_b = _new_household(household_id=2, health=0.9)
    doctor_b.medical_training_status = "doctor"
    doctor_b.medical_doctor_capacity_cap = 2.0
    doctor_b.skills_level = 0.0  # 2.0 visits

    patients = []
    for idx in range(3, 9):
        hh = _new_household(household_id=idx, cash_balance=1_000.0, health=0.25)
        hh.pending_healthcare_visits = 2
        hh.next_healthcare_request_tick = 0
        patients.append(hh)

    firm = _new_healthcare_firm(price=15.0)
    government = GovernmentAgent(cash_balance=50_000.0)
    economy = Economy(households=[doctor_a, doctor_b] + patients, firms=[firm], government=government)
    economy._apply_random_shocks = lambda: None

    # Neutralize seeded workforce assignments from economy initialization.
    for hh in patients:
        hh.medical_training_status = "none"
        hh.employer_id = None
        hh.wage = 0.0

    firm.employees = [doctor_a.household_id, doctor_b.household_id]
    doctor_a.medical_training_status = "doctor"
    doctor_b.medical_training_status = "doctor"
    doctor_a.pending_healthcare_visits = 0
    doctor_b.pending_healthcare_visits = 0
    doctor_a.employer_id = firm.firm_id
    doctor_b.employer_id = firm.firm_id
    doctor_a.wage = firm.wage_offer
    doctor_b.wage = firm.wage_offer

    economy._enqueue_healthcare_requests()
    assert len(firm.healthcare_queue) == len(patients)

    per_firm_sales = {}
    economy._process_healthcare_services(per_firm_sales)

    expected_capacity = 4.0
    completed = firm.healthcare_completed_visits_last_tick
    assert completed <= expected_capacity + 1e-8
    assert completed == pytest.approx(4.0, abs=1e-8)
    assert len(firm.healthcare_queue) == len(patients) - int(completed)
    assert firm.inventory_units == pytest.approx(0.0, abs=1e-8)

    sales = per_firm_sales.get(firm.firm_id, {"units_sold": 0.0, "revenue": 0.0})
    assert sales["units_sold"] == pytest.approx(completed, abs=1e-8)
    assert economy.healthcare_completed_visits_this_tick == pytest.approx(completed, abs=1e-8)
    assert economy.healthcare_attempted_slots_this_tick == pytest.approx(expected_capacity, abs=1e-8)


def test_contract_affordability_rejects_visit_without_subsidy(fixed_seed):
    """Healthcare contract: unaffordable visits are denied and removed from the queue."""
    patient = _new_household(household_id=1, cash_balance=2.0, health=0.25)
    patient.pending_healthcare_visits = 2
    patient.next_healthcare_request_tick = 0
    initial_health = patient.health

    doctor = _new_household(household_id=2, health=0.9)
    doctor.medical_training_status = "doctor"
    doctor.medical_doctor_capacity_cap = 2.0
    doctor.skills_level = 0.0

    firm = _new_healthcare_firm(price=30.0)
    government = GovernmentAgent(cash_balance=50_000.0)
    economy = Economy(households=[patient, doctor], firms=[firm], government=government)
    economy._apply_random_shocks = lambda: None

    firm.employees = [doctor.household_id]
    patient.medical_training_status = "none"
    patient.employer_id = None
    patient.wage = 0.0
    doctor.medical_training_status = "doctor"
    doctor.pending_healthcare_visits = 0
    doctor.employer_id = firm.firm_id
    doctor.wage = firm.wage_offer

    assert CONFIG.government.healthcare_visit_subsidy_share == pytest.approx(0.0, abs=1e-12)

    economy._enqueue_healthcare_requests()
    assert firm.healthcare_queue == [patient.household_id]

    per_firm_sales = {}
    economy._process_healthcare_services(per_firm_sales)

    assert firm.healthcare_completed_visits_last_tick == pytest.approx(0.0, abs=1e-8)
    assert economy.healthcare_affordability_rejects_this_tick == pytest.approx(1.0, abs=1e-8)
    assert patient.health == pytest.approx(initial_health, abs=1e-8)
    assert patient.queued_healthcare_firm_id is None
    assert patient.healthcare_queue_enter_tick == -1
    assert firm.healthcare_queue == []
    assert patient.pending_visit_heal_delta > 0.0
    assert economy.last_healthcare_events[-1]["event_type"] == "visit_denied_affordability"


def _two_doctor_clinic(price: float, expected_visits: float) -> FirmAgent:
    """Two doctors at the 40 wage offer, 2 visits each: 4 slots, an 80/week wage bill."""
    firm = _new_healthcare_firm(price=price)
    firm.healthcare_capacity_per_worker = 2.0
    firm.employees = [1, 2]
    firm.actual_wages = {1: 80.0, 2: 100.0}
    firm.unit_cost = 45.0
    firm.min_price = 1.0
    firm.healthcare_arrivals_ema = expected_visits
    return firm


def test_contract_healthcare_price_targets_doctor_labor_cost_plus_margin(fixed_seed):
    """When requests fill every slot, the price is the wage bill per slot plus 15%."""
    firm = _two_doctor_clinic(price=22.0, expected_visits=4.0)

    price_plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.5)

    # 80 / 4 slots = 20; 20 * 1.15 = 23 (no profit tax).
    assert price_plan["price_next"] == pytest.approx(23.0)
    assert price_plan["pricing_reason"] == "healthcare_labor_margin_target"
    assert firm.decision_diagnostics["healthcare_break_even_price"] == pytest.approx(20.0)
    assert firm.decision_diagnostics["healthcare_target_margin"] == pytest.approx(0.15)


def test_contract_healthcare_price_spreads_wages_over_expected_visits(fixed_seed):
    """Half-used slots: the wage bill is spread over the visits patients ask for, not idle slots."""
    firm = _two_doctor_clinic(price=45.0, expected_visits=2.0)

    price_plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.5)

    # 80 / 2 expected visits = 40; 40 * 1.15 = 46.
    assert firm.decision_diagnostics["healthcare_break_even_price"] == pytest.approx(40.0)
    assert price_plan["price_next"] == pytest.approx(46.0)


def test_contract_healthcare_expected_visits_are_capped_at_slots(fixed_seed):
    """More requests than slots does not lower the price below the full-slot cost."""
    firm = _two_doctor_clinic(price=22.0, expected_visits=10.0)

    price_plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.5)

    assert firm.decision_diagnostics["healthcare_break_even_price"] == pytest.approx(20.0)
    assert price_plan["price_next"] == pytest.approx(23.0)


@pytest.mark.parametrize("price, expected_next", [(9.0, 10.35), (40.0, 34.0)])
def test_contract_healthcare_price_moves_at_most_15_percent_a_week(fixed_seed, price, expected_next):
    """Target 23: from 9 the price rises to 9 * 1.15; from 40 it falls to 40 * 0.85."""
    firm = _two_doctor_clinic(price=price, expected_visits=4.0)

    price_plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.5)

    assert price_plan["price_next"] == pytest.approx(expected_next)


def _baseline_clinic(price: float) -> FirmAgent:
    """The default 1,000-household economy's clinic (seed 42): 20 doctors at the 36 minimum wage."""
    firm = _new_healthcare_firm(firm_id=4, price=price)
    firm.is_baseline = True
    firm.productivity_per_worker = 11.9  # goods units per worker; a doctor delivers 2.2 visits
    firm.healthcare_capacity_per_worker = 2.2
    firm.policy_minimum_wage = 36.0
    firm.wage_offer = 36.0
    firm.employees = list(range(1, 21))
    firm.actual_wages = {i: 36.0 for i in firm.employees}
    firm.min_price = 5.0
    return firm


def test_contract_baseline_healthcare_price_covers_payroll_at_observed_visits(fixed_seed):
    """Seed 42 on main: 21 requests a week for 44 slots, price fixed at 19.43, a loss every week."""
    firm = _baseline_clinic(price=19.43)
    firm.healthcare_arrivals_ema = 21.0

    for _ in range(12):  # weekly pricing rounds; the price moves at most 15% a week
        plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.1, profit_tax_rate=0.2)
        firm.apply_price_and_wage_updates(plan, {"wage_offer_next": 36.0})

    assert firm.price * 21.0 >= 36.0 * 20


def test_contract_baseline_healthcare_warmup_prices_from_visit_slots(fixed_seed):
    """Warmup uses the doctors' visit slots, not goods productivity (36 / 11.9 gave the 5 floor)."""
    firm = _baseline_clinic(price=19.0)
    firm.healthcare_arrivals_ema = 5.0  # warmup demand is not used for the price

    plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.1, in_warmup=True, profit_tax_rate=0.2)

    # 36 / 2.2 = 16.364 per slot; * (1 + 0.15 / 0.8) = 19.432.
    assert plan["price_next"] == pytest.approx(19.4318, abs=1e-4)


@pytest.mark.parametrize("cash", [0.0, 1_000_000.0])
def test_contract_healthcare_buys_no_capital(fixed_seed, cash):
    """Visit capacity is doctors x visits; a capital unit adds none, so a profitable clinic buys none."""
    firm = _baseline_clinic(price=45.0)
    firm.cash_balance = cash
    firm.smoothed_profit_margin = 0.15
    capital_before = firm.capital_stock

    firm.plan_capital_investment(bank=None)

    assert not firm.needs_investment_loan
    assert firm.capital_stock == pytest.approx(capital_before)
    assert firm.cash_balance == pytest.approx(cash)


def test_contract_healthcare_price_fix_flag_is_on_by_default():
    assert CONFIG.firms.fix_healthcare_price_covers_payroll is True


def test_contract_healthcare_flag_off_restores_full_slot_price(fixed_seed, monkeypatch):
    """Flag off: 80 / 4 slots * 1.15 = 23 in one step, whatever the requests."""
    monkeypatch.setattr(CONFIG.firms, "fix_healthcare_price_covers_payroll", False)
    firm = _two_doctor_clinic(price=9.0, expected_visits=2.0)

    price_plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.5)

    assert price_plan["price_next"] == pytest.approx(23.0)


def test_contract_healthcare_flag_off_restores_goods_unit_warmup_price(fixed_seed, monkeypatch):
    """Flag off: the generic baseline warmup rule, 36 / 11.9 * (1 + 0.05 / 0.8) = 3.214."""
    monkeypatch.setattr(CONFIG.firms, "fix_healthcare_price_covers_payroll", False)
    firm = _baseline_clinic(price=19.0)

    plan = firm.plan_pricing(sell_through_rate=0.0, unemployment_rate=0.1, in_warmup=True, profit_tax_rate=0.2)

    assert plan["price_next"] == pytest.approx(3.2143, abs=1e-4)


def test_contract_healthcare_flag_off_restores_capital_purchase(fixed_seed, monkeypatch):
    monkeypatch.setattr(CONFIG.firms, "fix_healthcare_price_covers_payroll", False)
    firm = _baseline_clinic(price=45.0)
    firm.cash_balance = 0.0
    firm.smoothed_profit_margin = 0.15

    firm.plan_capital_investment(bank=None)

    assert firm.needs_investment_loan


def test_contract_healthcare_excess_margin_is_shifted_to_doctor_bonus(fixed_seed):
    firm = _new_healthcare_firm(price=100.0)
    firm.employees = [1, 2]
    firm.actual_wages = {1: 20.0, 2: 20.0}
    firm.wage_offer = 20.0
    firm.last_tick_total_costs = 40.0
    firm.net_profit = 60.0
    firm.cash_balance = 1_000.0
    # The economy sets the binding policy minimum before planning; it is above
    # the config floor (20), so base wages reset to it (audit B19).
    firm.policy_minimum_wage = 36.0

    firm.adjust_wages_to_revenue_ratio(revenue=100.0)

    expected_bonus_pool = 60.0 - (100.0 * CONFIG.firms.healthcare_target_profit_margin)
    assert sum(firm.actual_wages.values()) == pytest.approx(36.0 * 2)
    assert firm.wage_offer == pytest.approx(36.0)
    assert firm.pending_healthcare_worker_bonus == pytest.approx(expected_bonus_pool)
    assert firm.decision_diagnostics["healthcare_base_wage_reset_to_minimum"] is True


def test_contract_healthcare_worker_bonus_pays_doctors_as_dividend_income(fixed_seed):
    doctor_a = _new_household(household_id=1)
    doctor_b = _new_household(household_id=2)
    firm = _new_healthcare_firm(price=100.0)
    firm.employees = [1, 2]
    firm.pending_healthcare_worker_bonus = 50.0
    firm.cash_balance = 1_000.0

    paid = firm.distribute_healthcare_worker_bonus({1: doctor_a, 2: doctor_b})

    assert paid == pytest.approx(50.0)
    assert firm.cash_balance == pytest.approx(950.0)
    assert doctor_a.cash_balance == pytest.approx(2_025.0)
    assert doctor_b.cash_balance == pytest.approx(2_025.0)
    assert doctor_a.last_dividend_income == pytest.approx(25.0)
    assert doctor_b.last_dividend_income == pytest.approx(25.0)


def test_contract_doctors_stay_healthy_each_tick(tiny_economy_factory):
    """Healthcare contract: doctor health lock keeps doctors healthy every tick."""
    economy = tiny_economy_factory(
        num_households=6,
        num_firms_per_category=1,
        include_healthcare=True,
        include_housing=False,
        include_services=False,
        baseline_firms=False,
        disable_shocks=True,
        seed=707,
    )

    doctor = economy.households[0]
    doctor.medical_training_status = "doctor"
    doctor.health = 0.15

    healthcare_firm = next(f for f in economy.firms if f.good_category.lower() == "healthcare")
    healthcare_firm.employees = [doctor.household_id]
    doctor.employer_id = healthcare_firm.firm_id
    doctor.wage = healthcare_firm.wage_offer

    economy.step()
    assert doctor.health == pytest.approx(CONFIG.households.doctor_health_lock_value, abs=1e-8)

    # Re-apply damage and ensure lock still holds on subsequent ticks.
    doctor.health = 0.2
    economy.step()
    assert doctor.health == pytest.approx(CONFIG.households.doctor_health_lock_value, abs=1e-8)


def test_contract_healthcare_wages_are_pinned_to_the_policy_minimum_wage(tiny_economy_factory):
    """B19: firms floor and pin wages at the binding policy minimum, not the config floor.

    Before the fix `apply_price_and_wage_updates` pinned healthcare wage offers and
    wages to `CONFIG.firms.minimum_wage_floor` (20) while the government's minimum
    wage (`get_minimum_wage()`, 36 at the default policy) was higher.
    """
    economy = tiny_economy_factory(
        num_households=8,
        include_housing=False,
        include_services=False,
        baseline_firms=False,
        seed=808,
    )
    policy_minimum = economy.government.get_minimum_wage()
    assert policy_minimum > CONFIG.firms.minimum_wage_floor

    healthcare = next(f for f in economy.firms if f.good_category.lower() == "healthcare")
    for _ in range(2):
        economy.step()
        assert healthcare.wage_offer == pytest.approx(policy_minimum)
        for worker_id in healthcare.employees:
            assert healthcare.actual_wages[worker_id] == pytest.approx(policy_minimum)


def test_contract_profitable_healthcare_firm_spends_nothing_on_rd(fixed_seed):
    """R&D buys quality, and no healthcare decision reads quality.

    Care is left out of the shopping snapshots, provider choice reads queue and
    price, and healing reads the patient's missing health. Before this rule the
    generic R&D step still spent up to 10% of a profitable week's revenue.
    """
    firm = _new_healthcare_firm(price=40.0)
    firm.cash_balance = 1_000.0
    firm.net_profit = 300.0
    rd_before = firm.accumulated_rd_investment

    spent = firm.apply_rd_and_quality_update(revenue=1_000.0)

    assert spent == 0.0
    assert firm.cash_balance == pytest.approx(1_000.0)
    assert firm.accumulated_rd_investment == pytest.approx(rd_before)


def test_contract_profitable_food_firm_still_spends_on_rd(fixed_seed):
    """Guard: the healthcare exception does not switch R&D off for goods firms."""
    firm = _new_healthcare_firm(price=40.0)
    firm.good_category = "Food"
    firm.good_name = "Food"
    firm.cash_balance = 1_000.0
    firm.net_profit = 300.0

    spent = firm.apply_rd_and_quality_update(revenue=1_000.0)

    assert spent > 0.0
    assert firm.cash_balance == pytest.approx(1_000.0 - spent)
