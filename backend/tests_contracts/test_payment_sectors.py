"""Focused money, quantity, and claim checks for PS3 sector adapters."""

from types import SimpleNamespace

import pytest

from config import clone_config, use_config
from payment_sectors import (PaymentGoodsMarket, _sale_quantity, apply_payment_housing_renewals,
                             payment_deposit_quotes,
                             enqueue_payment_care_requests, requeue_payment_care_due,
                             settle_payment_care, settle_payment_rent)
from payments import PaymentBook


class Actor(SimpleNamespace):
    def add_ledger_flow(self, key, amount):
        self.flows[key] = self.flows.get(key, 0.0) + amount


def _household(hid, cash):
    return Actor(household_id=hid, cash_balance=cash, goods_inventory={},
                 services_consumed_this_tick=0.0, min_food_per_tick=2.0,
                 flows={}, renting_from_firm_id=None, monthly_rent=0.0,
                 owns_housing=False, rent_arrears=0.0, rent_notice_remaining=0,
                 wage=100.0, employer_id=1, is_employed=True,
                 bank_deposit=0.0, payment_pre_policy_liquidity=0.0,
                 payment_care_due_tick=-1, pending_healthcare_visits=0,
                 queued_healthcare_firm_id=None, next_healthcare_request_tick=10**9)


def _firm(fid, name, category, price, stock):
    return Actor(firm_id=fid, good_name=name, good_category=category, price=price,
                 inventory_units=stock, last_units_produced=stock, cash_balance=0.0,
                 current_tenants=[], max_rental_units=1)


def _economy(households, firms, subsidy=0.0):
    economy = Actor(households=households, firms=firms,
                    household_lookup={h.household_id: h for h in households},
                    firm_lookup={f.firm_id: f for f in firms},
                    government=Actor(sector_subsidy_target="food", _sector_subsidy_rate=0.5,
                                     cash_balance=subsidy, get_unemployment_benefit_level=lambda: 0.0),
                    payment_state={"restrictions": {"G": subsidy, "rent": 0.0, "care": 0.0}},
                    sector_subsidy_remaining_this_tick=subsidy,
                    food_unmet_demand=0.0, services_unmet_demand=0.0,
                    services_unmet_demand_by_firm={}, current_tick=0,
                    cached_wage_percentiles=(None, None, None),
                    last_housing_diagnostics={})
    economy._estimated_firm_market_supply = lambda f, current_tick_capacity: f.last_units_produced if f.good_category == "Services" else f.inventory_units
    economy._effective_market_price = lambda f, available: f.price
    economy._record_firm_unmet_demand = lambda fid, qty: None
    economy._payment_spend_restriction = lambda name, amount: _spend_restriction(economy, name, amount)
    economy.payment_book = PaymentBook(economy)
    return economy


def _spend_restriction(economy, name, amount):
    if economy.payment_state["restrictions"][name] + 1e-6 < amount:
        return False
    economy.payment_state["restrictions"][name] -= amount
    economy.government.cash_balance -= amount
    if name == "G":
        economy.sector_subsidy_remaining_this_tick -= amount
    return True


def test_subsidy_exhaustion_shrinks_delivered_units_and_preserves_money():
    hh = _household(1, 20.0)
    food = _firm(7, "BasicFood", "Food", 5.0, 8.0)
    econ = _economy([hh], [food], subsidy=5.0)
    market = PaymentGoodsMarket(econ, {1: {"planned_purchases": {7: 8.0}}}, [food])
    market.first_pass()
    market.second_pass()
    purchases, sales = market.finish()
    assert purchases[1]["BasicFood"][0] == pytest.approx(5.0)
    assert sales[7] == pytest.approx({"units_sold": 5.0, "revenue": 25.0})
    assert hh.cash_balance == pytest.approx(0.0)
    assert hh.goods_inventory["BasicFood"] == pytest.approx(5.0)
    assert food.inventory_units == pytest.approx(3.0)
    assert econ.payment_book.clearing_cash == pytest.approx(25.0)
    assert econ.payment_book.clearing_payables[7] == pytest.approx(25.0)
    assert econ.food_unmet_demand == pytest.approx(3.0)
    assert econ.payment_book.release_firm_receipts(food) == pytest.approx(25.0)
    assert food.cash_balance == pytest.approx(25.0)
    assert econ.payment_book.clearing_cash == pytest.approx(0.0)


def test_failed_food_target_does_not_spend_cash_or_consume_need():
    hh = _household(1, 10.0)
    empty = _firm(1, "BasicFood", "Food", 5.0, 0.0)
    stocked = _firm(2, "OtherFood", "Food", 5.0, 2.0)
    econ = _economy([hh], [empty, stocked])
    market = PaymentGoodsMarket(econ, {1: {"planned_purchases": {1: 2.0, 2: 2.0}}}, [empty, stocked])
    market.first_pass()
    assert hh.goods_inventory == {"OtherFood": pytest.approx(2.0)}
    assert hh.cash_balance == pytest.approx(0.0)
    market.second_pass()
    market.finish()
    assert econ.food_unmet_demand == pytest.approx(2.0)


def test_partial_rent_creates_mirrored_arrears_then_expires_after_two_more_settlements():
    hh = _household(1, 5.0)
    landlord = _firm(2, "Housing", "Housing", 10.0, 0.0)
    landlord.current_tenants = [1]
    hh.renting_from_firm_id = 2
    hh.monthly_rent = 10.0
    econ = _economy([hh], [landlord])
    econ.government._sector_subsidy_rate = 0.0
    settle_payment_rent(econ)
    assert hh.rent_arrears == pytest.approx(5.0)
    assert landlord.rent_arrears_receivable_by_tenant[1] == pytest.approx(5.0)
    assert hh.rent_notice_remaining == 2
    assert landlord.cash_balance == pytest.approx(5.0)
    for remaining in (1, 0):
        settle_payment_rent(econ)
        assert hh.rent_notice_remaining == remaining
    assert hh.renting_from_firm_id is None
    assert 1 not in landlord.current_tenants
    assert hh.rent_arrears == 0.0
    assert landlord.rent_arrears_receivable_by_tenant == {}


def test_piecewise_subsidy_math_handles_exact_cap_boundary():
    assert _sale_quantity(5.0, 8.0, 8.0, 20.0, 0.5, 5.0) == pytest.approx(5.0)
    assert _sale_quantity(0.0, 8.0, 3.0, 0.0, 0.5, 0.0) == pytest.approx(3.0)


def test_deposit_quote_uses_same_services_effective_floor_as_goods_book():
    hh = _household(1, 0.0)
    firm = _firm(3, "BasicService", "Services", 10.0, 5.0)
    econ = _economy([hh], [firm])
    econ._effective_market_price = lambda f, supply: 20.0
    quote = payment_deposit_quotes(econ, {1: {"planned_purchases": {3: 2.0}}}, {})
    market = PaymentGoodsMarket(econ, {1: {"planned_purchases": {3: 2.0}}}, [firm])
    assert quote[1] == pytest.approx(40.0)
    assert market.prices[3] == pytest.approx(20.0)


def test_lease_renews_only_on_due_tick_and_caps_incumbent_not_ask():
    hh = _household(1, 100.0)
    hh.renting_from_firm_id = 2
    hh.monthly_rent = 10.0
    hh.lease_renewal_tick = 52
    landlord = _firm(2, "Housing", "Housing", 20.0, 0.0)
    econ = _economy([hh], [landlord])
    econ.government.rent_stabilization_level = "soft"
    econ.current_tick = 51
    apply_payment_housing_renewals(econ)
    assert hh.monthly_rent == 10.0
    econ.current_tick = 52
    apply_payment_housing_renewals(econ)
    assert hh.monthly_rent == pytest.approx(10.5)
    assert hh.lease_renewal_tick == 104
    assert landlord.price == 20.0


def test_zero_charge_request_with_zero_liquidity_keeps_one_due_episode(monkeypatch):
    monkeypatch.setattr("payment_loans.prepare_household_dues", lambda economy: {1: 0.0})
    hh = _household(1, 0.0)
    hh.health = 0.2
    hh.healthcare_critical_threshold = 0.3
    hh.healthcare_request_base_chance_pct = 0.0
    hh.pending_healthcare_visits = 1
    hh.payment_care_due_tick = 0
    hh.payment_care_episode_id = 9
    hh.next_healthcare_request_tick = 0
    hh.queued_healthcare_firm_id = None
    hh.healthcare_queue_enter_tick = -1
    hh.payment_care_due_retry = False
    hh.payment_care_accepted_quote = float("inf")
    hh._deterministic_unit_random = lambda tick, salt: 0.99
    clinic = _firm(8, "Clinic", "Healthcare", 25.0, 0.0)
    clinic.healthcare_queue = []
    clinic.healthcare_requests_last_tick = 0.0
    clinic.healthcare_arrivals_ema = 0.0
    econ = _economy([hh], [clinic])
    econ.payment_care_mode = "covered"
    econ._healthcare_firms = lambda: [clinic]
    econ._choose_healthcare_provider = lambda household, firms: clinic
    econ.healthcare_requests_this_tick = 0.0
    enqueue_payment_care_requests(econ)
    assert hh.queued_healthcare_firm_id == 8
    assert hh.payment_care_episode_id == 9
    assert hh.payment_care_due_tick == 0
    assert hh.payment_care_planning_liquidity == 0.0
    assert clinic.healthcare_queue == [1]
    assert econ.healthcare_requests_this_tick == 1.0
    enqueue_payment_care_requests(econ)
    assert clinic.healthcare_queue == [1]
    assert econ.healthcare_requests_this_tick == 1.0


def test_queued_due_age_survives_wait_and_higher_price_requires_new_consent(monkeypatch):
    monkeypatch.setattr("payment_loans.prepare_household_dues", lambda economy: {})
    hh = _household(1, 100.0)
    hh.health = 0.5
    hh.healthcare_critical_threshold = 0.3
    hh.healthcare_request_base_chance_pct = 0.0
    hh.pending_healthcare_visits = 1
    hh.pending_visit_heal_delta = 0.2
    hh.payment_care_episode_id = 4
    hh.payment_care_due_tick = 1
    hh.next_healthcare_request_tick = 0
    hh.queued_healthcare_firm_id = 8
    hh.healthcare_queue_enter_tick = 1
    hh.payment_care_accepted_quote = 20.0
    hh.payment_care_due_retry = False
    hh._deterministic_unit_random = lambda tick, salt: 0.0
    clinic = _firm(8, "Clinic", "Healthcare", 25.0, 0.0)
    clinic.employees = []
    clinic.healthcare_queue = [1]
    clinic.healthcare_capacity_carryover = 0.0
    clinic.healthcare_completed_visits_last_tick = 0.0
    clinic.healthcare_idle_streak = 0
    clinic.healthcare_requests_last_tick = 0.0
    clinic.healthcare_arrivals_ema = 0.0
    doctor = _household(2, 0.0)
    doctor.employer_id = 8
    doctor.medical_visit_capacity = lambda: 1.0
    clinic.employees = [2]
    econ = _economy([hh, doctor], [clinic])
    econ.current_tick = 6
    econ.payment_care_mode = "patient_pay"
    econ._healthcare_firms = lambda: [clinic]
    econ._choose_healthcare_provider = lambda household, firms: clinic
    econ._prioritize_healthcare_queue = lambda firm: None
    econ.healthcare_requests_this_tick = 0.0
    econ.healthcare_attempted_slots_this_tick = 0.0
    econ.healthcare_completed_visits_this_tick = 0.0
    econ.healthcare_affordability_rejects_this_tick = 0.0
    econ.last_healthcare_events = []
    enqueue_payment_care_requests(econ)
    assert econ.payment_care_due_ages[1] == 5
    settle_payment_care(econ, econ.payment_book.receipts)
    assert hh.payment_care_due_tick == 1
    assert hh.payment_care_episode_id == 4
    assert hh.payment_care_accepted_quote == float("inf")
    assert hh.queued_healthcare_firm_id is None
    econ.current_tick = 7
    requeue_payment_care_due(econ)
    assert hh.queued_healthcare_firm_id is None  # the higher quote needs a decision
    enqueue_payment_care_requests(econ)
    assert econ.payment_care_due_ages[1] == 6
    assert hh.payment_care_accepted_quote == 25.0
    assert hh.queued_healthcare_firm_id == 8


def test_real_two_tick_unfunded_care_retries_same_episode_without_new_arrival(factory, monkeypatch):
    cfg = clone_config()
    cfg.payment_sequence = "income_first"
    cfg.payment_care_mode = "patient_pay"
    cfg.payment_assistance = "reserve"
    with use_config(cfg):
        patient = factory.household(household_id=1, cash_balance=0.0, health=0.2,
                                    pending_healthcare_visits=1, payment_care_due_tick=0,
                                    payment_care_episode_id=1, next_healthcare_request_tick=0)
        patient.healthcare_critical_threshold = 0.3
        doctor = factory.household(household_id=2, employer_id=8, wage=40.0,
                                   medical_training_status="doctor", cash_balance=0.0)
        clinic = factory.firm(firm_id=8, category="Healthcare", is_baseline=True,
                              employees=[2], actual_wages={2: 40.0}, wage_offer=40.0,
                              price=25.0, cash_balance=1000.0)
        government = factory.government(cash_balance=0.0, unemployment_benefit_level=0.0,
                                        wage_tax_rate=0.0, profit_tax_rate=0.0)
        government.register_baseline_firm("Healthcare", 8)
        economy = factory.economy(households=[patient, doctor], firms=[clinic], government=government)
        economy.warmup_ticks = 100
        economy.configure_stabilizers(households=False, firms=False, government=False)
        monkeypatch.setattr(economy, "_run_labor_matching", lambda *_: (
            {8: {"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {2: 40.0}}},
            {1: {"employer_id": None, "wage": 0.0, "employer_category": None},
             2: {"employer_id": 8, "wage": 40.0, "employer_category": "Healthcare"}},
        ))
        monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *_: {
            1: {"planned_purchases": {}, "budget": 0.0},
            2: {"planned_purchases": {}, "budget": 0.0},
        })
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: 0)
        economy.step()
        first_arrivals = economy.healthcare_requests_this_tick
        first_id = patient.payment_care_episode_id
        assert patient.payment_care_due_retry
        economy.step()
    assert first_arrivals == 1.0
    assert economy.healthcare_requests_this_tick == 0.0
    assert patient.payment_care_episode_id == first_id
    assert patient.payment_care_due_tick == 0
    assert patient.healthcare_consumed_this_tick == 0.0
    assert economy.payment_care_due_ages[1] >= 1


def test_qualified_care_requires_full_funding_and_preserves_due_episode():
    patient = _household(1, 0.0)
    patient.health = 0.5
    patient.queued_healthcare_firm_id = 8
    patient.healthcare_queue_enter_tick = 0
    patient.pending_visit_heal_delta = 0.2
    patient.payment_care_accepted_quote = 25.0
    patient.medical_training_status = "none"
    patient.healthcare_consumed_this_tick = 0.0
    patient.last_healthcare_units = 0.0
    patient.last_healthcare_spend = 0.0
    patient.last_healthcare_provider_id = None
    patient.last_checkup_tick = -1
    patient.payment_care_due_retry = False
    patient.pending_healthcare_visits = 1
    patient.payment_care_due_tick = 0
    patient.next_healthcare_request_tick = 0
    doctor = _household(2, 0.0)
    doctor.employer_id = 8
    doctor.medical_visit_capacity = lambda: 1.0
    firm = _firm(8, "Clinic", "Healthcare", 25.0, 0.0)
    firm.employees = [2]
    firm.healthcare_queue = [1]
    firm.healthcare_capacity_carryover = 0.0
    firm.healthcare_completed_visits_last_tick = 0.0
    firm.healthcare_idle_streak = 0
    econ = _economy([patient, doctor], [firm])
    econ.payment_care_mode = "covered"
    econ.payment_care_remaining = 20.0
    econ.payment_state["restrictions"]["care"] = 20.0
    econ.government.cash_balance = 20.0
    econ._healthcare_firms = lambda: [firm]
    econ._prioritize_healthcare_queue = lambda f: None
    econ.healthcare_attempted_slots_this_tick = 0.0
    econ.healthcare_completed_visits_this_tick = 0.0
    econ.healthcare_affordability_rejects_this_tick = 0.0
    econ.last_healthcare_events = []
    sales = {}
    settle_payment_care(econ, sales)
    assert sales == {}
    assert patient.health == 0.5
    assert patient.payment_care_due_retry
    assert firm.healthcare_queue == []
    assert econ.payment_book.clearing_cash == 0.0
    assert econ.payment_state["restrictions"]["care"] == 20.0

    # The due episode is offered again against a fully funded care envelope.
    patient.queued_healthcare_firm_id = 8
    patient.payment_care_due_retry = False
    firm.healthcare_queue = [1]
    econ.payment_care_remaining = 25.0
    econ.payment_state["restrictions"]["care"] = 25.0
    econ.government.cash_balance = 25.0
    settle_payment_care(econ, econ.payment_book.receipts)
    sales = econ.payment_book.receipts
    assert sales[8] == pytest.approx({"units_sold": 1.0, "revenue": 25.0})
    assert patient.health == pytest.approx(0.7)
    assert patient.healthcare_consumed_this_tick == 1.0
    assert econ.payment_book.clearing_cash == pytest.approx(25.0)
    assert econ.payment_state["restrictions"]["care"] == pytest.approx(0.0)
