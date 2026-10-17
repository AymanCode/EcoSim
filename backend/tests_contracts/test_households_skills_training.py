"""Households h1+h2: skill learning, depreciation and training.

Behavior through public entry points: the traits, one weekly skills update
on an economy, the training decision and its financing. The flag defaults
off; tests of the new path turn it on.
"""

import numpy as np
import pytest

from agents import BankAgent, GovernmentAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_household


@pytest.fixture
def skills_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "skills_dynamics", True)


def _economy(households, bank=None):
    return Economy(households=list(households), firms=[],
                   government=GovernmentAgent(cash_balance=5_000.0), bank=bank)


def test_traits_vary_by_household_and_repeat():
    first = [make_household(i) for i in range(1, 401)]
    again = [make_household(i) for i in range(1, 401)]
    learn = np.array([h.learning_rate_annual for h in first])
    depreciate = np.array([h.skill_depreciation_annual for h in first])
    willing = np.array([h.training_willingness for h in first])
    assert list(learn) == [h.learning_rate_annual for h in again]
    assert 0.01 <= learn.min() and learn.max() <= 0.02 and learn.std() > 0.002
    assert 0.01 <= depreciate.min() and depreciate.max() <= 0.02
    assert 0.0 <= willing.min() and willing.max() <= 1.0 and 0.38 < willing.mean() < 0.48


def test_weekly_learning_and_depreciation(skills_on):
    worker = make_household(1, skills_level=0.4, learning_rate_annual=0.0156, skill_depreciation_annual=0.0156)
    worker.employer_id = 9
    idle = make_household(2, skills_level=0.4, learning_rate_annual=0.0156, skill_depreciation_annual=0.0156)
    idle.employer_id = None
    economy = _economy([worker, idle])
    economy._batch_update_skills()
    assert worker.skills_level == pytest.approx(0.4 + 0.0003 * 0.6)
    assert idle.skills_level == pytest.approx(0.4 * (1 - 0.0003))
    assert economy._hiring_skill == pytest.approx(worker.skills_level)


def test_a_year_of_work_closes_the_annual_share_of_the_gap(skills_on):
    worker = make_household(1, skills_level=0.2, learning_rate_annual=0.02)
    worker.employer_id = 9
    economy = _economy([worker])
    for _ in range(52):
        economy._batch_update_skills()
    closed = (worker.skills_level - 0.2) / 0.8
    assert closed == pytest.approx(0.02, rel=0.02)  # compounding weekly, about 2% of the gap


def test_flag_off_keeps_the_yearly_grant_and_legacy_education():
    household = make_household(1, skills_level=0.3, cash_balance=1_000.0, skill_growth_rate=0.001)
    household.employer_id = None
    assert household.maybe_active_education() == 100.0  # legacy path still runs


def test_flag_on_disables_legacy_education_and_yearly_grant(skills_on):
    household = make_household(1, skills_level=0.3, cash_balance=1_000.0, skill_growth_rate=0.001)
    household.employer_id = None
    assert household.maybe_active_education() == 0.0
    household.employer_id = 3
    household.last_skill_update_tick = 0
    household.apply_labor_outcome({"employer_id": 3, "wage": 50.0, "employer_category": "Food"}, current_tick=60)
    assert household.skills_level == 0.3  # weekly batch replaces the yearly grant


def test_only_those_behind_the_hiring_line_consider_training():
    behind = make_household(1, skills_level=0.2, training_willingness=1.0)
    behind.employer_id = None
    ahead = make_household(2, skills_level=0.6, training_willingness=1.0)
    ahead.employer_id = None
    employed = make_household(3, skills_level=0.2, training_willingness=1.0)
    employed.employer_id = 4
    unwilling = make_household(4, skills_level=0.2, training_willingness=0.0)
    unwilling.employer_id = None
    weeks = range(1, 201)
    assert sum(behind.wants_training(0.5, t) for t in weeks) == pytest.approx(200 * 0.6, abs=25)
    assert not any(ahead.wants_training(0.5, t) for t in weeks)
    assert not any(employed.wants_training(0.5, t) for t in weeks)
    assert not any(unwilling.wants_training(0.5, t) for t in weeks)


def _trainee(hid, cash, deposit=0.0):
    household = make_household(hid, skills_level=0.2, cash_balance=cash, training_willingness=1.0,
                               buffer_target_weeks=4.0, risk_aversion=1.0)
    household.employer_id = None
    household.bank_deposit = deposit
    return household


def test_training_pays_from_surplus_above_the_buffer_target(skills_on, monkeypatch):
    monkeypatch.setattr(type(_trainee(99, 0.0)), "wants_training", lambda self, s, t: True)
    rich = _trainee(1, cash=2_000.0)
    economy = _economy([rich])
    economy._hiring_skill = 0.5
    spent = economy._process_training(gov_benefit=30.0, unemployment_rate=0.0, mean_posted_wage=60.0)
    assert spent == pytest.approx(6.0)  # 0.10 * 60
    assert rich.cash_balance == pytest.approx(1_994.0)
    assert rich.skills_level == pytest.approx(0.204)
    assert rich.consumption_loan_remaining == 0.0


def test_shortfall_is_borrowed_through_the_consumption_loan_path(skills_on, monkeypatch):
    monkeypatch.setattr(type(_trainee(99, 0.0)), "wants_training", lambda self, s, t: True)
    # Target = 4 weeks * 1.0 * 30 benefit = 120; cash 120 leaves no surplus.
    at_target = _trainee(1, cash=120.0)
    bank = BankAgent(cash_reserves=10_000.0)
    bank.household_credit_scores[1] = 0.8
    economy = _economy([at_target], bank=bank)
    economy._hiring_skill = 0.5
    economy._process_training(gov_benefit=30.0, unemployment_rate=0.0, mean_posted_wage=60.0)
    assert at_target.consumption_loan_remaining > 6.0  # principal 6 plus interest
    assert at_target.cash_balance == pytest.approx(120.0)  # borrowed 6, paid 6
    assert at_target.skills_level == pytest.approx(0.204)
    assert bank.active_loans[-1]["subtype"] == "consumption"


def test_no_credit_no_training(skills_on, monkeypatch):
    monkeypatch.setattr(type(_trainee(99, 0.0)), "wants_training", lambda self, s, t: True)
    at_target = _trainee(1, cash=120.0)
    bank = BankAgent(cash_reserves=10_000.0)
    bank.household_credit_scores[1] = 0.2
    economy = _economy([at_target], bank=bank)
    economy._hiring_skill = 0.5
    assert economy._process_training(30.0, 0.0, 60.0) == 0.0
    assert at_target.skills_level == 0.2 and at_target.cash_balance == 120.0
    no_bank = _economy([_trainee(2, cash=120.0)])
    no_bank._hiring_skill = 0.5
    assert no_bank._process_training(30.0, 0.0, 60.0) == 0.0


def test_buffer_target_rises_with_unemployment_so_training_needs_more_surplus():
    household = _trainee(1, cash=200.0)
    assert household.training_shortfall(6.0, 30.0, unemployment_rate=0.0) == 0.0
    assert household.training_shortfall(6.0, 30.0, unemployment_rate=0.4) == pytest.approx(6.0)
