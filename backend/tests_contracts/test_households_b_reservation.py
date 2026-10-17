"""Households B (re-cut): adaptive reservation wage.

Behavior through public entry points: the trait, the live floor, one week
of the update, the labor plan and the economy's context. The flag defaults
off; tests of the new path turn it on.
"""

import numpy as np
import pytest

from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_economy, make_household


@pytest.fixture
def adaptive_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "adaptive_reservation_wage", True)


def _context(median=50.0, best=60.0, ratio=1.0, benefit=30.0):
    return {"median_offer": median, "best_offer": best, "finding_ratio": ratio, "benefit": benefit}


def _unemployed(hid=1, **kw):
    household = make_household(hid, **kw)
    household.employer_id = None
    household.wage = 0.0
    return household


def test_decay_trait_spans_the_krueger_mueller_range_and_repeats():
    decay = np.array([make_household(i).reservation_decay_rate for i in range(1, 401)])
    again = [make_household(i).reservation_decay_rate for i in range(1, 401)]
    assert list(decay) == again
    assert 0.0005 <= decay.min() and decay.max() <= 0.0014 and decay.std() > 0.0002


def test_floor_falls_to_the_benefit_as_job_finding_collapses():
    household = _unemployed()
    assert household.adaptive_reservation_floor(_context(ratio=1.0)) == pytest.approx(50.0)  # normal: M
    assert household.adaptive_reservation_floor(_context(ratio=0.5)) == pytest.approx(40.0)  # halfway to B
    assert household.adaptive_reservation_floor(_context(ratio=0.0)) == pytest.approx(30.0)  # slack: B


def test_floor_is_capped_at_the_best_hiring_offer():
    household = _unemployed()
    assert household.adaptive_reservation_floor(_context(ratio=3.0)) == pytest.approx(60.0)  # tight: P
    assert household.adaptive_reservation_floor(_context(benefit=90.0)) == pytest.approx(60.0)  # B > P


def test_no_hiring_firm_means_no_floor():
    assert _unemployed().adaptive_reservation_floor(_context(median=None, best=None)) is None


def test_job_loss_restarts_at_last_wage_then_decays_slowly(adaptive_on):
    household = make_household(1, reservation_decay_rate=0.001)
    household.employer_id = 7
    household.wage = 80.0
    household.apply_labor_outcome({"employer_id": None, "wage": 0.0}, reservation_context=_context())
    assert household.reservation_wage == pytest.approx(80.0 * (1 - 0.001))


def test_never_worked_starts_at_the_median_offer(adaptive_on):
    household = _unemployed(reservation_decay_rate=0.001)
    household.category_experience = {}
    household.unemployment_duration = 0
    household.apply_labor_outcome({"employer_id": None, "wage": 0.0}, reservation_context=_context(ratio=0.0))
    assert household.reservation_wage == pytest.approx(50.0 * (1 - 0.001))


def test_reservation_never_falls_below_the_floor(adaptive_on):
    household = _unemployed(reservation_decay_rate=0.0014)
    household.category_experience = {"Food": 10}
    household.reservation_wage = 41.0
    for _ in range(300):
        household.apply_labor_outcome({"employer_id": None, "wage": 0.0}, reservation_context=_context(ratio=0.5))
    assert household.reservation_wage == pytest.approx(40.0)


def test_desperation_can_still_take_the_ask_below_the_floor(adaptive_on):
    calm = _unemployed(1, cash_balance=5_000.0)
    broke_and_sick = _unemployed(2, cash_balance=0.0)
    broke_and_sick.health = 0.15
    for household in (calm, broke_and_sick):
        household.reservation_wage = 10.0
    floor = 40.0
    calm_plan = calm.plan_labor_supply(30.0, reservation_context=_context(ratio=0.5))
    desperate_plan = broke_and_sick.plan_labor_supply(30.0, reservation_context=_context(ratio=0.5))
    # Both start from max(F, r) = 40; the discount then applies after the floor.
    assert desperate_plan["reservation_wage"] < calm_plan["reservation_wage"] <= floor
    assert desperate_plan["reservation_wage"] < 0.9 * floor


def test_flag_off_keeps_legacy_reservation():
    household = _unemployed()
    household.reservation_wage = 0.5
    plan = household.plan_labor_supply(30.0, reservation_context=_context())
    assert plan["reservation_wage"] == pytest.approx(1.0)  # legacy $1 floor


def test_normal_weekly_rate_converts_the_monthly_cps_rate():
    assert Economy.normal_weekly_job_finding_rate() == pytest.approx(1 - 0.75 ** (12 / 52))
    assert 0.06 < Economy.normal_weekly_job_finding_rate() < 0.07


def test_economy_counts_hires_and_uses_only_hiring_firms(adaptive_on):
    economy = make_economy(num_households=30)
    assert economy.job_finding_rate() is None
    economy.step()
    rate = economy.job_finding_rate()
    assert rate is not None and 0.0 <= rate <= 1.0
    context = economy._reservation_context
    assert context is not None and set(context) == {"median_offer", "best_offer", "finding_ratio", "benefit"}
    if context["best_offer"] is not None:
        assert context["median_offer"] <= context["best_offer"]
