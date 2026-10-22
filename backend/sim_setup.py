"""Build the economy the dashboard SETUP builds.

``SimulationManager`` and the evidence-panel worker both call
``build_economy_from_setup`` so a panel arm is the same world the server
starts. The function only sequences existing construction calls. It does not
change household, firm, or government behavior.
"""

from __future__ import annotations

import ast
import random
from dataclasses import fields
from typing import Any

import numpy as np

from config import CONFIG, get_config
from tools.runners.run_large_simulation import create_large_economy


def parse_override_value(raw: str) -> Any:
    """Read a ``--set`` value as a Python literal, else keep it as text."""
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw


def coerce_to_current(path: str, current: Any, value: Any) -> Any:
    """Match an override to the type of the setting it replaces, or refuse it."""
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{path} is a bool; use True or False, got {value!r}")
        return value
    if isinstance(current, float) and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(current, tuple) and isinstance(value, list):
        return tuple(value)
    if current is not None and not isinstance(value, type(current)):
        raise ValueError(f"{path} is {type(current).__name__}; got {type(value).__name__} {value!r}")
    return value


def apply_config_overrides(config: Any, overrides: dict[str, Any]) -> None:
    """Set ``section.field`` values on CONFIG; an unknown name is an error, not a no-op."""
    for path, raw in sorted(overrides.items()):
        parts = path.split(".")
        if len(parts) < 2:
            raise ValueError(f"Config override {path!r} must name a section and field, e.g. households.poverty_threshold")
        target = config
        for part in parts[:-1]:
            if not hasattr(target, part):
                raise ValueError(f"Unknown config section {part!r} in override {path!r}")
            target = getattr(target, part)
        field = parts[-1]
        if not hasattr(target, field):
            raise ValueError(f"Unknown config field {field!r} in override {path!r}")
        setattr(target, field, coerce_to_current(path, getattr(target, field), parse_override_value(raw)))


def _payment_names(setup: Any) -> list[str]:
    model_fields = getattr(type(setup), "model_fields", None)
    if model_fields:
        return [name for name in model_fields if name.startswith("payment_")]
    return [name for name in vars(setup) if name.startswith("payment_")]


def _stabilizer_flags(setup: Any) -> tuple[list[str], bool, bool, bool]:
    """The same disabled-agent rules ``SimulationManager._initialize_economy`` applies."""
    disabled: list[str] = []
    if getattr(setup, "disable_stabilizers", False):
        disabled = list(getattr(setup, "disabled_agents", []) or [])
        if not disabled:
            disabled = ["households", "firms", "government"]
    elif getattr(setup, "disabled_agents", None):
        disabled = list(setup.disabled_agents)
    if disabled:
        households = not ("all" in disabled or "households" in disabled)
        firms = not ("all" in disabled or "firms" in disabled)
        government = not ("all" in disabled or "government" in disabled)
        return disabled, households, firms, government
    return [], True, True, True


def build_economy_from_setup(
    setup: Any,
    seed: int,
    *,
    config_overrides: dict[str, Any] | None = None,
    extra_levers: dict[str, Any] | None = None,
    factory: Any = None,
):
    """Build one economy from a dashboard ``SetupConfig`` (or the same attributes).

    Call inside ``use_config``. ``seed`` is written to ``CONFIG.random_seed`` and
    applied to the Python and NumPy RNGs before ``create_large_economy``, which
    is the seeding ``SimulationManager`` uses. Returns ``(economy, (households_on,
    firms_on, government_on))``.
    """
    seed = int(seed)
    config = CONFIG
    for name in _payment_names(setup):
        setattr(config, name, getattr(setup, name))
    if config_overrides:
        apply_config_overrides(config, config_overrides)
    config.random_seed = seed
    llm = getattr(setup, "enable_llm_government", None)
    if llm is not None:
        config.llm.enable_llm_government = bool(llm)
    random.seed(seed)
    np.random.seed(seed)

    # ``factory`` is the caller's create_large_economy so a patch of
    # server.create_large_economy still observes the dashboard SETUP.
    build = factory or create_large_economy
    economy = build(
        num_households=int(setup.num_households),
        num_firms_per_category=int(setup.num_firms),
    )
    actual = get_config()
    economy.payment_config_snapshot = {
        field.name: getattr(actual, field.name)
        for field in fields(actual)
        if field.name.startswith("payment_")
    }

    disabled, households_on, firms_on, government_on = _stabilizer_flags(setup)
    if disabled:
        economy.apply_stabilization_overrides(disabled)
    else:
        economy.configure_stabilizers(households=True, firms=True, government=True)

    levers = dict(getattr(setup, "initial_policy", None) or {})
    for name, raw in (extra_levers or {}).items():
        levers[name] = parse_override_value(raw) if isinstance(raw, str) else raw
    for lever, value in levers.items():
        economy.government.set_lever(lever, value)
    if "minimum_wage_policy" in levers:
        min_wage = float(economy.government.get_minimum_wage())
        for firm in economy.firms:
            if firm.wage_offer < min_wage:
                firm.wage_offer = min_wage
    return economy, (households_on, firms_on, government_on)
