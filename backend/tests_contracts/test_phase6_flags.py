"""Remediation phase 6: flag-gated macro behavior fixes.

Each fix sits behind a config flag that defaults to the old behavior. Every
test here checks the flag-on behavior and that the flag-off path keeps the
old behavior.
"""

import pytest

from config import CONFIG


# --- B12: distress wage cut survives the tick (fix_distress_wage_cut_persists)


def _distressed_baseline_firm(factory):
    firm = factory.firm(
        firm_id=1, category="Food", is_baseline=True, wage_offer=100.0,
        employees=[1, 2], actual_wages={1: 100.0, 2: 60.0},
    )
    firm.policy_minimum_wage = 20.0
    return firm


def _run_cut_then_next_tick(firm):
    """Phase 9 cut + planned-wage apply, then the next tick's phase-4 ratchet."""
    price_plan = {"price_next": firm.price, "markup_next": firm.markup}
    # Wage bill 160 against revenue 100 exceeds max_labor_share: the cut fires.
    firm.adjust_wages_to_revenue_ratio(100.0)
    cut = CONFIG.firms.max_wage_decrease_per_tick
    assert firm.actual_wages == pytest.approx({1: 100.0 * cut, 2: 60.0 * cut})
    # The wage plan was made at the start of the tick, before the cut.
    firm.apply_price_and_wage_updates(price_plan, {"wage_offer_next": 100.0})
    offer_after_update = firm.wage_offer
    firm.apply_labor_outcome({"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}})
    return offer_after_update, dict(firm.actual_wages)


def test_b12_flag_off_distress_cut_is_undone_next_tick(factory):
    assert CONFIG.firms.fix_distress_wage_cut_persists is False
    firm = _distressed_baseline_firm(factory)
    offer, wages = _run_cut_then_next_tick(firm)
    assert offer == pytest.approx(100.0)
    assert wages == pytest.approx({1: 100.0, 2: 100.0})


def test_b12_flag_on_distress_cut_survives_update_and_ratchet(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.firms, "fix_distress_wage_cut_persists", True)
    firm = _distressed_baseline_firm(factory)
    cut = CONFIG.firms.max_wage_decrease_per_tick
    offer, wages = _run_cut_then_next_tick(firm)
    assert offer == pytest.approx(100.0 * cut)
    assert wages == pytest.approx({1: 100.0 * cut, 2: 60.0 * cut})
    assert firm._current_wage_bill() == pytest.approx(160.0 * cut)

    # Only the tick after a cut is protected: without a new cut, the planned
    # offer applies and the ordinary ratchet resumes.
    firm.apply_price_and_wage_updates(
        {"price_next": firm.price, "markup_next": firm.markup}, {"wage_offer_next": 90.0}
    )
    assert firm.wage_offer == pytest.approx(90.0)
    firm.apply_labor_outcome({"hired_households_ids": [], "confirmed_layoffs_ids": [], "actual_wages": {}})
    assert firm.actual_wages == pytest.approx({1: 90.0, 2: 90.0})


def test_b12_flag_on_planned_offer_below_cut_is_kept(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.firms, "fix_distress_wage_cut_persists", True)
    firm = _distressed_baseline_firm(factory)
    firm.adjust_wages_to_revenue_ratio(100.0)
    firm.apply_price_and_wage_updates(
        {"price_next": firm.price, "markup_next": firm.markup}, {"wage_offer_next": 50.0}
    )
    assert firm.wage_offer == pytest.approx(50.0)
