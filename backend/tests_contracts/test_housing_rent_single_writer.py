"""The legacy Housing rent has one writer per tick (legacy payment path).

Before this fix the housing phase moved ``firm.price`` with the occupancy rule,
the dynamic rent floor ``max(10, p25 wage x 0.30)`` and the rent-stabilization
cap, and firm settlement then overwrote it with the ``plan_pricing`` result.
In a seeded run the posted rent went 5 -> 10.8 -> 5 every week, so none of
those three rules reached tenants. These tests check the posted rent a tenant
would see at the end of each tick.
"""

import contextlib
import io

import pytest

from agents import GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import make_firm, make_household, seed_everything
from tools.runners.run_large_simulation import create_large_economy

SEED = 42
HOUSEHOLDS = 300
TICKS = 24


def _rule(monkeypatch, rule: str) -> None:
    monkeypatch.setattr(CONFIG.labor_market, "housing_rent_rule", rule, raising=False)


@pytest.fixture
def single_writer(monkeypatch):
    _rule(monkeypatch, "plan_then_market")


def _run(*, lever: str = "off", ticks: int = TICKS):
    """Run a seeded legacy economy; return per-tick (start, end) Housing rents."""
    original_seed = CONFIG.random_seed
    CONFIG.random_seed = SEED
    seed_everything(SEED)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=HOUSEHOLDS)
        economy.government.rent_stabilization_level = lever
        history = []
        for _ in range(ticks):
            start = {f.firm_id: f.price for f in economy.firms if f.good_category == "Housing"}
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            end = {f.firm_id: f.price for f in economy.firms if f.good_category == "Housing"}
            history.append((start, end))
        return economy, history
    finally:
        CONFIG.random_seed = original_seed


def test_dynamic_rent_floor_survives_firm_settlement(single_writer):
    _, history = _run()
    floor = CONFIG.labor_market.rent_floor_absolute_min
    for start, end in history[2:]:
        for firm_id, rent in end.items():
            assert rent >= floor - 1e-9, (firm_id, start.get(firm_id), rent)


def test_strict_rent_stabilization_caps_the_weekly_rise(single_writer):
    economy, history = _run(lever="strict")
    lm = CONFIG.labor_market
    strict = CONFIG.government.rent_stabilization_strict_max_increase
    wage_p25 = economy.cached_wage_percentiles[0] or 0.0
    # Once the floor is reached, a week's rise is at most the strict multiplier
    # unless the (rising) floor itself lifts the rent.
    for start, end in history[4:]:
        for firm_id, rent in end.items():
            before = start.get(firm_id)
            if before is None:
                continue
            floor_now = max(lm.rent_floor_absolute_min, wage_p25 * lm.rent_affordability_share)
            assert rent <= max(before * strict, floor_now) + 1e-6, (firm_id, before, rent)


def test_rent_stabilization_changes_the_posted_rent_when_the_market_raises_it(monkeypatch):
    # Under "plan_then_market" the seeded landlord's plan cuts rent faster than
    # full occupancy raises it, so rent sits on the dynamic floor, which the
    # cap does not limit. Under "market_or_plan_higher" occupancy drives rent
    # up and the lever must bite.
    _rule(monkeypatch, "market_or_plan_higher")
    _, off = _run(lever="off", ticks=40)
    _, strict = _run(lever="strict", ticks=40)
    for firm_id, rent in strict[-1][1].items():
        assert rent < off[-1][1][firm_id]


def test_flag_off_restores_the_settlement_overwrite(monkeypatch):
    _rule(monkeypatch, "settlement_overwrites")
    _, history = _run(ticks=14)
    for _, end in history[2:]:
        for rent in end.values():
            assert rent < CONFIG.labor_market.rent_floor_absolute_min


def _economy_with_full_landlord(price: float):
    household: HouseholdAgent = make_household(household_id=1, cash_balance=500.0)
    household.employer_id = 99
    household.wage = 1_000.0
    household.renting_from_firm_id = 10
    household.monthly_rent = price
    household.owns_housing = True
    firm = make_firm(
        firm_id=10,
        category="Housing",
        is_baseline=True,
        cash_balance=5_000.0,
        max_rental_units=1,
        price=price,
    )
    firm.current_tenants = [household.household_id]
    government = GovernmentAgent(cash_balance=50_000.0, unemployment_benefit_level=0.0, transfer_budget=0.0)
    economy = Economy(households=[household], firms=[firm], government=government)
    economy.cached_wage_percentiles = (None, None, None)
    return economy, firm


def test_market_rules_start_from_the_firm_plan_and_cap_against_last_week(single_writer):
    economy, firm = _economy_with_full_landlord(price=20.0)
    # Settlement has applied the firm's own plan (+15% obligation coverage).
    firm.price = 23.0
    economy._apply_legacy_housing_rent_rules({firm.firm_id: 20.0})
    # Full occupancy: plan x 1.02.
    assert firm.price == pytest.approx(23.0 * CONFIG.labor_market.rent_increase_high_occupancy)

    economy.government.rent_stabilization_level = "soft"
    firm.price = 23.0
    economy._apply_legacy_housing_rent_rules({firm.firm_id: 20.0})
    # The cap is measured against the rent posted last week, not the plan.
    assert firm.price == pytest.approx(20.0 * CONFIG.government.rent_stabilization_soft_max_increase)
    assert firm.decision_diagnostics["rent_stabilization_limited"] is True


def test_market_or_plan_higher_keeps_the_market_move_unless_the_plan_is_higher(monkeypatch):
    _rule(monkeypatch, "market_or_plan_higher")
    economy, firm = _economy_with_full_landlord(price=20.0)
    high = CONFIG.labor_market.rent_increase_high_occupancy
    # Plan cuts rent (costs covered); the full building's market move wins.
    firm.price = 19.0
    economy._apply_legacy_housing_rent_rules({firm.firm_id: 20.0})
    assert firm.price == pytest.approx(20.0 * high)
    # Plan raises rent to cover obligations by more than the market move.
    firm.price = 23.0
    economy._apply_legacy_housing_rent_rules({firm.firm_id: 20.0})
    assert firm.price == pytest.approx(23.0)


def test_plan_then_market_is_the_default():
    assert CONFIG.labor_market.housing_rent_rule == "plan_then_market"


def test_clearing_leaves_the_price_to_the_post_settlement_writer(single_writer):
    economy, firm = _economy_with_full_landlord(price=20.0)
    economy._clear_housing_rental_market()
    assert firm.price == pytest.approx(20.0)
