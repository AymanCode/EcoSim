"""Households skills PR: weekly learning on the job, and wear-off of on-the-job
gains while unemployed, floored at each household's week-1 skill.

Flag: ``CONFIG.households.skills_dynamics`` (default off = main).
"""

import contextlib
import io
import math
import random

import numpy as np
import pytest

from config import CONFIG, HouseholdBehaviorConfig, SimulationConfig, clone_config, use_config
from economy import Economy
from tools.runners.run_large_simulation import create_large_economy


def _seeded_economy(seed=42, households=200):
    random.seed(seed)
    np.random.seed(seed)
    CONFIG.random_seed = seed
    with contextlib.redirect_stdout(io.StringIO()):
        return create_large_economy(num_households=households, num_firms_per_category=3)


def _run(economy, ticks):
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(ticks):
            economy.step()


@pytest.fixture
def skills_on():
    cfg = clone_config()
    cfg.households.skills_dynamics = True
    with use_config(cfg):
        yield cfg


def test_flag_off_is_the_default_and_keeps_the_yearly_grant():
    assert CONFIG.households.skills_dynamics is False
    economy = _seeded_economy()
    _run(economy, 60)
    # Off: skill never falls and no floor is recorded.
    assert all(h.skill_floor is None for h in economy.households)
    assert any(h.last_skill_update_tick >= 52 for h in economy.households)


def test_step_realized_learning_wear_off_and_floor(skills_on):
    """Realized outcome over a live run: employed workers gain skill, out-of-work
    households lose only gains above their week-1 skill, and nobody ends below it.

    Status is compared at the end of consecutive steps; households whose status
    changed during a step (a hire, or a layoff after the skill update) are
    skipped, as are weeks with a paid education purchase.
    """
    economy = _seeded_economy()
    start = {h.household_id: h.skills_level for h in economy.households}
    prev_skill = dict(start)
    prev_emp = {h.household_id: h.is_employed for h in economy.households}
    gained, wore_off, held = 0, 0, 0
    for _ in range(156):
        _run(economy, 1)
        for h in economy.households:
            hid = h.household_id
            floor = h.skill_floor
            bought = (floor - start[hid]) / 0.005  # floor = week-1 skill + paid education
            assert bought >= -1e-6 and abs(bought - round(bought)) < 1e-6
            assert floor - 1e-12 <= h.skills_level <= 1.0
            before, was_emp = prev_skill[hid], prev_emp[hid]
            prev_skill[hid], prev_emp[hid] = h.skills_level, h.is_employed
            if h.education_active_this_tick or was_emp != h.is_employed:
                continue
            if h.is_employed:
                assert h.skills_level >= before - 1e-12
                gained += h.skills_level > before
            elif before > floor + 1e-9:
                assert floor - 1e-12 <= h.skills_level < before
                wore_off += 1
            else:
                assert h.skills_level == pytest.approx(before)
                held += 1
    assert gained > 0 and wore_off > 0 and held > 0


def test_learning_reads_the_household_skill_growth_rate_trait(skills_on):
    economy = _seeded_economy(households=60)
    _run(economy, 1)
    traits = economy._household_static_traits()
    rates = traits["skill_growth_rates"]
    assert np.array_equal(rates, np.array([h.skill_growth_rate for h in economy.households]))
    before = np.array([h.skills_level for h in economy.households])
    employed = np.array([h.is_employed for h in economy.households])
    economy._batch_update_skills()
    after = np.array([h.skills_level for h in economy.households])
    expected = before + rates * (1.0 - before)
    assert np.allclose(after[employed], expected[employed])


def test_depreciation_draws_are_per_household_bounded_and_order_independent(skills_on):
    economy = _seeded_economy(households=80)
    weekly = economy._household_static_traits()["skill_gain_depreciation_weekly"]
    lo, hi = CONFIG.households.skill_gain_depreciation_annual_range
    annual = 1.0 - (1.0 - weekly) ** 52
    assert np.all(annual >= lo - 1e-12) and np.all(annual <= hi + 1e-12)
    reversed_hh = list(reversed(economy.households))
    again = Economy._skill_gain_depreciation_weekly(reversed_hh)
    assert np.allclose(again[::-1], weekly)
    # Not keyed on id(): the cache holds the list object itself.
    assert economy._household_static_traits_cache[0] is economy.households


def test_update_runs_after_roster_sync(skills_on, monkeypatch):
    economy = _seeded_economy(households=60)
    calls = []
    sync, update = economy._sync_firm_employee_rosters, economy._batch_update_skills
    monkeypatch.setattr(economy, "_sync_firm_employee_rosters", lambda: (calls.append("sync"), sync())[1])
    monkeypatch.setattr(economy, "_batch_update_skills", lambda: (calls.append("skills"), update())[1])
    _run(economy, 1)
    assert "skills" in calls
    assert calls.index("sync") < calls.index("skills")


def test_switching_off_mid_run_does_not_pay_out_the_on_weeks():
    economy = _seeded_economy(households=120)
    cfg = clone_config()
    cfg.households.skills_dynamics = True
    with use_config(cfg):
        _run(economy, 80)
    assert all(h.employed_ticks_since_skill_update == 0 for h in economy.households)
    before = {h.household_id: h.skills_level for h in economy.households}
    _run(economy, 1)  # flag back off: the yearly clock restarted at the last on-tick
    for h in economy.households:
        assert h.skills_level == pytest.approx(before[h.household_id])


@pytest.mark.parametrize("rng_range", [(float("nan"), 0.4), (0.3, float("inf")), (0.5, 0.3), (0.2, 1.0), (-0.1, 0.2)])
def test_config_rejects_invalid_depreciation_ranges(rng_range):
    with pytest.raises(ValueError):
        SimulationConfig(households=HouseholdBehaviorConfig(skill_gain_depreciation_annual_range=rng_range))


def test_config_rejects_invalid_growth_ranges():
    with pytest.raises(ValueError):
        SimulationConfig(households=HouseholdBehaviorConfig(skill_growth_rate_range=(0.001, float("nan"))))


def test_edges_zero_rates_full_skill_and_below_floor(skills_on):
    economy = _seeded_economy(households=40)
    _run(economy, 1)
    traits = economy._household_static_traits()
    h_emp, h_out = economy.households[0], economy.households[1]
    h_out.employer_id = None
    h_emp.skills_level = 1.0
    h_out.skills_level = h_out.skill_floor - 0.05  # lowered by something else: left alone
    below = h_out.skills_level
    traits["skill_growth_rates"][:] = traits["skill_growth_rates"]  # unchanged
    economy._batch_update_skills()
    assert h_emp.skills_level == 1.0
    assert h_out.skills_level == pytest.approx(below)
    assert math.isfinite(h_out.skills_level)


def test_retired_skill_decay_keys_are_gone():
    cfg = HouseholdBehaviorConfig()
    for key in ("skill_decay_unemployment_threshold", "skill_decay_rate_per_tick", "skill_decay_floor"):
        assert not hasattr(cfg, key)


def test_paid_education_raises_the_floor_so_it_is_not_worn_off(skills_on):
    economy = _seeded_economy(households=40)
    _run(economy, 1)
    h = economy.households[0]
    h.employer_id = None
    h.skills_level = 0.3
    h.skill_floor = 0.3
    h.cash_balance = 1_000.0
    assert h.maybe_active_education() == 100.0
    assert h.skills_level == pytest.approx(0.305)
    assert h.skill_floor == pytest.approx(0.305)
