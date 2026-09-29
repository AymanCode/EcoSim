"""Remediation phase 6: flag-gated macro behavior fixes.

Each fix sits behind a config flag that defaults to the old behavior. Every
test here checks the flag-on behavior and that the flag-off path keeps the
old behavior.
"""

import random

import numpy as np
import pytest

from config import CONFIG
from tests_contracts.factories import patch_agent_method


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


# --- B13/B14: job-switcher vacancies (fix_switcher_vacancies)


def _labor_plan(household, *, reservation=10.0, switching=False):
    return {
        "household_id": household.household_id,
        "skills_level": household.skills_level,
        "reservation_wage": reservation,
        "searching_for_job": True,
        "job_switching": switching,
        "medical_only": False,
    }


def _production_plan(hires=0, layoffs=()):
    return {"planned_hires_count": hires, "planned_layoffs_ids": list(layoffs)}


def _switcher_market(factory):
    """Private idle firms 1-3; switcher 1 works at firm 1, switcher 5 is laid off by firm 3."""
    switcher = factory.household(household_id=1, skills_level=0.9, employer_id=1, wage=50.0)
    unemployed = [factory.household(household_id=i, skills_level=0.5) for i in (2, 3, 4)]
    laid_off_switcher = factory.household(household_id=5, skills_level=0.4, employer_id=3, wage=50.0)
    firms = [
        factory.firm(firm_id=1, is_baseline=False, employees=[1], actual_wages={1: 50.0}),
        factory.firm(firm_id=2, is_baseline=False),
        factory.firm(firm_id=3, is_baseline=False, employees=[5], actual_wages={5: 50.0}),
    ]
    households = [switcher, *unemployed, laid_off_switcher]
    economy = factory.economy(households=households, firms=firms)
    production = {1: _production_plan(), 2: _production_plan(), 3: _production_plan(layoffs=[5])}
    wages = {fid: {"wage_offer_next": 60.0} for fid in (1, 2, 3)}
    labor = {h.household_id: _labor_plan(h) for h in unemployed}
    labor[1] = _labor_plan(switcher, switching=True)
    # Nobody's offer reaches household 5's reservation wage.
    labor[5] = _labor_plan(laid_off_switcher, reservation=1_000.0, switching=True)
    return economy, production, wages, labor


def test_b13_flag_off_switchers_open_vacancies_for_everyone(factory):
    assert CONFIG.labor_market.fix_switcher_vacancies is False
    economy, production, wages, labor = _switcher_market(factory)
    firm_out, hh_out = economy._match_labor_fast(production, wages, labor)
    # Two switchers give every private idle firm, the laying-off one too, two
    # vacancies, written into the caller's plans and filled from the whole pool.
    assert [production[fid]["planned_hires_count"] for fid in (1, 2, 3)] == [2, 2, 2]
    assert all(firm_out[fid]["synthetic_switcher_vacancies"] == 2 for fid in (1, 2, 3))
    assert sum(hh_out[i]["employer_id"] is not None for i in (2, 3, 4)) == 3
    # The laid-off switcher falls back to the firm that laid them off.
    assert hh_out[5]["employer_id"] == 3


def test_b13_flag_on_switcher_vacancies_are_local_capped_and_switcher_only(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.labor_market, "fix_switcher_vacancies", True)
    economy, production, wages, labor = _switcher_market(factory)
    firm_out, hh_out = economy._match_labor_fast(production, wages, labor)
    assert [production[fid]["planned_hires_count"] for fid in (1, 2, 3)] == [0, 0, 0]
    # Cap 1 per firm; none for the firm planning layoffs.
    assert [firm_out[fid]["synthetic_switcher_vacancies"] for fid in (1, 2, 3)] == [1, 1, 0]
    # Unemployed non-switchers do not fill switcher vacancies.
    assert all(hh_out[i]["employer_id"] is None for i in (2, 3, 4))
    # The switcher cannot be "hired" by their own employer; firm 2 takes them.
    assert hh_out[1]["employer_id"] == 2
    assert firm_out[2]["hired_households_ids"] == [1]
    assert firm_out[1]["hired_households_ids"] == []
    # A laid-off switcher who found nothing stays laid off.
    assert hh_out[5]["employer_id"] is None


@pytest.mark.parametrize("tick", range(6))
def test_b14_flag_on_hiring_firm_skips_own_worker_without_losing_them(factory, monkeypatch, tick):
    monkeypatch.setattr(CONFIG.labor_market, "fix_switcher_vacancies", True)
    own = factory.household(household_id=6, skills_level=0.9, employer_id=4, wage=50.0)
    other = factory.household(household_id=2, skills_level=0.5)
    firms = [
        factory.firm(firm_id=4, is_baseline=True, employees=[6], actual_wages={6: 50.0}),
        factory.firm(firm_id=5, is_baseline=True),
    ]
    economy = factory.economy(households=[own, other], firms=firms)
    economy.current_tick = tick  # varies the seeded firm order
    production = {4: _production_plan(hires=1), 5: _production_plan(hires=1)}
    wages = {4: {"wage_offer_next": 60.0}, 5: {"wage_offer_next": 60.0}}
    labor = {6: _labor_plan(own, switching=True), 2: _labor_plan(other)}
    firm_out, hh_out = economy._match_labor_fast(production, wages, labor)
    assert hh_out[6]["employer_id"] == 5
    assert hh_out[2]["employer_id"] == 4
    assert firm_out[4]["hired_households_ids"] == [2]


# --- B11: living cost from category prices (fix_category_price_beliefs)


def test_b11_plan_labor_supply_uses_category_prices_when_given(factory):
    worker = factory.household(household_id=1, employer_id=1, wage=100.0, min_food_per_tick=2.0)
    # Real beliefs are keyed by good name, so the old "housing"/"food" lookups miss.
    worker.price_beliefs = {"HousingFirm2": 200.0, "FoodFirm3": 8.0}
    old_living_cost = 0.3 * worker.default_price_level + 2.0 * worker.default_price_level
    new_living_cost = 0.3 * 200.0 + 2.0 * 8.0
    worker.cash_balance = (old_living_cost + new_living_cost) / 2.0
    assert worker.plan_labor_supply()["searching_for_job"] is False
    plan = worker.plan_labor_supply(category_expected_prices={"housing": 200.0, "food": 8.0})
    assert plan["searching_for_job"] is True


def _category_price_economy(factory):
    worker = factory.household(household_id=1, employer_id=4, wage=20.0)
    firms = [
        factory.firm(firm_id=1, category="Housing", price=300.0),
        factory.firm(firm_id=2, category="Housing", price=100.0),
        factory.firm(firm_id=3, category="Housing", price=200.0),
        factory.firm(firm_id=4, category="Food", price=20.0, employees=[1], actual_wages={1: 20.0}),
        factory.firm(firm_id=5, category="Healthcare", price=999.0),
    ]
    return worker, factory.economy(households=[worker], firms=firms)


@pytest.mark.parametrize("flag", [False, True])
def test_b11_step_passes_median_category_prices_only_with_flag(factory, monkeypatch, flag):
    monkeypatch.setattr(CONFIG.households, "fix_category_price_beliefs", flag)
    worker, economy = _category_price_economy(factory)
    seen = []
    original = worker.plan_labor_supply

    def record(*args, **kwargs):
        seen.append(kwargs.get("category_expected_prices"))
        return original(*args, **kwargs)

    patch_agent_method(monkeypatch, worker, "plan_labor_supply", record)
    economy.step()
    if flag:
        assert seen == [{"housing": 200.0, "food": 20.0}]
    else:
        assert seen == [None]


@pytest.mark.parametrize("flag", [False, True])
def test_b11_post_warmup_living_cost_floor(factory, monkeypatch, flag):
    monkeypatch.setattr(CONFIG.households, "fix_category_price_beliefs", flag)
    worker, economy = _category_price_economy(factory)
    economy._reset_post_warmup_expectations()
    if flag:
        # Median housing 200, food 20: living cost 0.3 * 200 + min_food * 20.
        expected = 0.3 * 200.0 + worker.min_food_per_tick * 20.0
    else:
        default = worker.default_price_level
        expected = max(25.0, 0.3 * default + worker.min_food_per_tick * default)
    expected = max(expected, economy.government.get_minimum_wage())
    assert worker.wage == pytest.approx(expected)


# --- B32: tie-break noise per firm, additive friction (fix_seller_choice_noise)


def _food_primary(factory, firm_ids):
    """Primary food firm a fresh household picks among equal-utility sellers."""
    household = factory.household(household_id=17, cash_balance=1_000.0)
    n = len(firm_ids)
    cache = {"food": {
        "firm_ids": np.array(firm_ids, dtype=np.int64),
        "prices": np.full(n, 5.0),
        "qualities": np.full(n, 5.0),
    }}
    household._plan_category_purchases(
        100.0,
        price_cache={"food": (5.0, 5.0, 5.0)},
        category_fraction_override={"food": 1.0},
        category_array_cache=cache,
    )
    return household.current_primary_firm["food"]


def test_b32_flag_off_primary_follows_pool_position(factory):
    assert CONFIG.households.fix_seller_choice_noise is False
    # Noise is indexed by position, so reordering the same pool flips the pick.
    assert _food_primary(factory, [1, 2]) != _food_primary(factory, [2, 1])


def test_b32_flag_on_primary_follows_firm_not_position(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.households, "fix_seller_choice_noise", True)
    state_np = np.random.get_state()[1].copy()
    state_py = random.getstate()
    first = _food_primary(factory, [1, 2, 3])
    assert _food_primary(factory, [3, 2, 1]) == first
    assert _food_primary(factory, [2, first] if first != 2 else [1, 2]) == first
    # Deterministic hashing does not consume the shared RNGs.
    assert np.array_equal(np.random.get_state()[1], state_np)
    assert random.getstate() == state_py


def test_b32_flag_on_noise_is_bounded_and_stable_per_firm(factory, monkeypatch):
    monkeypatch.setattr(CONFIG.households, "fix_seller_choice_noise", True)
    household = factory.household(household_id=5)
    wide = household._firm_tie_break_noise("food", np.array([1, 2, 3, 4], dtype=np.int64))
    narrow = household._firm_tie_break_noise("food", np.array([4, 2], dtype=np.int64))
    assert narrow.tolist() == [wide[3], wide[1]]
    # The per-category cache returns the same values when a pool comes back.
    again = household._firm_tie_break_noise("food", np.array([1, 2, 3, 4], dtype=np.int64))
    assert again.tolist() == wide.tolist()
    scale = CONFIG.households.tie_break_scale
    assert np.all(np.abs(wide) <= scale) and np.ptp(wide) > 0.0
    other_category = household._firm_tie_break_noise("services", np.array([1, 2, 3, 4], dtype=np.int64))
    assert not np.array_equal(wide, other_category)


@pytest.mark.parametrize("flag", [False, True])
def test_b32_friction_with_negative_utilities(factory, monkeypatch, flag):
    monkeypatch.setattr(CONFIG.households, "fix_seller_choice_noise", flag)
    household = factory.household(household_id=5)
    household.current_primary_firm["food"] = 1
    friction = CONFIG.households.switching_friction_food
    # Firm 2 is better by a quarter of the friction margin.
    current, best = -2.0, -2.0 + 0.25 * friction * 2.0
    target = household._apply_switching_friction("food", 2, best, {1: current, 2: best})
    # Multiplicative friction inverts below zero: the small gain switches.
    assert target == (1 if flag else 2)
    # A gain above the margin switches either way.
    household.current_primary_firm["food"] = 1
    best = -2.0 + 2.0 * friction * 2.0
    assert household._apply_switching_friction("food", 2, best, {1: current, 2: best}) == 2


# --- B10: category preferences applied once (fix_preference_applied_once)


def test_b10_batch_fractions_apply_preferences_once_and_cache_follows_flag(factory, monkeypatch):
    household = factory.household(household_id=1)
    household.food_preference, household.housing_preference, household.services_preference = 2.0, 1.0, 1.0
    # What __post_init__ stores for an equal base: normalize(base * preference).
    household.category_weights = {"food": 0.5, "housing": 0.25, "services": 0.25}
    economy = factory.economy(households=[household], firms=[factory.firm(firm_id=1)])

    assert CONFIG.households.fix_preference_applied_once is False
    squared = economy._household_static_traits()["precomputed_fractions"][0]
    # Flag off: the preference multiplies again, so food's share is 2^2 / (4 + 1 + 1).
    assert squared == pytest.approx({"food": 4.0 / 6.0, "housing": 1.0 / 6.0, "services": 1.0 / 6.0})

    monkeypatch.setattr(CONFIG.households, "fix_preference_applied_once", True)
    once = economy._household_static_traits()["precomputed_fractions"][0]
    assert once == pytest.approx({"food": 0.5, "housing": 0.25, "services": 0.25})

    monkeypatch.setattr(CONFIG.households, "fix_preference_applied_once", False)
    assert economy._household_static_traits()["precomputed_fractions"][0] == pytest.approx(squared)
