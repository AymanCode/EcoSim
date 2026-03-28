"""
Run large-scale EcoSim simulation with 10,000 agents.

This script creates a larger economy and runs it for a specified number of ticks.
Progress is printed every 10 ticks to monitor performance and economic indicators.
"""

import argparse
import json
import math
import random
import sqlite3
import sys
import time
from collections import deque, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from agents import HouseholdAgent, FirmAgent, GovernmentAgent
from config import CONFIG
from economy import Economy

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def create_large_economy(num_households: int = 10000, num_firms_per_category: int = 10):
    """
    Create a large economy with specified number of agents.

    Args:
        num_households: Number of household agents to create
        num_firms_per_category: Number of firms per essential category

    Returns:
        Economy instance
    """
    print(f"Creating economy with {num_households} households...")

    essential_categories = ["Food", "Housing", "Services", "Healthcare"]

    # Create government with scaled parameters
    gov = GovernmentAgent(
        wage_tax_rate=0.15,
        profit_tax_rate=0.20,
        unemployment_benefit_level=0.0,
        transfer_budget=0.0,
        cash_balance=num_households * 3000.0     # Scale with population
    )

    # Baseline firm prices set to be competitive but not artificially low
    # This prevents them from dominating the market early on
    baseline_prices = dict(CONFIG.baseline_prices)

    # Create firms
    baseline_firms: List[FirmAgent] = []
    queued_firms: List[FirmAgent] = []
    next_firm_id = 1

    # Create baseline firms (government-controlled "safety net")
    # These provide basic goods at competitive prices, not artificially low prices
    # They should serve as a fallback option, not dominate the market
    print(f"Creating {len(essential_categories)} baseline firms...")
    for category in essential_categories:
        firm_rng = random.Random(CONFIG.random_seed + next_firm_id * 10007)
        baseline_units = np.random.randint(0, 51) if category == "Housing" else 0
        baseline_firm = FirmAgent(
            firm_id=next_firm_id,
            good_name=f"Baseline{category}",
            cash_balance=2_000_000.0,  # Reduced from 10M - still comfortable but not infinite
            inventory_units=0.0 if category in {"Housing", "Healthcare"} else 20_000.0,
            good_category=category,
            quality_level=max(0.0, min(10.0, 3.0 + firm_rng.uniform(-0.05, 0.05))),
            wage_offer=CONFIG.firms.minimum_wage_floor * 1.50,  # Baseline = government pay: 150% of min wage
            price=baseline_prices.get(category, 8.0),
            expected_sales_units=num_households * 0.1,
            production_capacity_units=100_000.0,  # Reduced from 200k
            units_per_worker=80.0,  # Balanced: enough production with reasonable workforce
            productivity_per_worker=12.0 + firm_rng.uniform(-0.2, 0.2),
            personality="conservative",
            is_baseline=True,
            baseline_production_quota=num_households * 3.0,  # Enough to serve population basic needs
            max_rental_units=baseline_units
        )
        baseline_firm.set_personality("conservative")

        # Initialize hidden happiness boost for service firms only
        if category == "Services":
            # Baseline service has low happiness boost (government service quality)
            baseline_firm.happiness_boost_per_unit = random.uniform(0.002, 0.01)
        elif category == "Healthcare":
            baseline_firm.happiness_boost_per_unit = 0.0

        gov.register_baseline_firm(category, baseline_firm.firm_id)
        baseline_firms.append(baseline_firm)
        next_firm_id += 1

    # Create competitive private firms (HIGHER quality than government)
    target_total_firms = max(
        len(baseline_firms),
        int((num_households / 1000.0) * CONFIG.firms.target_firms_per_1000_households)
    )
    print(f"Target total firms based on population: {target_total_firms}")
    print(f"Creating competitive firms...")
    personalities = ["aggressive", "moderate", "conservative"]

    private_needed = max(
        len(essential_categories) * num_firms_per_category,
        target_total_firms - len(baseline_firms)
    )
    per_category = private_needed // len(essential_categories)
    remainder = private_needed % len(essential_categories)
    category_private_targets: Dict[str, int] = {}
    for idx, category in enumerate(essential_categories):
        category_private_targets[category] = per_category + (1 if idx < remainder else 0)

    # Force a single healthcare provider model:
    # exactly one baseline healthcare firm, zero private healthcare firms.
    planned_private_healthcare = category_private_targets.get("Healthcare", 0)
    if planned_private_healthcare > 0:
        category_private_targets["Healthcare"] = 0
        redistribute_categories = [cat for cat in essential_categories if cat != "Healthcare"]
        for i in range(planned_private_healthcare):
            category_private_targets[redistribute_categories[i % len(redistribute_categories)]] += 1

    for idx, category in enumerate(essential_categories):
        firms_in_category = category_private_targets.get(category, 0)
        for i in range(firms_in_category):
            firm_rng = random.Random(CONFIG.random_seed + next_firm_id * 10007)
            personality = personalities[(i + idx) % len(personalities)]
            quality_seed = 5.0 + (i * 0.3)
            quality_level = max(1.0, min(10.0, quality_seed + firm_rng.uniform(-0.05, 0.05)))
            price_multiplier = max(0.5, min(3.0, 0.95 + i * 0.03 + firm_rng.uniform(-0.005, 0.005)))
            wage_offer = min(200.0, 25.0 + (i * 3.0) + firm_rng.uniform(-0.2, 0.2))
            competitive_firm = FirmAgent(
                firm_id=next_firm_id,
                good_name=f"{category}Co{i+1}",
                cash_balance=800_000.0,  # Increased from 500k - competitive with baseline
                inventory_units=0.0 if category == "Healthcare" else 300.0,
                good_category=category,
                quality_level=quality_level,
                wage_offer=wage_offer,
                price=baseline_prices.get(category, 5.0) * price_multiplier,
                expected_sales_units=num_households * 0.03,
                production_capacity_units=60_000.0,  # Better capacity
                units_per_worker=40.0,
                productivity_per_worker=15.0 + (i * 0.8) + firm_rng.uniform(-0.2, 0.2),
                personality=personality,
                is_baseline=False
            )
            competitive_firm.set_personality(personality)

            # Initialize hidden happiness boost for service firms only
            if category == "Services":
                # Happiness boost between 0.005 and 0.03 per unit consumed
                # Households don't know this value - they discover it through consumption
                competitive_firm.happiness_boost_per_unit = random.uniform(0.005, 0.03)
            elif category == "Healthcare":
                competitive_firm.happiness_boost_per_unit = 0.0

            queued_firms.append(competitive_firm)
            next_firm_id += 1

    # Create households with distributed characteristics
    print(f"Creating {num_households} households...")
    households = []

    for i in range(num_households):
        # Distribute skills across population (0.2 to 0.95)
        skill_level = min(0.95, 0.2 + (i / num_households) * 0.75)

        # Distribute ages (22 to 62)
        age = 22 + (i % 40)

        # Distribute starting cash (500 to 2000)
        base_cash = 500.0 + (i % 100) * 15.0

        households.append(
            HouseholdAgent(
                household_id=i,
                skills_level=skill_level,
                age=age,
                cash_balance=base_cash
            )
        )

        # Progress indicator for large populations
        if (i + 1) % 1000 == 0:
            print(f"  Created {i + 1}/{num_households} households...")

    # Bootstrap healthcare staffing so high-population runs do not start with
    # severe care undersupply during warm-up.
    healthcare_firms = [f for f in baseline_firms if f.good_category == "Healthcare"]
    target_doctors = 0
    if healthcare_firms and households:
        doctor_ratio = max(0.0, min(1.0, float(CONFIG.firms.healthcare_staff_population_ratio)))
        target_doctors = min(
            len(households),
            max(len(healthcare_firms), int(math.ceil(num_households * doctor_ratio)))
        )
        doctor_candidates = sorted(
            households,
            key=lambda h: (h.skills_level, h.health, h.cash_balance, -h.household_id),
            reverse=True,
        )[:target_doctors]

        for idx, doctor in enumerate(doctor_candidates):
            assigned_firm = healthcare_firms[idx % len(healthcare_firms)]
            doctor.medical_training_status = "doctor"
            doctor.medical_training_start_tick = 0
            doctor.expected_wage = max(doctor.expected_wage, doctor.medical_doctor_expected_wage_anchor)
            doctor.reservation_wage = max(
                doctor.reservation_wage,
                doctor.medical_doctor_reservation_wage_anchor * 0.85,
            )

            doctor_wage = max(assigned_firm.wage_offer, doctor.reservation_wage)
            doctor.employer_id = assigned_firm.firm_id
            doctor.wage = doctor_wage

            assigned_firm.actual_wages[doctor.household_id] = doctor_wage
            if doctor.household_id not in assigned_firm.employees:
                assigned_firm.employees.append(doctor.household_id)

        avg_doctor_wage = float(np.mean([h.wage for h in doctor_candidates])) if doctor_candidates else 0.0
        for firm in healthcare_firms:
            firm.wage_offer = max(firm.wage_offer, avg_doctor_wage * 0.95)

        print(
            f"✓ Seeded initial doctors: {target_doctors} "
            f"({(target_doctors / max(1, num_households)) * 100:.2f}% of households)"
        )

    # Assign owners to firms (1-3 households per firm)
    # This creates a wealth recycling mechanism where firm profits flow back to households
    print(f"Assigning ownership of {len(baseline_firms) + len(queued_firms)} firms...")
    # No seed - ownership is stochastic for run-to-run variation

    for firm in baseline_firms + queued_firms:
        # Randomly assign 1-3 owners per firm (stochastic)
        num_owners = random.randint(1, 3)
        # Select owners from household population (stochastic)
        owner_ids = random.sample(range(num_households), num_owners)
        firm.owners = owner_ids

    total_firms = len(baseline_firms) + len(queued_firms)
    print(f"✓ Ownership assigned (avg {sum(len(f.owners) for f in baseline_firms + queued_firms) / total_firms:.1f} owners/firm)")

    print(f"✓ Economy created successfully!")
    print(f"  Total agents: {len(households) + len(baseline_firms) + 1}")
    print(f"    - Households: {len(households)}")
    print(f"    - Firms: {len(baseline_firms)} (queued: {len(queued_firms)})")
    print(f"    - Government: 1")
    print()

    economy = Economy(
        households=households,
        firms=baseline_firms,
        government=gov,
        queued_firms=queued_firms
    )
    economy.target_total_firms = max(
        len(economy.firms) + len(economy.queued_firms),
        target_total_firms
    )
    return economy


def init_database(db_path: str):
    """Initialize SQLite database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Households table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS households (
            tick INTEGER,
            household_id INTEGER,
            skills_level REAL,
            age INTEGER,
            cash_balance REAL,
            employer_id INTEGER,
            wage REAL,
            is_employed BOOLEAN,
            goods_inventory TEXT,
            happiness REAL,
            morale REAL,
            health REAL,
            performance_multiplier REAL,
            food_experience INTEGER,
            housing_experience INTEGER,
            services_experience INTEGER,
            healthcare_experience INTEGER,
            unemployment_duration INTEGER,
            reservation_wage REAL,
            PRIMARY KEY (tick, household_id)
        )
    """)

    # Firms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firms (
            tick INTEGER,
            firm_id INTEGER,
            good_name TEXT,
            good_category TEXT,
            quality_level REAL,
            cash_balance REAL,
            inventory_units REAL,
            employee_count INTEGER,
            employees TEXT,
            wage_offer REAL,
            price REAL,
            unit_cost REAL,
            markup REAL,
            expected_sales_units REAL,
            production_capacity_units REAL,
            personality TEXT,
            investment_propensity REAL,
            risk_tolerance REAL,
            PRIMARY KEY (tick, firm_id)
        )
    """)

    # Government table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS government (
            tick INTEGER PRIMARY KEY,
            cash_balance REAL,
            wage_tax_rate REAL,
            profit_tax_rate REAL,
            unemployment_benefit_level REAL,
            transfer_budget REAL,
            infrastructure_productivity_multiplier REAL,
            technology_quality_multiplier REAL,
            social_happiness_multiplier REAL
        )
    """)

    # Aggregate metrics
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aggregate_metrics (
            tick INTEGER PRIMARY KEY,
            total_households INTEGER,
            total_firms INTEGER,
            unemployment_rate REAL,
            mean_wage REAL,
            median_wage REAL,
            mean_household_cash REAL,

                             median_household_cash REAL,
            mean_happiness REAL,
            mean_morale REAL,
            mean_health REAL,
            mean_performance REAL,
            total_firm_cash REAL,
            mean_price REAL,
            government_cash REAL,
            gdp_this_tick REAL,
            total_net_worth REAL
        )
    """)

    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_households_tick ON households(tick)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_firms_tick ON firms(tick)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_households_employed ON households(is_employed)")

    conn.commit()
    conn.close()


def compute_household_stats(households: List[HouseholdAgent]) -> Dict[str, float]:
    """Vectorized snapshot of household metrics for reuse."""
    if not households:
        return {
            "total_households": 0,
            "employed_count": 0,
            "unemployed_count": 0,
            "unemployment_rate": 0.0,
            "mean_wage": 0.0,
            "median_wage": 0.0,
            "mean_expected_wage": 0.0,
            "mean_unemployed_expected_wage": 0.0,
            "mean_cash": 0.0,
            "median_cash": 0.0,
            "gini_coefficient": 0.0,
            "top10_wealth_share": 0.0,
            "bottom50_wealth_share": 0.0,
            "mean_happiness": 0.0,
            "mean_morale": 0.0,
            "mean_health": 0.0,
            "mean_performance": 0.0,
            "cash_below_100_share": 0.0,
            "cash_below_zero_share": 0.0,
            "health_below_50_share": 0.0,
            "happiness_below_50_share": 0.0,
            "food_insecure_share": 0.0,
            "housing_insecure_share": 0.0,
            "homeless_household_count": 0,
            "pending_healthcare_visits_total": 0,
        }

    cash = np.array([h.cash_balance for h in households], dtype=float)
    happiness = np.array([h.happiness for h in households], dtype=float)
    morale = np.array([h.morale for h in households], dtype=float)
    health = np.array([h.health for h in households], dtype=float)
    performance = np.array([h.get_performance_multiplier() for h in households], dtype=float)
    employment = np.array([1.0 if h.is_employed else 0.0 for h in households], dtype=float)
    employed_wages = np.array([h.wage for h in households if h.is_employed], dtype=float)
    expected_wages = np.array([h.expected_wage for h in households], dtype=float)
    unemployed_expected_wages = np.array([h.expected_wage for h in households if not h.is_employed], dtype=float)
    food_security = np.array([_food_security_ratio(h) for h in households], dtype=float)
    housing_security = np.array([1.0 if _housing_security_flag(h) else 0.0 for h in households], dtype=float)
    pending_healthcare_visits = np.array(
        [max(0, int(getattr(h, "pending_healthcare_visits", 0))) for h in households],
        dtype=float,
    )

    total_households = int(cash.size)
    employed_count = int(employment.sum())
    unemployed_count = int(total_households - employed_count)
    unemployment_rate = 1.0 - (employment.mean() if employment.size else 0.0)
    mean_wage = float(employed_wages.mean()) if employed_wages.size else 0.0
    median_wage = float(np.median(employed_wages)) if employed_wages.size else 0.0

    sorted_cash = np.sort(cash)
    total_cash = float(sorted_cash.sum())
    if sorted_cash.size > 1 and total_cash > 0.0:
        index = np.arange(1, sorted_cash.size + 1, dtype=float)
        gini = float((2.0 * np.dot(index, sorted_cash)) / (sorted_cash.size * total_cash) - (sorted_cash.size + 1.0) / sorted_cash.size)
        top10_start = int(sorted_cash.size * 0.9)
        bottom50_end = int(sorted_cash.size * 0.5)
        top10_share = float(sorted_cash[top10_start:].sum() / total_cash)
        bottom50_share = float(sorted_cash[:bottom50_end].sum() / total_cash)
    else:
        gini = 0.0
        top10_share = 0.0
        bottom50_share = 0.0

    return {
        "total_households": total_households,
        "employed_count": employed_count,
        "unemployed_count": unemployed_count,
        "unemployment_rate": unemployment_rate,
        "mean_wage": mean_wage,
        "median_wage": median_wage,
        "mean_expected_wage": float(expected_wages.mean()) if expected_wages.size else 0.0,
        "mean_unemployed_expected_wage": float(unemployed_expected_wages.mean()) if unemployed_expected_wages.size else 0.0,
        "mean_cash": float(cash.mean()),
        "median_cash": float(np.median(cash)),
        "gini_coefficient": max(0.0, min(1.0, gini)),
        "top10_wealth_share": top10_share,
        "bottom50_wealth_share": bottom50_share,
        "mean_happiness": float(happiness.mean()),
        "mean_morale": float(morale.mean()),
        "mean_health": float(health.mean()),
        "mean_performance": float(performance.mean()),
        "cash_below_100_share": float((cash < 100.0).mean()),
        "cash_below_zero_share": float((cash < 0.0).mean()),
        "health_below_50_share": float((health < 0.5).mean()),
        "happiness_below_50_share": float((happiness < 0.5).mean()),
        "food_insecure_share": float((food_security < 0.999).mean()),
        "housing_insecure_share": float((housing_security < 0.5).mean()),
        "homeless_household_count": int((housing_security < 0.5).sum()),
        "pending_healthcare_visits_total": int(pending_healthcare_visits.sum()),
    }


def _classify_household_state(household: HouseholdAgent) -> str:
    """Map household labor/training state to a stable warehouse label."""
    medical_status = (household.medical_training_status or "none").lower()
    if medical_status == "student":
        return "MED_SCHOOL"
    if household.is_employed:
        return "WORKING"
    return "UNEMPLOYED"


def _food_security_ratio(household: HouseholdAgent) -> float:
    """Return last-tick food sufficiency as a bounded ratio."""
    required_food = max(0.1, float(getattr(household, "min_food_per_tick", 0.0)))
    consumed_food = float(getattr(household, "food_consumed_last_tick", 0.0))
    return max(0.0, min(1.0, consumed_food / required_food))


def _housing_security_flag(household: HouseholdAgent) -> bool:
    """Return whether the household had housing security this tick."""
    return bool(
        household.owns_housing
        or household.renting_from_firm_id is not None
        or household.met_housing_need
    )


def compute_household_snapshot_rows(households: List[HouseholdAgent]) -> List[Dict[str, object]]:
    """Build sampled warehouse rows for the full household population."""
    rows: List[Dict[str, object]] = []
    for household in households:
        rows.append({
            "household_id": int(household.household_id),
            "state": _classify_household_state(household),
            "medical_status": str((household.medical_training_status or "none").lower()),
            "employer_id": int(household.employer_id) if household.employer_id is not None else None,
            "is_employed": bool(household.is_employed),
            "can_work": bool(household.can_work),
            "cash_balance": float(household.cash_balance),
            "wage": float(household.wage),
            "last_wage_income": float(getattr(household, "last_wage_income", 0.0)),
            "last_transfer_income": float(getattr(household, "last_transfer_income", 0.0)),
            "last_dividend_income": float(getattr(household, "last_dividend_income", 0.0)),
            "reservation_wage": float(household.reservation_wage),
            "expected_wage": float(household.expected_wage),
            "skill_level": float(household.skills_level),
            "health": float(household.health),
            "happiness": float(household.happiness),
            "morale": float(household.morale),
            "food_security": float(_food_security_ratio(household)),
            "housing_security": bool(_housing_security_flag(household)),
            "unemployment_duration": int(household.unemployment_duration),
            "pending_healthcare_visits": int(max(0, getattr(household, "pending_healthcare_visits", 0))),
        })

    rows.sort(key=lambda row: int(row["household_id"]))
    return rows


def compute_tracked_household_history_rows(
    household_lookup: Dict[int, HouseholdAgent],
    tracked_household_ids: List[int],
) -> List[Dict[str, object]]:
    """Build every-tick rows for the tracked-household subset only.

    This avoids a full household scan on non-snapshot ticks. The live frontend
    already maintains a tracked subset, so reuse that selection for the
    high-frequency warehouse history path.
    """
    rows: List[Dict[str, object]] = []
    for household_id in tracked_household_ids:
        household = household_lookup.get(household_id)
        if household is None:
            continue
        rows.append({
            "household_id": int(household.household_id),
            "state": _classify_household_state(household),
            "medical_status": str((household.medical_training_status or "none").lower()),
            "employer_id": int(household.employer_id) if household.employer_id is not None else None,
            "is_employed": bool(household.is_employed),
            "can_work": bool(household.can_work),
            "cash_balance": float(household.cash_balance),
            "wage": float(household.wage),
            "expected_wage": float(household.expected_wage),
            "reservation_wage": float(household.reservation_wage),
            "health": float(household.health),
            "happiness": float(household.happiness),
            "morale": float(household.morale),
            "skill_level": float(household.skills_level),
            "unemployment_duration": int(household.unemployment_duration),
            "pending_healthcare_visits": int(max(0, getattr(household, "pending_healthcare_visits", 0))),
        })

    rows.sort(key=lambda row: int(row["household_id"]))
    return rows


def compute_sector_tick_rollups(firms: List[FirmAgent]) -> List[Dict[str, float]]:
    """Build per-sector aggregates used by the warehouse and history APIs.

    This is intentionally narrower than ``compute_firm_stats``. It avoids
    leaderboards and other UI-only structures so the warehouse path can record
    per-tick sector state with one lightweight firm scan.
    """
    if not firms:
        return []

    category_map = defaultdict(lambda: {
        "firm_count": 0,
        "employees": 0,
        "vacancies": 0,
        "price_sum": 0.0,
        "wage_sum": 0.0,
        "inventory_sum": 0.0,
        "output_sum": 0.0,
        "revenue_sum": 0.0,
        "profit_sum": 0.0,
    })

    for firm in firms:
        sector = firm.good_category or "Other"
        data = category_map[sector]
        data["firm_count"] += 1
        data["employees"] += len(firm.employees)
        data["vacancies"] += max(0, int(getattr(firm, "planned_hires_count", 0)))
        data["price_sum"] += max(0.0, float(firm.price))
        data["wage_sum"] += max(0.0, float(firm.wage_offer))
        data["inventory_sum"] += max(0.0, float(firm.inventory_units))
        data["output_sum"] += max(0.0, float(getattr(firm, "last_units_produced", 0.0)))
        data["revenue_sum"] += float(getattr(firm, "last_revenue", 0.0))
        data["profit_sum"] += float(getattr(firm, "last_profit", 0.0))

    rollups = []
    for sector, data in category_map.items():
        firm_count = max(1, int(data["firm_count"]))
        rollups.append({
            "sector": sector,
            "firm_count": int(data["firm_count"]),
            "employees": int(data["employees"]),
            "vacancies": int(data["vacancies"]),
            "mean_wage_offer": float(data["wage_sum"] / firm_count),
            "mean_price": float(data["price_sum"] / firm_count),
            "mean_inventory": float(data["inventory_sum"] / firm_count),
            "total_output": float(data["output_sum"]),
            "total_revenue": float(data["revenue_sum"]),
            "total_profit": float(data["profit_sum"]),
        })

    rollups.sort(key=lambda item: item["sector"])
    return rollups


def compute_firm_snapshot_rows(
    firms: List[FirmAgent],
    household_lookup: Optional[Dict[int, HouseholdAgent]] = None,
) -> List[Dict[str, object]]:
    """Build narrow per-firm snapshot rows for warehouse persistence.

    This intentionally avoids UI-only leaderboards and only captures the state
    needed to explain pricing, labor demand, cash stress, and healthcare
    throughput. The row stays small enough to store every tick.
    """
    if not firms:
        return []

    rows: List[Dict[str, object]] = []
    for firm in firms:
        sector = firm.good_category or "Other"
        is_healthcare = sector.lower() == "healthcare"
        doctor_employee_count = 0
        medical_employee_count = 0
        if is_healthcare and household_lookup is not None and firm.employees:
            for employee_id in firm.employees:
                worker = household_lookup.get(employee_id)
                if worker is None:
                    continue
                if worker.medical_training_status == "doctor":
                    doctor_employee_count += 1
                    medical_employee_count += 1
                elif worker.medical_training_status == "resident":
                    medical_employee_count += 1

        rows.append({
            "firm_id": int(firm.firm_id),
            "firm_name": str(firm.good_name),
            "sector": str(sector),
            "is_baseline": bool(getattr(firm, "is_baseline", False)),
            "employee_count": int(len(firm.employees)),
            "doctor_employee_count": int(doctor_employee_count),
            "medical_employee_count": int(medical_employee_count),
            "planned_hires_count": int(max(0, getattr(firm, "planned_hires_count", 0))),
            "planned_layoffs_count": int(len(getattr(firm, "planned_layoffs_ids", []))),
            "actual_hires_count": int(max(0, getattr(firm, "last_tick_actual_hires", 0))),
            "wage_offer": float(getattr(firm, "wage_offer", 0.0)),
            "price": float(getattr(firm, "price", 0.0)),
            "inventory_units": float(getattr(firm, "inventory_units", 0.0)),
            "output_units": float(getattr(firm, "last_units_produced", 0.0)),
            "cash_balance": float(getattr(firm, "cash_balance", 0.0)),
            "revenue": float(getattr(firm, "last_revenue", 0.0)),
            "profit": float(getattr(firm, "last_profit", 0.0)),
            "quality_level": float(getattr(firm, "quality_level", 0.0)),
            "queue_depth": int(len(getattr(firm, "healthcare_queue", []))) if is_healthcare else 0,
            "visits_completed": float(getattr(firm, "healthcare_completed_visits_last_tick", 0.0)) if is_healthcare else 0.0,
            "burn_mode": bool(getattr(firm, "burn_mode", False)),
            "zero_cash_streak": int(max(0, getattr(firm, "zero_cash_streak", 0))),
        })

    rows.sort(key=lambda row: int(row["firm_id"]))
    return rows


def compute_firm_stats(
    firms: List[FirmAgent],
    top_n: int = 12,
    household_lookup: Optional[Dict[int, HouseholdAgent]] = None
) -> Dict[str, object]:
    """Aggregate firm-level statistics plus leaderboards."""
    if not firms:
        return {
            "total_firms": 0,
            "total_employees": 0,
            "total_doctors": 0,
            "total_medical_workers": 0,
            "avg_employees": 0.0,
            "avg_price": 0.0,
            "avg_wage_offer": 0.0,
            "avg_inventory": 0.0,
            "avg_quality": 0.0,
            "mean_cash": 0.0,
            "median_cash": 0.0,
            "struggling_firms": 0,
            "categories": [],
            "top_cash": [],
            "top_employers": []
        }

    cash = np.array([f.cash_balance for f in firms], dtype=float)
    prices = np.array([max(f.price, 0.0) for f in firms], dtype=float)
    wages = np.array([max(f.wage_offer, 0.0) for f in firms], dtype=float)
    inventories = np.array([max(f.inventory_units, 0.0) for f in firms], dtype=float)
    qualities = np.array([max(f.quality_level, 0.0) for f in firms], dtype=float)
    employee_counts = np.array([len(f.employees) for f in firms], dtype=float)

    total_employees = int(employee_counts.sum())
    avg_employees = float(total_employees / len(firms)) if firms else 0.0
    total_doctors = 0
    total_medical_workers = 0

    category_map = defaultdict(lambda: {
        "firm_count": 0,
        "cash": 0.0,
        "price": 0.0,
        "inventory": 0.0,
        "quality": 0.0,
        "wage": 0.0,
        "employees": 0,
        "doctor_employees": 0,
        "medical_employees": 0,
        "visit_revenue": 0.0,
        "visits_completed": 0.0,
    })

    for f in firms:
        cat = f.good_category or "Other"
        data = category_map[cat]
        data["firm_count"] += 1
        data["cash"] += f.cash_balance
        data["price"] += max(f.price, 0.0)
        data["inventory"] += max(f.inventory_units, 0.0)
        data["quality"] += max(f.quality_level, 0.0)
        data["wage"] += max(f.wage_offer, 0.0)
        data["employees"] += len(f.employees)
        if cat.lower() == "healthcare":
            visits_completed = float(getattr(f, "healthcare_completed_visits_last_tick", 0.0))
            visit_revenue = float(getattr(f, "last_revenue", 0.0))
            data["visits_completed"] += visits_completed
            data["visit_revenue"] += visit_revenue

        if household_lookup is not None and f.employees:
            doctor_count = 0
            medical_count = 0
            for employee_id in f.employees:
                worker = household_lookup.get(employee_id)
                if worker is None:
                    continue
                if worker.medical_training_status == "doctor":
                    doctor_count += 1
                    medical_count += 1
                elif worker.medical_training_status == "resident":
                    medical_count += 1
            data["doctor_employees"] += doctor_count
            data["medical_employees"] += medical_count
            total_doctors += doctor_count
            total_medical_workers += medical_count

    categories = []
    for cat, data in category_map.items():
        count = data["firm_count"] or 1
        categories.append({
            "category": cat,
            "firm_count": data["firm_count"],
            "avg_cash": data["cash"] / count,
            "avg_price": data["price"] / count,
            "avg_inventory": data["inventory"] / count,
            "avg_quality": data["quality"] / count,
            "avg_wage": data["wage"] / count,
            "total_employees": data["employees"],
            "doctor_employees": data["doctor_employees"],
            "medical_employees": data["medical_employees"],
            "visit_revenue": data["visit_revenue"],
            "visits_completed": data["visits_completed"],
        })

    categories.sort(key=lambda c: c["firm_count"], reverse=True)

    def serialize_firm(f: FirmAgent) -> Dict[str, object]:
        doctor_employees = 0
        medical_employees = 0
        if household_lookup is not None and f.employees:
            for employee_id in f.employees:
                worker = household_lookup.get(employee_id)
                if worker is None:
                    continue
                if worker.medical_training_status == "doctor":
                    doctor_employees += 1
                    medical_employees += 1
                elif worker.medical_training_status == "resident":
                    medical_employees += 1

        is_healthcare = (f.good_category or "").lower() == "healthcare"
        visits_completed = float(getattr(f, "healthcare_completed_visits_last_tick", 0.0))
        visit_revenue = float(getattr(f, "last_revenue", 0.0)) if is_healthcare else 0.0

        return {
            "id": f.firm_id,
            "name": f.good_name,
            "category": f.good_category,
            "cash": f.cash_balance,
            "price": f.price,
            "wageOffer": f.wage_offer,
            "inventory": f.inventory_units,
            "quality": f.quality_level,
            "employees": len(f.employees),
            "doctorEmployees": doctor_employees,
            "medicalEmployees": medical_employees,
            "visitsCompleted": visits_completed,
            "visitRevenue": visit_revenue,
            "lastRevenue": getattr(f, "last_revenue", 0.0),
            "lastProfit": getattr(f, "last_profit", 0.0),
            "state": "BURN" if getattr(f, "burn_mode", False) else "ACTIVE"
        }

    top_cash = [serialize_firm(f) for f in sorted(firms, key=lambda f: f.cash_balance, reverse=True)[:top_n]]
    top_employers = [serialize_firm(f) for f in sorted(firms, key=lambda f: len(f.employees), reverse=True)[:top_n]]

    struggling = sum(1 for f in firms if f.cash_balance <= 0)

    return {
        "total_firms": len(firms),
        "total_employees": total_employees,
        "total_doctors": total_doctors,
        "total_medical_workers": total_medical_workers,
        "avg_employees": avg_employees,
        "avg_price": float(prices.mean()) if prices.size else 0.0,
        "avg_wage_offer": float(wages.mean()) if wages.size else 0.0,
        "avg_inventory": float(inventories.mean()) if inventories.size else 0.0,
        "avg_quality": float(qualities.mean()) if qualities.size else 0.0,
        "mean_cash": float(cash.mean()) if cash.size else 0.0,
        "median_cash": float(np.median(cash)) if cash.size else 0.0,
        "struggling_firms": struggling,
        "categories": categories,
        "top_cash": top_cash,
        "top_employers": top_employers
    }


def export_tick_data(
    economy: Economy,
    tick: int,
    conn: sqlite3.Connection,
    household_stats: Optional[Dict[str, float]] = None
):
    """Export current tick data using an open database connection."""
    cursor = conn.cursor()

    # Export households
    household_rows = []
    for h in economy.households:
        household_rows.append((
            tick,
            h.household_id,
            h.skills_level,
            h.age,
            h.cash_balance,
            h.employer_id,
            h.wage,
            h.is_employed,
            json.dumps(h.goods_inventory),
            h.happiness,
            h.morale,
            h.health,
            h.get_performance_multiplier(),
            h.category_experience.get("Food", 0),
            h.category_experience.get("Housing", 0),
            h.category_experience.get("Services", 0),
            h.category_experience.get("Healthcare", 0),
            h.unemployment_duration,
            h.reservation_wage
        ))

    cursor.executemany(
        "INSERT INTO households VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        household_rows
    )

    # Export firms
    firm_rows = []
    for f in economy.firms:
        firm_rows.append((
            tick,
            f.firm_id,
            f.good_name,
            f.good_category,
            f.quality_level,
            f.cash_balance,
            f.inventory_units,
            len(f.employees),
            json.dumps(f.employees),
            f.wage_offer,
            f.price,
            f.unit_cost,
            f.markup,
            f.expected_sales_units,
            f.production_capacity_units,
            f.personality,
            f.investment_propensity,
            f.risk_tolerance
        ))

    cursor.executemany(
        "INSERT INTO firms VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        firm_rows
    )

    # Export government
    gov = economy.government
    cursor.execute(
        "INSERT INTO government VALUES (?,?,?,?,?,?,?,?,?)",
        (tick, gov.cash_balance, gov.wage_tax_rate, gov.profit_tax_rate,
         gov.unemployment_benefit_level, gov.transfer_budget,
         gov.infrastructure_productivity_multiplier,
         gov.technology_quality_multiplier,
         gov.social_happiness_multiplier)
    )

    # Calculate and export aggregate metrics
    stats = household_stats or compute_household_stats(economy.households)
    total_firm_cash = sum(f.cash_balance for f in economy.firms)
    total_household_cash = sum(h.cash_balance for h in economy.households)
    total_net_worth = total_household_cash + total_firm_cash + gov.cash_balance
    mean_price = sum(f.price for f in economy.firms) / len(economy.firms) if economy.firms else 0.0

    # Calculate GDP (sum of firm revenues this tick)
    gdp_this_tick = sum(economy.last_tick_revenue.values())

    cursor.execute(
        "INSERT INTO aggregate_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            tick,
            len(economy.households),
            len(economy.firms),
            stats["unemployment_rate"],
            stats["mean_wage"],
            stats["median_wage"],
            stats["mean_cash"],
            stats["median_cash"],
            stats["mean_happiness"],
            stats["mean_morale"],
            stats["mean_health"],
            stats["mean_performance"],
            total_firm_cash,
            mean_price,
            gov.cash_balance,
            gdp_this_tick,
            total_net_worth
        )
    )

    conn.commit()


def main(
    num_households: int = 10000,
    num_firms_per_category: int = 10,
    num_ticks: int = 500,
    export_every: int = 50,
    output_tag: str = "10k_balanced"
):
    """Run EcoSim simulation with configurable size."""
    print("=" * 80)
    print(f"ECOSIM SIMULATION ({num_households:,} households, {num_ticks} ticks)")
    print("=" * 80)
    print()

    # Create output directory
    output_dir = Path("sample_data")
    output_dir.mkdir(exist_ok=True)

    # Create economy
    start_time = time.time()
    economy = create_large_economy(num_households, num_firms_per_category)
    creation_time = time.time() - start_time
    print(f"Economy creation time: {creation_time:.2f} seconds")
    print()

    # Select sample households and firms to track
    sample_household_ids = [0, num_households // 10, num_households // 2,
                           3 * num_households // 4, num_households - 1]
    sample_firm_ids = []
    if len(economy.firms) >= 5:
        # Track first 3 baseline firms + 2 random private firms
        sample_firm_ids = [f.firm_id for f in economy.firms[:3]]
        if len(economy.firms) > 3:
            sample_firm_ids.extend([economy.firms[len(economy.firms)//2].firm_id,
                                   economy.firms[-1].firm_id])

    print(f"Tracking sample households: {sample_household_ids}")
    print(f"Tracking sample firms: {sample_firm_ids[:5]}")
    print()

    # Initialize database (remove existing file if present)
    db_path = output_dir / f"ecosim_{output_tag}.db"
    if db_path.exists():
        db_path.unlink()  # Delete existing database
        print(f"Removed existing database: {db_path}")
    print(f"Initializing database: {db_path}")
    init_database(str(db_path))
    print()

    # Prepare persistent DB connection
    db_conn = sqlite3.connect(str(db_path))

    # Run simulation
    print(f"Running simulation for {num_ticks} ticks...")
    print(f"(Exporting to database every {export_every} ticks)")
    print()
    print("Tick | Time(s) | Firms | Unemploy |   Happiness | Avg Wage | Gov Cash")
    print("-" * 80)

    tick_time_history: deque[float] = deque(maxlen=10)
    tick_time_sum = 0.0

    # Track sample households and firms every 100 ticks for detailed output
    sample_snapshots = []

    for tick in range(num_ticks):
        tick_start = time.time()

        # Step economy
        economy.step()

        tick_time = time.time() - tick_start
        tick_time_history.append(tick_time)
        tick_time_sum += tick_time
        household_stats = compute_household_stats(economy.households)

        # Export data periodically
        if tick % export_every == 0 or tick == num_ticks - 1:
            export_tick_data(economy, tick, db_conn, household_stats)

        # Capture sample snapshots every 100 ticks
        if tick % 100 == 0 or tick == num_ticks - 1:
            snapshot = {"tick": tick, "households": [], "firms": []}

            # Sample households
            for hh_id in sample_household_ids:
                hh = next((h for h in economy.households if h.household_id == hh_id), None)
                if hh:
                    snapshot["households"].append({
                        "id": hh_id,
                        "cash": hh.cash_balance,
                        "employed": hh.is_employed,
                        "wage": hh.wage if hh.is_employed else 0,
                        "happiness": hh.happiness,
                        "unemployment_duration": hh.unemployment_duration
                    })

            # Sample firms
            for firm_id in sample_firm_ids:
                firm = next((f for f in economy.firms if f.firm_id == firm_id), None)
                if firm:
                    snapshot["firms"].append({
                        "id": firm_id,
                        "name": firm.good_name,
                        "cash": firm.cash_balance,
                        "employees": len(firm.employees),
                        "wage_offer": firm.wage_offer,
                        "inventory": firm.inventory_units
                    })

            sample_snapshots.append(snapshot)

        # Print progress every 10 ticks
        if tick % 10 == 0 or tick == num_ticks - 1:
            avg_tick_time = sum(tick_time_history) / len(tick_time_history)

            print(f"{tick:4d} | {avg_tick_time:7.3f} | {len(economy.firms):5d} | "
                  f"{household_stats['unemployment_rate']:7.1%} | {household_stats['mean_happiness']:11.3f} | "
                  f"${household_stats['mean_wage']:7.2f} | ${economy.government.cash_balance:9.0f}")

    print()
    total_time = time.time() - start_time
    avg_tick_time = tick_time_sum / num_ticks

    db_conn.close()

    print(f"✓ Simulation complete!")
    print(f"  Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"  Average tick time: {avg_tick_time:.3f} seconds")
    print(f"  Ticks per second: {1/avg_tick_time:.2f}")
    print(f"  Database saved to: {db_path}")
    print()

    # Generate summary statistics
    print("Generating summary statistics...")
    conn = sqlite3.connect(str(db_path))

    # Query final state
    final_tick = num_ticks - 1
    final_metrics = conn.execute(
        "SELECT * FROM aggregate_metrics WHERE tick = ?", (final_tick,)
    ).fetchone()

    # Get time series data for key metrics
    metrics_over_time = conn.execute(
        "SELECT tick, unemployment_rate, mean_wage, mean_happiness FROM aggregate_metrics ORDER BY tick"
    ).fetchall()

    summary = {
        "simulation_info": {
            "num_ticks": num_ticks,
            "num_households": num_households,
            "num_firms_initial": len(economy.firms),
            "num_firms_final": final_metrics[2] if final_metrics else 0,
            "total_simulation_time_seconds": total_time,
            "average_tick_time_seconds": avg_tick_time
        },
        "final_state": {
            "tick": final_tick,
            "unemployment_rate": final_metrics[3] if final_metrics else 0,
            "mean_wage": final_metrics[4] if final_metrics else 0,
            "median_wage": final_metrics[5] if final_metrics else 0,
            "mean_household_cash": final_metrics[6] if final_metrics else 0,
            "median_household_cash": final_metrics[7] if final_metrics else 0,
            "mean_happiness": final_metrics[8] if final_metrics else 0,
            "mean_morale": final_metrics[9] if final_metrics else 0,
            "mean_health": final_metrics[10] if final_metrics else 0,
            "government_cash": final_metrics[14] if final_metrics else 0,
            "total_firm_cash": final_metrics[12] if final_metrics else 0
        },
        "database_stats": {
            "households_rows": conn.execute("SELECT COUNT(*) FROM households").fetchone()[0],
            "firms_rows": conn.execute("SELECT COUNT(*) FROM firms").fetchone()[0],
            "government_rows": conn.execute("SELECT COUNT(*) FROM government").fetchone()[0],
        },
        "time_series_sample": {
            "ticks": [row[0] for row in metrics_over_time[::10]],  # Every 10th tick
            "unemployment_rate": [row[1] for row in metrics_over_time[::10]],
            "mean_wage": [row[2] for row in metrics_over_time[::10]],
            "mean_happiness": [row[3] for row in metrics_over_time[::10]]
        },
        "sample_trajectories": {
            "household_ids": sample_household_ids,
            "firm_ids": sample_firm_ids,
            "snapshots": sample_snapshots
        }
    }

    conn.close()

    # Save summary (remove existing file to avoid stale content)
    summary_path = output_dir / f"simulation_{output_tag}_summary.json"
    if summary_path.exists():
        summary_path.unlink()
        print(f"Removed existing summary: {summary_path}")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✓ Summary saved to: {summary_path}")
    print()

    # Get comprehensive economic metrics from the economy
    metrics = economy.get_economic_metrics()

    print("=" * 80)
    print("📊 COMPREHENSIVE ECONOMIC DASHBOARD")
    print("=" * 80)
    print()

    # GDP and Economic Output
    print("📈 ECONOMIC OUTPUT")
    print("-" * 80)
    print(f"  Current tick GDP:             ${metrics['gdp_this_tick']:>15,.2f}")
    print(f"  Total wealth (economy):       ${metrics['total_economy_cash']:>15,.2f}")
    print()

    # Labor Market
    print("👥 LABOR MARKET")
    print("-" * 80)
    print(f"  Total households:             {metrics['total_households']:>15,}")
    print(f"  Employed:                     {metrics['employed_count']:>15,}")
    print(f"  Unemployed:                   {metrics['unemployed_count']:>15,}")
    print(f"  Unemployment rate:            {metrics['unemployment_rate']:>15.1%}")
    print(f"  Average wage:                 ${metrics['mean_wage']:>14,.2f}")
    print(f"  Median wage:                  ${metrics['median_wage']:>14,.2f}")
    print(f"  Min wage:                     ${metrics['min_wage']:>14,.2f}")
    print(f"  Max wage:                     ${metrics['max_wage']:>14,.2f}")
    print()

    # Household Wellbeing
    print("😊 HOUSEHOLD WELLBEING")
    print("-" * 80)
    print(f"  Average happiness:            {metrics['mean_happiness']:>18.3f}")
    print(f"  Average morale:               {metrics['mean_morale']:>18.3f}")
    print(f"  Average health:               {metrics['mean_health']:>18.3f}")
    print(f"  Average skills:               {metrics['mean_skills']:>18.3f}")
    print()

    # Household Finances
    print("💰 HOUSEHOLD FINANCES")
    print("-" * 80)
    print(f"  Total household cash:         ${metrics['total_household_cash']:>15,.2f}")
    print(f"  Average cash per household:   ${metrics['mean_household_cash']:>15,.2f}")
    print(f"  Median cash per household:    ${metrics['median_household_cash']:>15,.2f}")
    print()

    # Firm Sector
    print("🏢 FIRM SECTOR")
    print("-" * 80)
    print(f"  Active firms:                 {metrics['total_firms']:>18,}")
    print(f"  Total firm cash:              ${metrics['total_firm_cash']:>15,.2f}")
    print(f"  Average firm cash:            ${metrics['mean_firm_cash']:>15,.2f}")
    print(f"  Median firm cash:             ${metrics['median_firm_cash']:>15,.2f}")
    print(f"  Total inventory (units):      {metrics['total_firm_inventory']:>18,}")
    print(f"  Total employees:              {metrics['total_employees']:>18,}")
    print(f"  Average firm quality:         {metrics['mean_quality']:>18.2f}")
    print(f"  Average firm price:           ${metrics['mean_price']:>14,.2f}")
    print(f"  Median firm price:            ${metrics['median_price']:>14,.2f}")
    print()

    # Government
    print("🏛️  GOVERNMENT FINANCES & POLICY")
    print("-" * 80)
    print(f"  Government cash:              ${metrics['government_cash']:>15,.2f}")
    print(f"  Wage tax rate:                {metrics['wage_tax_rate']:>15.1%}")
    print(f"  Profit tax rate:              {metrics['profit_tax_rate']:>15.1%}")
    print(f"  Unemployment benefit:         ${metrics['unemployment_benefit']:>14,.2f}")
    print(f"  Transfer budget:              ${metrics['transfer_budget']:>14,.2f}")
    print(f"  Infrastructure multiplier:    {metrics['infrastructure_productivity']:>18.3f}")
    print(f"  Technology multiplier:        {metrics['technology_quality']:>18.3f}")
    print(f"  Social multiplier:            {metrics['social_happiness']:>18.3f}")
    print()

    # Performance
    print("⚡ SIMULATION PERFORMANCE")
    print("-" * 80)
    print(f"  Total agents:                 {num_households + len(economy.firms) + 1:>15,}")
    print(f"  Total ticks:                  {num_ticks:>18,}")
    print(f"  Current tick:                 {metrics['current_tick']:>18,}")
    print(f"  Total time:                   {total_time:>15.2f} seconds")
    print(f"  Average time per tick:        {avg_tick_time*1000:>15.1f} ms")
    print(f"  Ticks per second:             {1/avg_tick_time:>18.2f}")
    print()

    print("=" * 80)
    print("📸 SAMPLE TRAJECTORIES (5 households, 5 firms)")
    print("=" * 80)
    print()

    # Print household sample summary
    print("HOUSEHOLD SAMPLES:")
    for hh_id in sample_household_ids:
        # Extract household data from snapshots
        hh_data = []
        for snapshot in sample_snapshots:
            for h in snapshot["households"]:
                if h["id"] == hh_id:
                    hh_data.append(h)
                    break

        if hh_data:
            first = hh_data[0]
            last = hh_data[-1]
            print(f"  HH {hh_id:4d}: ${first['cash']:7.2f} → ${last['cash']:7.2f} cash | "
                  f"Employed: {first['employed']} → {last['employed']} | "
                  f"Happiness: {first['happiness']:.2f} → {last['happiness']:.2f}")
    print()

    # Print firm sample summary
    print("FIRM SAMPLES:")
    if sample_firm_ids:
        for firm_id in sample_firm_ids:
            # Extract firm data from snapshots
            firm_data = []
            for snapshot in sample_snapshots:
                for f in snapshot["firms"]:
                    if f["id"] == firm_id:
                        firm_data.append(f)
                        break

            if firm_data:
                first = firm_data[0]
                last = firm_data[-1]
                print(f"  Firm {firm_id:3d} ({last['name']:20s}): "
                      f"${first['cash']:10,.0f} → ${last['cash']:10,.0f} cash | "
                      f"Employees: {first['employees']:3d} → {last['employees']:3d}")
    else:
        print("  No firms tracked in sample")
    print()

    print("=" * 80)
    print("FILES GENERATED")
    print("=" * 80)
    print(f"  Database:  {db_path}")
    print(f"  Summary:   {summary_path} (includes sample trajectories)")
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EcoSim simulation.")
    parser.add_argument("--households", type=int, default=10000, help="Number of households")
    parser.add_argument("--firms-per-category", type=int, default=10, help="Firms per category at creation")
    parser.add_argument("--ticks", type=int, default=500, help="Number of ticks to run")
    parser.add_argument("--export-every", type=int, default=50, help="Export interval (ticks)")
    parser.add_argument("--tag", type=str, default="10k_balanced", help="Output tag for DB/summary filenames")
    parser.add_argument(
        "--small",
        action="store_true",
        help="Shortcut for a 1000-household, 200-tick diagnostic run"
    )
    args = parser.parse_args()

    if args.small:
        args.households = 1000
        args.ticks = 500
        args.export_every = max(10, args.export_every // 2)
        if args.tag == "10k_balanced":
            args.tag = "1k_test"

    main(
        num_households=args.households,
        num_firms_per_category=args.firms_per_category,
        num_ticks=args.ticks,
        export_every=args.export_every,
        output_tag=args.tag
    )
