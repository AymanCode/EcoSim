import math

import numpy as np

from agents import FirmAgent, HouseholdAgent
from config import CONFIG


def test_contract_no_spiral_collapse_under_baseline(tiny_economy_factory):
    """Contract L: Short baseline run should stay numerically and behaviorally sane."""
    economy = tiny_economy_factory(
        num_households=12,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=444,
        government_cash=80_000.0,
    )

    for _ in range(15):
        economy.step()

    health = np.array([h.health for h in economy.households], dtype=float)
    happiness = np.array([h.happiness for h in economy.households], dtype=float)
    morale = np.array([h.morale for h in economy.households], dtype=float)

    assert np.mean(health) > 0.1
    assert np.mean(happiness) > 0.1
    assert np.mean(morale) > 0.1

    assert np.isfinite(health).all()
    assert np.isfinite(happiness).all()
    assert np.isfinite(morale).all()

    unemployment_rate = sum(1 for h in economy.households if not h.is_employed) / len(economy.households)
    assert unemployment_rate < 1.0

    for firm in economy.firms:
        assert firm.price > 0.0
        assert math.isfinite(firm.price)
        assert math.isfinite(firm.wage_offer)
        assert math.isfinite(firm.cash_balance)


def test_contract_healthcare_demand_appears_when_health_is_low(tiny_economy_factory):
    """Contract M: Low-health households generate more healthcare service demand."""
    economy = tiny_economy_factory(
        num_households=10,
        num_firms_per_category=1,
        include_healthcare=True,
        baseline_firms=False,
        disable_shocks=True,
        seed=555,
    )

    low_ids = {h.household_id for h in economy.households[:5]}
    high_ids = {h.household_id for h in economy.households[5:]}

    for household in economy.households:
        household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
        if household.household_id in low_ids:
            household.health = 0.1
            # Force low-health households to have pending visits (new episode model).
            household.pending_healthcare_visits = 3
            household.next_healthcare_request_tick = 0
        else:
            household.health = 0.95
            # Healthy households should not request care this tick.
            household.pending_healthcare_visits = 0
            household.next_healthcare_request_tick = economy.current_tick + 999

    healthcare_firms = [f for f in economy.firms if f.good_category.lower() == "healthcare"]
    assert healthcare_firms
    for firm in healthcare_firms:
        firm.employees = list(range(1000 + firm.firm_id, 1004 + firm.firm_id))
        firm.healthcare_capacity_per_worker = 2.0

    economy._enqueue_healthcare_requests()

    low_requested = sum(
        1 for household in economy.households
        if household.household_id in low_ids and household.queued_healthcare_firm_id is not None
    )
    high_requested = sum(
        1 for household in economy.households
        if household.household_id in high_ids and household.queued_healthcare_firm_id is not None
    )

    assert low_requested > 0
    assert low_requested > high_requested

    per_firm_sales = {}
    economy._process_healthcare_services(per_firm_sales)
    total_completed = sum(f.healthcare_completed_visits_last_tick for f in healthcare_firms)
    total_capacity = sum(len(f.employees) * f.healthcare_capacity_per_worker for f in healthcare_firms)
    assert total_completed <= total_capacity + 1e-8


def test_contract_firm_survival_mode_behaviors():
    """Contract N: Survival mode engages and blocks R&D/dividends under distress."""
    firm = FirmAgent(
        firm_id=900,
        good_name="StressFirm",
        cash_balance=100.0,
        inventory_units=300.0,
        good_category="Food",
        quality_level=5.0,
        wage_offer=100.0,
        price=10.0,
        expected_sales_units=200.0,
        production_capacity_units=400.0,
        productivity_per_worker=12.0,
        personality="moderate",
        is_baseline=False,
    )

    # Give the firm a known run-rate so it is below the 2-week runway threshold.
    firm.employees = list(range(1, 11))
    firm.actual_wages = {employee_id: 100.0 for employee_id in firm.employees}
    firm.last_revenue = 0.0

    plan = firm.plan_production_and_labor(
        last_tick_sales_units=0.0,
        in_warmup=False,
        total_households=30,
    )

    assert firm.survival_mode is True
    assert len(plan["planned_layoffs_ids"]) > 0
    assert plan["planned_hires_count"] == 0
    assert plan["planned_production_units"] <= firm.production_capacity_units * 0.1 + 1e-9

    # In survival mode, R&D and dividends should be halted.
    rd_spend = firm.apply_rd_and_quality_update(revenue=1_000.0)
    assert rd_spend == 0.0

    owner = HouseholdAgent(household_id=1, skills_level=0.5, age=30, cash_balance=1_000.0)
    firm.net_profit = 5_000.0
    firm.owners = [1]
    paid = firm.distribute_profits({1: owner})
    assert paid == 0.0


def test_contract_post_warmup_labor_market_remains_active(tiny_economy_factory):
    """Contract O: After warmup (tick > 52), non-healthcare labor matching still produces hires."""
    economy = tiny_economy_factory(
        num_households=180,
        num_firms_per_category=3,
        include_healthcare=True,
        baseline_firms=True,
        disable_shocks=True,
        seed=777,
        government_cash=120_000.0,
    )

    post_warmup_hires = 0
    for _ in range(70):
        economy.step()
        if economy.current_tick > 52:
            post_warmup_hires += sum(
                int(getattr(firm, "last_tick_actual_hires", 0))
                for firm in economy.firms
                if (firm.good_category or "").lower() != "healthcare"
            )

    assert economy.current_tick >= 70
    assert economy.in_warmup is False

    # A hard failure mode is "everyone can work but matching never hires".
    work_capable = [h for h in economy.households if h.can_work]
    employed_capable = sum(1 for h in work_capable if h.is_employed)
    assert employed_capable > 0
    assert post_warmup_hires > 0

    # Diagnostics should still indicate active seekers (not a dead labor market).
    diagnostics = economy.last_labor_diagnostics
    assert diagnostics.get("labor_seekers_total", 0.0) > 0.0
