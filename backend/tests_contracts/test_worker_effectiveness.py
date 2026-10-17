"""Contracts for worker output: skill factor x effort x hours present (round 1 PR2).

Requirements (Ayman, 2026-10-17 re-review): output per worker = units per
worker x skill factor x effort x hours present. Effort comes from morale and
happiness and moves output by about +/-12% end to end. Hours present come
from health as sickness absence, multiply the rest, and so cannot be made up
by skill. No weighted average and no 0.8-1.25 band.
"""

import itertools
from dataclasses import replace

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG, SimulationConfig
from economy import Economy
from worker_effectiveness import (
    absence_rate,
    effort,
    hours_present,
    skill_factor,
    worker_effectiveness,
)

GRID = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]


# --- effort -----------------------------------------------------------------

def test_effort_is_one_when_morale_and_happiness_average_one_half():
    assert effort(0.5, 0.5) == pytest.approx(1.0)
    assert effort(1.0, 0.0) == pytest.approx(1.0)


def test_effort_spans_about_twelve_percent_each_way():
    assert effort(0.0, 0.0) == pytest.approx(0.88)
    assert effort(1.0, 1.0) == pytest.approx(1.12)


def test_morale_and_happiness_count_equally():
    for m, h in itertools.product(GRID, repeat=2):
        assert effort(m, h) == pytest.approx(effort(h, m))


def test_effort_rises_with_morale_and_with_happiness():
    for other in GRID:
        values_m = [effort(x, other) for x in GRID]
        values_h = [effort(other, x) for x in GRID]
        assert values_m == sorted(values_m) and len(set(values_m)) == len(GRID)
        assert values_h == sorted(values_h) and len(set(values_h)) == len(GRID)


# --- hours present ------------------------------------------------------------

def test_absence_at_reference_health_equals_the_sourced_rate():
    ref = CONFIG.firms.worker_absence_reference_health
    assert absence_rate(ref) == pytest.approx(CONFIG.firms.worker_absence_reference_rate)


def test_sickest_worker_is_absent_sick_ratio_times_as_much_as_the_healthiest():
    assert absence_rate(0.0) / absence_rate(1.0) == pytest.approx(CONFIG.firms.worker_absence_sick_ratio)


def test_hours_present_rise_with_health_and_stay_near_full_time():
    values = [hours_present(h) for h in GRID]
    assert values == sorted(values) and len(set(values)) == len(GRID)
    assert all(0.97 < v < 1.0 for v in values)


def test_skill_cannot_make_up_for_absence():
    """Being sick costs the same share of output at any skill level."""
    for skill in GRID:
        sick = worker_effectiveness(skill, 0.1, 0.5, 0.5)
        well = worker_effectiveness(skill, 1.0, 0.5, 0.5)
        assert sick / well == pytest.approx(hours_present(0.1) / hours_present(1.0))


# --- skill factor and the product ---------------------------------------------

def test_skill_factor_matches_the_hire_pay_premium():
    assert skill_factor(0.0) == pytest.approx(1.0)
    assert skill_factor(1.0) == pytest.approx(1.25)
    assert skill_factor(0.4, experience_bonus=0.1) == pytest.approx(1.2)


def test_multiplier_is_the_product_of_the_three_factors():
    for s, hl, m, h in itertools.product([0.0, 0.5, 1.0], repeat=4):
        expected = skill_factor(s) * effort(m, h) * hours_present(hl)
        assert worker_effectiveness(s, hl, m, h) == pytest.approx(expected)


@pytest.mark.parametrize("position", range(4))
def test_multiplier_rises_with_each_input(position):
    for base in itertools.product([0.2, 0.6], repeat=3):
        values = []
        for x in GRID:
            args = list(base)
            args.insert(position, x)
            values.append(worker_effectiveness(*args))
        assert values == sorted(values) and len(set(values)) == len(GRID)


def test_out_of_range_inputs_are_clipped_not_extrapolated():
    assert worker_effectiveness(2.0, 2.0, 2.0, 2.0) == pytest.approx(worker_effectiveness(1, 1, 1, 1))
    assert worker_effectiveness(-1.0, -1.0, -1.0, -1.0) == pytest.approx(worker_effectiveness(0, 0, 0, 0))
    assert worker_effectiveness(float("nan"), 0.5, 0.5, 0.5) == pytest.approx(worker_effectiveness(0, 0.5, 0.5, 0.5))


def test_sizes_come_from_config():
    flat = replace(CONFIG.firms, worker_effort_range=0.0, worker_absence_reference_rate=0.0)
    assert worker_effectiveness(0.0, 0.0, 0.0, 1.0, config=flat) == pytest.approx(1.0)
    double = replace(CONFIG.firms, worker_effort_range=0.24)
    assert effort(1.0, 1.0, config=double) == pytest.approx(1.24)


@pytest.mark.parametrize("field,value", [
    ("worker_effort_range", 1.0),
    ("worker_effort_range", -0.1),
    ("worker_absence_reference_rate", 1.0),
    ("worker_absence_reference_health", 1.5),
    ("worker_absence_sick_ratio", 0.5),
])
def test_config_rejects_out_of_range_values(field, value):
    with pytest.raises(ValueError):
        SimulationConfig(firms=replace(CONFIG.firms, **{field: value}))


# --- production paths ---------------------------------------------------------

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
    assert sad == pytest.approx(planned * worker_effectiveness(0.5, 0.5, 0.5, 0.0))
    assert happy == pytest.approx(planned * worker_effectiveness(0.5, 0.5, 0.5, 1.0))
    # Happiness alone (morale held at 0.5) moves effort by 6% each way.
    assert happy / sad == pytest.approx(effort(0.5, 1.0) / effort(0.5, 0.0))


def test_services_output_follows_the_shared_rule():
    # 2 workers x 4 units each; planned above capacity so effectiveness binds.
    sad = _realized(_services_firm(), happiness=0.0, planned=100.0)
    happy = _realized(_services_firm(), happiness=1.0, planned=100.0)
    assert sad == pytest.approx(2 * 4.0 * worker_effectiveness(0.5, 0.5, 0.5, 0.0))
    assert happy == pytest.approx(2 * 4.0 * worker_effectiveness(0.5, 0.5, 0.5, 1.0))
    assert sad < happy


def test_services_firms_differ_by_their_own_throughput():
    slow, fast = _services_firm(), _services_firm()
    slow.units_per_worker, fast.units_per_worker = 2.0, 6.0
    assert _realized(fast, 0.5, 100.0) == pytest.approx(3 * _realized(slow, 0.5, 100.0))


def test_household_performance_multiplier_reports_effort_times_hours_present():
    firm = _food_firm()
    household = _worker(1, firm, happiness=0.9, skill=0.2)
    assert household.get_performance_multiplier() == pytest.approx(effort(0.5, 0.9) * hours_present(0.5))
