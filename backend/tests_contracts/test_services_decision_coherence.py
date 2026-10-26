"""Services intent survives pricing, lending and matching boundaries."""

from types import SimpleNamespace

import pytest

from agents import BankAgent
from config import clone_config, use_config
from economy import Economy
from payment_sectors import PaymentGoodsMarket
from payment_government import activate_payment_services_slots
from payments import PaymentBook


SEQUENCES = ("income_first", "income_late")


def salon(factory, workers=5, slots=5, wage=20.0, price=9.0):
    firm = factory.firm(firm_id=90, category="Services", is_baseline=False,
                        production_capacity_units=float(slots), cash_balance=100_000.0,
                        employees=list(range(1, workers + 1)),
                        actual_wages={hid: wage for hid in range(1, workers + 1)},
                        inventory_units=0.0, owners=[], ceo_household_id=None)
    # Personality sampling initializes these; this fixture fixes economic inputs.
    firm.units_per_worker = 5.0
    firm.wage_offer = wage
    firm.price = price
    firm.markup = 0.5
    firm.min_price = 0.01
    firm.age_in_ticks = 100
    firm.last_units_produced = workers * 5.0
    firm.last_units_sold = 10.0
    firm.last_revenue = firm.last_units_sold * price
    firm.last_profit = firm.last_revenue - workers * wage
    return firm


def observe_space(firm, *, unmet=2.0, sold=None):
    firm.age_in_ticks += 1
    return firm.consider_service_infrastructure_upgrade(
        SimpleNamespace(services_unmet_demand_by_firm={firm.firm_id: unmet}),
        current_units_sold=firm.last_units_produced if sold is None else sold,
    )


@pytest.mark.parametrize("sequence", SEQUENCES)
@pytest.mark.parametrize("tax", (0.0, 0.2))
def test_quote_target_does_not_compound_through_stabilization_and_market(factory, sequence, tax):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, workers=10, slots=10, wage=50.0, price=15.0)
        firm.last_units_produced = 50.0
        firm.last_units_sold = 42.5
        firm.unit_cost = 1.0  # Accounting cost is deliberately a different basis.
        firm.pricing_profit_tax_rate_known = True
        firm.pricing_profit_tax_rate = tax
        economy = factory.economy(households=[], firms=[firm])
        economy.government.price_stabilization_target = "Services"
        economy.government.price_stabilization_level = "soft"
        economy.payment_book = PaymentBook(economy, timing=sequence)
        prices = []
        for _ in range(104):
            plan = firm.plan_pricing(0.85, 0.1, profit_tax_rate=tax)
            economy._apply_price_stabilization_to_plan(firm, plan)
            market = PaymentGoodsMarket(economy, {}, [firm])
            prices.append(market.prices[firm.firm_id])
            firm.apply_price_and_wage_updates(plan, {"wage_offer_next": 50.0})
        equilibrium = 10.0 * (1.0 + 0.5 / (1.0 - tax))
        assert max(prices) <= equilibrium + 1e-6
        assert firm.price == pytest.approx(equilibrium, abs=1e-6)
        assert firm.service_target_markup_after_tax == 0.5
        assert firm.markup == pytest.approx(firm.price / 10.0 - 1.0)


def test_stabilizer_measures_markup_on_services_cost(factory):
    firm = salon(factory, workers=10, slots=10, wage=50.0, price=10.0)
    firm.last_units_produced = 50.0
    firm.unit_cost = 1.0
    economy = factory.economy(households=[], firms=[firm])
    economy.government.price_stabilization_target = "Services"
    economy.government.price_stabilization_level = "soft"
    plan = firm.plan_pricing(1.0, 0.1, profit_tax_rate=0.2)
    economy._apply_price_stabilization_to_plan(firm, plan)
    assert plan["price_next"] == pytest.approx(10.30)
    assert plan["markup_next"] == pytest.approx(0.03)
    assert firm.service_target_markup_after_tax == 0.5


def test_markup_basis_fix_preserves_existing_distress_cap_exception(factory):
    firm = salon(factory, workers=10, slots=10, wage=50.0, price=1.0)
    firm.last_units_produced = 50.0
    firm.unit_cost = 1.0
    firm.cash_balance = 0.0
    economy = factory.economy(households=[], firms=[firm])
    economy.government.price_stabilization_target = "Services"
    economy.government.price_stabilization_level = "soft"
    plan = {"price_next": 12.0, "markup_next": 0.5}
    economy._apply_price_stabilization_to_plan(firm, plan)
    assert plan["price_next"] == pytest.approx(1.03)
    assert plan["markup_next"] == 0.0


@pytest.mark.parametrize("sequence", SEQUENCES)
def test_paid_public_slot_keeps_its_retained_installer_staffable(factory, sequence):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, workers=6, slots=5, price=20.0)
        firm.service_staffing_target = 5
        firm.service_full_utilization_streak = 5
        firm.service_unmet_demand_window = [2.0] * 5
        economy = factory.economy(households=[], firms=[firm])
        economy.payment_state["services_future_slots"] = [
            {"firm_id": firm.firm_id, "units": 1, "open_tick": economy.current_tick}
        ]
        assert activate_payment_services_slots(economy) == 1
        plan = firm.plan_production_and_labor(20.0, total_households=100, minimum_wage_floor=20.0)
        assert firm.production_capacity_units == 6
        assert firm.service_staffing_target == 6
        assert plan["planned_layoffs_ids"] == []
        assert plan["planned_hires_count"] == 0
        assert firm.service_full_utilization_streak == 0


def test_public_installation_starts_new_recovery_evidence_at_the_new_target(factory):
    firm = salon(factory, workers=4, slots=5, price=20.0)
    firm.service_staffing_target = 4
    for _ in range(2):
        plan = firm.plan_production_and_labor(18.0, total_households=100, minimum_wage_floor=20.0)
        assert plan["planned_hires_count"] == 0
    assert firm.service_staffing_recovery_streak == 2
    # A funded public-project installer is retained at the expanded target.
    firm.employees.append(5)
    firm.actual_wages[5] = 20.0
    firm._invalidate_wage_bill_cache()
    economy = factory.economy(households=[], firms=[firm])
    economy.payment_state["services_future_slots"] = [{"firm_id": 90, "units": 1, "open_tick": 0}]
    activate_payment_services_slots(economy)
    assert firm.service_staffing_target == 5
    assert firm.service_staffing_recovery_streak == 0
    # Lagged sales still came from four workers; they cannot validate target five.
    plan = firm.plan_production_and_labor(18.0, total_households=100, minimum_wage_floor=20.0)
    assert plan["planned_hires_count"] == 0
    assert firm.service_staffing_recovery_streak == 0
    firm.last_units_produced = 25.0
    for expected in (0, 0, 1):
        plan = firm.plan_production_and_labor(22.5, total_households=100, minimum_wage_floor=20.0)
        assert plan["planned_hires_count"] == expected


@pytest.mark.parametrize("cost,utilization,target", [(10.0, .85, 16.25), (12.0, .85, 19.5), (10.0, .95, 16.875)])
def test_price_still_responds_to_cost_and_utilization(factory, cost, utilization, target):
    firm = salon(factory, workers=10, slots=10, wage=cost * 5.0, price=15.0)
    firm.last_units_produced = 50.0
    for _ in range(104):
        plan = firm.plan_pricing(utilization, 0.1, profit_tax_rate=0.2)
        firm.apply_price_and_wage_updates(plan, {"wage_offer_next": firm.wage_offer})
    assert firm.price == pytest.approx(target, abs=1e-6)


def test_profitable_cut_waits_for_three_strong_sales_observations(factory):
    firm = salon(factory)
    firm.service_weak_demand_streak = 4
    plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
    assert len(plan["planned_layoffs_ids"]) == 1
    # Resolve the planned cut through the firm's actual labor application.
    firm.apply_labor_outcome({"confirmed_layoffs_ids": plan["planned_layoffs_ids"],
                              "hired_households_ids": [], "actual_wages": {}})
    assert len(firm.employees) == 4
    firm.last_units_produced = 20.0
    firm.last_revenue, firm.last_profit = 90.0, 10.0
    for _ in range(4):
        plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
        assert plan["planned_hires_count"] == 0
        assert not plan["planned_layoffs_ids"]
    for expected in (0, 0, 1):
        firm.last_revenue, firm.last_profit = 162.0, 82.0
        plan = firm.plan_production_and_labor(18.0, total_households=100, minimum_wage_floor=20.0)
        assert plan["planned_hires_count"] == expected
    assert firm.service_staffing_target == 5


def test_new_capacity_and_failed_recruitment_are_not_a_new_demand_trial(factory):
    firm = salon(factory, workers=2, slots=5)
    plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
    assert plan["planned_hires_count"] == 3
    plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
    assert plan["planned_hires_count"] == 3  # Last week's vacancies were unfilled.
    firm._add_service_worker_slots(1.0)
    plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
    assert plan["planned_hires_count"] == 4


def test_cash_emergency_can_still_reduce_staff_without_waiting(factory):
    firm = salon(factory)
    firm.cash_balance = 100.0
    plan = firm.plan_production_and_labor(10.0, total_households=100, minimum_wage_floor=20.0)
    assert plan["planned_layoffs_ids"]
    assert firm.service_weak_demand_streak == 1
    assert firm.service_staffing_target < 5


def test_capacity_history_counts_real_observations_and_restarts_when_understaffed(factory):
    firm = salon(factory)
    firm.cash_runway_ticks = 100.0
    for _ in range(4):
        assert not observe_space(firm)
        # Re-reading a decision within the same tick must not invent evidence.
        assert not firm.consider_service_infrastructure_upgrade(
            SimpleNamespace(services_unmet_demand_by_firm={firm.firm_id: 2.0}),
            current_units_sold=firm.last_units_produced,
        )
    assert observe_space(firm)
    firm.needs_service_infrastructure_loan = False
    firm.service_infrastructure_loan_amount = 0.0
    firm.employees.pop()
    assert not observe_space(firm)
    firm.employees.append(5)
    for _ in range(4):
        assert not observe_space(firm)
    assert observe_space(firm)


@pytest.mark.parametrize("sequence", SEQUENCES)
@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
@pytest.mark.parametrize("staffed", (False, True))
def test_both_real_loan_routes_recheck_physical_space_and_record_funding(factory, sequence, route, staffed):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, workers=5 if staffed else 2, slots=5, price=20.0)
        firm.last_revenue = firm.revenue_ema = 1000.0
        firm.service_full_utilization_streak = 5
        firm.service_unmet_demand_window = [2.0] * 5
        firm.service_staffing_target = 5
        bank = BankAgent(cash_reserves=100_000.0)
        economy = Economy(households=[], firms=[firm], government=factory.government(), bank=bank)
        economy.payment_book = PaymentBook(economy, timing=sequence)
        economy.payment_state["prior_settled_firm_operating_cashflow"] = {firm.firm_id: 1000.0}
        before = bank.cash_reserves
        if route == "long_term":
            granted = economy._maybe_offer_long_term_capital_loan(
                firm, SimpleNamespace(sell_through_rate=1.0), unemployment_rate=.5, total_households=100)
        else:
            firm.needs_service_infrastructure_loan = True  # Even a stale request must be checked.
            firm.service_infrastructure_loan_amount = 7000.0
            economy._offer_service_infrastructure_loans()
            granted = bool(bank.active_loans)
        assert bool(granted) is staffed
        if staffed:
            assert firm.production_capacity_units > 5
            assert len(firm.employees) == 5  # A loan doesn't hire workers.
            assert before - bank.cash_reserves == pytest.approx(firm.bank_loan_remaining)
            assert firm.service_staffing_target == int(firm.production_capacity_units)
            assert len(bank.active_loans) == 1
            assert firm.service_full_utilization_streak == 0
            assert firm.service_unmet_demand_window == []
        else:
            assert bank.cash_reserves == before
            assert firm.production_capacity_units == 5
            assert not bank.active_loans


@pytest.mark.parametrize("sequence", SEQUENCES)
@pytest.mark.parametrize("route", ("long_term", "infrastructure"))
@pytest.mark.parametrize("missing", ("persistence", "unmet_demand"))
def test_full_staffing_alone_does_not_qualify_for_either_loan(factory, sequence, route, missing):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, price=20.0)
        firm.last_revenue = firm.revenue_ema = 1000.0
        firm.service_full_utilization_streak = 4 if missing == "persistence" else 5
        firm.service_unmet_demand_window = [2.0] * 5 if missing == "persistence" else [0.0] * 4 + [2.0]
        bank = BankAgent(cash_reserves=100_000.0)
        economy = Economy(households=[], firms=[firm], government=factory.government(), bank=bank)
        economy.payment_book = PaymentBook(economy, timing=sequence)
        economy.payment_state["prior_settled_firm_operating_cashflow"] = {90: 1000.0}
        if route == "long_term":
            assert not economy._maybe_offer_long_term_capital_loan(
                firm, SimpleNamespace(sell_through_rate=1.0), unemployment_rate=.5, total_households=100)
        else:
            firm.needs_service_infrastructure_loan = True
            firm.service_infrastructure_loan_amount = 7000.0
            economy._offer_service_infrastructure_loans()
        assert bank.cash_reserves == 100_000.0
        assert not bank.active_loans
        assert firm.production_capacity_units == 5


@pytest.mark.parametrize("matcher", ("_match_labor", "_match_labor_fast"))
def test_matcher_cannot_invent_a_service_rehire_during_patience(factory, matcher):
    switcher = factory.household(household_id=20, employer_id=1, wage=20.0)
    incumbent = factory.firm(firm_id=1, category="Food", is_baseline=False,
                              employees=[20], actual_wages={20: 20.0})
    firm = salon(factory, workers=4)
    firm.service_staffing_target = 4
    workers = [factory.household(household_id=hid, employer_id=90, wage=20.0) for hid in firm.employees]
    economy = factory.economy(households=[switcher, *workers], firms=[incumbent, firm])
    production = {fid: {"planned_hires_count": 0, "planned_layoffs_ids": []} for fid in (1, 90)}
    wages = {fid: {"wage_offer_next": 60.0} for fid in production}
    labor = {h.household_id: {"household_id": h.household_id, "skills_level": h.skills_level,
             "reservation_wage": 10.0, "searching_for_job": h is switcher,
             "job_switching": h is switcher, "medical_only": False} for h in economy.households}
    firm_out, _ = getattr(economy, matcher)(production, wages, labor)
    assert firm_out[90]["hired_households_ids"] == []
    assert production[90]["planned_hires_count"] == 0


@pytest.mark.parametrize("sequence", SEQUENCES)
def test_three_observations_reach_real_matching_and_funded_payroll(factory, monkeypatch, sequence):
    """Only shopping intentions are fixed; matching, production and money settle."""
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, workers=4, slots=5, price=20.0)
        firm.service_staffing_target = 4
        firm.last_units_sold = 19.0
        firm.last_revenue, firm.last_profit = 380.0, 300.0
        households = [factory.household(household_id=hid, employer_id=90 if hid <= 4 else None,
                          wage=20.0 if hid <= 4 else 0.0, cash_balance=10000.0,
                          expected_wage=20.0, reservation_wage=5.0) for hid in range(1, 6)]
        economy = Economy(households=households, firms=[firm], government=factory.government(
            minimum_wage_policy="low", unemployment_benefit_level=0.0, transfer_budget=0.0))
        economy.current_tick = 40
        economy.in_warmup = False
        economy.warmup_ticks = 10
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: None)
        economy.last_tick_sales_units[90] = 19.0
        # All existing customers attempt ample orders. Their cash and actual
        # inventory/service delivery still constrain the real market.
        monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *a, **kw: {
            h.household_id: {"planned_purchases": {90: 100.0}, "budget": 2000.0} for h in households
        })
        for expected_workers in (4, 4, 5):
            economy.step()
            assert len(firm.employees) == expected_workers, (firm.service_staffing_target,
                firm.service_staffing_recovery_streak, economy.last_labor_events)
            assert all(economy.household_lookup[hid].employer_id == 90 for hid in firm.employees)
            paid = sum(economy.payment_book.current_paid_by_firm_worker.get((90, hid), 0.0)
                       for hid in firm.employees)
            assert paid == pytest.approx(economy.payment_book.funded_wages_by_firm[90])
            assert paid > 0.0
            assert economy.payment_book.clearing_cash == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("sequence", SEQUENCES)
def test_completed_market_observations_precede_real_infrastructure_funding(factory, monkeypatch, sequence):
    cfg = clone_config()
    cfg.payment_sequence = sequence
    with use_config(cfg):
        firm = salon(factory, price=20.0)
        households = [factory.household(household_id=hid, employer_id=90, wage=20.0,
                                       cash_balance=10000.0) for hid in range(1, 6)]
        bank = BankAgent(cash_reserves=100000.0)
        economy = Economy(households=households, firms=[firm], bank=bank,
                          government=factory.government(minimum_wage_policy="low",
                          unemployment_benefit_level=0.0, transfer_budget=0.0))
        economy.current_tick = 40
        economy.in_warmup = False
        economy.warmup_ticks = 10
        monkeypatch.setattr(economy, "_maybe_create_new_firms", lambda: None)
        monkeypatch.setattr(economy, "_batch_plan_consumption", lambda *a, **kw: {
            h.household_id: {"planned_purchases": {90: 100.0}, "budget": 2000.0} for h in households
        })
        for index in range(5):
            economy.step()
            if index < 4:
                assert firm.production_capacity_units == 5
                assert not bank.active_loans
        loans = [loan for loan in bank.active_loans if loan.get("subtype") == "service_infrastructure"]
        assert len(loans) == 1, (firm.service_full_utilization_streak,
            firm.service_unmet_demand_window, len(firm.employees), firm.production_capacity_units,
            economy.payment_state.get("prior_settled_firm_operating_cashflow"))
        assert loans[0]["principal"] == 7000.0
        assert firm.production_capacity_units > 5
        assert firm.service_full_utilization_streak == 0
        assert firm.service_unmet_demand_window == []
        assert len(firm.employees) == 5
        assert economy.payment_book.clearing_cash == pytest.approx(0.0, abs=1e-6)
