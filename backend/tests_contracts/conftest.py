import random
from types import SimpleNamespace
from typing import Callable, Dict, List

import numpy as np
import pytest

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy
from tests_contracts.factories import (
    make_economy as make_test_economy,
    make_factory_namespace,
)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def total_money(economy: Economy) -> float:
    household_cash = sum(h.cash_balance for h in economy.households)
    firm_cash = sum(f.cash_balance for f in economy.firms)
    queued_firm_cash = sum(f.cash_balance for f in getattr(economy, "queued_firms", []))
    government_cash = economy.government.cash_balance
    misc_pool = getattr(economy, "misc_firm_revenue", 0.0)
    return household_cash + firm_cash + queued_firm_cash + government_cash + misc_pool


@pytest.fixture
def fixed_seed() -> int:
    seed = 20260302
    seed_everything(seed)
    return seed


@pytest.fixture
def factory(fixed_seed: int) -> SimpleNamespace:
    """
    Scenario factory namespace for handcrafted and generated test setups.

    Usage:
      hh = factory.household(household_id=1, health=0.4)
      firm = factory.firm(firm_id=1, category=\"Services\", price=12.0)
      eco = factory.economy(households=[hh], firms=[firm], government=factory.government())
    """
    seed_everything(fixed_seed)
    return make_factory_namespace()


@pytest.fixture
def economy_factory(fixed_seed: int) -> Callable[..., Economy]:
    """Generic deterministic economy builder with optional explicit entities."""
    def _build(**kwargs) -> Economy:
        seed = kwargs.pop("seed", fixed_seed)
        return make_test_economy(seed=seed, **kwargs)

    return _build


@pytest.fixture
def tiny_economy_factory(fixed_seed: int) -> Callable[..., Economy]:
    def _build(
        num_households: int = 10,
        num_firms_per_category: int = 1,
        include_healthcare: bool = True,
        include_housing: bool = True,
        include_services: bool = True,
        baseline_firms: bool = True,
        disable_shocks: bool = True,
        seed: int = fixed_seed,
        government_cash: float = 20_000.0,
    ) -> Economy:
        seed_everything(seed)

        categories: List[str] = ["Food"]
        if include_housing:
            categories.append("Housing")
        if include_services:
            categories.append("Services")
        if include_healthcare:
            categories.append("Healthcare")

        government = GovernmentAgent(
            cash_balance=government_cash,
            wage_tax_rate=0.15,
            profit_tax_rate=0.20,
            unemployment_benefit_level=30.0,
            transfer_budget=2_000.0,
        )

        firms: List[FirmAgent] = []
        next_firm_id = 1
        for category in categories:
            for idx in range(num_firms_per_category):
                firm_rng = random.Random(seed + next_firm_id * 10007)
                price_base = CONFIG.baseline_prices.get(category, 10.0)
                inventory = 0.0 if category in {"Housing", "Healthcare"} else 500.0
                max_units = 20 if category == "Housing" else 0
                firm = FirmAgent(
                    firm_id=next_firm_id,
                    good_name=f"{category}Firm{idx + 1}",
                    cash_balance=40_000.0,
                    inventory_units=inventory,
                    good_category=category,
                    quality_level=5.0 + firm_rng.uniform(-0.1, 0.1),
                    wage_offer=40.0 + firm_rng.uniform(-0.5, 0.5),
                    price=150.0 if category == "Housing" else price_base,
                    expected_sales_units=60.0,
                    production_capacity_units=600.0 if category != "Housing" else float(max_units),
                    productivity_per_worker=12.0 + firm_rng.uniform(-0.2, 0.2),
                    personality="moderate",
                    is_baseline=baseline_firms,
                    max_rental_units=max_units,
                )
                # happiness_boost_per_unit removed — services affect happiness via wellbeing path only
                if baseline_firms:
                    government.register_baseline_firm(category, firm.firm_id)
                firms.append(firm)
                next_firm_id += 1

        households: List[HouseholdAgent] = []
        for idx in range(num_households):
            hh = HouseholdAgent(
                household_id=idx + 1,
                skills_level=0.35 + 0.03 * (idx % 5),
                age=25 + (idx % 30),
                cash_balance=1_200.0 + 20.0 * idx,
            )
            hh.health = 0.85
            hh.food_consumed_last_tick = CONFIG.households.food_health_high_threshold
            households.append(hh)

        economy = Economy(households=households, firms=firms, government=government)
        if disable_shocks:
            economy._apply_random_shocks = lambda: None
        return economy

    return _build


@pytest.fixture
def category_market_info() -> Dict[str, List[Dict[str, float]]]:
    return {
        "food": [{"firm_id": 1, "good_name": "FoodFirm", "price": 10.0, "quality": 5.0, "inventory": 1000.0}],
        "housing": [{"firm_id": 2, "good_name": "HousingFirm", "price": 100.0, "quality": 5.0, "inventory": 100.0}],
        "services": [{"firm_id": 3, "good_name": "ServicesFirm", "price": 10.0, "quality": 5.0, "inventory": 1000.0}],
    }
