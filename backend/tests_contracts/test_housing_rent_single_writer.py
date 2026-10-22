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
from config import CONFIG, LaborMarketConfig, SimulationConfig
from economy import Economy
from tests_contracts.factories import make_firm, make_household, seed_everything
from tools.runners.run_large_simulation import create_large_economy

SEED = 42
HOUSEHOLDS = 300
TICKS = 24


def _rule(monkeypatch, rule: str) -> None:
    monkeypatch.setattr(CONFIG.labor_market, "housing_rent_rule", rule)


@pytest.fixture
def single_writer(monkeypatch):
    _rule(monkeypatch, "plan_then_market")


def _dynamic_floor(economy) -> float:
    lm = CONFIG.labor_market
    wage_p25 = economy.cached_wage_percentiles[0]
    if wage_p25 is None:
        return lm.rent_floor_absolute_min
    return max(lm.rent_floor_absolute_min, wage_p25 * lm.rent_affordability_share)


def _run(*, lever: str = "off", ticks: int = TICKS):
    """Run a seeded legacy economy.

    Returns the economy and, per tick, ``(start, end, floor)``: the Housing
    rents before and after ``step()`` and the dynamic floor the rent rules
    used that tick (read when they ran).
    """
    original_seed = CONFIG.random_seed
    CONFIG.random_seed = SEED
    seed_everything(SEED)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            economy = create_large_economy(num_households=HOUSEHOLDS)
        economy.government.rent_stabilization_level = lever
        floors = []
        apply_rules = economy._apply_legacy_housing_rent_rules

        def recording_rules(rent_before):
            floors.append(_dynamic_floor(economy))
            apply_rules(rent_before)

        economy._apply_legacy_housing_rent_rules = recording_rules
        history = []
        for _ in range(ticks):
            start = {f.firm_id: f.price for f in economy.firms if f.good_category == "Housing"}
            floors.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                economy.step()
            end = {f.firm_id: f.price for f in economy.firms if f.good_category == "Housing"}
            assert len(floors) == 1
            history.append((start, end, floors[0]))
        return economy, history
    finally:
        CONFIG.random_seed = original_seed


def test_dynamic_rent_floor_survives_firm_settlement(single_writer):
    _, history = _run()
    for start, end, floor in history:
        for firm_id, rent in end.items():
            assert rent >= floor - 1e-9, (firm_id, start.get(firm_id), rent, floor)


def test_strict_rent_stabilization_caps_the_weekly_rise(single_writer):
    _, history = _run(lever="strict")
    strict = CONFIG.government.rent_stabilization_strict_max_increase
    # A week's rise is at most the strict multiplier unless that week's
    # dynamic floor itself lifts the rent.
    for start, end, floor in history:
        for firm_id, rent in end.items():
            before = start.get(firm_id)
            if before is None:
                continue
            assert rent <= max(before * strict, floor) + 1e-6, (firm_id, before, rent, floor)


def test_rent_stabilization_does_not_change_the_seeded_legacy_rent(single_writer):
    # Current behavior, not a target: the seeded landlord's plan cuts rent
    # towards its obligation cover, so the posted rent sits on the dynamic
    # floor, and the cap never limits a rise to the floor. The strict lever
    # therefore never binds here and the rent path is the same as with it off.
    _, off = _run(lever="off", ticks=40)
    economy, strict = _run(lever="strict", ticks=40)
    assert [end for _, end, _ in strict] == [end for _, end, _ in off]
    assert economy.rent_increase_limited_count == 0
    for start, end, floor in strict[4:]:
        for firm_id, rent in end.items():
            assert rent == pytest.approx(floor), (firm_id, start.get(firm_id), rent, floor)


def test_flag_off_restores_the_settlement_overwrite(monkeypatch):
    _rule(monkeypatch, "settlement_overwrites")
    _, history = _run(ticks=14)
    for _, end, _ in history[2:]:
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


def test_strict_cap_lets_a_rise_to_the_floor_through(single_writer):
    # Current behavior, recorded so a change to it is deliberate: when the
    # wage-indexed floor jumps, the rent follows it in one week whatever the
    # lever says (whether the cap should limit this is an open owner question).
    economy, firm = _economy_with_full_landlord(price=20.0)
    economy.government.rent_stabilization_level = "strict"
    lm = CONFIG.labor_market
    economy.cached_wage_percentiles = (24.0 / lm.rent_affordability_share, None, None)
    firm.price = 19.0  # the firm's plan cut the rent
    economy._apply_legacy_housing_rent_rules({firm.firm_id: 20.0})
    assert firm.price == pytest.approx(24.0)  # +20% in one week
    assert economy.rent_increase_limited_count == 0
    assert "rent_stabilization_limited" not in firm.decision_diagnostics


def test_plan_then_market_is_the_default():
    assert LaborMarketConfig().housing_rent_rule == "plan_then_market"
    assert CONFIG.labor_market.housing_rent_rule == "plan_then_market"


@pytest.mark.parametrize("rule", ["plan_then_markt", "unknown", ""])
def test_unknown_housing_rent_rule_raises(monkeypatch, rule):
    with pytest.raises(ValueError, match="housing_rent_rule"):
        SimulationConfig(labor_market=LaborMarketConfig(housing_rent_rule=rule))
    # A value set after the config was built (as the evidence panel's --set
    # does) fails when the economy is built ...
    _rule(monkeypatch, rule)
    with pytest.raises(ValueError, match="housing_rent_rule"):
        _economy_with_full_landlord(price=20.0)
    # ... and when it is changed under a running economy.
    _rule(monkeypatch, "plan_then_market")
    economy, _ = _economy_with_full_landlord(price=20.0)
    _rule(monkeypatch, rule)
    with pytest.raises(ValueError, match="housing_rent_rule"):
        economy._clear_housing_rental_market()


def test_clearing_leaves_the_price_to_the_post_settlement_writer(single_writer):
    economy, firm = _economy_with_full_landlord(price=20.0)
    economy._clear_housing_rental_market()
    assert firm.price == pytest.approx(20.0)
