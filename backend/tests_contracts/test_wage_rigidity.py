"""Contracts for round 1 PR4b wage rigidity (CONFIG.firms.wage_rigidity_enabled).

Requirements:
- outside survival mode (cash runway >= survival_mode_runway_weeks) no
  current worker's contract wage is cut: distress cut, baseline labor-share
  cut, healthcare reset;
- in survival mode the old cuts apply;
- a posted offer falls at most offer_cut_cap per tick, the cap rises
  smoothly with unemployment, and raises are never capped;
- with the flag off every rule is the old one.
"""

import contextlib
import io
import math
import random

import numpy as np
import pytest

from agents import FirmAgent
from config import CONFIG, clone_config, use_config
from tools.runners.run_large_simulation import create_large_economy


@pytest.fixture(autouse=True)
def _isolated_config():
    with use_config(clone_config()):
        yield


def _distressed_firm(category="Food", is_baseline=False, runway=5.0):
    firm = FirmAgent(
        firm_id=3, good_name=category, cash_balance=1_000.0, inventory_units=0.0, good_category=category,
        quality_level=5.0, wage_offer=60.0, price=10.0, expected_sales_units=10.0,
        production_capacity_units=10.0, productivity_per_worker=10.0, is_baseline=is_baseline,
    )
    firm.policy_minimum_wage = 36.0
    firm.employees = [1, 2]
    firm.actual_wages = {1: 60.0, 2: 80.0}
    firm._invalidate_wage_bill_cache()
    firm.cash_runway_ticks = runway
    firm.smoothed_profit_margin = -0.5  # distressed, so the old rule cuts
    firm.offer_cut_cap = 0.02
    return firm


@pytest.mark.parametrize("is_baseline", [False, True])
def test_distress_cut_spares_current_staff_outside_survival(is_baseline):
    firm = _distressed_firm(is_baseline=is_baseline)
    firm.adjust_wages_to_revenue_ratio(revenue=50.0)
    assert firm.actual_wages == {1: 60.0, 2: 80.0}
    # The offer still falls, by no more than the cap.
    assert firm.wage_offer == pytest.approx(60.0 * 0.98)


@pytest.mark.parametrize("is_baseline", [False, True])
def test_distress_cut_applies_in_survival_mode(is_baseline):
    firm = _distressed_firm(is_baseline=is_baseline, runway=1.0)
    firm.adjust_wages_to_revenue_ratio(revenue=50.0)
    cut = 0.98 if not is_baseline else CONFIG.firms.max_wage_decrease_per_tick
    assert firm.actual_wages[1] == pytest.approx(max(60.0 * cut, 36.0))
    assert firm.actual_wages[2] == pytest.approx(max(80.0 * cut, 36.0))


@pytest.mark.parametrize("enabled", [False, True])
def test_baseline_offer_cut_capped_only_when_enabled(enabled):
    CONFIG.firms.wage_rigidity_enabled = enabled
    firm = _distressed_firm(is_baseline=True)
    firm.adjust_wages_to_revenue_ratio(revenue=50.0)
    expected = 60.0 * (0.98 if enabled else CONFIG.firms.max_wage_decrease_per_tick)
    assert firm.wage_offer == pytest.approx(expected)


def test_flag_off_restores_the_old_staff_cut():
    CONFIG.firms.wage_rigidity_enabled = False
    firm = _distressed_firm()
    firm.adjust_wages_to_revenue_ratio(revenue=50.0)
    assert firm.actual_wages == {1: pytest.approx(58.8), 2: pytest.approx(78.4)}


@pytest.mark.parametrize("runway, enabled, expected", [
    (5.0, True, {1: 60.0, 2: 80.0}),   # no cut outside survival
    (1.0, True, {1: 36.0, 2: 36.0}),   # survival: reset to the minimum wage
    (5.0, False, {1: 36.0, 2: 36.0}),  # flag off: old reset
])
def test_healthcare_reset_respects_rigidity(runway, enabled, expected):
    CONFIG.firms.wage_rigidity_enabled = enabled
    firm = _distressed_firm(category="Healthcare", is_baseline=True, runway=runway)
    firm.apply_price_and_wage_updates({"price_next": 10.0, "markup_next": 0.1}, {"wage_offer_next": 36.0})
    assert firm.actual_wages == pytest.approx(expected)


def test_capped_offer_limits_cuts_not_raises():
    firm = _distressed_firm()
    assert firm.capped_offer(40.0, 50.0) == pytest.approx(49.0)
    assert firm.capped_offer(49.5, 50.0) == pytest.approx(49.5)
    assert firm.capped_offer(70.0, 50.0) == pytest.approx(70.0)
    firm.cash_runway_ticks = 1.0
    assert firm.capped_offer(40.0, 50.0) == pytest.approx(40.0)


def test_offer_cut_cap_rises_smoothly_with_unemployment():
    caps = [CONFIG.firms.offer_cut_cap_max * math.tanh(u / CONFIG.firms.offer_cut_slack_scale)
            for u in (0.0, 0.02, 0.05, 0.10, 0.36)]
    assert caps[0] == 0.0
    assert all(a < b for a, b in zip(caps, caps[1:]))
    assert caps[3] == pytest.approx(0.0152, abs=1e-4)
    assert caps[-1] <= CONFIG.firms.offer_cut_cap_max


def test_seeded_run_posts_no_offer_cut_above_the_cap():
    CONFIG.firms.wage_rigidity_enabled = True
    random.seed(42)
    np.random.seed(42)
    CONFIG.random_seed = 42
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(300, 3)
        for _ in range(40):
            before = {firm.firm_id: firm.wage_offer for firm in economy.firms}
            economy.step()
            for firm in economy.firms:
                old = before.get(firm.firm_id)
                if old is None or firm.wage_cuts_allowed():
                    continue
                assert firm.wage_offer >= old * (1.0 - firm.offer_cut_cap) - 1e-9, firm.firm_id
                assert 0.0 <= firm.offer_cut_cap <= CONFIG.firms.offer_cut_cap_max
