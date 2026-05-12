"""Contract tests for household dividend income perception.

Current household planning tracks aggregate dividend income and firm IDs that
paid dividends. It does not expose the older ``last_after_tax_income`` or
``last_dividend_by_firm`` diagnostic fields.
"""

import pytest

from agents import HouseholdAgent
from config import CONFIG
from tests_contracts.factories import make_firm, make_household


BENEFIT = CONFIG.government.default_unemployment_benefit
PRICES = {"Food": 5.0, "Services": 10.0}


def _plan(hh: HouseholdAgent, **kwargs) -> dict:
    return hh.plan_consumption(
        market_prices=PRICES,
        unemployment_rate=0.05,
        **kwargs,
    )


def _planned_spend(plan: dict) -> float:
    purchases = plan.get("planned_purchases", {})
    return sum(float(qty) * PRICES[good] for good, qty in purchases.items())


def test_contract_unemployed_with_dividends_plans_more_spending_than_zero_dividend():
    hh_no_income = make_household(cash_balance=1_000.0)
    hh_no_income.employer_id = None
    hh_no_income.wage = 0.0
    hh_no_income.last_dividend_income = 0.0
    hh_no_income.bank_deposit = 0.0

    hh_dividend = make_household(cash_balance=1_000.0)
    hh_dividend.employer_id = None
    hh_dividend.wage = 0.0
    hh_dividend.last_dividend_income = 200.0
    hh_dividend.bank_deposit = 0.0

    assert _planned_spend(_plan(hh_dividend)) > _planned_spend(_plan(hh_no_income))


def test_contract_employed_with_dividends_plans_more_spending_than_wage_alone():
    hh_wage_only = make_household(cash_balance=1_000.0)
    hh_wage_only.employer_id = 1
    hh_wage_only.wage = 300.0
    hh_wage_only.last_dividend_income = 0.0
    hh_wage_only.bank_deposit = 0.0

    hh_wage_div = make_household(cash_balance=1_000.0)
    hh_wage_div.employer_id = 1
    hh_wage_div.wage = 300.0
    hh_wage_div.last_dividend_income = 100.0
    hh_wage_div.bank_deposit = 0.0

    assert _planned_spend(_plan(hh_wage_div)) > _planned_spend(_plan(hh_wage_only))


def test_contract_unemployed_full_dividend_cover_not_maximally_frugal():
    hh_no_div = make_household(cash_balance=0.0)
    hh_no_div.employer_id = None
    hh_no_div.wage = 0.0
    hh_no_div.last_dividend_income = 0.0
    hh_no_div.bank_deposit = 0.0

    hh_full_div = make_household(cash_balance=0.0)
    hh_full_div.employer_id = None
    hh_full_div.wage = 0.0
    hh_full_div.last_dividend_income = BENEFIT
    hh_full_div.bank_deposit = 0.0

    assert _planned_spend(_plan(hh_full_div)) >= _planned_spend(_plan(hh_no_div))


def test_contract_distribute_profits_tracks_paying_firm_id():
    firm = make_firm(firm_id=42, cash_balance=10_000.0, is_baseline=True)
    household = make_household(cash_balance=500.0)

    firm.owners = [household.household_id]
    firm.net_profit = 1_000.0
    firm.last_tick_total_costs = 0.0
    firm.survival_mode = False
    firm.payout_ratio = 0.5

    household.last_dividend_income = 0.0
    household.last_dividend_firm_ids = []

    paid = firm.distribute_profits({household.household_id: household})

    assert paid == pytest.approx(500.0)
    assert household.last_dividend_income == pytest.approx(paid)
    assert household.last_dividend_firm_ids == [firm.firm_id]


def test_contract_multiple_firms_track_distinct_paying_firm_ids():
    firm_a = make_firm(firm_id=10, cash_balance=10_000.0, is_baseline=True)
    firm_b = make_firm(firm_id=20, cash_balance=10_000.0, is_baseline=True)
    household = make_household(cash_balance=500.0)

    household.last_dividend_income = 0.0
    household.last_dividend_firm_ids = []

    for firm in (firm_a, firm_b):
        firm.owners = [household.household_id]
        firm.net_profit = 800.0
        firm.last_tick_total_costs = 0.0
        firm.survival_mode = False
        firm.payout_ratio = 0.5

    paid_a = firm_a.distribute_profits({household.household_id: household})
    paid_b = firm_b.distribute_profits({household.household_id: household})

    assert household.last_dividend_firm_ids == [10, 20]
    assert household.last_dividend_income == pytest.approx(paid_a + paid_b)


def test_contract_services_consumption_improves_happiness_without_wage_income():
    without_services = make_household(cash_balance=200.0)
    with_services = make_household(cash_balance=200.0)
    for household in (without_services, with_services):
        household.employer_id = None
        household.wage = 0.0
        household.last_wage_income = 0.0
        household.last_transfer_income = 0.0
        household.last_dividend_income = 500.0
        household.met_housing_need = True
        household.food_consumed_this_tick = household.min_food_per_tick

    without_services.services_consumed_this_tick = 0.0
    with_services.services_consumed_this_tick = 1.0

    without_services.update_wellbeing()
    with_services.update_wellbeing()

    assert with_services.happiness > without_services.happiness
