"""Infrastructure spending raises firms' production frontier.

Before the fix, ``infrastructure_productivity_multiplier`` multiplied realized
goods output and was then clamped to ``_capacity_for_workers(n)``, which did
not include it, so a firm producing at its frontier got nothing from it, and
Services never saw it. In a seed-42 run with high infrastructure (multiplier
1.05-1.15) realized private Food output rose 0.2% and Services 0%.
"""

import pytest

from config import CONFIG


def _staffed(economy, category: str, workers: int):
    firm = next(f for f in economy.firms if f.good_category == category)
    staff = economy.households[:workers]
    for household in staff:
        household.employer_id = firm.firm_id
    firm.employees = [h.household_id for h in staff]
    return firm


def test_frontier_and_labor_need_scale_with_public_capital():
    from agents import FirmAgent

    firm = FirmAgent(
        firm_id=1, good_name="Food1", cash_balance=10_000.0, inventory_units=0.0,
        good_category="Food", quality_level=5.0, wage_offer=40.0, price=8.0,
        expected_sales_units=100.0, production_capacity_units=10_000.0,
        productivity_per_worker=12.0, personality="moderate",
    )
    base_capacity = firm._capacity_for_workers(20)
    base_workers = firm._workers_for_sales(base_capacity)

    firm.public_capital_tfp = 1.15

    assert firm._capacity_for_workers(20) == pytest.approx(1.15 * base_capacity)
    assert firm._workers_for_sales(base_capacity) < base_workers


def test_goods_firm_at_its_frontier_produces_more_with_infrastructure(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=30)
    firm = _staffed(economy, "Food", workers=10)
    firm.production_capacity_units = 1e9  # isolate the labor frontier
    without = economy._calculate_experience_adjusted_production(firm, firm._capacity_for_workers(10))

    economy.government.infrastructure_productivity_multiplier = 1.15
    firm.public_capital_tfp = 1.15  # what the planning phase sets each tick
    with_infra = economy._calculate_experience_adjusted_production(firm, firm._capacity_for_workers(10))

    assert with_infra == pytest.approx(1.15 * without)


def test_flag_off_keeps_the_pre_fix_clamp(tiny_economy_factory, monkeypatch):
    monkeypatch.setattr(CONFIG.government, "infrastructure_raises_firm_capacity_enabled", False)
    economy = tiny_economy_factory(num_households=30)
    firm = _staffed(economy, "Food", workers=10)
    firm.production_capacity_units = 1e9
    planned = firm._capacity_for_workers(10)
    without = economy._calculate_experience_adjusted_production(firm, planned)

    economy.government.infrastructure_productivity_multiplier = 1.15
    with_infra = economy._calculate_experience_adjusted_production(firm, planned)

    # The multiplier is applied, then clamped back to the frontier.
    assert with_infra == pytest.approx(min(planned, without * 1.15))
    assert with_infra <= planned


def test_services_capacity_scales_with_infrastructure(tiny_economy_factory):
    economy = tiny_economy_factory(num_households=30)
    firm = _staffed(economy, "Services", workers=5)
    firm.production_capacity_units = 5  # five worker slots
    unlimited_plan = 1e9
    without = economy._calculate_experience_adjusted_production(firm, unlimited_plan)

    firm.public_capital_tfp = 1.15
    with_infra = economy._calculate_experience_adjusted_production(firm, unlimited_plan)

    assert with_infra == pytest.approx(1.15 * without)


def test_planning_phase_hands_firms_the_live_multiplier(tiny_economy_factory, monkeypatch):
    economy = tiny_economy_factory(num_households=30)
    economy.step()
    assert all(f.public_capital_tfp == 1.0 for f in economy.firms)  # lever "none"

    economy.government.infrastructure_productivity_multiplier = 1.1
    economy.step()
    # The multiplier may decay within the step; firms got the value at planning.
    assert all(f.public_capital_tfp == pytest.approx(1.1) for f in economy.firms)

    monkeypatch.setattr(CONFIG.government, "infrastructure_raises_firm_capacity_enabled", False)
    economy.step()
    assert all(f.public_capital_tfp == 1.0 for f in economy.firms)
