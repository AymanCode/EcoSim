import random
from dataclasses import fields
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from agents import FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy


def seed_everything(seed: int) -> None:
    """Seed Python and NumPy RNGs for deterministic tests."""
    random.seed(seed)
    np.random.seed(seed)


def _init_field_names(cls) -> set[str]:
    return {f.name for f in fields(cls) if f.init}


HOUSEHOLD_INIT_FIELDS = _init_field_names(HouseholdAgent)
FIRM_INIT_FIELDS = _init_field_names(FirmAgent)
GOV_INIT_FIELDS = _init_field_names(GovernmentAgent)


def _split_init_overrides(overrides: Dict[str, object], init_fields: set[str]) -> tuple[Dict[str, object], Dict[str, object]]:
    ctor_kwargs: Dict[str, object] = {}
    post_kwargs: Dict[str, object] = {}
    for key, value in overrides.items():
        if key in init_fields:
            ctor_kwargs[key] = value
        else:
            post_kwargs[key] = value
    return ctor_kwargs, post_kwargs


def make_household(
    household_id: int = 1,
    *,
    skills_level: float = 0.5,
    age: int = 30,
    cash_balance: float = 1_000.0,
    **overrides,
) -> HouseholdAgent:
    """Create one household with sensible defaults and optional overrides."""
    ctor = {
        "household_id": household_id,
        "skills_level": skills_level,
        "age": age,
        "cash_balance": cash_balance,
    }
    ctor_overrides, post_overrides = _split_init_overrides(overrides, HOUSEHOLD_INIT_FIELDS)
    ctor.update(ctor_overrides)

    household = HouseholdAgent(**ctor)
    household.health = max(0.0, min(1.0, household.health))
    household.food_consumed_last_tick = CONFIG.households.food_health_high_threshold

    for key, value in post_overrides.items():
        setattr(household, key, value)
    return household


def make_households(
    count: int,
    *,
    start_id: int = 1,
    skills_start: float = 0.35,
    skills_step: float = 0.03,
    age_start: int = 25,
    age_cycle: int = 30,
    cash_start: float = 1_200.0,
    cash_step: float = 20.0,
    household_overrides: Optional[Dict[str, object]] = None,
) -> List[HouseholdAgent]:
    """Create a deterministic household batch for scenario tests."""
    overrides = household_overrides or {}
    households: List[HouseholdAgent] = []
    for idx in range(count):
        households.append(
            make_household(
                household_id=start_id + idx,
                skills_level=skills_start + skills_step * (idx % 5),
                age=age_start + (idx % max(1, age_cycle)),
                cash_balance=cash_start + cash_step * idx,
                **overrides,
            )
        )
    return households


def make_firm(
    firm_id: int = 1,
    *,
    category: str = "Food",
    is_baseline: bool = True,
    seed: int = CONFIG.random_seed,
    **overrides,
) -> FirmAgent:
    """Create one firm with category-aware defaults and optional overrides."""
    category_name = category.strip().title()
    rng = random.Random(seed + firm_id * 10007)
    max_units = 20 if category_name == "Housing" else 0
    ctor = {
        "firm_id": firm_id,
        "good_name": f"{category_name}Firm{firm_id}",
        "cash_balance": 40_000.0,
        "inventory_units": 0.0 if category_name in {"Housing", "Healthcare"} else 500.0,
        "good_category": category_name,
        "quality_level": 5.0 + rng.uniform(-0.1, 0.1),
        "wage_offer": 40.0 + rng.uniform(-0.5, 0.5),
        "price": 150.0 if category_name == "Housing" else CONFIG.baseline_prices.get(category_name, 10.0),
        "expected_sales_units": 60.0,
        "production_capacity_units": 600.0 if category_name != "Housing" else float(max_units),
        "productivity_per_worker": 12.0 + rng.uniform(-0.2, 0.2),
        "personality": "moderate",
        "is_baseline": is_baseline,
        "max_rental_units": max_units,
    }

    ctor_overrides, post_overrides = _split_init_overrides(overrides, FIRM_INIT_FIELDS)
    ctor.update(ctor_overrides)
    firm = FirmAgent(**ctor)

    for key, value in post_overrides.items():
        setattr(firm, key, value)
    return firm


def make_firms(
    categories: Sequence[str],
    *,
    num_per_category: int = 1,
    start_id: int = 1,
    is_baseline: bool = True,
    seed: int = CONFIG.random_seed,
    government: Optional[GovernmentAgent] = None,
    firm_overrides: Optional[Dict[str, object]] = None,
) -> List[FirmAgent]:
    """Create firms across categories, optionally registering baseline firms with government."""
    overrides = firm_overrides or {}
    firms: List[FirmAgent] = []
    next_id = start_id
    for category in categories:
        for _ in range(num_per_category):
            firm = make_firm(
                firm_id=next_id,
                category=category,
                is_baseline=is_baseline,
                seed=seed,
                **overrides,
            )
            if is_baseline and government is not None:
                government.register_baseline_firm(firm.good_category, firm.firm_id)
            firms.append(firm)
            next_id += 1
    return firms


def make_government(**overrides) -> GovernmentAgent:
    """Create a government agent for tests."""
    ctor = {
        "cash_balance": 20_000.0,
        "wage_tax_rate": 0.15,
        "profit_tax_rate": 0.20,
        "unemployment_benefit_level": 30.0,
        "transfer_budget": 2_000.0,
    }
    ctor_overrides, post_overrides = _split_init_overrides(overrides, GOV_INIT_FIELDS)
    ctor.update(ctor_overrides)
    government = GovernmentAgent(**ctor)
    for key, value in post_overrides.items():
        setattr(government, key, value)
    return government


def make_economy(
    *,
    households: Optional[List[HouseholdAgent]] = None,
    firms: Optional[List[FirmAgent]] = None,
    government: Optional[GovernmentAgent] = None,
    queued_firms: Optional[List[FirmAgent]] = None,
    num_households: int = 10,
    categories: Sequence[str] = ("Food", "Housing", "Services", "Healthcare"),
    num_firms_per_category: int = 1,
    baseline_firms: bool = True,
    seed: int = 20260302,
    disable_shocks: bool = True,
) -> Economy:
    """
    Build a test economy from explicit entities or auto-generated defaults.

    - Pass explicit `households` / `firms` / `government` for handcrafted scenarios.
    - Omit them to generate deterministic defaults via this helper.
    """
    seed_everything(seed)
    gov = government or make_government()
    hhs = households or make_households(num_households)
    fs = firms or make_firms(
        categories=categories,
        num_per_category=num_firms_per_category,
        is_baseline=baseline_firms,
        seed=seed,
        government=gov if baseline_firms else None,
    )
    economy = Economy(households=hhs, firms=fs, government=gov, queued_firms=queued_firms or [])
    if disable_shocks:
        economy._apply_random_shocks = lambda: None
    return economy


def make_factory_namespace() -> SimpleNamespace:
    """Return a convenience namespace for fixture use."""
    return SimpleNamespace(
        seed=seed_everything,
        household=make_household,
        households=make_households,
        firm=make_firm,
        firms=make_firms,
        government=make_government,
        economy=make_economy,
    )
