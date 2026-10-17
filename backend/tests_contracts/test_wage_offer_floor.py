"""Contracts for FirmAgent.get_wage_offer_floor and Economy.get_posted_wage_offers.

Households read both. Requirement: the floor getter returns the floor each
firm's offer rule applies (max(minimum wage, 1.5 x benefit) for annual-review
and weekly-rule private Food-type firms; the minimum wage alone for baseline,
healthcare and weekly-rule Services firms), posted offers never sit below it
after warm-up, and neither getter changes an offer.
"""

import contextlib
import io
import random

import numpy as np
import pytest

from agents import FirmAgent
from config import CONFIG, clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy


def _firm(category="Food", is_baseline=False):
    firm = FirmAgent(
        firm_id=7, good_name=category, cash_balance=10_000.0, inventory_units=0.0, good_category=category,
        quality_level=5.0, wage_offer=50.0, price=10.0, expected_sales_units=100.0,
        production_capacity_units=100.0, productivity_per_worker=10.0, is_baseline=is_baseline,
    )
    firm.policy_minimum_wage = 36.0
    return firm


def test_private_floor_is_one_and_a_half_times_the_benefit_when_that_binds():
    assert _firm().get_wage_offer_floor(30.0) == pytest.approx(45.0)
    reviewed = _firm("Services")
    reviewed.annual_wage_control = True
    assert reviewed.get_wage_offer_floor(30.0) == pytest.approx(45.0)


def test_private_floor_is_the_minimum_wage_when_benefits_are_low():
    assert _firm().get_wage_offer_floor(20.0) == pytest.approx(36.0)


def test_baseline_healthcare_and_weekly_services_floors_ignore_the_benefit():
    assert _firm(is_baseline=True).get_wage_offer_floor(30.0) == pytest.approx(36.0)
    assert _firm("Healthcare").get_wage_offer_floor(30.0) == pytest.approx(36.0)
    assert _firm("Services").get_wage_offer_floor(30.0) == pytest.approx(36.0)


@pytest.fixture(scope="module")
def economy_after_30_ticks():
    with use_config(clone_config()):
        random.seed(42)
        np.random.seed(42)
        CONFIG.random_seed = 42
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(300, 3)
            for _ in range(30):
                economy.step()
        yield economy


def test_floor_is_the_tight_lower_bound_of_posted_offers(economy_after_30_ticks):
    economy = economy_after_30_ticks
    benefit = economy.government.get_unemployment_benefit_level()
    assert benefit > 0
    firms = {firm.firm_id: firm for firm in economy.firms}
    at_floor = {"private": 0, "baseline": 0}
    for firm_id, offer in economy.get_posted_wage_offers(include_baseline=True).items():
        firm = firms[firm_id]
        floor = firm.get_wage_offer_floor(benefit)
        assert offer >= floor - 1e-9, (firm_id, offer, floor)
        if abs(offer - floor) < 1e-6:
            at_floor["baseline" if firm.is_baseline else "private"] += 1
    # Some private firms post exactly 1.5x benefit and baseline firms post
    # exactly the minimum wage, so the getter is the binding floor.
    assert at_floor["private"] > 0 and at_floor["baseline"] > 0


def test_posted_offers_exclude_baseline_firms_unless_asked(economy_after_30_ticks):
    economy = economy_after_30_ticks
    baseline_ids = {firm.firm_id for firm in economy.firms if firm.is_baseline}
    private = economy.get_posted_wage_offers()
    everyone = economy.get_posted_wage_offers(include_baseline=True)
    assert private and not baseline_ids & private.keys()
    assert baseline_ids <= everyone.keys()
    assert {k: v for k, v in everyone.items() if k not in baseline_ids} == private


def test_posted_offers_is_a_copy(economy_after_30_ticks):
    economy = economy_after_30_ticks
    offers = economy.get_posted_wage_offers()
    offers.clear()
    assert economy.get_posted_wage_offers()


def test_posted_offers_empty_before_first_step():
    with use_config(clone_config()):
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(50, 1)
    assert economy.get_posted_wage_offers(include_baseline=True) == {}
