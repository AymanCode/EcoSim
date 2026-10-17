"""Households h1: weekly skill learning on the job and depreciation out of work.

Behavior through public entry points: the traits, one weekly skills update
on an economy, and the legacy paths the flag replaces or leaves alone. The
flag defaults off; tests of the new path turn it on.
"""

import math

import numpy as np
import pytest

from agents import GovernmentAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_household


@pytest.fixture
def skills_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "skills_dynamics", True)


def _economy(households):
    return Economy(households=list(households), firms=[], government=GovernmentAgent(cash_balance=5_000.0))


def test_traits_vary_by_household_and_repeat():
    first = [make_household(i) for i in range(1, 401)]
    again = [make_household(i) for i in range(1, 401)]
    learn = np.array([h.learning_rate_annual for h in first])
    depreciate = np.array([h.skill_depreciation_annual for h in first])
    assert list(learn) == [h.learning_rate_annual for h in again]
    assert list(depreciate) == [h.skill_depreciation_annual for h in again]
    assert 0.03 <= learn.min() and learn.max() <= 0.05 and learn.std() > 0.004
    assert 0.06 <= depreciate.min() and depreciate.max() <= 0.10 and depreciate.std() > 0.008


def test_learning_range_is_centred_on_the_mincer_half_life():
    # Mincer (1974) P(1): marginal return 0.081 - 0.0024x halves at x = 16.9 years.
    half_life_years = 0.081 / (2 * 0.0024)
    lo, hi = CONFIG.households.learning_rate_annual_range
    assert (lo + hi) / 2 == pytest.approx(math.log(2) / half_life_years, abs=0.002)  # range rounded to 0.03-0.05


def test_weekly_learning_and_depreciation(skills_on):
    worker = make_household(1, skills_level=0.4, learning_rate_annual=0.052, skill_depreciation_annual=0.052)
    worker.employer_id = 9
    idle = make_household(2, skills_level=0.4, learning_rate_annual=0.052, skill_depreciation_annual=0.052)
    idle.employer_id = None
    _economy([worker, idle])._batch_update_skills()
    assert worker.skills_level == pytest.approx(0.4 + 0.001 * 0.6)
    assert idle.skills_level == pytest.approx(0.4 * (1 - 0.001))


def test_a_year_of_work_closes_the_annual_share_of_the_gap(skills_on):
    worker = make_household(1, skills_level=0.2, learning_rate_annual=0.04)
    worker.employer_id = 9
    economy = _economy([worker])
    for _ in range(52):
        economy._batch_update_skills()
    closed = (worker.skills_level - 0.2) / 0.8
    assert closed == pytest.approx(0.04, rel=0.03)  # compounding weekly, about 4% of the gap


def test_a_year_out_of_work_matches_the_measured_rank_loss(skills_on):
    # Edin & Gustavsson (2008): a median worker falls to about the 44.5th
    # percentile after a year out. In the sim, s(44.5)/s(50) is 0.93-0.94.
    idle = make_household(1, skills_level=0.6, skill_depreciation_annual=0.07)
    idle.employer_id = None
    economy = _economy([idle])
    for _ in range(52):
        economy._batch_update_skills()
    assert 0.92 < idle.skills_level / 0.6 < 0.95


def test_flag_off_keeps_the_yearly_grant_and_legacy_education():
    household = make_household(1, skills_level=0.3, cash_balance=1_000.0, skill_growth_rate=0.001)
    household.employer_id = None
    assert household.maybe_active_education() == 100.0
    worker = make_household(2, skills_level=0.3, skill_growth_rate=0.001)
    worker.employer_id = 3
    worker.last_skill_update_tick = 0
    worker.apply_labor_outcome({"employer_id": 3, "wage": 50.0, "employer_category": "Food"}, current_tick=60)
    assert worker.skills_level > 0.3  # the yearly grant still fires


def test_flag_on_replaces_only_the_yearly_grant(skills_on):
    household = make_household(1, skills_level=0.3, cash_balance=1_000.0, skill_growth_rate=0.001)
    household.employer_id = None
    assert household.maybe_active_education() == 100.0  # legacy education is untouched by h1
    worker = make_household(2, skills_level=0.3, skill_growth_rate=0.001)
    worker.employer_id = 3
    worker.last_skill_update_tick = 0
    worker.apply_labor_outcome({"employer_id": 3, "wage": 50.0, "employer_category": "Food"}, current_tick=60)
    assert worker.skills_level == 0.3  # the weekly batch replaces the yearly grant


def test_skills_stay_in_bounds(skills_on):
    top = make_household(1, skills_level=1.0, learning_rate_annual=0.05)
    top.employer_id = 9
    bottom = make_household(2, skills_level=0.0, skill_depreciation_annual=0.10)
    bottom.employer_id = None
    economy = _economy([top, bottom])
    for _ in range(10):
        economy._batch_update_skills()
    assert top.skills_level == 1.0 and bottom.skills_level == 0.0
