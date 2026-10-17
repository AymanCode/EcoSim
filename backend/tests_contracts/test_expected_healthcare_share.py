"""Read-only estimate of the household's share of a healthcare visit price.

``GovernmentAgent.expected_healthcare_household_share`` and its Economy
wrapper must give the share the visit charge in
``Economy._process_healthcare_services`` would produce, without paying,
reserving or recording anything.
"""

import pytest

from config import CONFIG
from tests_contracts.factories import make_economy


def _economy(level: int = 0, budget: float = 1_000_000.0, cash: float = 1_000_000.0):
    economy = make_economy(num_households=4, seed=11)
    gov = economy.government
    if level:
        gov.set_lever("sector_subsidy_target", "healthcare")
        gov.set_lever("sector_subsidy_level", level)
    gov.cash_balance = cash
    economy.sector_subsidy_remaining_this_tick = budget
    return economy


def test_no_subsidy_means_the_household_pays_everything():
    assert CONFIG.government.healthcare_visit_subsidy_share == 0.0
    economy = _economy()
    assert economy.expected_healthcare_household_share(80.0) == pytest.approx(1.0)


def test_subsidy_below_the_cap_gives_the_lever_share():
    economy = _economy(level=50)
    assert economy.expected_healthcare_household_share(80.0) == pytest.approx(0.5)


def test_binding_cap_raises_the_share_with_the_price():
    economy = _economy(level=50, budget=10.0)
    # The treasury pays at most $10, whatever the price.
    assert economy.expected_healthcare_household_share(100.0) == pytest.approx(0.9)
    assert economy.expected_healthcare_household_share(20.0) == pytest.approx(0.5)
    assert economy.expected_healthcare_household_share(40.0) == pytest.approx(0.75)


def test_empty_treasury_means_no_subsidy():
    economy = _economy(level=50, cash=0.0)
    assert economy.expected_healthcare_household_share(80.0) == pytest.approx(1.0)


def test_price_zero_returns_the_uncapped_share():
    economy = _economy(level=50, budget=0.0)
    assert economy.expected_healthcare_household_share(0.0) == pytest.approx(0.5)
    assert economy.government.expected_healthcare_household_share(0.0) == pytest.approx(0.5)


def test_the_estimate_changes_nothing():
    economy = _economy(level=50, budget=30.0)
    gov = economy.government
    before = (economy.sector_subsidy_remaining_this_tick, gov.cash_balance,
              economy.last_tick_gov_subsidy_requested, economy.last_tick_gov_subsidies,
              economy.last_tick_gov_subsidy_denied_by_cap)
    for price in (0.0, 10.0, 60.0, 500.0):
        economy.expected_healthcare_household_share(price)
    after = (economy.sector_subsidy_remaining_this_tick, gov.cash_balance,
             economy.last_tick_gov_subsidy_requested, economy.last_tick_gov_subsidies,
             economy.last_tick_gov_subsidy_denied_by_cap)
    assert after == before


@pytest.mark.parametrize("budget", [1_000_000.0, 30.0, 0.0])
def test_estimate_matches_what_the_charge_path_pays(budget):
    economy = _economy(level=50, budget=budget)
    price = 60.0
    expected = economy.expected_healthcare_household_share(price)
    share = economy.government.healthcare_visit_subsidy_share()
    government_cost, _denied = economy.apply_sector_subsidy_payment(price * share)
    assert (price - government_cost) / price == pytest.approx(expected)


def test_government_getter_takes_the_budget_explicitly():
    gov = _economy(level=25).government
    assert gov.expected_healthcare_household_share(100.0) == pytest.approx(0.75)  # no cap passed
    assert gov.expected_healthcare_household_share(100.0, subsidy_budget_left=5.0) == pytest.approx(0.95)
    assert gov.expected_healthcare_household_share(-10.0) == pytest.approx(0.75)  # negative price reads as 0


@pytest.mark.parametrize("sequence", ["income_first", "income_late"])
@pytest.mark.parametrize("care_mode,expected", [("patient_pay", 1.0), ("covered", 0.0)])
def test_payment_sequences_follow_the_care_mode_not_the_subsidy_lever(sequence, care_mode, expected):
    from payment_sectors import payment_care_public_share

    economy = _economy(level=50, budget=10.0)
    economy.payment_sequence = sequence
    economy.payment_care_mode = care_mode
    assert payment_care_public_share(economy) == 1.0 - expected
    for price in (0.0, 19.43, 500.0):
        assert economy.expected_healthcare_household_share(price) == expected
