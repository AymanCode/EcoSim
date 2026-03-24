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


def test_contract_annual_visit_plan_by_health_bucket_is_deterministic(fixed_seed):
    """Healthcare contract: annual sampled visits follow health-bucket ranges and deterministic seeds."""
    interval = CONFIG.households.healthcare_plan_interval_ticks
    buckets = [
        (0.95, {0, 1, 2}),
        (0.60, {1, 2, 3}),
        (0.20, {2, 3, 4}),
        (0.05, {4, 5, 6}),
    ]

    for offset, (health, allowed_visits) in enumerate(buckets):
        hh = _new_household(household_id=100 + offset, health=health)
        sampled_once = hh._sample_annual_visit_count(anchor_tick=0)
        sampled_twice = hh._sample_annual_visit_count(anchor_tick=0)

        assert sampled_once == sampled_twice
        assert sampled_once in allowed_visits

        hh._refresh_annual_healthcare_visit_plan(current_tick=0)
        assert len(hh.care_plan_due_ticks) == sampled_once
        assert len(hh.care_plan_heal_deltas) == sampled_once
        assert hh.care_plan_due_ticks == sorted(hh.care_plan_due_ticks)
        assert all(0 <= due < interval for due in hh.care_plan_due_ticks)

        if sampled_once > 0:
            expected_total_heal = 1.0 - health
            assert sum(hh.care_plan_heal_deltas) == pytest.approx(expected_total_heal, abs=1e-8)


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


def test_contract_affordability_defers_visit_without_subsidy(fixed_seed):
    """Healthcare contract: when a household cannot pay and subsidy is zero, visit is deferred in queue."""
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
    assert patient.queued_healthcare_firm_id == firm.firm_id
    assert firm.healthcare_queue == [patient.household_id]
    assert patient.pending_visit_heal_delta > 0.0


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
