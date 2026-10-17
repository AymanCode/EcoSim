"""Households B: adaptive reservation wage.

Checks behavior through public entry points: the traits, the live floor,
one week of the update, and the labor plan. The flag defaults off; each test
that covers the new path turns it on.
"""

import numpy as np
import pytest

from config import CONFIG
from tests_contracts.factories import make_economy, make_household


@pytest.fixture
def adaptive_on(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "adaptive_reservation_wage", True)


def _context(offers=None, tightness=0.5, benefit=30.0):
    offers = {1: 40.0, 2: 50.0, 3: 60.0} if offers is None else offers
    values = sorted(offers.values())
    return {
        "offers": offers,
        "median_offer": float(np.median(values)) if values else 0.0,
        "best_offer": values[-1] if values else 0.0,
        "tightness": tightness,
        "benefit": benefit,
    }


def _unemployed(hid=1, **kw):
    household = make_household(hid, **kw)
    household.employer_id = None
    household.wage = 0.0
    household.awareness_pool = {}
    return household


def test_traits_vary_by_household_and_repeat():
    first = [make_household(i) for i in range(1, 301)]
    again = [make_household(i) for i in range(1, 301)]
    decay = np.array([h.reservation_decay_rate for h in first])
    share = np.array([h.reservation_floor_share for h in first])
    assert list(decay) == [h.reservation_decay_rate for h in again]
    assert 0.0012 < decay.mean() < 0.0016 and decay.std() > 0.0003
    assert 0.5 <= share.min() and share.max() <= 0.9 and 0.66 < share.mean() < 0.74


def test_floor_share_trait_is_clamped_to_one(monkeypatch):
    monkeypatch.setattr(CONFIG.households, "reservation_floor_share_range", (0.75, 1.05, 1.35))
    shares = [make_household(i).reservation_floor_share for i in range(1, 301)]
    assert max(shares) == 1.0 and min(shares) >= 0.75
    household = _unemployed(reservation_floor_share=max(shares))
    # s_min = 1: the floor is the median offer even in the tightest market.
    assert household.adaptive_reservation_floor(_context(tightness=1.0)) == pytest.approx(50.0)


def test_floor_is_capped_at_best_known_offer_and_never_below_benefit():
    household = _unemployed(reservation_floor_share=0.7)
    # Slack market: s = 0.7, s*M = 35 > benefit 30.
    assert household.adaptive_reservation_floor(_context(tightness=0.0)) == pytest.approx(35.0)
    # Tight market: s -> 1, s*M = 50.
    assert household.adaptive_reservation_floor(_context(tightness=1.0)) == pytest.approx(50.0)
    # Generous benefit above every offer: capped at the best offer.
    assert household.adaptive_reservation_floor(_context(benefit=90.0)) == pytest.approx(60.0)
    # Benefit above s*M but below the best offer: the benefit binds.
    assert household.adaptive_reservation_floor(_context(benefit=45.0, tightness=0.0)) == pytest.approx(45.0)


def test_known_firms_beat_economy_wide_offers():
    household = _unemployed(reservation_floor_share=0.7)
    household.awareness_pool = {"food": [1]}
    assert household.known_offer_stats(_context()) == (40.0, 40.0)
    household.awareness_pool = {"food": [99]}  # knows no posting firm
    assert household.known_offer_stats(_context()) == (50.0, 60.0)


def test_no_offers_yet_means_no_floor():
    household = _unemployed()
    assert household.adaptive_reservation_floor(_context(offers={})) is None


def test_job_loss_restarts_at_last_wage_then_decays_slowly(adaptive_on):
    household = make_household(1, cash_balance=0.0, reservation_decay_rate=0.0014, reservation_floor_share=0.5)
    household.employer_id = 7
    household.wage = 80.0
    household.awareness_pool = {}
    context = _context(tightness=0.5)
    household.apply_labor_outcome({"employer_id": None, "wage": 0.0}, reservation_context=context)
    # One week: d = 0.0014 * (2 - 0.5) = 0.0021.
    assert household.reservation_wage == pytest.approx(80.0 * (1 - 0.0021))


def test_slack_market_decays_faster_and_savings_do_not_matter(adaptive_on):
    def week(tightness, cash, deposit=0.0):
        household = _unemployed(cash_balance=cash, reservation_decay_rate=0.0014, reservation_floor_share=0.5)
        household.bank_deposit = deposit
        household.unemployment_duration = 5
        household.category_experience = {"Food": 10}
        household.reservation_wage = 100.0
        household.apply_labor_outcome({"employer_id": None, "wage": 0.0},
                                      reservation_context=_context(tightness=tightness))
        return 100.0 - household.reservation_wage

    assert week(0.0, 0.0) > week(1.0, 0.0)          # slack market
    assert week(0.0, 0.0) == pytest.approx(100.0 * 0.0014 * 2.0)
    # Savings are neutral: broke, cash-rich and deposit-rich decay alike.
    assert week(0.5, 0.0) == pytest.approx(week(0.5, 1e6)) == pytest.approx(week(0.5, 0.0, 1e6))
    assert week(0.5, 0.0) == pytest.approx(100.0 * 0.0014 * 1.5)


def test_reservation_never_falls_below_the_floor(adaptive_on):
    household = _unemployed(cash_balance=0.0, reservation_decay_rate=0.004, reservation_floor_share=0.7)
    household.category_experience = {"Food": 10}
    household.reservation_wage = 36.0
    for _ in range(200):
        household.apply_labor_outcome({"employer_id": None, "wage": 0.0},
                                      reservation_context=_context(tightness=0.0))
    assert household.reservation_wage == pytest.approx(35.0)


def test_plan_uses_live_floor_instead_of_one_dollar(adaptive_on):
    household = _unemployed(reservation_floor_share=0.7)
    household.reservation_wage = 0.5
    plan = household.plan_labor_supply(30.0, reservation_context=_context(tightness=0.0))
    assert plan["reservation_wage"] == pytest.approx(35.0)


def test_flag_off_keeps_legacy_reservation():
    household = _unemployed()
    household.reservation_wage = 0.5
    plan = household.plan_labor_supply(30.0, reservation_context=_context())
    assert plan["reservation_wage"] == pytest.approx(1.0)  # legacy $1 floor


def test_economy_job_finding_rate_and_context(adaptive_on):
    economy = make_economy(num_households=20)
    assert economy.job_finding_rate() is None
    context = economy._build_reservation_context(30.0)
    assert context["offers"] == {} and context["tightness"] == 0.5
    economy.step()
    rate = economy.job_finding_rate()
    assert rate is not None and 0.0 <= rate <= 1.0
    offers = economy.get_posted_wage_offers(include_baseline=True)
    assert economy._build_reservation_context(30.0)["offers"] == offers
