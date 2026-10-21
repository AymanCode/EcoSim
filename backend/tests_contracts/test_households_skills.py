"""Households skills PR: on-the-job skill wears off out of work at a fixed rate,
never below each household's week-1 skill; learning keeps main's yearly grant.

Switches:
- ``CONFIG.households.skills_dynamics`` (default off in this commit). Off = main.
- ``CONFIG.households.skills_weekly_learning`` (default off; read only with
  ``skills_dynamics`` on). On = learning credited weekly instead of yearly.
- ``CONFIG.households.skill_loss_per_year_out_of_work`` (default 0.04).
"""

import contextlib
import hashlib
import io
import math
import random

import numpy as np
import pytest

from config import CONFIG, HouseholdBehaviorConfig, SimulationConfig, clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy

EMPLOYED = {"employer_id": 1, "wage": 50.0, "employer_category": "Food"}
UNEMPLOYED = {"employer_id": None, "wage": 0.0, "employer_category": None}


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


@contextlib.contextmanager
def _flags(dynamics, weekly=False, loss=None):
    cfg = clone_config()
    cfg.households.skills_dynamics = dynamics
    cfg.households.skills_weekly_learning = weekly
    if loss is not None:
        cfg.households.skill_loss_per_year_out_of_work = loss
    with use_config(cfg):
        yield cfg


def _state_digest(economy):
    """Hash of household and firm state at full float precision."""
    parts = []
    for h in economy.households:
        parts.append(repr((h.household_id, h.skills_level, h.cash_balance, h.bank_deposit, h.employer_id,
                           h.wage, h.happiness, h.health)))
    for f in economy.firms:
        parts.append(repr((f.firm_id, f.cash_balance, f.price, f.wage_offer, len(f.employees))))
    parts.append(repr(economy.government.cash_balance))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _drive(economy, household, outcome, tick):
    """One week for one household: the labor outcome, then the weekly skill update."""
    household.apply_labor_outcome(outcome, current_tick=tick)
    economy._batch_update_skills()


def test_defaults():
    cfg = HouseholdBehaviorConfig()
    assert cfg.skills_dynamics is False
    assert cfg.skills_weekly_learning is False
    assert cfg.skill_loss_per_year_out_of_work == 0.04


def test_flag_off_never_calls_the_update_and_skill_never_falls(monkeypatch):
    with _flags(False):
        economy = _seeded_economy()
        monkeypatch.setattr(economy, "_batch_update_skills", lambda: pytest.fail("called with the flag off"))
        start = {h.household_id: h.skills_level for h in economy.households}
        _run(economy, 60)
        assert all(h.skill_floor is None for h in economy.households)
        assert all(h.skills_level >= start[h.household_id] - 1e-12 for h in economy.households)
        assert any(h.last_skill_update_tick >= 52 for h in economy.households)


def test_cross_flag_matrix():
    """skills_dynamics x skills_weekly_learning, 60 live ticks each.

    (off, off) is main. (off, on) must equal it exactly: weekly learning is
    read only with skills_dynamics on. The two on combinations differ from
    main and from each other, and nobody falls below the floor.
    """
    digests = {}
    for dynamics in (False, True):
        for weekly in (False, True):
            with _flags(dynamics, weekly):
                economy = _seeded_economy(households=150)
                _run(economy, 60)
                digests[(dynamics, weekly)] = _state_digest(economy)
                if dynamics:
                    assert all(h.skills_level >= h.skill_floor - 1e-12 for h in economy.households)
    assert digests[(False, True)] == digests[(False, False)]
    assert digests[(True, False)] != digests[(False, False)]
    assert digests[(True, True)] != digests[(False, False)]
    assert digests[(True, True)] != digests[(True, False)]


def test_step_yearly_grant_is_mains_grant_for_the_same_weeks_worked():
    """With weekly learning off, an employed household's skill moves only at
    the 52-tick grant, by exactly what main's grant pays for the weeks worked."""
    results = {}
    for dynamics in (False, True):
        with _flags(dynamics):
            economy = _seeded_economy(households=30)
            h = economy.households[0]
            h.skills_level, h.skill_floor = 0.4, 0.3
            h.last_skill_update_tick, h.employed_ticks_since_skill_update = 0, 0
            path = []
            for tick in range(1, 53):
                if dynamics:
                    _drive(economy, h, EMPLOYED, tick)
                else:
                    h.apply_labor_outcome(EMPLOYED, current_tick=tick)
                path.append(h.skills_level)
            results[dynamics] = path
            assert all(s == 0.4 for s in path[:51])
            assert path[51] == pytest.approx(0.4 + h.skill_growth_rate * 0.6 * 52)
    assert results[True] == results[False]


@pytest.mark.parametrize("gain", [0.005, 0.02, 0.04, 0.2])
def test_step_one_year_out_loses_min_a_and_gain(gain):
    with _flags(True):
        economy = _seeded_economy(households=30)
        h = economy.households[0]
        _drive(economy, h, UNEMPLOYED, 1)  # records floors
        h.skill_floor, h.skills_level = 0.3, 0.3 + gain
        weekly = []
        for tick in range(2, 54):
            before = h.skills_level
            _drive(economy, h, UNEMPLOYED, tick)
            weekly.append(before - h.skills_level)
            assert h.skills_level >= 0.3 - 1e-12
        lost = 0.3 + gain - h.skills_level
        assert lost == pytest.approx(min(0.04, gain), abs=1e-12)
        assert max(weekly) <= 0.04 / 52 + 1e-15
        # Fixed per year: the same gain loses the same amount late in a run.
        h.skill_floor, h.skills_level = 0.3, 0.3 + gain
        for tick in range(500, 552):
            _drive(economy, h, UNEMPLOYED, tick)
        assert 0.3 + gain - h.skills_level == pytest.approx(lost, abs=1e-12)


def test_loss_rate_is_read_from_config():
    with _flags(True, loss=0.52):
        economy = _seeded_economy(households=30)
        h = economy.households[0]
        _drive(economy, h, UNEMPLOYED, 1)
        h.skill_floor, h.skills_level = 0.2, 0.5
        _drive(economy, h, UNEMPLOYED, 2)
        assert h.skills_level == pytest.approx(0.49)
    with _flags(True, loss=0.0):
        economy = _seeded_economy(households=30)
        h = economy.households[0]
        _drive(economy, h, UNEMPLOYED, 1)
        h.skill_floor, h.skills_level = 0.2, 0.5
        _drive(economy, h, UNEMPLOYED, 2)
        assert h.skills_level == 0.5


def test_weekly_learning_reads_the_household_skill_growth_rate_trait():
    with _flags(True, weekly=True):
        economy = _seeded_economy(households=60)
        _run(economy, 1)
        rates = economy._household_static_traits()["skill_growth_rates"]
        assert np.array_equal(rates, np.array([h.skill_growth_rate for h in economy.households]))
        before = np.array([h.skills_level for h in economy.households])
        employed = np.array([h.is_employed for h in economy.households])
        economy._batch_update_skills()
        after = np.array([h.skills_level for h in economy.households])
        assert np.allclose(after[employed], (before + rates * (1.0 - before))[employed])


def test_yearly_mode_employed_skill_is_untouched_by_the_weekly_update():
    with _flags(True):
        economy = _seeded_economy(households=60)
        _run(economy, 1)
        before = np.array([h.skills_level for h in economy.households])
        employed = np.array([h.is_employed for h in economy.households])
        economy._batch_update_skills()
        after = np.array([h.skills_level for h in economy.households])
        assert np.array_equal(after[employed], before[employed])


def test_live_run_realized_wear_off_and_floor():
    """156 live ticks, default flags: out-of-work households above the floor lose
    exactly min(a/52, s - f) a week, nobody ends below the floor, and employed
    skill only rises. Weeks with a status change or paid education are skipped."""
    with _flags(True):
        economy = _seeded_economy()
        start = {h.household_id: h.skills_level for h in economy.households}
        prev_skill = dict(start)
        prev_emp = {h.household_id: h.is_employed for h in economy.households}
        wore_off = held = 0
        step = CONFIG.households.skill_loss_per_year_out_of_work / 52.0
        for _ in range(156):
            _run(economy, 1)
            for h in economy.households:
                hid, floor = h.household_id, h.skill_floor
                bought = (floor - start[hid]) / 0.005  # floor = week-1 skill + paid education
                assert bought >= -1e-6 and abs(bought - round(bought)) < 1e-6
                assert floor - 1e-12 <= h.skills_level <= 1.0
                before, was_emp = prev_skill[hid], prev_emp[hid]
                prev_skill[hid], prev_emp[hid] = h.skills_level, h.is_employed
                if h.education_active_this_tick or was_emp != h.is_employed:
                    continue
                if h.is_employed:
                    assert h.skills_level >= before - 1e-12
                elif before > floor + 1e-12:
                    assert before - h.skills_level == pytest.approx(min(step, before - floor), abs=1e-12)
                    wore_off += 1
                else:
                    assert h.skills_level == before
                    held += 1
        assert wore_off > 0 and held > 0


def test_update_runs_after_roster_sync(monkeypatch):
    with _flags(True):
        economy = _seeded_economy(households=60)
        calls = []
        sync, update = economy._sync_firm_employee_rosters, economy._batch_update_skills
        monkeypatch.setattr(economy, "_sync_firm_employee_rosters", lambda: (calls.append("sync"), sync())[1])
        monkeypatch.setattr(economy, "_batch_update_skills", lambda: (calls.append("skills"), update())[1])
        _run(economy, 1)
        assert "skills" in calls
        assert calls.index("sync") < calls.index("skills")


def test_switching_weekly_learning_off_mid_run_does_not_pay_out_the_on_weeks():
    economy = _seeded_economy(households=120)
    with _flags(True, weekly=True):
        _run(economy, 80)
    assert all(h.employed_ticks_since_skill_update == 0 for h in economy.households)
    with _flags(True, weekly=False):
        employed_before = {h.household_id: h.skills_level for h in economy.households if h.is_employed}
        _run(economy, 1)  # yearly clock restarted at the last weekly tick: no grant due
        for h in economy.households:
            if h.household_id in employed_before and h.is_employed:
                assert h.skills_level == pytest.approx(employed_before[h.household_id])


@pytest.mark.parametrize("loss", [float("nan"), float("inf"), -0.01, 1.5, True, "0.04"])
def test_config_rejects_invalid_loss(loss):
    with pytest.raises(ValueError):
        SimulationConfig(households=HouseholdBehaviorConfig(skill_loss_per_year_out_of_work=loss))


@pytest.mark.parametrize("field", ["skills_dynamics", "skills_weekly_learning"])
def test_config_rejects_non_bool_switches(field):
    with pytest.raises(ValueError):
        SimulationConfig(households=HouseholdBehaviorConfig(**{field: 1}))


def test_config_rejects_invalid_growth_ranges():
    with pytest.raises(ValueError):
        SimulationConfig(households=HouseholdBehaviorConfig(skill_growth_rate_range=(0.001, float("nan"))))


def test_edges_full_skill_and_below_floor():
    with _flags(True, weekly=True):
        economy = _seeded_economy(households=40)
        _run(economy, 1)
        h_emp, h_out = economy.households[0], economy.households[1]
        h_emp.employer_id, h_out.employer_id = 1, None
        h_emp.skills_level = 1.0
        h_out.skills_level = h_out.skill_floor - 0.05  # lowered by something else: left alone
        below = h_out.skills_level
        economy._batch_update_skills()
        assert h_emp.skills_level == 1.0
        assert h_out.skills_level == below
        assert math.isfinite(h_out.skills_level)


def test_retired_keys_are_gone():
    cfg = HouseholdBehaviorConfig()
    for key in ("skill_decay_unemployment_threshold", "skill_decay_rate_per_tick", "skill_decay_floor",
                "skill_gain_depreciation_annual_range"):
        assert not hasattr(cfg, key)


def test_paid_education_raises_the_floor_so_it_is_not_worn_off():
    with _flags(True):
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
