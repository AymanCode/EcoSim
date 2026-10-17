"""Contracts for the shared worker-effectiveness rule (round 1 PR2).

Requirement (first-pass spec item 2): one pure function of skill, health,
morale and happiness drives worker output for every firm; happiness alone
moves output by at most +/-12%; the result is clamped to 0.8-1.25x.
"""

import itertools
import math
from dataclasses import replace

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG, SimulationConfig
from economy import Economy
from worker_effectiveness import worker_effectiveness

GRID = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]


def test_average_worker_is_exactly_one():
    assert worker_effectiveness(0.5, 0.5, 0.5, 0.5) == pytest.approx(1.0)


def test_extremes_hit_the_configured_clamp():
    assert worker_effectiveness(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.8)
    assert worker_effectiveness(1.0, 1.0, 1.0, 1.0) == pytest.approx(1.25)


def test_result_stays_in_band_for_every_input_combination():
    for combo in itertools.product(GRID, repeat=4):
        value = worker_effectiveness(*combo)
        assert 0.8 - 1e-12 <= value <= 1.25 + 1e-12, combo


@pytest.mark.parametrize("position", range(4))
def test_non_decreasing_in_each_input(position):
    for others in itertools.product(GRID, repeat=3):
        previous = -math.inf
        for x in GRID:
            args = list(others)
            args.insert(position, x)
            value = worker_effectiveness(*args)
            assert value >= previous - 1e-12, (position, args)
            previous = value


def test_each_input_strictly_raises_output_away_from_the_clamp():
    base = worker_effectiveness(0.5, 0.5, 0.5, 0.5)
    for position in range(4):
        args = [0.5] * 4
        args[position] = 0.6
        assert worker_effectiveness(*args) > base, position


def test_happiness_alone_moves_output_twelve_percent_at_most():
    # Neutral worker: happiness spans exactly 0.88x-1.12x.
    assert worker_effectiveness(0.5, 0.5, 0.5, 0.0) == pytest.approx(0.88)
    assert worker_effectiveness(0.5, 0.5, 0.5, 1.0) == pytest.approx(1.12)
    # Any other worker: the happiness swing never exceeds 0.24 in total.
    for skill, health, morale in itertools.product(GRID, repeat=3):
        swing = worker_effectiveness(skill, health, morale, 1.0) - worker_effectiveness(skill, health, morale, 0.0)
        assert 0.0 <= swing <= 0.24 + 1e-12


def test_out_of_range_inputs_are_clipped_not_extrapolated():
    assert worker_effectiveness(2.0, 0.5, 0.5, 0.5) == worker_effectiveness(1.0, 0.5, 0.5, 0.5)
    assert worker_effectiveness(-1.0, 0.5, 0.5, 0.5) == worker_effectiveness(0.0, 0.5, 0.5, 0.5)
    assert worker_effectiveness(float("nan"), 0.5, 0.5, 0.5) == worker_effectiveness(0.0, 0.5, 0.5, 0.5)


def test_clamp_and_slope_come_from_config():
    narrow = replace(CONFIG.firms, worker_effectiveness_min=0.95, worker_effectiveness_max=1.05)
    assert worker_effectiveness(0.0, 0.0, 0.0, 0.0, config=narrow) == pytest.approx(0.95)
    assert worker_effectiveness(1.0, 1.0, 1.0, 1.0, config=narrow) == pytest.approx(1.05)
    flat = replace(CONFIG.firms, worker_effectiveness_slope=0.1)
    assert worker_effectiveness(1.0, 1.0, 1.0, 1.0, config=flat) == pytest.approx(1.05)


def test_config_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(ValueError, match="worker_effectiveness weights"):
        SimulationConfig(firms=replace(CONFIG.firms, worker_effectiveness_happiness_weight=0.5))


def test_config_rejects_bounds_that_exclude_one():
    with pytest.raises(ValueError, match="worker_effectiveness bounds"):
        SimulationConfig(firms=replace(CONFIG.firms, worker_effectiveness_min=1.1))


def _worker(household_id, firm, happiness, skill=0.5):
    household = HouseholdAgent(household_id=household_id, skills_level=skill, age=30, cash_balance=1_000.0)
    household.employer_id = firm.firm_id
    household.health = 0.5
    household.morale = 0.5
    household.happiness = happiness
    return household


def _food_firm():
    firm = FirmAgent(
        firm_id=10, good_name="Food", cash_balance=100_000.0, inventory_units=0.0, good_category="Food",
        quality_level=5.0, wage_offer=40.0, price=10.0, expected_sales_units=100.0,
        production_capacity_units=1_000_000.0, productivity_per_worker=50.0, personality="moderate",
    )
    firm.units_per_worker = 50.0
    firm.capital_stock = 10_000.0
    return firm


def _services_firm():
    firm = FirmAgent(
        firm_id=20, good_name="Services", cash_balance=100_000.0, inventory_units=0.0, good_category="Services",
        quality_level=5.0, wage_offer=40.0, price=10.0, expected_sales_units=100.0,
        production_capacity_units=2.0, productivity_per_worker=4.0, personality="moderate",
    )
    firm.units_per_worker = 4.0
    return firm


def _realized(firm, happiness, planned):
    workers = [_worker(1, firm, happiness), _worker(2, firm, happiness)]
    firm.employees = [w.household_id for w in workers]
    firm.actual_wages = {w.household_id: firm.wage_offer for w in workers}
    government = GovernmentAgent(cash_balance=10_000.0, transfer_budget=0.0, unemployment_benefit_level=0.0)
    economy = Economy(households=workers, firms=[firm], government=government)
    return economy._calculate_experience_adjusted_production(firm, planned_production_units=planned)


def test_goods_output_follows_the_shared_rule():
    planned = 100.0
    sad = _realized(_food_firm(), happiness=0.0, planned=planned)
    happy = _realized(_food_firm(), happiness=1.0, planned=planned)
    assert sad == pytest.approx(planned * 0.88)
    assert happy == pytest.approx(planned * 1.12)


def test_services_output_follows_the_shared_rule():
    # 2 workers x 4 units each; planned above capacity so effectiveness binds.
    sad = _realized(_services_firm(), happiness=0.0, planned=100.0)
    assert sad == pytest.approx(2 * 4.0 * 0.88)


def test_services_firms_differ_by_their_own_throughput():
    slow, fast = _services_firm(), _services_firm()
    slow.units_per_worker, fast.units_per_worker = 2.0, 6.0
    assert _realized(fast, 0.5, 100.0) == pytest.approx(3 * _realized(slow, 0.5, 100.0))


def test_household_performance_multiplier_reports_the_production_rule():
    firm = _food_firm()
    household = _worker(1, firm, happiness=0.9, skill=0.2)
    assert household.get_performance_multiplier() == pytest.approx(worker_effectiveness(0.2, 0.5, 0.5, 0.9))
