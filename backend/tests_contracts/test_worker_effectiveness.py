"""Effective labour. Flag off keeps the headcount formulas. Flag on moves realized units."""

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG, SimulationConfig, clone_config, use_config
from economy import Economy
from worker_effectiveness import (
    REFERENCE_HAPPINESS,
    REFERENCE_MORALE,
    absence_rate,
    effort,
    experience_premium,
    hours_present,
    load_spec,
    spell_snapshot,
    worker_weights,
)


def _household(household_id, skill, health=1.0, category="Food", ticks=0):
    household = HouseholdAgent(
        household_id=household_id,
        skills_level=skill,
        age=35,
        cash_balance=2_000.0,
    )
    household.health = health
    household.morale = REFERENCE_MORALE
    household.happiness = REFERENCE_HAPPINESS
    household.employer_id = 1
    household.wage = 40.0
    household.reservation_wage = 1.0
    household.category_experience = {category: ticks}
    return household


def _food_firm(employee_ids):
    firm = FirmAgent(
        firm_id=1,
        good_name="Food",
        good_category="Food",
        cash_balance=500_000.0,
        inventory_units=0.0,
        employees=list(employee_ids),
        production_capacity_units=10_000.0,
        units_per_worker=2.0,
        wage_offer=40.0,
        expected_sales_units=400.0,
        age_in_ticks=30,
        price=8.0,
        revenue_ema=5_000.0,
        profit_ema=1_000.0,
        last_revenue=5_000.0,
        last_profit=1_000.0,
    )
    # Personality sampling overwrites units. Capacity has to sit under the
    # sales target, or both skill levels produce the same plan.
    firm.units_per_worker = 1.0
    firm.production_capacity_units = 10_000.0
    for employee_id in employee_ids:
        firm.actual_wages[employee_id] = 40.0
    return firm


def _services_firm(employee_ids):
    firm = FirmAgent(
        firm_id=1,
        good_name="Services",
        good_category="Services",
        cash_balance=500_000.0,
        inventory_units=0.0,
        employees=list(employee_ids),
        production_capacity_units=float(len(employee_ids)),
        units_per_worker=7.0,
        wage_offer=40.0,
        expected_sales_units=400.0,
        age_in_ticks=30,
        price=10.0,
        revenue_ema=5_000.0,
        profit_ema=1_000.0,
        last_revenue=5_000.0,
        last_profit=1_000.0,
    )
    firm.units_per_worker = 7.0
    firm.production_capacity_units = float(len(employee_ids))
    for employee_id in employee_ids:
        firm.actual_wages[employee_id] = 40.0
    return firm


def _step(category, skill, health):
    """One real Economy.step with the flag on. Returns realized units."""
    count = 2 if category == "Food" else 4
    workers = [
        _household(i, skill, health=health, category=category)
        for i in range(1, count + 1)
    ]
    firm = _food_firm(range(1, count + 1)) if category == "Food" else _services_firm(range(1, count + 1))
    config = clone_config()
    config.firms.effective_labor_enabled = True
    with use_config(config):
        economy = Economy(
            households=workers,
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        economy.warmup_ticks = 0
        economy.in_warmup = False
        economy.current_tick = 30
        economy.last_tick_sales_units[firm.firm_id] = 10_000.0
        economy.step()
    return float(firm.last_units_produced)


def test_step_skill_moves_realized_units_for_food_and_services():
    """Deleting the skill weight makes these two economies produce the same units."""
    food_low = _step("Food", 0.2, health=1.0)
    food_high = _step("Food", 0.8, health=1.0)
    services_low = _step("Services", 0.2, health=1.0)
    services_high = _step("Services", 0.8, health=1.0)
    assert food_low > 0.0
    assert services_low > 0.0
    assert food_high > food_low
    assert services_high > services_low


def test_step_health_still_moves_realized_units():
    """Flag-on default keeps main's health weight. Dropping it makes these equal."""
    sick = _step("Food", 0.6, health=0.5)
    well = _step("Food", 0.6, health=1.0)
    assert sick > 0.0
    assert well > sick


def test_flag_off_goods_production_matches_the_headcount_formula():
    workers = [
        _household(1, 0.2, health=0.6, ticks=52),
        _household(2, 0.9, health=0.4, ticks=10 * 52),
    ]
    firm = _food_firm([1, 2])
    firm.units_per_worker = 50.0
    firm.supply_shock_multiplier = 1.05
    economy = Economy(
        households=workers,
        firms=[firm],
        government=GovernmentAgent(cash_balance=1_000_000.0),
    )
    economy.government.infrastructure_productivity_multiplier = 1.1
    planned = 2.0
    assert CONFIG.firms.effective_labor_enabled is False
    actual = economy._calculate_experience_adjusted_production(firm, planned)

    total = 0.0
    for household in workers:
        productivity = 1.0 + household.skills_level * 0.25
        years = household.category_experience["Food"] / 52.0
        productivity += min(years * 0.05, 0.5)
        productivity *= household.get_performance_multiplier()
        total += productivity
    average = total / len(workers)
    average *= 1.1 * 1.05
    expected = min(planned * average, firm.production_capacity_units, firm._capacity_for_workers(2))
    assert actual == pytest.approx(expected)
    assert actual > planned  # flag off still pays the above-plan multiplier


def test_experience_premium_matches_the_pay_expression():
    """Pay is min(years * 0.03, 0.3). Flag-on productivity uses that, not 5%/50%."""
    for years in (0.0, 0.5, 1.0, 5.0, 10.0, 20.0):
        assert experience_premium(years) == min(years * 0.03, 0.3)


def test_validation_rejects_absence_over_one_and_non_finite_values():
    config = clone_config()
    config.firms.worker_absence_reference_rate = 0.5
    config.firms.worker_absence_sick_ratio = 2.2
    with pytest.raises(ValueError, match="absence"):
        config.__post_init__()

    for bad in (float("nan"), float("inf"), float("-inf")):
        broken = clone_config()
        broken.firms.worker_effort_range = bad
        with pytest.raises(ValueError, match="finite"):
            broken.__post_init__()

    SimulationConfig()  # defaults pass


def test_weights_are_zero_for_missing_or_non_finite_workers():
    spec = load_spec(CONFIG.firms, CONFIG.households)
    assert worker_weights(None, "Food", spec) == (0.0, 0.0)
    broken = _household(1, 0.5)
    broken.skills_level = float("nan")
    assert worker_weights(broken, "Food", spec) == (0.0, 0.0)

    firm = _food_firm([])
    assert firm._capacity_for_labor_units(0.0) == 0.0
    assert firm._capacity_for_labor_units(float("nan")) == 0.0


def test_hours_clamp_effort_center_and_absence_anchors():
    spec = load_spec(CONFIG.firms, CONFIG.households)
    assert effort(REFERENCE_MORALE, REFERENCE_HAPPINESS, spec) == pytest.approx(1.0, abs=1e-9)
    assert absence_rate(1.0, spec) == pytest.approx(0.011)
    assert absence_rate(0.0, spec) == pytest.approx(0.011 * 2.2)

    overflowing = load_spec(CONFIG.firms, CONFIG.households)
    # Bypass validation: the function itself clamps hours to [0, 1].
    from dataclasses import replace
    overflowing = replace(
        overflowing,
        absence_reference_rate=0.5,
        absence_sick_ratio=2.2,
        presenteeism_multiple=3.3,
        health_mode="presenteeism",
    )
    assert hours_present(0.0, overflowing, presenteeism=True) == 0.0

    skilled = _household(1, 1.0)
    observable, _full = worker_weights(skilled, "Food", spec)
    assert observable > 1.0


def test_missing_worker_produces_nothing_when_the_flag_is_on():
    firm = _food_firm([99])
    config = clone_config()
    config.firms.effective_labor_enabled = True
    with use_config(config):
        economy = Economy(
            households=[],
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        spec = load_spec(CONFIG.firms, CONFIG.households)
        firm.bind_effective_labor(economy.household_lookup, spec)
        produced = economy._calculate_experience_adjusted_production(firm, 100.0)
    assert produced == 0.0


def test_spell_snapshot_counts_long_spells_and_the_never_rehired_group():
    def person(household_id, employed, duration, skill, health=1.0):
        household = _household(household_id, skill, health=health)
        household.employer_id = 1 if employed else None
        household.unemployment_duration = duration
        return household

    # Tick 120. A spell that started at tick 15 has duration 106 (120 - 15 + 1).
    households = [
        person(1, False, 10, 0.9),
        person(2, False, 30, 0.4),
        person(3, False, 60, 0.2),
        person(4, False, 106, 0.3),
        person(5, True, 0, 0.8),
        person(6, False, 200, 0.1, health=0.0),  # cannot work; not in the labor force
    ]
    snap = spell_snapshot(households, 120)
    assert snap["unemp_gt26"] == pytest.approx(3 / 4)
    assert snap["unemp_gt52"] == pytest.approx(2 / 4)
    assert snap["median_spell"] == pytest.approx(45.0)
    assert snap["never_rehired_n"] == 1.0
    assert snap["never_rehired_skill"] == pytest.approx(0.3)
    assert math.isfinite(snap["median_spell"])


def _flag_on_config():
    config = clone_config()
    config.firms.effective_labor_enabled = True
    return config


def test_anchor_is_set_after_tick_1_and_unchanged_at_tick_52():
    workers = [_household(1, 0.2), _household(2, 0.8)]
    firm = _food_firm([1, 2])
    config = _flag_on_config()
    with use_config(config):
        economy = Economy(
            households=workers,
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        economy.warmup_ticks = 0
        economy.in_warmup = False
        economy.step()
        assert economy.current_tick == 1
        anchor = economy.effective_labor_anchor_skill
        assert 0.0 <= anchor <= 1.0
        for _ in range(51):
            economy.step()
        assert economy.current_tick == 52
        assert economy.effective_labor_anchor_skill == anchor


def test_two_seeds_store_different_anchors():
    """Private firms enter on week 1 only after warm-up. Their draws change who is hired.

    During the default warm-up, week 1 is baseline firms only and the anchor
    does not depend on the seed. This run turns warm-up off so entry happens
    before matching.
    """
    import random

    import numpy as np
    from tools.runners.run_large_simulation import create_large_economy

    def once(seed):
        config = _flag_on_config()
        with use_config(config):
            random.seed(seed)
            np.random.seed(seed)
            CONFIG.random_seed = seed
            economy = create_large_economy(400, 3)
            economy.configure_stabilizers(households=True, firms=True, government=True)
            economy.warmup_ticks = 0
            economy.in_warmup = False
            economy.step()
            anchor = float(economy.effective_labor_anchor_skill)
            assert 0.0 <= anchor <= 1.0
            return anchor

    assert once(42) != once(43)


def test_anchor_edge_cases():
    config = _flag_on_config()
    with use_config(config):
        people = [_household(1, 0.2), _household(2, 0.4), _household(3, 0.9)]
        for person in people:
            person.employer_id = None
        housing = _food_firm([])
        housing.good_category = "Housing"
        housing.good_name = "Housing"
        economy = Economy(
            households=people,
            firms=[housing],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        economy._record_effective_labor_anchor()
        assert economy.effective_labor_anchor_skill == pytest.approx(0.4)

        food = _food_firm([1])
        people[0].skills_level = float("nan")
        people[0].employer_id = 1
        nan_economy = Economy(
            households=people,
            firms=[food],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        nan_economy._record_effective_labor_anchor()
        assert nan_economy.effective_labor_anchor_skill == pytest.approx((0.4 + 0.9) / 2.0)

        for person in people:
            person.skills_level = float("inf")
        empty_economy = Economy(
            households=people,
            firms=[food],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        empty_economy._record_effective_labor_anchor()
        assert empty_economy.effective_labor_anchor_skill == pytest.approx(config.firms.worker_reference_skill)

        high = [_household(1, 0.2), _household(2, 0.2)]
        high[0].skills_level = 1.5
        high[1].skills_level = 1.4
        high_firm = _food_firm([1, 2])
        high_economy = Economy(
            households=high,
            firms=[high_firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        high_economy._record_effective_labor_anchor()
        assert high_economy.effective_labor_anchor_skill == 1.0

        low = [_household(1, 0.2), _household(2, 0.2)]
        low[0].skills_level = -0.4
        low[1].skills_level = -0.2
        low_firm = _food_firm([1, 2])
        low_economy = Economy(
            households=low,
            firms=[low_firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        low_economy._record_effective_labor_anchor()
        assert low_economy.effective_labor_anchor_skill == 0.0


def test_flag_off_run_does_not_compute_the_anchor():
    workers = [_household(1, 0.4), _household(2, 0.8)]
    firm = _food_firm([1, 2])
    with use_config(clone_config()):
        assert CONFIG.firms.effective_labor_enabled is False
        economy = Economy(
            households=workers,
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        economy.warmup_ticks = 0
        economy.in_warmup = False
        economy.step()
        assert economy.current_tick == 1
        assert not hasattr(economy, "effective_labor_anchor_skill")
        economy._record_effective_labor_anchor()
        assert not hasattr(economy, "effective_labor_anchor_skill")


def test_capital_gate_uses_labour_units_when_each_head_counts_as_more_than_one():
    workers = [_household(1, 1.0), _household(2, 1.0)]
    firm = _food_firm([1, 2])
    firm.smoothed_profit_margin = 0.5
    firm.expected_sales_units = 100_000.0
    firm.inventory_units = 0.0
    firm.planned_headcount = 2
    firm.price = 80.0
    firm.pricing_operating_unit_cost = 0.0
    firm.capital_stock = 15.0
    firm.units_per_worker = 10.0
    firm.survival_mode = False
    firm.burn_mode = False
    config = _flag_on_config()
    config.payment_sequence = "income_first"
    with use_config(config):
        economy = Economy(
            households=workers,
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        spec = load_spec(CONFIG.firms, CONFIG.households)
        firm.bind_effective_labor(economy.household_lookup, spec)
        per_head = firm._labor_units_for_headcount(float(len(firm.employees)), skill_only=False) / len(firm.employees)
        assert per_head > 1.0
        firm.plan_capital_investment()
    incremental = firm.decision_diagnostics["capital_incremental_sellable_units"]
    assert incremental > 0.0


def test_services_capacity_uses_labour_units_not_headcount():
    """Replacing the labour-unit sum with a headcount makes this fail."""
    from dataclasses import replace

    workers = [_household(i, 1.0, category="Services") for i in range(1, 5)]
    firm = _services_firm(range(1, 5))
    firm.supply_shock_multiplier = 1.0
    config = _flag_on_config()
    with use_config(config):
        economy = Economy(
            households=workers,
            firms=[firm],
            government=GovernmentAgent(cash_balance=1_000_000.0),
        )
        spec = replace(load_spec(CONFIG.firms, CONFIG.households), reference_skill=0.2)
        firm.bind_effective_labor(economy.household_lookup, spec)
        produced = economy._calculate_experience_adjusted_production(firm, 1_000_000.0)
        labor = sum(firm._effective_labor_weights[i][1] for i in firm.employees)
        per_unit = firm._service_units_per_worker()
        expected = per_unit * labor * firm.supply_shock_multiplier
        headcount = per_unit * len(firm.employees) * firm.supply_shock_multiplier
    assert labor != pytest.approx(float(len(workers)))
    assert produced == pytest.approx(expected)
    assert produced != pytest.approx(headcount)


def test_flag_off_state_hash_matches_main_for_60_ticks():
    """Flag-off snapshot equals an origin/main worktree. Skips when that tree is absent."""
    repo = Path(__file__).resolve().parents[2]
    main_root = Path(os.environ.get("ECOSIM_MAIN_ROOT", repo.parent / "main"))
    if not (main_root / "backend" / "economy.py").is_file():
        pytest.skip(f"origin/main worktree not at {main_root}")
    script = r"""
import contextlib, hashlib, io, json, os, sys
root, sequence = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, "backend"))
from config import CONFIG, clone_config, use_config
from tools.benchmarks.regression_snapshot import ROUND_DECIMALS, _set_seed, snapshot_economy
from tools.runners.run_large_simulation import create_large_economy
buf = io.StringIO()
with contextlib.redirect_stdout(buf), use_config(clone_config()):
    _set_seed(42)
    CONFIG.payment_sequence = sequence
    if hasattr(CONFIG.firms, "effective_labor_enabled"):
        CONFIG.firms.effective_labor_enabled = False
    economy = create_large_economy(1000, 5)
    economy.configure_stabilizers(households=True, firms=True, government=True)
    for _ in range(60):
        economy.step()
    snap = snapshot_economy(economy, ROUND_DECIMALS)
print(hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest())
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"

    def digest(root, sequence):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(root), sequence],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        assert completed.returncode == 0, completed.stderr[-2000:]
        return completed.stdout.strip().splitlines()[-1]

    for sequence in ("income_first", "legacy"):
        assert digest(repo, sequence) == digest(main_root, sequence)
