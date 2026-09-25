"""Versioned, observational evidence for comparison runners (never the tick engine).

Rows/features keep their historical schemas. This sidecar describes their meaning
and the conditions that actually produced them; a shared seed is not a claim of
identical pre-policy state or paired external shocks.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import hashlib
import json
import platform
import importlib.metadata
import subprocess
from pathlib import Path
from typing import Any

from config import get_config
from policy_schema import PROMPT_POLICY_LEVERS

SCHEMA_VERSION = "ecosim.comparison-evidence.v1"
METRIC_VERSION = "ecosim.metrics.legacy.v1"
CONTROL_CAPABILITIES = {
    "target_inflation_rate": {
        "status": "inactive",
        "aliases": ["inflationRate"],
        "description": "Stored legacy target only; no engine response. Changing it does not set realized inflation.",
    },
}
METRIC_DEFINITIONS = {
    "gdp_this_tick": {
        "units": "currency/tick",
        "definition": "Sum of Economy.last_tick_revenue; nominal sales proxy, not real GDP or a complete national account.",
    },
    "mean_price": {
        "units": "currency per heterogeneous unit",
        "definition": "Unweighted mean of active firm prices; not a fixed consumption basket or CPI.",
    },
    "gini_coefficient": {
        "units": "fraction",
        "definition": "Gini of household cash_balance only; excludes deposits, debt and ownership.",
    },
    "households_below_poverty": {
        "units": "households",
        "definition": "Cash below government's current min_cash_threshold; threshold can change with benefits, not an independent poverty standard.",
    },
    "unemployment_rate": {
        "units": "fraction",
        "definition": "Economy metric: jobless/all households when count_cannot_work_as_unemployed is true; otherwise jobless who can_work/all who can_work. See runner-specific overrides.",
    },
    "mean_happiness": {
        "units": "model index",
        "definition": "Mean household happiness, in model units; not empirically calibrated welfare.",
    },
    "mean_health": {"units": "model index", "definition": "Mean household health, in model units."},
    "government_cash": {
        "units": "currency stock",
        "definition": "Treasury cash_balance; negative cash is not an issued debt instrument.",
    },
    "realized_inflation": {
        "units": "fraction per observed period",
        "definition": "Requires an explicitly named price series and lag. The stored target is not this measure; these runners do not export CPI inflation.",
    },
}


def model_identity(root: Path | None = None) -> dict[str, Any]:
    """Hash executed source once per sweep, including uncommitted source changes."""
    root = root or Path(__file__).resolve().parents[1]
    paths = set()
    for folder in (root / "backend", root / "policy_forecasting"):
        for path in folder.rglob("*.py"):
            if not any(part.startswith("test") or part == "__pycache__" for part in path.relative_to(root).parts):
                paths.add(path)
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

    def git(*args):
        try:
            result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    dirty = git("status", "--porcelain")
    return {
        "commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(dirty) if dirty is not None else None,
        "source_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "files_sha256": hashes,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy",)},
    }


def conditions(economy: Any) -> dict[str, Any]:
    """Read settings without calling agent planners, metrics or RNGs."""
    gov = economy.government
    policy = {
        key: copy.deepcopy(getattr(gov, "public_works_toggle" if key == "public_works" else key))
        for key in PROMPT_POLICY_LEVERS
    }
    for key in (
        "wage_bracket_scalers",
        "target_inflation_rate",
        "ubi_amount",
        "wealth_tax_rate",
        "wealth_tax_threshold",
        "birth_rate",
        "unemployment_benefit_level",
        "min_cash_threshold",
        "_minimum_wage_floor",
        "_sector_subsidy_rate",
        "infrastructure_investment_budget",
        "technology_investment_budget",
        "social_investment_budget",
    ):
        policy[key] = copy.deepcopy(getattr(gov, key))
    return {
        "policy": policy,
        "stabilizers": {
            name: bool(getattr(economy, f"enable_{name}_stabilizers")) for name in ("household", "firm", "government")
        },
        "runtime_parameters": {"transfer_budget": gov.transfer_budget, "spending_efficiency": gov.spending_efficiency},
        "bank_policy": None
        if economy.bank is None
        else {
            "base_interest_rate": economy.bank.base_interest_rate,
            "reserve_ratio": economy.bank.reserve_ratio,
            "min_profit_margin_per_tick": economy.bank.min_profit_margin_per_tick,
        },
        "execution": {
            "performance_mode": bool(economy.performance_mode),
            "warmup_ticks": economy.warmup_ticks,
            "bank_present": economy.bank is not None,
            "payment_sequence": getattr(economy, "payment_sequence", "legacy"),
            "payment_care_mode": getattr(economy, "payment_care_mode", "patient_pay"),
            "payment_assistance": getattr(economy, "payment_assistance", "reserve"),
            "payment_parameters": copy.deepcopy(getattr(economy, "payment_config_snapshot", None))
            or {
                field.name: copy.deepcopy(getattr(economy.config, field.name))
                for field in dataclasses.fields(economy.config)
                if field.name.startswith("payment_")
            },
            "performance_mode_semantics": "When enabled, reuse consumption plans between 5-tick updates and update wellbeing every 10 ticks.",
        },
    }


class RunEvidence:
    """One run's settings, changes at tick boundaries, and explicit completion."""

    def __init__(
        self, *, run_id: str, seed: int, ticks: int, factory: dict[str, Any], requested_policy: dict[str, Any]
    ):
        self.data = {
            "run_id": run_id,
            "seed": int(seed),
            "ticks_requested": ticks,
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "factory": dict(factory),
            "requested_policy": copy.deepcopy(requested_policy),
            "configuration_initial": dataclasses.asdict(get_config()),
            "conditions": [],
            "status": "started",
            "ticks_completed": 0,
            "failure": None,
        }
        self._last = None
        self.completed = 0

    def observe(self, economy: Any, *, phase: str) -> None:
        observed = conditions(economy)
        if observed != self._last:
            self.data["conditions"].append({"tick_boundary": int(economy.current_tick), "phase": phase, **observed})
            self._last = observed

    def policy_applied(self, economy: Any) -> None:
        self.data["policy_application"] = {
            "tick_boundary": int(economy.current_tick),
            "phase": "before_step",
            "effective_policy": conditions(economy)["policy"],
        }
        self.observe(economy, phase="after_requested_policy")

    def finish(
        self, economy: Any = None, *, error: Exception | None = None, phase: str | None = None
    ) -> dict[str, Any]:
        if economy is not None:
            self.observe(economy, phase="failure" if error else "end")
            self.data["engine_tick_at_end"] = int(economy.current_tick)
        self.data.update(
            {
                "status": "failed" if error else "completed",
                "ticks_completed": self.completed,
                "configuration_final": dataclasses.asdict(get_config()),
                "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "failure": None
                if error is None
                else {
                    "phase": phase,
                    "type": type(error).__name__,
                    "message": str(error),
                    "attempted_tick": int(economy.current_tick) if economy is not None else None,
                },
            }
        )
        return self.data


def comparison_evidence(
    *,
    model: dict[str, Any],
    runs: list[dict[str, Any]],
    runner: str,
    metric_schema: dict[str, Any] | None = None,
    planned_runs: list[dict[str, Any]] | None = None,
    failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "runner": runner,
        "model": model,
        "comparison_design": {
            "pairing": "same seed across independently initialized policy arms",
            "policy_timing": "before first step, after factory initialization",
            "limits": "No saved pre-policy branch, common-shock guarantee or causal identification claim. W10 remains design work.",
            "observation_timing": "Settings at initialization, policy application and changed step boundaries; not an intra-tick trace.",
        },
        "control_capabilities": copy.deepcopy(CONTROL_CAPABILITIES),
        "metric_definitions": {
            "version": METRIC_VERSION,
            "definitions": copy.deepcopy(METRIC_DEFINITIONS),
            "runner_schema": metric_schema or {},
        },
        "planned_runs": planned_runs or [],
        "sweep_failures": failures or [],
        "runs": runs,
    }


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    """Replace one JSON sidecar atomically so interrupted writes are recognizable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
