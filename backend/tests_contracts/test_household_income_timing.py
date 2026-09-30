"""New funds reach the same week's legacy shopping decision, paid once.

Ported onto the remediation code on 2026-09-29 from the 2026-09-28 session
written against 17d5c0b (docs/reviews/2026-09-28-household-income-timing.md).
``isolated_run`` and ``small_world`` come from the ported
``tools/checks/run_agent_scenarios.py``.
"""

import copy

import pytest

from agents import FirmAgent
from tests_contracts.factories import patch_agent_method


from tools.checks.run_agent_scenarios import isolated_run, small_world


@pytest.mark.parametrize("performance_mode", [False, True])
@pytest.mark.parametrize("funding", ["wage", "loan", "benefit"])
def test_zero_cash_household_buys_food_in_week_funds_arrive(monkeypatch, performance_mode, funding):
    with isolated_run(1337):
        economy = small_world(1337, cash=0)
        economy.performance_mode = performance_mode
        economy.current_tick = 17  # An intermediate cache tick, beyond warmup/stimulus.
        # Port adaptation: in_warmup was computed at construction (tick 0), so
        # without this the step crosses the warm-up boundary and pays the
        # post-warm-up stimulus before planning, funding every variant.
        economy.in_warmup = False
        household = economy.households[0]
        if funding != "wage":
            household.health = 0.05  # Real eligibility rule prevents a job in this fixture.
            household.employer_id = None
            household.wage = 0.0
            economy.firms[0].employees = []
            economy.firms[0].actual_wages = {}
        if funding != "loan":
            economy.bank = None
        if funding != "benefit":
            economy.government.unemployment_benefit_level = 0
        # Isolate the requested funding source, using the existing investment rule.
        economy.firms[0].cash_balance = 0  # Prevent self-funded capital investment.
        economy.config.firms.capital_cost_per_unit = 1_000_000  # Make new capital unprofitable.
        observations, tax_payments = [], []
        plan = economy._batch_plan_consumption
        fiscal = economy.government.apply_fiscal_results

        def record_plan(*args, **kwargs):
            observations.append((household.cash_balance, household.last_wage_income, household.last_transfer_income))
            return plan(*args, **kwargs)

        def record_fiscal(wage_tax, profit_tax, transfers, property_tax=0):
            tax_payments.append((wage_tax, transfers))
            return fiscal(wage_tax, profit_tax, transfers, property_tax)

        monkeypatch.setattr(economy, "_batch_plan_consumption", record_plan)
        patch_agent_method(monkeypatch, economy.government, "apply_fiscal_results", record_fiscal)
        economy.step()

        assert len(observations) == 1
        assert observations[0][0] > 0
        assert household.last_consumption_spending > 0
        assert household.food_consumed_this_tick > 0
        assert household.last_tick_ledger["wage"] == pytest.approx(household.last_wage_income)
        assert sum(x[0] for x in tax_payments) == pytest.approx(-household.last_tick_ledger["taxes"])
        assert sum(x[1] for x in tax_payments) == pytest.approx(household.last_transfer_income)
        assert all(firm.capital_investment_this_tick == 0 for firm in economy.firms)
        if funding != "wage":
            assert household.last_wage_income == 0
        if funding != "benefit":
            assert household.last_transfer_income == 0
        if funding != "loan":
            assert household.consumption_loan_remaining == 0
        if funding == "wage":
            assert household.last_wage_income > 0
        elif funding == "benefit":
            assert household.last_transfer_income == 30
        else:
            assert household.consumption_loan_remaining > 0


def test_cached_basket_changes_budget_without_repeating_seller_choices(monkeypatch):
    with isolated_run(1337):
        economy = small_world(1337, cash=100)
        economy.performance_mode = True
        household = economy.households[0]
        household.last_wage_income = 40
        household.last_other_income = -4
        market = economy._build_category_market_snapshot()
        lookup = economy._build_good_category_lookup()
        before = copy.deepcopy(economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0))
        economy.current_tick = 1
        household.cash_balance += 200
        household.last_wage_income = 80

        def forbidden_replan(*args, **kwargs):
            raise AssertionError("Seller choices should be reused for a funded cached basket")

        monkeypatch.setattr(economy, "_batch_plan_consumption", forbidden_replan)
        after = economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)
        assert after[1]["budget"] > before[1]["budget"]
        assert after[1]["planned_purchases"]
        purchases, _ = economy._clear_goods_market(after, economy.firms)
        assert sum(q * p for q, p in purchases[1].values()) <= after[1]["budget"]
        assert after[1]["planned_purchases"] == before[1]["planned_purchases"]
        household.cash_balance = 0
        household.bank_deposit = 0
        empty = economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)
        purchases, _ = economy._clear_goods_market(empty, economy.firms)
        assert purchases[1] == {}
        assert empty[1]["planned_purchases"] == before[1]["planned_purchases"]


def test_cached_zero_budget_recovers_after_extra_cash_arrives():
    with isolated_run(1337):
        economy = small_world(1337, cash=0)
        economy.performance_mode = True
        market = economy._build_category_market_snapshot()
        lookup = economy._build_good_category_lookup()
        empty = economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)
        assert empty[1]["budget"] == 0
        economy.current_tick = 1
        economy.households[0].cash_balance = 200
        funded = economy._plan_legacy_consumption_after_income({}, market, lookup, 0, 0)
        assert funded[1]["budget"] > 0
        assert funded[1]["planned_purchases"]


def test_income_settlement_and_receipts_do_not_pay_wages_twice():
    with isolated_run(1337):
        economy = small_world(1337, cash=0)
        household, firm = economy.households[0], economy.firms[0]
        before_total = household.cash_balance + firm.cash_balance + economy.government.cash_balance
        firm.apply_production_and_costs({"realized_production_units": 0})
        economy._apply_household_income({1: 10}, {1: 4}, {1: 40})
        economy.government.apply_fiscal_results(4, 0, 10)
        assert household.cash_balance == 46
        economy._batch_apply_household_updates({1: 10}, {1: 4}, {}, frozen_wages={1: 40}, income_already_settled=True)
        assert household.cash_balance == 46
        assert household.last_tick_ledger["wage"] == 40
        assert household.cash_balance + firm.cash_balance + economy.government.cash_balance == pytest.approx(before_total)


def test_settled_budget_uses_paid_wage_instead_of_future_contract():
    with isolated_run(1337):
        economy = small_world(1337, cash=100)
        household = economy.households[0]
        household.last_wage_income = 40
        household.last_other_income = -4
        before = economy._household_consumption_budgets(0, 0, settled_income=True)
        household.wage = 400
        after = economy._household_consumption_budgets(0, 0, settled_income=True)
        assert after == pytest.approx(before)


@pytest.mark.parametrize("target", [1, "Shop"])
@pytest.mark.parametrize("cash, food_cap, supply, expected_quantity, expected_unmet", [
    (15, 100, 10, 0.75, 0),  # A price rise cannot make cached orders overdraw cash.
    (100, 24, 10, 1.2, 0),  # Extra income retains the normal food spending cap.
    (15, 100, 0.25, 0.25, 0.5),  # Only affordable unfilled demand is recorded.
])
def test_cached_orders_respect_current_price_cash_food_cap_and_supply(
    target, cash, food_cap, supply, expected_quantity, expected_unmet,
):
    with isolated_run(1337):
        economy = small_world(1337, cash=cash)
        firm = economy.firms[0]
        firm.price = 20
        firm.inventory_units = supply
        plans = {1: {
            "household_id": 1, "budget": 100, "planned_purchases": {target: 10},
            "_purchase_scale": 2.0, "_food_budget_cap": food_cap,
        }}
        purchases, sales = economy._clear_goods_market(plans, economy.firms)
        quantity, price = purchases[1]["Shop"]
        assert quantity == pytest.approx(expected_quantity)
        assert price == 20
        assert sales[1]["revenue"] == pytest.approx(quantity * price)
        assert quantity * price <= min(cash, food_cap)
        assert economy.food_unmet_demand == pytest.approx(expected_unmet)


@pytest.mark.parametrize("target", [1, "Shop"])
@pytest.mark.parametrize("planned, scale", [(1.0, 3.0), (0.6, 2.5)])
def test_b28_scaled_cached_housing_keeps_the_one_unit_cap(target, planned, scale):
    """Audit B28(a): every planner path buys at most one housing unit a week."""
    with isolated_run(1337):
        economy = small_world(1337, cash=1_000, category="Housing")
        firm = economy.firms[0]
        firm.price = 10
        firm.inventory_units = 5
        plans = {1: {
            "household_id": 1, "budget": 500, "planned_purchases": {target: planned},
            "_purchase_scale": scale, "_food_budget_cap": 0.0,
        }}
        purchases, sales = economy._clear_goods_market(plans, economy.firms)
        quantity, _price = purchases[1]["Shop"]
        assert quantity == pytest.approx(1.0)
        assert sales[1]["units_sold"] == pytest.approx(1.0)


def _two_food_sellers(cash):
    """Two Food firms selling the same good: the cheap one has little stock."""
    economy = small_world(1337, cash=cash)
    cheap = economy.firms[0]
    cheap.price, cheap.inventory_units = 20, 0.5
    dear = FirmAgent(
        firm_id=2, good_name="Shop", good_category="Food", cash_balance=10_000.0,
        inventory_units=10.0, price=25.0, wage_offer=40.0, expected_sales_units=40.0,
        quality_level=5.0, production_capacity_units=200.0, productivity_per_worker=12.0,
        personality="moderate", is_baseline=False,
    )
    economy.firms.append(dear)
    return economy


def test_b28_spent_budget_ends_the_seller_scan_and_records_no_unmet_demand():
    """Audit B28(b): a budget-limited shortfall is not supply-limited unmet demand."""
    with isolated_run(1337):
        economy = _two_food_sellers(cash=15)
        plans = {1: {
            "household_id": 1, "budget": 100, "planned_purchases": {"Shop": 10},
            "_purchase_scale": 1.0, "_food_budget_cap": 1_000.0,
        }}
        purchases, sales = economy._clear_goods_market(plans, economy.firms)
        quantity, price = purchases[1]["Shop"]
        # 0.5 at 20 from the cheap seller, then the last 5 buys 0.2 at 25.
        assert quantity == pytest.approx(0.7)
        assert quantity * price == pytest.approx(15.0)
        assert sales[2]["units_sold"] == pytest.approx(0.2)
        assert economy.food_unmet_demand == pytest.approx(0.0)
        assert sum(economy.current_tick_unmet_demand_by_firm.values()) == pytest.approx(0.0)


def test_b28_spent_budget_records_no_unmet_demand_at_a_later_sold_out_firm():
    """Audit B28(b): once the money is gone, a sold-out seller is not short of supply."""
    with isolated_run(1337):
        economy = _two_food_sellers(cash=10)
        economy.firms[1].inventory_units = 0.0
        plans = {1: {
            "household_id": 1, "budget": 100, "planned_purchases": {1: 5, 2: 5},
            "_purchase_scale": 1.0, "_food_budget_cap": 1_000.0,
        }}
        purchases, _sales = economy._clear_goods_market(plans, economy.firms)
        quantity, _price = purchases[1]["Shop"]
        assert quantity == pytest.approx(0.5)
        assert economy.current_tick_unmet_demand_by_firm.get(2, 0.0) == pytest.approx(0.0)
        assert economy.food_unmet_demand == pytest.approx(0.0)
