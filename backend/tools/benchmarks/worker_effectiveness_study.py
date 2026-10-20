"""Cap-binding share and realized skill/health counterfactuals. Flag on only.

The config change is undone in a finally block. This does not patch production.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import clone_config, use_config
from economy import Economy
from tools.benchmarks.regression_snapshot import _set_seed
from tools.runners.run_large_simulation import create_large_economy
from worker_effectiveness import REFERENCE_HAPPINESS, REFERENCE_MORALE, load_spec


def _quiet_step_units(category: str, skill: float, health: float, ticks: int = 8) -> float:
    """Sum of realized units over a short run. Same fixture as the contract test, repeated."""
    count = 2 if category == "Food" else 4
    total = 0.0
    workers = []
    for household_id in range(1, count + 1):
        household = HouseholdAgent(
            household_id=household_id, skills_level=skill, age=35, cash_balance=2_000.0,
        )
        household.health = health
        household.morale = REFERENCE_MORALE
        household.happiness = REFERENCE_HAPPINESS
        household.employer_id = 1
        household.wage = 40.0
        household.reservation_wage = 1.0
        workers.append(household)
    firm = FirmAgent(
        firm_id=1,
        good_name=category,
        good_category=category,
        cash_balance=500_000.0,
        inventory_units=0.0,
        employees=list(range(1, count + 1)),
        production_capacity_units=10_000.0 if category == "Food" else float(count),
        units_per_worker=2.0 if category == "Food" else 7.0,
        wage_offer=40.0,
        expected_sales_units=400.0,
        age_in_ticks=30,
        price=8.0,
        revenue_ema=5_000.0,
        profit_ema=1_000.0,
        last_revenue=5_000.0,
        last_profit=1_000.0,
    )
    firm.units_per_worker = 1.0 if category == "Food" else 7.0
    firm.production_capacity_units = 10_000.0 if category == "Food" else float(count)
    for household in workers:
        firm.actual_wages[household.household_id] = 40.0
    economy = Economy(
        households=workers,
        firms=[firm],
        government=GovernmentAgent(cash_balance=1_000_000.0),
    )
    economy.warmup_ticks = 0
    economy.in_warmup = False
    economy.current_tick = 30
    for _ in range(ticks):
        economy.last_tick_sales_units[firm.firm_id] = 10_000.0
        economy.step()
        total += float(firm.last_units_produced)
    return total


def _cap_binding_share(seed: int, ticks: int) -> dict:
    """Share of goods firm-weeks whose realized units sit on effective capacity."""
    _set_seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):
        economy = create_large_economy(80, 1)
    spec = load_spec(economy.config.firms, economy.config.households)
    bound = 0
    considered = 0
    for _ in range(ticks):
        economy.step()
        for firm in economy.firms:
            if firm.is_baseline or firm.good_category.lower() != "food":
                continue
            if firm.last_units_produced <= 0.0:
                continue
            considered += 1
            firm.bind_effective_labor(economy.household_lookup, spec)
            weights = firm._effective_labor_weights or {}
            labor_units = 0.0
            for employee_id in firm.employees:
                pair = weights.get(employee_id)
                if pair is not None:
                    labor_units += float(pair[1])
            capacity = firm._capacity_for_labor_units(labor_units)
            if abs(firm.last_units_produced - min(capacity, firm.production_capacity_units)) <= 1e-6:
                bound += 1
    return {
        "goods_firm_weeks": considered,
        "cap_binding_share": (bound / considered) if considered else 0.0,
    }


def main() -> None:
    config = clone_config()
    config.firms.effective_labor_enabled = True
    try:
        with use_config(config):
            food_skill = {
                "0": _quiet_step_units("Food", 0.0, 1.0),
                "1": _quiet_step_units("Food", 1.0, 1.0),
            }
            food_health = {
                "0.5": _quiet_step_units("Food", 0.6, 0.5),
                "1": _quiet_step_units("Food", 0.6, 1.0),
            }
            services_skill = {
                "0": _quiet_step_units("Services", 0.0, 1.0),
                "1": _quiet_step_units("Services", 1.0, 1.0),
            }
            binding = _cap_binding_share(42, 20)
    finally:
        config.firms.effective_labor_enabled = False
    print({
        "food_units_skill_0_vs_1": food_skill,
        "food_units_health_0.5_vs_1": food_health,
        "services_units_skill_0_vs_1": services_skill,
        "cap_binding": binding,
    })


if __name__ == "__main__":
    main()
