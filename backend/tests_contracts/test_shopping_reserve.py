"""Legacy shopping budget reserves the week's known rent and loan installments.

Since income is credited before the week's one shopping decision, the budget
was capped at cash plus 90% of deposits while rent (housing phase) and loan
installments (settlement phase) were debited later in the same tick, so a
household that spent its budget ended the week below zero. The budget now
sets those obligations aside first (2026-10-02, item 1).
"""

import pytest

from agents import FirmAgent
from economy import Economy
from tools.checks.run_agent_scenarios import isolated_run, small_world


def _renter_with_loan(seed, *, cash, rent, loan_principal=100.0):
    economy = small_world(seed, cash=cash)
    housing = FirmAgent(
        firm_id=2, good_name="Flat", good_category="Housing", cash_balance=10_000.0,
        inventory_units=0.0, price=rent, wage_offer=40.0, expected_sales_units=1.0,
        quality_level=5.0, production_capacity_units=1.0, productivity_per_worker=1.0,
        personality="moderate", is_baseline=False, max_rental_units=1,
    )
    housing.age_in_ticks = 30
    economy = Economy(economy.households, economy.firms + [housing], economy.government, bank=economy.bank)
    household = economy.households[0]
    household.renting_from_firm_id = housing.firm_id
    household.monthly_rent = rent
    household.owns_housing = True
    housing.current_tenants.append(household.household_id)
    if loan_principal:
        loan = economy.bank.originate_loan("household", household.household_id, loan_principal, 0.05, 26)
        loan["subtype"] = "consumption"
        household.cash_balance += loan_principal
        household.consumption_loan_remaining = loan["remaining"]
        household.consumption_loan_payment_per_tick = loan["payment_per_tick"]
    # Keep the week's cash flows to wage, rent, installment and food: no firm
    # capital spending recycled to the one household, no construction.
    # Government discretionary spending is redistributed through the misc
    # firm, so the treasury starts empty too.
    economy.config.firms.capital_cost_per_unit = 1_000_000
    housing.cash_balance = 0.0
    economy.government.cash_balance = 0.0
    household.category_weights = {"food": 1.0}  # the whole budget goes to the one food shop
    economy.current_tick = 15  # a full plan, then two cached-plan ticks in performance mode
    economy.in_warmup = False
    return economy, household


@pytest.mark.parametrize("deposits", [0.0, 60.0])
@pytest.mark.parametrize("performance_mode", [False, True])
def test_employed_renter_with_loan_ends_week_nonnegative(performance_mode, deposits):
    with isolated_run(1337):
        # The loan proceeds are already spent: no cash besides this week's wage
        # (and, in one variant, a deposit the budget may draw on).
        economy, household = _renter_with_loan(1337, cash=0.0, rent=10.0)
        household.cash_balance = 0.0
        if deposits:
            household.bank_deposit = deposits
            economy.bank.accept_deposit(household.household_id, deposits)
        economy.performance_mode = performance_mode
        loan = economy.bank.loans_for("household", household.household_id)[0]
        for _ in range(3):  # covers the cached-plan rescale path in performance mode
            owed = loan["remaining"]
            economy.step()
            assert household.renting_from_firm_id == 2
            assert household.last_tick_ledger.get("rent", 0.0) == pytest.approx(-10.0)
            assert owed - loan["remaining"] == pytest.approx(loan["payment_per_tick"])  # installment paid
            assert household.last_consumption_spending > 0
            assert household.cash_balance >= -1e-9


@pytest.mark.parametrize("performance_mode", [False, True])
def test_unaffordable_rent_is_not_reserved_and_eviction_is_unchanged(performance_mode):
    """A tenant the rent check will evict shops like a household with no lease."""
    outcomes = []
    for renting in (True, False):
        with isolated_run(1337):
            economy, household = _renter_with_loan(1337, cash=20.0, rent=500.0, loan_principal=0.0)
            if not renting:
                economy.firms[1].current_tenants.clear()
                household.renting_from_firm_id = None
                household.monthly_rent = 0.0
                household.owns_housing = False
            economy.performance_mode = performance_mode
            economy.step()
            outcomes.append((household.renting_from_firm_id, household.last_consumption_spending,
                             household.cash_balance))
    assert outcomes[0][0] is None and outcomes[1][0] is None  # evicted, as before; no lease taken
    assert outcomes[0][1] > 0
    assert outcomes[0][1:] == pytest.approx(outcomes[1][1:])
