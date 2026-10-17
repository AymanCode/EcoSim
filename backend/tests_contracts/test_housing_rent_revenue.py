"""Rent collected on the legacy path is the Housing firm's revenue.

Before this fix the housing phase moved rent straight into the landlord's
cash and nothing booked it as revenue: the firm's ``last_revenue`` was 0, its
taxable profit and ``net_profit`` were minus its wage bill, so it paid no
profit tax and ``distribute_profits`` never paid its owners. The named payment
arms already book rent as revenue (``PaymentBook.rent_receipts``). These tests
check the observable results: the tax snapshot, the firm's revenue, profit
and cash after a full tick, and that the rent is not credited to cash twice.
"""

import pytest

from agents import GovernmentAgent
from config import CONFIG
from economy import Economy
from tests_contracts.conftest import total_money_net_of_injections, total_money_with_bank
from tests_contracts.factories import make_economy, make_firm, make_household

RENT = 12.0


@pytest.fixture
def booking(monkeypatch):
    monkeypatch.setattr(CONFIG.labor_market, "rent_tracks_posted_price", True, raising=False)
    monkeypatch.setattr(CONFIG.labor_market, "rent_booked_as_revenue", True, raising=False)


def _one_tenant_economy():
    household = make_household(household_id=1, cash_balance=500.0)
    household.employer_id = 99
    household.wage = 1_000.0
    household.renting_from_firm_id = 10
    household.monthly_rent = RENT
    household.owns_housing = True
    firm = make_firm(firm_id=10, category="Housing", is_baseline=True,
                     cash_balance=5_000.0, max_rental_units=10, price=RENT)
    firm.current_tenants = [household.household_id]
    government = GovernmentAgent(cash_balance=50_000.0, unemployment_benefit_level=0.0, transfer_budget=0.0)
    return Economy(households=[household], firms=[firm], government=government), household, firm


def test_collected_rent_enters_the_tax_snapshot_as_revenue(booking):
    economy, household, firm = _one_tenant_economy()
    economy._clear_housing_rental_market()

    snapshot = {s["firm_id"]: s for s in economy._build_firm_tax_snapshots({})}[firm.firm_id]

    assert snapshot["profit_before_tax"] == pytest.approx(RENT - firm._current_wage_bill())


def test_rent_counts_once_in_cash_and_once_in_revenue(booking):
    firm = make_firm(firm_id=10, category="Housing", is_baseline=True, cash_balance=5_000.0)
    firm.last_tick_total_costs = 2.0
    cash_before = firm.cash_balance

    # 30 of revenue: 10 from goods sales (not yet in cash), 20 rent already in cash.
    firm.apply_sales_and_profit({"units_sold": 0.0, "revenue": 30.0,
                                 "revenue_already_in_cash": 20.0, "profit_taxes_paid": 3.0})

    assert firm.last_revenue == pytest.approx(30.0)
    assert firm.net_profit == pytest.approx(30.0 - 3.0 - 2.0)
    assert firm.cash_balance == pytest.approx(cash_before + 10.0 - 3.0)


def test_housing_firm_revenue_equals_rent_tenants_paid_this_tick(booking):
    economy = make_economy(num_households=10)
    housing = next(f for f in economy.firms if f.good_category == "Housing")
    for _ in range(3):
        economy.step()
        rent_paid = -sum(h.last_tick_ledger.get("rent", 0.0) for h in economy.households)
        goods_revenue = economy.last_tick_revenue.get(housing.firm_id, 0.0)

        assert rent_paid > 0.0
        assert housing.last_revenue == pytest.approx(goods_revenue + rent_paid)


def test_legacy_money_is_conserved_with_rent_booked(booking):
    economy = make_economy(num_households=10)
    initial = total_money_with_bank(economy)
    for _ in range(15):
        economy.step()
        assert total_money_net_of_injections(economy) - initial == pytest.approx(0.0, abs=1e-6)


def test_flag_off_leaves_rent_out_of_revenue(monkeypatch):
    monkeypatch.setattr(CONFIG.labor_market, "rent_booked_as_revenue", False, raising=False)
    economy, household, firm = _one_tenant_economy()
    economy._clear_housing_rental_market()

    snapshot = {s["firm_id"]: s for s in economy._build_firm_tax_snapshots({})}[firm.firm_id]

    assert snapshot["profit_before_tax"] == pytest.approx(-firm._current_wage_bill())


def test_default_books_rent():
    assert CONFIG.labor_market.rent_booked_as_revenue is True
