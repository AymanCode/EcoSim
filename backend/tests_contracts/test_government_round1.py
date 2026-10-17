"""Round 1 PR5 government behavior: hooks, public debt, flat profit tax,
decaying public capital and the price-cap hold rule.

Tests call the public agent/economy methods and assert observable outcomes
(cash, debt, tax owed, multipliers, prices), not internal call order.
"""

import pytest

from agents import GovernmentAgent, HouseholdAgent
from economy import Economy


def _household(household_id: int, wage: float = 0.0, employed: bool = False) -> HouseholdAgent:
    hh = HouseholdAgent(household_id=household_id, skills_level=0.5, age=30, cash_balance=1_000.0)
    if employed:
        hh.employer_id = 99
        hh.wage = wage
    return hh


# ── get_benefit_replacement_rate ─────────────────────────────────────

def test_benefit_replacement_rate_is_benefit_over_mean_employed_wage():
    gov = GovernmentAgent(cash_balance=10_000.0)
    gov.unemployment_benefit_level = 30.0
    assert gov.get_benefit_replacement_rate(60.0) == pytest.approx(0.5)


@pytest.mark.parametrize("wage, expected", [(0.0, 0.0), (-5.0, 0.0), (10.0, 1.0)])
def test_benefit_replacement_rate_clamps_to_unit_interval(wage, expected):
    gov = GovernmentAgent(cash_balance=10_000.0)
    gov.unemployment_benefit_level = 30.0
    assert gov.get_benefit_replacement_rate(wage) == expected


def test_economy_replacement_rate_ignores_unemployed_households():
    households = [_household(1, 40.0, True), _household(2, 80.0, True), _household(3)]
    gov = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=households, firms=[], government=gov)
    gov.unemployment_benefit_level = 30.0
    assert economy.mean_employed_wage() == pytest.approx(60.0)
    assert economy.get_benefit_replacement_rate() == pytest.approx(0.5)


# ── get_health_coverage ──────────────────────────────────────────────

def test_health_coverage_is_zero_without_visits():
    assert GovernmentAgent(cash_balance=1.0).get_health_coverage() == 0.0


def test_health_coverage_reads_last_ticks_completed_visits_only():
    gov = GovernmentAgent(cash_balance=10_000.0)
    economy = Economy(households=[_household(1)], firms=[], government=gov)
    economy.last_healthcare_events = [
        {"event_type": "visit_completed", "visit_price": 20.0, "government_cost": 15.0},
        {"event_type": "visit_completed", "visit_price": 20.0, "government_cost": 5.0},
        # Denied visits are not healthcare spending and must not count.
        {"event_type": "visit_denied_affordability", "visit_price": 20.0, "government_cost": 0.0},
    ]
    economy._reset_healthcare_tick_state()
    assert economy.get_health_coverage() == pytest.approx(0.5)
    # The next tick's reset rolls an empty event list: coverage drops to 0.
    economy._reset_healthcare_tick_state()
    assert economy.get_health_coverage() == 0.0
