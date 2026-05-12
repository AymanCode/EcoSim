"""Summarize saved LLM government run artifacts.

Usage:
    python backend/tools/analysis/analyze_llm_government_log.py llm_run_outputs/llm_government_latest.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


GROUP_LEVERS = {
    "price_stabilization": {"price_stabilization_target", "price_stabilization_level"},
    "rent_stabilization": {"rent_stabilization_level"},
    "bailout": {"bailout_policy", "bailout_target", "bailout_budget"},
    "sector_subsidy": {"sector_subsidy_target", "sector_subsidy_level"},
}


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _counter_from_changes(records: Iterable[Dict[str, Any]], key: str) -> Counter:
    counts: Counter = Counter()
    for record in records:
        for lever in (record.get(key) or {}).keys():
            counts[lever] += 1
    return counts


def _group_partial_attempt_count(records: List[Dict[str, Any]]) -> int:
    count = 0
    for record in records:
        raw = set((record.get("raw_changes") or {}).keys())
        if not raw:
            continue
        for levers in GROUP_LEVERS.values():
            overlap = raw & levers
            if overlap and overlap != levers:
                count += 1
                break
    return count


def _policy_churn(records: List[Dict[str, Any]]) -> Counter:
    churn: Counter = Counter()
    previous: Dict[str, Any] = {}
    for record in records:
        after = record.get("current_policy_after") or {}
        if previous:
            for lever, value in after.items():
                if previous.get(lever) != value:
                    churn[lever] += 1
        previous = after
    return churn


def _first_last(values: List[float]) -> tuple[float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    return values[0], values[-1], max(values), min(values)


def analyze(path: Path) -> Dict[str, Any]:
    artifact = _load(path)
    decisions = list(artifact.get("decision_records") or artifact.get("decision_history_raw") or [])
    ticks = [int(item.get("tick", 0) or 0) for item in decisions]
    raw_non_empty = sum(1 for item in decisions if item.get("raw_changes"))
    accepted_non_empty = sum(
        1 for item in decisions
        if item.get("accepted_llm_changes") or item.get("accepted_changes") or item.get("decisions")
    )
    rejected = [rej for item in decisions for rej in (item.get("rejected_changes") or [])]
    metrics = list(artifact.get("tick_metrics") or [])
    gdp = [float(row.get("gdp_this_tick", row.get("gdp", 0.0)) or 0.0) for row in metrics]
    cash = [float(row.get("government_cash", row.get("gov_cash", 0.0)) or 0.0) for row in metrics]
    unemployment = [float(row.get("unemployment_rate", 0.0) or 0.0) for row in metrics]
    fiscal_pairs = Counter(
        (
            item.get("llm_fiscal_mode", item.get("fiscal_mode", "NORMAL")),
            item.get("computed_fiscal_mode", "UNKNOWN"),
        )
        for item in decisions
    )
    agreement_items = [
        item for item in decisions
        if item.get("computed_fiscal_mode") is not None
    ]
    agreement = (
        sum(
            1 for item in agreement_items
            if item.get("llm_fiscal_mode", item.get("fiscal_mode")) == item.get("computed_fiscal_mode")
        )
        / max(1, len(agreement_items))
    )
    return {
        "decisions": len(decisions),
        "decision_ticks": ticks,
        "cadence_deltas": [b - a for a, b in zip(ticks, ticks[1:])],
        "raw_non_empty_rate": raw_non_empty / max(1, len(decisions)),
        "accepted_non_empty_rate": accepted_non_empty / max(1, len(decisions)),
        "rejected_rate_per_raw_change": len(rejected) / max(1, sum(len(item.get("raw_changes") or {}) for item in decisions)),
        "rejection_reasons": dict(Counter(str(item.get("reason", "")) for item in rejected)),
        "raw_lever_counts": dict(_counter_from_changes(decisions, "raw_changes")),
        "accepted_llm_lever_counts": dict(_counter_from_changes(decisions, "accepted_llm_changes")),
        "mechanical_correction_counts": dict(_counter_from_changes(decisions, "mechanical_corrections")),
        "grouped_partial_attempt_count": _group_partial_attempt_count(decisions),
        "policy_churn_count": dict(_policy_churn(decisions)),
        "fiscal_mode_pairs": {str(key): value for key, value in fiscal_pairs.items()},
        "llm_computed_fiscal_mode_agreement": agreement,
        "gdp_first_last_peak_trough": _first_last(gdp),
        "cash_first_last_peak_trough": _first_last(cash),
        "unemployment_first_last_peak_trough": _first_last(unemployment),
        "final_policy": artifact.get("final_policy", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze an EcoSim LLM government JSON artifact.")
    parser.add_argument("path", type=Path, help="Path to llm_government JSON artifact")
    args = parser.parse_args()
    summary = analyze(args.path)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
