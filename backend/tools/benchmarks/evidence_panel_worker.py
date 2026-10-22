"""One run of the evidence panel, in its own process (read-only on the model).

``run_evidence_panel`` starts this file as a script, once per arm, payment
sequence and seed. The process imports the simulator from the arm's checkout
(``spec["root"]/backend``), so a PR arm and a ``main`` arm can be compared even
when ``main`` lacks the PR's flag. Nothing from the simulator is imported at
module level for that reason.

Construction uses ``sim_setup.build_economy_from_setup`` when the arm has it
(the same call ``SimulationManager`` makes) and the historical inline setup
otherwise. Each tick calls ``economy.step()`` and then the dashboard's
``get_economic_metrics`` and ``compute_household_stats``.

    python backend/tools/benchmarks/evidence_panel_worker.py SPEC.json OUT.json
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import numbers
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

# Load measuring code beside this worker, before selecting an arm's imports.
# Importing the candidate's conftest would let arms measure money differently.
_money_spec = importlib.util.spec_from_file_location("_panel_money", Path(__file__).with_name("panel_money.py"))
_money = importlib.util.module_from_spec(_money_spec)
_money_spec.loader.exec_module(_money)
total_money_net_of_injections = _money.total_money_net_of_injections

PANEL_CATEGORIES = ("Food", "Services")
WEEKS_PER_MONTH = 52.0 / 12.0
_CATEGORY_SAFE = re.compile(r"[^A-Za-z0-9]+")

# Lever name -> government attribute, so a timed lever can be put back.
LEVER_FIELDS = {
    "wage_tax_rate": "wage_tax_rate",
    "profit_tax_rate": "profit_tax_rate",
    "investment_tax_rate": "investment_tax_rate",
    "benefit_level": "benefit_level",
    "public_works": "public_works_toggle",
    "minimum_wage_policy": "minimum_wage_policy",
    "sector_subsidy_target": "sector_subsidy_target",
    "sector_subsidy_level": "sector_subsidy_level",
    "infrastructure_spending": "infrastructure_spending",
    "technology_spending": "technology_spending",
    "social_spending": "social_spending",
    "price_stabilization_target": "price_stabilization_target",
    "price_stabilization_level": "price_stabilization_level",
    "rent_stabilization_level": "rent_stabilization_level",
    "bailout_policy": "bailout_policy",
    "bailout_target": "bailout_target",
    "bailout_budget": "bailout_budget",
}


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


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _plain(value: Any) -> Any:
    """A JSON-stable copy of a loan or ledger field: numbers as floats, mappings as sorted pairs."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, numbers.Real):
        return float(value)
    if isinstance(value, dict):
        return sorted((str(key), _plain(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return repr(value)


def _record(item: Any) -> Any:
    if isinstance(item, dict):
        return _plain(item)
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return _plain({field.name: getattr(item, field.name) for field in dataclasses.fields(item)})
    return repr(item)


def _total(mapping: Any) -> float:
    return float(sum((mapping or {}).values()))


def _loan_book(economy: Any) -> list[Any]:
    """Every bank loan record (all fields) and every housing firm's mortgage contracts."""
    bank = getattr(economy, "bank", None)
    bank_loans = [_record(loan) for loan in (getattr(bank, "active_loans", None) or [])] if bank is not None else None
    mortgages = []
    for firm in list(getattr(economy, "firms", []) or []) + list(getattr(economy, "queued_firms", []) or []):
        contracts = getattr(firm, "housing_active_loans", None) or []
        if contracts:
            mortgages.append([int(firm.firm_id), [_record(contract) for contract in contracts]])
    mortgages.sort(key=lambda item: item[0])
    return [bank_loans, mortgages]


def _payment_ledger(economy: Any) -> Any:
    """Totals of the payment sequences' claims, holds and restriction budgets. None before they existed."""
    state = getattr(economy, "payment_state", None)
    if not isinstance(state, dict):
        return None
    book = getattr(economy, "payment_book", None)
    routes = state.get("capital_routes") or ()
    book_totals = None
    if book is not None:
        book_totals = [
            _num(getattr(book, "clearing_cash", 0.0)),
            _total(getattr(book, "late_income", None)),
            _total(getattr(book, "medical_funding_pending", None)),
            _total(getattr(book, "clearing_payables", None)),
        ]
    return [
        str(getattr(economy, "payment_sequence", "")),
        _total(state.get("wage_claims")),
        len(state.get("wage_claims") or {}),
        _total(state.get("recovery_holds")),
        _total(state.get("ceo_holds")),
        _num(state.get("housing_equal_distribution_hold", 0.0)),
        float(sum(float(row.get("amount", 0.0)) for row in routes)),
        bool(state.get("capital_routes_released", True)),
        _plain(state.get("restrictions")),
        len(state.get("unpaid_streaks") or {}),
        book_totals,
    ]


def _rng_state() -> list[Any]:
    """The process-wide ``random`` and ``numpy.random`` states the engine draws from."""
    import random

    import numpy as np

    version, internal, gauss = random.getstate()
    name, keys, position, has_gauss, cached = np.random.get_state()
    return [
        version,
        hashlib.sha256(json.dumps(list(internal)).encode("utf-8")).hexdigest(),
        gauss,
        str(name),
        hashlib.sha256(np.ascontiguousarray(keys).tobytes()).hexdigest(),
        int(position),
        int(has_gauss),
        float(cached),
    ]


STATE_COMPONENTS = ("households", "firms", "government", "bank", "loans", "payments", "rng")


def state_components(economy: Any) -> dict[str, str]:
    """Hash households, firms, government, the bank, loans, payment ledgers and RNG state.

    Panel rows are not an input. A change in a field the table does not report
    (skill, for example) still changes the household component, which is what
    the identity check reads. ``loans`` covers every bank loan field and the
    housing mortgages, ``payments`` the payment sequences' claim and hold
    totals, and ``rng`` the global ``random`` / ``numpy.random`` states, so an
    arm that draws one extra number diverges here even before any balance moves.
    """
    households = []
    for household in economy.households:
        inventory = getattr(household, "goods_inventory", {}) or {}
        households.append([
            int(household.household_id),
            _num(household.cash_balance),
            _num(getattr(household, "bank_deposit", 0.0)),
            None if household.employer_id is None else int(household.employer_id),
            _num(getattr(household, "wage", 0.0)),
            _num(getattr(household, "happiness", 0.0)),
            _num(getattr(household, "health", 0.0)),
            _num(getattr(household, "skills_level", 0.0)),
            _num(getattr(household, "expected_wage", 0.0)),
            _num(getattr(household, "morale", 0.0)),
            _num(getattr(household, "unemployment_duration", 0.0)),
            _num(getattr(household, "consumption_loan_remaining", 0.0)),
            sorted((str(key), _num(amount)) for key, amount in inventory.items()),
        ])
    households.sort(key=lambda item: item[0])

    def firm_payload(firm: Any, queued: bool) -> list[Any]:
        employees = tuple(sorted(int(employee) for employee in (getattr(firm, "employees", []) or [])))
        return [
            int(firm.firm_id),
            queued,
            bool(getattr(firm, "is_baseline", False)),
            str(getattr(firm, "good_category", "") or ""),
            _num(firm.cash_balance),
            _num(getattr(firm, "price", 0.0)),
            _num(getattr(firm, "inventory_units", 0.0)),
            _num(getattr(firm, "last_profit", 0.0)),
            _num(getattr(firm, "last_units_sold", 0.0)),
            _num(getattr(firm, "last_revenue", 0.0)),
            _num(getattr(firm, "wage_offer", 0.0)),
            employees,
        ]

    firms = [firm_payload(firm, False) for firm in economy.firms]
    firms.extend(firm_payload(firm, True) for firm in (getattr(economy, "queued_firms", []) or []))
    firms.sort(key=lambda item: (item[1], item[0]))

    government = economy.government
    government_payload = [
        _num(government.cash_balance),
        _num(getattr(government, "public_debt", 0.0)),
        _num(government.wage_tax_rate),
        _num(government.profit_tax_rate),
        _num(getattr(government, "investment_tax_rate", 0.0)),
        _num(getattr(government, "unemployment_benefit_level", 0.0)),
        str(getattr(government, "benefit_level", "")),
        _num(getattr(government, "transfer_budget", 0.0)),
        _num(getattr(government, "fiscal_pressure", 0.0)),
        _num(getattr(government, "last_tick_revenue", 0.0)),
        _num(getattr(government, "last_tick_spending", 0.0)),
        _num(getattr(economy, "misc_firm_revenue", 0.0)),
        _num(getattr(economy, "external_injection_total", 0.0)),
    ]

    bank = getattr(economy, "bank", None)
    if bank is None:
        bank_payload: Any = None
    else:
        loans = getattr(bank, "active_loans", []) or []
        loan_rows = []
        for loan in loans:
            if isinstance(loan, dict):
                loan_rows.append([
                    _num(loan.get("principal")),
                    _num(loan.get("remaining")),
                ])
            else:
                loan_rows.append([
                    _num(getattr(loan, "principal", None)),
                    _num(getattr(loan, "remaining", None)),
                ])
        bank_payload = [
            _num(getattr(bank, "cash_reserves", 0.0)),
            _num(getattr(bank, "total_deposits", 0.0)),
            _num(getattr(bank, "public_debt_held", 0.0)),
            len(loans),
            loan_rows,
        ]
    components = {
        "households": _digest(households),
        "firms": _digest(firms),
        "government": _digest(government_payload),
        "bank": _digest(bank_payload),
        "loans": _digest(_loan_book(economy)),
        "payments": _digest(_payment_ledger(economy)),
        "rng": _digest(_rng_state()),
    }
    components["combined"] = _digest([components[name] for name in STATE_COMPONENTS])
    return components


def _load_plugins(spec: dict[str, Any]):
    paths = list(spec.get("metrics_plugins") or [])
    single = spec.get("metrics_plugin")
    if single and single not in paths:
        paths.append(single)
    functions = []
    for path in paths:
        if not path:
            continue
        loaded = importlib.util.spec_from_file_location(f"evidence_panel_plugin_{len(functions)}", path)
        if loaded is None or loaded.loader is None:
            raise ValueError(f"Cannot load metrics plugin {path!r}")
        module = importlib.util.module_from_spec(loaded)
        loaded.loader.exec_module(module)
        extra = getattr(module, "extra_metrics", None)
        if not callable(extra):
            raise ValueError(f"Metrics plugin {path!r} must define extra_metrics(economy) -> dict")
        functions.append(extra)
    return functions


def _category_key(category: Any) -> str:
    return _CATEGORY_SAFE.sub("", str(category or "Other")) or "Other"


def _labour_force_unemployed(economy: Any) -> set[int]:
    return {
        int(household.household_id)
        for household in economy.households
        if household.can_work and not household.is_employed
    }


def _legacy_ids(economy: Any) -> set[int]:
    return {int(firm.firm_id) for firm in economy.firms if bool(getattr(firm, "is_baseline", False))}


def panel_row(economy: Any, metrics: dict[str, Any], stats: dict[str, Any], config: Any, np: Any, flows: dict[str, Any] | None = None) -> dict[str, Any]:
    """The standard measures for one tick, read from state the engine already holds."""
    households = economy.households
    liquid = np.fromiter(
        (h.cash_balance + max(0.0, h.bank_deposit) for h in households), dtype=np.float64, count=len(households)
    )
    happiness = np.fromiter((h.happiness for h in households), dtype=np.float64, count=len(households))
    gdp = float(metrics.get("gdp_this_tick", 0.0))
    cpi = float(metrics.get("consumer_price_index", 100.0) or 100.0)
    firms = economy.firms
    private = [firm for firm in firms if not getattr(firm, "is_baseline", False)]
    legacy = [firm for firm in firms if getattr(firm, "is_baseline", False)]
    flows = flows or {}
    row = {
        "tick": int(economy.current_tick),
        "labor_force_unemployment_rate": float(metrics.get("labor_force_unemployment_rate", 0.0)),
        "unemployment_rate": float(stats["unemployment_rate"]),
        "gdp": gdp,
        "consumer_price_index": cpi,
        "real_gdp": gdp * 100.0 / cpi,
        "food_services_units_sold": float(
            sum(float(getattr(firm, "last_units_sold", 0.0)) for firm in firms if firm.good_category in PANEL_CATEGORIES)
        ),
        "mean_price": float(metrics.get("mean_price", 0.0)),
        "fiscal_balance": float(metrics.get("gov_revenue_this_tick", 0.0)) - float(metrics.get("gov_spending_this_tick", 0.0)),
        "government_cash": float(economy.government.cash_balance),
        "bond_buy": float(metrics.get("gov_bond_purchases_this_tick", 0.0)),
        "private_profit": float(sum(float(getattr(firm, "last_profit", 0.0)) for firm in private)),
        "private_firms": float(len(private)),
        "private_headcount": float(sum(len(getattr(firm, "employees", []) or []) for firm in private)),
        "legacy_firms": float(len(legacy)),
        "legacy_headcount": float(sum(len(getattr(firm, "employees", []) or []) for firm in legacy)),
        "legacy_profit": float(sum(float(getattr(firm, "last_profit", 0.0)) for firm in legacy)),
        "legacy_exits": float(flows.get("legacy_exits") or 0.0),
        "job_finding_rate": flows.get("job_finding_rate"),
        "layoffs_per_month": flows.get("layoffs_per_month"),
        "openings_per_unemployed": flows.get("openings_per_unemployed"),
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
    if happiness.size:
        row["happiness_median"] = float(np.median(happiness))
        row["happiness_p10"] = float(np.percentile(happiness, 10))
        row["happiness_p90"] = float(np.percentile(happiness, 90))
        row["happiness_le_005"] = float((happiness <= 0.05).mean())
        row["happiness_ge_095"] = float((happiness >= 0.95).mean())
    if liquid.size:
        for pct, value in zip(range(10, 100, 10), np.percentile(liquid, list(range(10, 100, 10)))):
            row[f"liquid_wealth_p{pct}"] = float(value)
    units: dict[str, float] = {}
    revenue: dict[str, float] = {}
    for firm in firms:
        category = _category_key(getattr(firm, "good_category", ""))
        units[category] = units.get(category, 0.0) + float(getattr(firm, "last_units_sold", 0.0) or 0.0)
        revenue[category] = revenue.get(category, 0.0) + float(getattr(firm, "last_revenue", 0.0) or 0.0)
    for category, sold in units.items():
        row[f"units__{category}"] = sold
        row[f"rev__{category}"] = revenue.get(category, 0.0)
    return row


def _k06_hold_pool(_self: Any) -> None:
    """Keep the misc pool on the money stock. The payout to households does not run."""
    return None


def install_hooks(economy: Any, hooks: list[str] | None) -> None:
    for name in hooks or []:
        if name != "k06_hold_pool":
            raise ValueError(f"Unknown arm hook {name!r}. Known hooks: k06_hold_pool")
        economy._misc_firm_redistribute_revenue = _k06_hold_pool.__get__(economy, type(economy))


def _lever_value(government: Any, name: str) -> Any:
    return getattr(government, LEVER_FIELDS.get(name, name))


def _lift_minimum_wages(economy: Any) -> None:
    min_wage = float(economy.government.get_minimum_wage())
    for firm in economy.firms:
        if firm.wage_offer < min_wage:
            firm.wage_offer = min_wage


def apply_timed_levers(economy: Any, timed: list[dict[str, Any]], saved: dict[str, Any], week: int) -> None:
    """Apply a lever at ``start`` and put the previous value back after ``end``."""
    for item in timed:
        name = str(item["name"])
        start = int(item["start"])
        end = item.get("end")
        if start == week:
            saved.setdefault(name, _lever_value(economy.government, name))
            economy.government.set_lever(name, parse_override_value(str(item["value"])))
            if name == "minimum_wage_policy":
                _lift_minimum_wages(economy)
        if end is not None and week == int(end) + 1:
            if name not in saved:
                raise ValueError(f"Timed lever {name!r} ends at week {end} without a saved value")
            economy.government.set_lever(name, saved[name])


def _labour_flows(economy: Any, previous_unemployed: set[int]) -> dict[str, Any]:
    employed_now = {int(household.household_id) for household in economy.households if household.is_employed}
    found = len(previous_unemployed & employed_now)
    job_finding = (found / len(previous_unemployed)) if previous_unemployed else None
    layoffs = 0
    openings = 0
    for firm in list(economy.firms) + list(getattr(economy, "queued_firms", []) or []):
        layoffs += len(getattr(firm, "planned_layoffs_ids", []) or [])
        openings += max(0, int(getattr(firm, "planned_hires_count", 0) or 0))
    unemployed_now = _labour_force_unemployed(economy)
    return {
        "job_finding_rate": job_finding,
        "layoffs_per_month": layoffs * WEEKS_PER_MONTH,
        "openings_per_unemployed": (openings / len(unemployed_now)) if unemployed_now else None,
    }


def _try_sim_setup():
    """The arm's shared builder, or None when this checkout is older than the helper."""
    try:
        import sim_setup
    except ImportError:
        return None
    return sim_setup if hasattr(sim_setup, "build_economy_from_setup") else None


def _construct(spec: dict[str, Any], seed: int):
    """Build the economy. Prefer the server's builder; fall back for an older ``main``."""
    from types import SimpleNamespace

    from config import CONFIG

    overrides = dict(spec.get("config_overrides") or {})
    builder = _try_sim_setup()
    if builder is not None:
        setup = SimpleNamespace(
            num_households=int(spec["households"]),
            num_firms=int(spec["firms_per_category"]),
            payment_sequence=spec["payment_sequence"],
            enable_llm_government=False,
            disable_stabilizers=False,
            disabled_agents=[],
            initial_policy={},
        )
        economy, _flags = builder.build_economy_from_setup(
            setup, seed, config_overrides=overrides, extra_levers=spec.get("levers") or {},
        )
        return economy

    apply_config_overrides(CONFIG, overrides)
    CONFIG.random_seed = seed
    CONFIG.payment_sequence = spec["payment_sequence"]
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    from tools.runners.run_large_simulation import create_large_economy

    economy = create_large_economy(int(spec["households"]), int(spec["firms_per_category"]))
    economy.configure_stabilizers(households=True, firms=True, government=True)
    for lever, raw in sorted((spec.get("levers") or {}).items()):
        economy.government.set_lever(lever, parse_override_value(raw))
    if "minimum_wage_policy" in (spec.get("levers") or {}):
        _lift_minimum_wages(economy)
    return economy


def run(spec: dict[str, Any]) -> dict[str, Any]:
    """Run one seeded economy and return its rows, state digest and money check."""
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
    from tools.runners.run_large_simulation import compute_household_stats

    plugins = _load_plugins(spec)
    seed = int(spec["seed"])
    rows: list[dict[str, Any]] = []
    digests: list[dict[str, Any]] = []
    money: list[float] = []
    started = time.perf_counter()
    with use_config(clone_config()), contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        np.random.seed(seed)
        CONFIG.random_seed = seed
        economy = _construct(spec, seed)
        install_hooks(economy, spec.get("hooks") or [])
        saved_levers: dict[str, Any] = {}
        timed = list(spec.get("timed_levers") or [])
        previous_unemployed = _labour_force_unemployed(economy)
        previous_legacy = _legacy_ids(economy)
        if total_money_net_of_injections is not None:
            money.append(float(total_money_net_of_injections(economy)))

        for week in range(1, int(spec["ticks"]) + 1):
            apply_timed_levers(economy, timed, saved_levers, week)
            economy.step()
            metrics = economy.get_economic_metrics()
            stats = compute_household_stats(economy.households)
            flows = _labour_flows(economy, previous_unemployed)
            legacy_now = _legacy_ids(economy)
            flows["legacy_exits"] = len(previous_legacy - legacy_now)
            row = panel_row(economy, metrics, stats, CONFIG, np, flows)
            seen: set[str] = set()
            for extra_metrics in plugins:
                for key, value in (extra_metrics(economy) or {}).items():
                    if key in seen:
                        raise ValueError(f"Plugin metric {key!r} is defined more than once")
                    seen.add(key)
                    row[f"x_{key}"] = None if value is None else float(value)
            rows.append(row)
            component = state_components(economy)
            component["tick"] = int(economy.current_tick)
            digests.append(component)
            previous_unemployed = _labour_force_unemployed(economy)
            previous_legacy = legacy_now
            if total_money_net_of_injections is not None:
                money.append(float(total_money_net_of_injections(economy)))
        final = {
            "misc_firm_revenue": float(getattr(economy, "misc_firm_revenue", 0.0) or 0.0),
            "wage_tax_rate": float(economy.government.wage_tax_rate),
        }

    drift = [value - money[0] for value in money] if money else []
    fingerprint = _digest([item["combined"] for item in digests])
    return {
        "spec": spec,
        "rows": rows,
        "state_digests": digests,
        "fingerprint": fingerprint,
        "row_fingerprint": rows_fingerprint(rows),
        "final": final,
        "money": {
            "definition": "evaluator panel_money.total_money_net_of_injections, change since construction",
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
