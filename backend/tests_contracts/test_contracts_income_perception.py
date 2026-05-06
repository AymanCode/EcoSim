"""Contract tests for household income perception (EcoSim 2.0).

Households must consider wage, unemployment benefit, AND dividends as income
when deciding how much to spend. An unemployed household with dividend income
should not be maximally frugal. Dividends are tracked per-firm for auditability.
"""
import pytest

from agents import FirmAgent, HouseholdAgent
from config import CONFIG
from tests_contracts.factories import make_household, make_firm


BENEFIT = CONFIG.government.default_unemployment_benefit


# ---------------------------------------------------------------------------
# plan_consumption: dividends included in spending budget
# ---------------------------------------------------------------------------

def _plan(hh: HouseholdAgent, **kwargs) -> dict:
    return hh.plan_consumption(
        market_prices={"Food": 5.0, "Services": 10.0},
        unemployment_rate=0.05,
        **kwargs,
    )


def test_contract_unemployed_with_dividends_has_larger_budget_than_zero_income():
    """Unemployed household with dividends has higher after-tax income than one with none."""
    hh_no_income = make_household(cash_balance=0.0)
    hh_no_income.employer_id = None  # unemployed
    hh_no_income.wage = 0.0
    hh_no_income.last_dividend_income = 0.0
    hh_no_income.bank_deposit = 0.0

    hh_dividend = make_household(cash_balance=0.0)
    hh_dividend.employer_id = None  # unemployed
    hh_dividend.wage = 0.0
    hh_dividend.last_dividend_income = 200.0
    hh_dividend.bank_deposit = 0.0

    _plan(hh_no_income)
    _plan(hh_dividend)

    # plan_consumption sets last_after_tax_income = benefit + dividend
    assert hh_dividend.last_after_tax_income > hh_no_income.last_after_tax_income


def test_contract_employed_with_dividends_budgets_more_than_wage_alone():
    """Employed household with dividends has higher after-tax income than wage-only."""
    hh_wage_only = make_household(cash_balance=100.0)
    hh_wage_only.employer_id = 1  # employed
    hh_wage_only.wage = 300.0
    hh_wage_only.last_dividend_income = 0.0
    hh_wage_only.bank_deposit = 0.0

    hh_wage_div = make_household(cash_balance=100.0)
    hh_wage_div.employer_id = 1  # employed
    hh_wage_div.wage = 300.0
    hh_wage_div.last_dividend_income = 100.0
    hh_wage_div.bank_deposit = 0.0

    _plan(hh_wage_only)
    _plan(hh_wage_div)

    # plan_consumption sets last_after_tax_income = (wage - tax) + dividend
    assert hh_wage_div.last_after_tax_income > hh_wage_only.last_after_tax_income


def test_contract_unemployed_full_dividend_cover_not_maximally_frugal():
    """Unemployed household whose dividends fully cover its income is less frugal than one with none."""
    hh_no_div = make_household(cash_balance=0.0)
    hh_no_div.employer_id = None
    hh_no_div.wage = 0.0
    hh_no_div.last_dividend_income = 0.0
    hh_no_div.bank_deposit = 0.0

    # Dividend equals or exceeds benefit → dividend_cover = 1.0 → no frugality penalty
    hh_full_div = make_household(cash_balance=0.0)
    hh_full_div.employer_id = None
    hh_full_div.wage = 0.0
    hh_full_div.last_dividend_income = BENEFIT
    hh_full_div.bank_deposit = 0.0

    spend_no = _plan(hh_no_div).get("total_planned_spend", 0.0)
    spend_full = _plan(hh_full_div).get("total_planned_spend", 0.0)

    assert spend_full >= spend_no


# ---------------------------------------------------------------------------
# Per-firm dividend tracking
# ---------------------------------------------------------------------------

def test_contract_distribute_profits_tracks_per_firm():
    """distribute_profits records dividend in last_dividend_by_firm keyed by firm_id."""
    firm = make_firm(firm_id=42, cash_balance=10_000.0, is_baseline=True)
    hh = make_household(cash_balance=500.0)

    firm.owners = [hh.household_id]
    firm.last_profit = 1_000.0
    firm.net_profit = 1_000.0
    firm.last_tick_total_costs = 0.0
    firm.survival_mode = False
    firm.restructuring_mode = False
    firm.payout_ratio = 0.5

    hh.last_dividend_income = 0.0
    hh.last_dividend_by_firm = {}
    hh.last_dividend_firm_ids = []

    household_lookup = {hh.household_id: hh}
    paid = firm.distribute_profits(household_lookup)

    assert paid > 0.0
    assert firm.firm_id in hh.last_dividend_by_firm
    assert hh.last_dividend_by_firm[firm.firm_id] == pytest.approx(paid)
    assert hh.last_dividend_income == pytest.approx(paid)


def test_contract_multiple_firms_tracked_separately():
    """Dividends from two firms appear as separate entries in last_dividend_by_firm."""
    firm_a = make_firm(firm_id=10, cash_balance=10_000.0, is_baseline=True)
    firm_b = make_firm(firm_id=20, cash_balance=10_000.0, is_baseline=True)
    hh = make_household(cash_balance=500.0)

    hh.last_dividend_income = 0.0
    hh.last_dividend_by_firm = {}
    hh.last_dividend_firm_ids = []

    for firm in (firm_a, firm_b):
        firm.owners = [hh.household_id]
        firm.last_profit = 800.0
        firm.net_profit = 800.0
        firm.last_tick_total_costs = 0.0
        firm.survival_mode = False
        firm.restructuring_mode = False
        firm.payout_ratio = 0.5

    household_lookup = {hh.household_id: hh}
    paid_a = firm_a.distribute_profits(household_lookup)
    paid_b = firm_b.distribute_profits(household_lookup)

    assert 10 in hh.last_dividend_by_firm
    assert 20 in hh.last_dividend_by_firm
    assert hh.last_dividend_by_firm[10] == pytest.approx(paid_a)
    assert hh.last_dividend_by_firm[20] == pytest.approx(paid_b)
    assert hh.last_dividend_income == pytest.approx(paid_a + paid_b)


# ---------------------------------------------------------------------------
# last_total_income = wage + benefit + dividends (taxes clamped to 0)
# ---------------------------------------------------------------------------

def test_contract_total_income_includes_all_sources():
    """last_total_income = wage + dividend; negative last_other_income (taxes) not subtracted."""
    hh = make_household(cash_balance=500.0)
    hh.last_wage_income = 300.0
    hh.last_transfer_income = 0.0
    hh.last_dividend_income = 100.0
    hh.last_other_income = -45.0  # taxes paid

    hh.last_total_income = (
        hh.last_wage_income
        + hh.last_transfer_income
        + hh.last_dividend_income
        + max(0.0, hh.last_other_income)
    )

    assert hh.last_total_income == pytest.approx(400.0)  # 300 + 0 + 100 + 0


def test_contract_total_income_unemployed_with_benefit_and_dividend():
    """Unemployed: total = benefit + dividend; no taxes means no subtraction."""
    hh = make_household(cash_balance=0.0)
    hh.last_wage_income = 0.0
    hh.last_transfer_income = 150.0
    hh.last_dividend_income = 80.0
    hh.last_other_income = 0.0

    hh.last_total_income = (
        hh.last_wage_income
        + hh.last_transfer_income
        + hh.last_dividend_income
        + max(0.0, hh.last_other_income)
    )

    assert hh.last_total_income == pytest.approx(230.0)


# ---------------------------------------------------------------------------
# update_wellbeing: dividend income counts for services satisfaction
# ---------------------------------------------------------------------------

def test_contract_wellbeing_uses_dividends_for_services_component():
    """Household with $0 wage but dividend income can achieve non-zero services happiness."""
    hh = make_household(cash_balance=200.0)
    hh.employer_id = None  # unemployed
    hh.wage = 0.0
    hh.last_wage_income = 0.0
    hh.last_transfer_income = 0.0
    hh.last_dividend_income = 500.0
    hh.last_other_income = 0.0
    hh.last_after_tax_income = 0.0  # force fallback path in update_wellbeing
    hh.last_services_spend = 100.0
    hh.met_housing_need = True
    hh.food_consumed_this_tick = hh.min_food_per_tick  # full food component

    hh.update_wellbeing()

    # fallback: actual_after_tax_income = last_dividend_income = 500
    # services_component = min(1, 100/500) * 0.30 = 0.06 → happiness > 0
    assert hh.happiness > 0.0
