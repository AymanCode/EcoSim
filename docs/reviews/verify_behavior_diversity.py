"""Bounded initialization probe; no economic-effect or calibration claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import copy

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from agents import FirmAgent, HouseholdAgent  # noqa: E402
from config import CONFIG  # noqa: E402


def summarize(agents, repeat_agents, field_names):
    profiles = [tuple(getattr(agent, field) for field in field_names) for agent in agents]
    repeated = [tuple(getattr(agent, field) for field in field_names) for agent in repeat_agents]
    return {
        "count": len(agents),
        "distinct_selected_trait_profiles": len(set(profiles)),
        "same_seed_and_id_reproduces_selected_traits": profiles == repeated,
        "fields": {
            name: {
                "distinct_values": len(set(values)),
                "minimum": min(values),
                "maximum": max(values),
            }
            for index, name in enumerate(field_names)
            for values in [[profile[index] for profile in profiles]]
        },
    }


def main():
    CONFIG.random_seed = 42
    household_fields = [
        "spending_tendency", "saving_tendency", "savings_drawdown_rate",
        "price_sensitivity", "price_expectation_alpha", "wage_expectation_alpha",
        "job_switch_threshold", "health_decay_rate",
    ]
    firm_fields = [
        "risk_tolerance", "price_adjustment_rate", "wage_adjustment_rate",
        "rd_spending_rate", "units_per_worker", "sales_expectation_alpha",
        "target_inventory_weeks",
    ]

    def households():
        return [
            HouseholdAgent(household_id=i, skills_level=0.5, age=30, cash_balance=1000.0)
            for i in range(1, 1001)
        ]

    def firms():
        return [
            FirmAgent(
                firm_id=i, good_name=f"ProbeFood{i}", good_category="Food",
                cash_balance=40000.0, inventory_units=500.0,
                personality="moderate", is_baseline=False,
            )
            for i in range(1, 101)
        ]

    rd_template = firms()[0]
    rd_template.net_profit = 100.0
    rd_probe = []
    for proposed_rate in (0.0, 0.25):
        candidate = copy.deepcopy(rd_template)
        candidate.rd_spending_rate = proposed_rate
        cash_before = candidate.cash_balance
        spent = candidate.apply_rd_and_quality_update(1000.0)
        rd_probe.append({
            "rd_spending_rate": proposed_rate,
            "net_profit": 100.0,
            "revenue": 1000.0,
            "survival_mode": candidate.survival_mode,
            "actual_rd_spending": spent,
            "cash_change": candidate.cash_balance - cash_before,
            "quality_after": candidate.quality_level,
        })

    result = {
        "purpose": "Measure existing initialized diversity with equal stated starting inputs.",
        "seed": 42,
        "source_sha256": {
            rel: hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
            for rel in ("backend/agents.py", "backend/config.py")
        },
        "household_constructor": {
            "household_id": "1..1000", "skills_level": 0.5, "age": 30,
            "cash_balance": 1000.0, "other_fields": "current constructor defaults",
        },
        "firm_constructor": {
            "firm_id": "1..100", "good_name": "ProbeFood<id>",
            "good_category": "Food", "cash_balance": 40000.0,
            "inventory_units": 500.0, "personality": "moderate", "is_baseline": False,
            "other_fields": "current constructor defaults",
        },
        "households": summarize(households(), households(), household_fields),
        "firms": summarize(firms(), firms(), firm_fields),
        "isolated_rd_method_probe": {
            "method": "FirmAgent.apply_rd_and_quality_update",
            "starting_firm": "Two deep copies of firm 1 from the stated constructor",
            "cases": rd_probe,
            "same_spending_despite_changed_field": (
                rd_probe[0]["actual_rd_spending"] == rd_probe[1]["actual_rd_spending"]
            ),
        },
        "limits": [
            "No economy ticks, policy comparisons, market clearing, or model calls are executed.",
            "A distinct parameter profile does not establish distinct behavior or empirical realism.",
            "Selected traits and populations only; not a proof of global uniqueness or full-state replay.",
            "Firm sample covers one non-baseline Food personality; it is not all firm categories.",
            "The R&D probe exercises one isolated method and does not estimate economic effects.",
        ],
    }
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
