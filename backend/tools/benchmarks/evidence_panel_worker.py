"""One run of the evidence panel, in its own process (read-only on the model).

``run_evidence_panel`` starts this file as a script, once per arm, payment
sequence and seed. The process imports the simulator from the arm's checkout
(``spec["root"]/backend``), so a PR arm and a ``main`` arm can be compared even
when ``main`` lacks the PR's flag. Nothing from the simulator is imported at
module level for that reason.

Construction mirrors a dashboard SETUP (``server.SimulationManager``): seed the
Python, NumPy and config RNGs, build with ``create_large_economy``, switch the
three stabilizer groups on, then apply any requested policy levers. Each tick
calls ``economy.step()`` and then the same two observations the dashboard makes
every tick, ``economy.get_economic_metrics()`` and ``compute_household_stats``.

    python backend/tools/benchmarks/evidence_panel_worker.py SPEC.json OUT.json
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

PANEL_CATEGORIES = ("Food", "Services")


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


def rows_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Hash the per-tick panel rows at full float precision."""
    payload = json.dumps(rows, sort_keys=True, allow_nan=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_plugin(path: str | None):
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("evidence_panel_plugin", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load metrics plugin {path!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "extra_metrics", None)):
        raise ValueError(f"Metrics plugin {path!r} must define extra_metrics(economy) -> dict")
    return module.extra_metrics


def panel_row(economy: Any, metrics: dict[str, Any], stats: dict[str, Any], config: Any, np: Any) -> dict[str, Any]:
    """The standard measures for one tick, read from state the engine already holds."""
    households = economy.households
    liquid = np.fromiter(
        (h.cash_balance + max(0.0, h.bank_deposit) for h in households), dtype=np.float64, count=len(households)
    )
    gdp = float(metrics.get("gdp_this_tick", 0.0))
    cpi = float(metrics.get("consumer_price_index", 100.0) or 100.0)
    firms = economy.firms
    private = [f for f in firms if not getattr(f, "is_baseline", False)]
    row = {
        "tick": int(economy.current_tick),
        "labor_force_unemployment_rate": float(metrics.get("labor_force_unemployment_rate", 0.0)),
        "unemployment_rate": float(stats["unemployment_rate"]),
        "gdp": gdp,
        "consumer_price_index": cpi,
        "real_gdp": gdp * 100.0 / cpi,
        "food_services_units_sold": float(
            sum(float(getattr(f, "last_units_sold", 0.0)) for f in firms if f.good_category in PANEL_CATEGORIES)
        ),
        "mean_price": float(metrics.get("mean_price", 0.0)),
        "fiscal_balance": float(metrics.get("gov_revenue_this_tick", 0.0)) - float(metrics.get("gov_spending_this_tick", 0.0)),
        "government_cash": float(economy.government.cash_balance),
        "bond_buy": float(metrics.get("gov_bond_purchases_this_tick", 0.0)),
        "private_profit": float(sum(float(getattr(f, "last_profit", 0.0)) for f in private)),
        "private_firms": float(len(private)),
        "poverty_share": float((liquid < float(config.households.poverty_threshold)).mean()) if liquid.size else 0.0,
        "extreme_poverty_share": float((liquid < float(config.households.extreme_poverty_threshold)).mean())
        if liquid.size
        else 0.0,
        "food_sufficient_share": 1.0 - float(stats.get("food_insecure_share", 0.0)),
        "happiness": float(stats["mean_happiness"]),
        "health": float(stats["mean_health"]),
        "food_unmet_demand": float(getattr(economy, "food_unmet_demand", 0.0)),
        "services_unmet_demand": float(getattr(economy, "services_unmet_demand", 0.0)),
    }
    if liquid.size:
        for pct, value in zip(range(10, 100, 10), np.percentile(liquid, list(range(10, 100, 10)))):
            row[f"liquid_wealth_p{pct}"] = float(value)
    return row


def run(spec: dict[str, Any]) -> dict[str, Any]:
    """Run one seeded economy and return its rows, fingerprint and money check."""
    backend = str(Path(spec["root"]).resolve() / "backend")
    if sys.path[0] != backend:
        sys.path.insert(0, backend)

    import random

    import numpy as np

    runtime = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "numpy": np.__version__,
    }
    planned = spec.get("runtime") or {}
    mismatched = {key: (planned[key], value) for key, value in runtime.items() if key in planned and planned[key] != value}
    if mismatched:
        raise RuntimeError(f"Worker runtime differs from the planned run (planned, actual): {mismatched}")

    from config import CONFIG, clone_config, use_config
    from tools.runners.run_large_simulation import compute_household_stats, create_large_economy

    try:
        from tests_contracts.conftest import total_money_net_of_injections
    except ImportError:  # An older checkout without the shared money helper.
        total_money_net_of_injections = None

    extra_metrics = _load_plugin(spec.get("metrics_plugin"))
    seed = int(spec["seed"])
    rows: list[dict[str, Any]] = []
    money: list[float] = []
    started = time.perf_counter()
    with use_config(clone_config()), contextlib.redirect_stdout(io.StringIO()):
        # Same seeding as regression_snapshot._set_seed and a dashboard SETUP.
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        CONFIG.payment_sequence = spec["payment_sequence"]
        apply_config_overrides(CONFIG, spec.get("config_overrides") or {})
        economy = create_large_economy(int(spec["households"]), int(spec["firms_per_category"]))
        economy.configure_stabilizers(households=True, firms=True, government=True)
        levers = spec.get("levers") or {}
        for lever, raw in sorted(levers.items()):
            economy.government.set_lever(lever, parse_override_value(raw))
        if "minimum_wage_policy" in levers:
            min_wage = float(economy.government.get_minimum_wage())
            for firm in economy.firms:
                if firm.wage_offer < min_wage:
                    firm.wage_offer = min_wage
        if total_money_net_of_injections is not None:
            money.append(float(total_money_net_of_injections(economy)))

        for _ in range(int(spec["ticks"])):
            economy.step()
            metrics = economy.get_economic_metrics()
            stats = compute_household_stats(economy.households)
            row = panel_row(economy, metrics, stats, CONFIG, np)
            if extra_metrics is not None:
                for key, value in (extra_metrics(economy) or {}).items():
                    row[f"x_{key}"] = None if value is None else float(value)
            rows.append(row)
            if total_money_net_of_injections is not None:
                money.append(float(total_money_net_of_injections(economy)))

    drift = [value - money[0] for value in money] if money else []
    return {
        "spec": spec,
        "rows": rows,
        "fingerprint": rows_fingerprint(rows),
        "money": {
            "definition": "tests_contracts.conftest.total_money_net_of_injections, change since construction",
            "available": bool(money),
            "final_drift": drift[-1] if drift else None,
            "max_abs_drift": max((abs(value) for value in drift), default=None),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": {**runtime, "thread_env": {name: os.environ.get(name) for name in planned.get("thread_env") or {}}},
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: evidence_panel_worker.py SPEC.json OUT.json", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    # Replace this script's folder (benchmarks/) on the path with the arm's
    # backend, so the arm's own config, economy and helpers are imported.
    sys.path[0] = str(Path(spec["root"]).resolve() / "backend")
    result = run(spec)
    out = Path(argv[1])
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    temporary.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
