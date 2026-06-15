from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""EcoSim LLM Government Runner

Runs the simulation with an LLM government agent making policy decisions.
Prints economic state and LLM decisions/reasoning in real-time to the console.

Usage:
    python run_llm_government_test.py                          # defaults
    python run_llm_government_test.py --ticks 60               # longer run
    python run_llm_government_test.py --philosophy keynesian   # different philosophy
    python run_llm_government_test.py --model qwen3:8b         # different model
    python run_llm_government_test.py --households 500         # bigger economy
    python run_llm_government_test.py --interval 8             # decide every 8 ticks
    python run_llm_government_test.py --provider lmstudio --base-url http://127.0.0.1:8080
    python run_llm_government_test.py --provider groq --model llama-3.3-70b-versatile
    python run_llm_government_test.py --ticks 200 --first-decision-tick 15
    python run_llm_government_test.py --warmup-ticks 12        # shorter bootstrap period
    python run_llm_government_test.py --no-probe               # skip warmup probe
"""

import argparse
import asyncio
import json
import sys
import os
import time
import random
from collections import Counter
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy
from llm_provider import OllamaProvider, LMStudioProvider, OpenRouterProvider, GroqProvider
from llm_government import LLMGovernmentAdvisor


def parse_args():
    parser = argparse.ArgumentParser(description="EcoSim LLM Government Runner")
    parser.add_argument("--ticks", type=int, default=24, help="Number of ticks to run (default: 24)")
    parser.add_argument("--households", type=int, default=200, help="Number of households (default: 200)")
    parser.add_argument("--interval", type=int, default=26, help="Ticks between LLM decisions (default: 26)")
    parser.add_argument("--first-decision-tick", type=int, default=15,
                        help="First tick where the LLM may change policy (default: 15)")
    parser.add_argument("--philosophy", type=str, default="capitalist",
                        choices=["capitalist", "keynesian", "balanced"],
                        help="Government philosophy (default: capitalist)")
    parser.add_argument("--model", type=str, default="phi4-mini-reasoning", help="Model name (default: phi4-mini-reasoning)")
    parser.add_argument("--provider", type=str, default="lmstudio", choices=["ollama", "lmstudio", "openrouter", "groq"],
                        help="LLM provider (default: lmstudio)")
    parser.add_argument("--base-url", type=str, default=None,
                        help="Provider base URL for local servers, e.g. http://127.0.0.1:8080 for llama.cpp")
    parser.add_argument("--temperature", type=float, default=0.4, help="LLM temperature (default: 0.4)")
    parser.add_argument("--top-p", type=float, default=None, help="LLM top_p (default: config value)")
    parser.add_argument("--warmup-ticks", type=int, default=10,
                        help="Warmup ticks before queued firms activate (default: 10)")
    parser.add_argument("--no-probe", action="store_true", help="Skip the warmup LLM probe")
    parser.add_argument("--timeout", type=float, default=300.0, help="LLM call timeout in seconds (default: 300)")
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens per LLM call (default: config value)")
    parser.add_argument("--seed", type=int, default=42, help="Simulation random seed (default: 42)")
    parser.add_argument("--no-think", action="store_true", help="Append /no_think to disable DeepSeek R1 thinking")
    parser.add_argument("--labor-diagnostics", action="store_true", help="Print detailed labor diagnostics each tick")
    parser.add_argument("--flow-diagnostics", action="store_true", help="Print income/spending/inventory/forecast diagnostics each tick")
    parser.add_argument("--category-gap-diagnostics", action="store_true",
                        help="Print per-category planned-vs-cleared spending gaps for ticks 12-15")
    parser.add_argument("--firm-hire-gate-diagnostics", action="store_true",
                        help="Print per-firm hiring gate diagnostics at the final tick")
    parser.add_argument("--output-dir", type=str, default="experiments/llm_government_supporting_runs",
                        help="Directory for JSON/Markdown run artifacts (default: experiments/llm_government_supporting_runs)")
    parser.add_argument("--no-output-files", action="store_true",
                        help="Do not write JSON/Markdown run artifacts")
    parser.add_argument("--disable-bailouts", action="store_true",
                        help="Keep bailout levers off after every LLM decision for no-bailout comparison runs")
    return parser.parse_args()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float):
        if np.isfinite(value):
            return value
        return str(value)
    return value


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_decision_for_markdown(item: dict) -> str:
    accepted = item.get("accepted_llm_changes") or item.get("accepted_changes") or item.get("decisions") or {}
    mechanical = item.get("mechanical_corrections") or {}
    applied = item.get("applied_changes") or item.get("decisions") or {}
    rejected = item.get("rejected_changes") or []
    raw = item.get("raw_changes") or {}
    rejected_text = "; ".join(
        f"{r.get('group') or r.get('lever')}={r.get('value')} ({r.get('reason')})"
        for r in rejected
    ) or "none"
    return (
        f"| {item.get('tick')} | {item.get('fiscal_mode', 'NORMAL')} | "
        f"{item.get('primary_goal', 'hold')} | `{raw}` | `{accepted}` | `{mechanical}` | `{applied}` | {rejected_text} | "
        f"${float(item.get('gov_cash', 0.0) or 0.0):,.0f} | "
        f"${float(item.get('gdp', 0.0) or 0.0):,.0f} | "
        f"{float(item.get('unemployment_rate', 0.0) or 0.0) * 100.0:.1f}% |"
    )


def _median(values):
    values = sorted(float(value) for value in values if value is not None)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _dist(values):
    values = [float(value) for value in values if value is not None]
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    arr = np.array(values, dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "median": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def build_wage_reservation_summary(economy):
    firms = list(getattr(economy, "firms", []) or [])
    households = list(getattr(economy, "households", []) or [])

    employed = [
        household for household in households
        if bool(getattr(household, "is_employed", False))
    ]
    unemployed_can_work = [
        household for household in households
        if (not bool(getattr(household, "is_employed", False)))
        and bool(getattr(household, "can_work", True))
    ]
    cannot_work = [
        household for household in households
        if not bool(getattr(household, "can_work", True))
    ]

    all_offers = [
        float(getattr(firm, "wage_offer", 0.0) or 0.0)
        for firm in firms
        if float(getattr(firm, "wage_offer", 0.0) or 0.0) > 0.0
    ]
    private_offers = [
        float(getattr(firm, "wage_offer", 0.0) or 0.0)
        for firm in firms
        if not bool(getattr(firm, "is_baseline", False))
        and float(getattr(firm, "wage_offer", 0.0) or 0.0) > 0.0
    ]
    active_private_offers = [
        float(getattr(firm, "wage_offer", 0.0) or 0.0)
        for firm in firms
        if not bool(getattr(firm, "is_baseline", False))
        and int(getattr(firm, "planned_hires_count", 0) or 0) > 0
        and float(getattr(firm, "wage_offer", 0.0) or 0.0) > 0.0
    ]
    baseline_offers = [
        float(getattr(firm, "wage_offer", 0.0) or 0.0)
        for firm in firms
        if bool(getattr(firm, "is_baseline", False))
        and float(getattr(firm, "wage_offer", 0.0) or 0.0) > 0.0
    ]
    employed_wages = [
        float(getattr(household, "wage", 0.0) or 0.0)
        for household in employed
        if float(getattr(household, "wage", 0.0) or 0.0) > 0.0
    ]
    unemployed_reservations = [
        float(getattr(household, "reservation_wage", 0.0) or 0.0)
        for household in unemployed_can_work
    ]
    unemployed_expected = [
        float(getattr(household, "expected_wage", 0.0) or 0.0)
        for household in unemployed_can_work
    ]
    last_labor_plans = dict(getattr(economy, "last_household_labor_plans", {}) or {})
    unemployed_tick_reservations = [
        float(last_labor_plans.get(getattr(household, "household_id", None), {}).get(
            "reservation_wage",
            getattr(household, "reservation_wage", 0.0),
        ) or 0.0)
        for household in unemployed_can_work
    ]
    cannot_work_reservations = [
        float(getattr(household, "reservation_wage", 0.0) or 0.0)
        for household in cannot_work
    ]

    offer_anchor = _median(active_private_offers) or _median(private_offers) or _median(all_offers)
    min_wage = float(economy.government.get_minimum_wage())
    benefit = float(economy.government.get_unemployment_benefit_level())
    benefit_floor = benefit * float(CONFIG.households.min_job_premium_over_unemployment)

    def share_at_or_below(values, cutoff):
        if not values or cutoff <= 0.0:
            return 0.0
        return sum(1 for value in values if float(value) <= cutoff + 1e-9) / len(values)

    return {
        "employed_wages": _dist(employed_wages),
        "all_firm_offers": _dist(all_offers),
        "private_firm_offers": _dist(private_offers),
        "active_private_firm_offers": _dist(active_private_offers),
        "baseline_firm_offers": _dist(baseline_offers),
        "unemployed_reservations": _dist(unemployed_reservations),
        "unemployed_tick_reservations": _dist(unemployed_tick_reservations),
        "unemployed_expected_wages": _dist(unemployed_expected),
        "cannot_work_reservations": _dist(cannot_work_reservations),
        "offer_anchor": offer_anchor,
        "minimum_wage_floor": min_wage,
        "unemployment_benefit": benefit,
        "benefit_floor": benefit_floor,
        "share_unemployed_reservation_lte_offer_anchor": share_at_or_below(unemployed_reservations, offer_anchor),
        "share_unemployed_reservation_lte_min_wage": share_at_or_below(unemployed_reservations, min_wage),
        "share_unemployed_reservation_lte_benefit_floor": share_at_or_below(unemployed_reservations, benefit_floor),
        "share_tick_reservation_lte_offer_anchor": share_at_or_below(unemployed_tick_reservations, offer_anchor),
        "share_tick_reservation_lte_min_wage": share_at_or_below(unemployed_tick_reservations, min_wage),
        "share_tick_reservation_lte_benefit_floor": share_at_or_below(unemployed_tick_reservations, benefit_floor),
        "active_private_firms_hiring": sum(
            1 for firm in firms
            if not bool(getattr(firm, "is_baseline", False))
            and int(getattr(firm, "planned_hires_count", 0) or 0) > 0
        ),
    }


def build_unmet_demand_summary(economy):
    firms = list(getattr(economy, "firms", []) or [])
    housing_diag = dict(getattr(economy, "last_housing_diagnostics", {}) or {})
    health_diag = dict(getattr(economy, "last_health_diagnostics", {}) or {})

    firm_unmet_rows = []
    sector_unmet = Counter()
    baseline_unmet = Counter()
    private_unmet = Counter()
    for firm in firms:
        unmet = float(getattr(firm, "last_tick_raw_lost_sales_units", 0.0) or 0.0)
        if unmet <= 0.0:
            continue
        sector = str(getattr(firm, "good_category", "unknown") or "unknown").lower()
        is_baseline = bool(getattr(firm, "is_baseline", False))
        sector_unmet[sector] += unmet
        if is_baseline:
            baseline_unmet[sector] += unmet
        else:
            private_unmet[sector] += unmet
        firm_unmet_rows.append({
            "firm_id": int(getattr(firm, "firm_id", -1)),
            "sector": sector,
            "baseline": is_baseline,
            "unmet": unmet,
            "observed_demand": float(getattr(firm, "last_tick_observed_demand_units", 0.0) or 0.0),
            "sold": float(getattr(firm, "last_units_sold", 0.0) or 0.0),
            "inventory": float(getattr(firm, "inventory_units", 0.0) or 0.0),
            "workers": len(getattr(firm, "employees", []) or []),
            "planned_hires": int(getattr(firm, "planned_hires_count", 0) or 0),
            "cash_runway": float(getattr(firm, "cash_runway_ticks", 0.0) or 0.0),
            "survival": bool(getattr(firm, "survival_mode", False)),
            "burn": bool(getattr(firm, "burn_mode", False)),
        })

    explicit_goods_unmet = {
        "food": float(getattr(economy, "food_unmet_demand", 0.0) or 0.0),
        "services": float(getattr(economy, "services_unmet_demand", 0.0) or 0.0),
    }
    total_goods_unmet = sum(explicit_goods_unmet.values())
    top_firms = sorted(firm_unmet_rows, key=lambda item: item["unmet"], reverse=True)[:8]
    service_unmet_by_firm = {
        int(fid): float(value)
        for fid, value in (getattr(economy, "services_unmet_demand_by_firm", {}) or {}).items()
    }

    return {
        "explicit_goods_unmet": explicit_goods_unmet,
        "total_goods_unmet": total_goods_unmet,
        "firm_level_unmet_by_sector": dict(sector_unmet),
        "baseline_unmet_by_sector": dict(baseline_unmet),
        "private_unmet_by_sector": dict(private_unmet),
        "top_firms": top_firms,
        "service_unmet_by_firm": service_unmet_by_firm,
        "housing_failure_count": float(housing_diag.get("housing_failure_count", 0.0) or 0.0),
        "housing_unaffordable_count": float(housing_diag.get("housing_unaffordable_count", 0.0) or 0.0),
        "housing_no_supply_count": float(housing_diag.get("housing_no_supply_count", 0.0) or 0.0),
        "homeless_household_count": float(housing_diag.get("homeless_household_count", 0.0) or 0.0),
        "housing_shortage_flag": float(housing_diag.get("housing_shortage_flag", 0.0) or 0.0),
        "healthcare_queue_depth": float(health_diag.get("healthcare_queue_depth", 0.0) or 0.0),
        "healthcare_completed_count": float(health_diag.get("healthcare_completed_count", 0.0) or 0.0),
        "healthcare_denied_count": float(health_diag.get("healthcare_denied_count", 0.0) or 0.0),
    }


def _firm_debt_remaining(firm) -> float:
    housing_debt = sum(
        float(getattr(loan, "principal_remaining", 0.0) or 0.0)
        for loan in (getattr(firm, "housing_active_loans", []) or [])
    )
    return (
        max(0.0, float(getattr(firm, "government_loan_remaining", 0.0) or 0.0))
        + max(0.0, float(getattr(firm, "bank_loan_remaining", 0.0) or 0.0))
        + max(0.0, float(getattr(firm, "service_infrastructure_loan_remaining", 0.0) or 0.0))
        + max(0.0, housing_debt)
    )


def _firm_debt_payment(firm) -> float:
    housing_pmt = sum(
        float(getattr(loan, "pmt_per_tick", 0.0) or 0.0)
        for loan in (getattr(firm, "housing_active_loans", []) or [])
    )
    return (
        max(0.0, float(getattr(firm, "loan_payment_per_tick", 0.0) or 0.0))
        + max(0.0, float(getattr(firm, "bank_loan_payment_per_tick", 0.0) or 0.0))
        + max(0.0, float(getattr(firm, "service_infrastructure_loan_payment_per_tick", 0.0) or 0.0))
        + max(0.0, housing_pmt)
    )


def _firm_net_worth_proxy(firm) -> float:
    cash = float(getattr(firm, "cash_balance", 0.0) or 0.0)
    price = max(0.0, float(getattr(firm, "price", 0.0) or 0.0))
    inventory_value = max(0.0, float(getattr(firm, "inventory_units", 0.0) or 0.0)) * price
    capital_value = (
        max(0.0, float(getattr(firm, "capital_stock", 0.0) or 0.0))
        * max(0.0, float(getattr(CONFIG.firms, "capital_cost_per_unit", 0.0) or 0.0))
    )
    housing_value = 0.0
    if str(getattr(firm, "good_category", "") or "").lower() == "housing":
        housing_value = (
            max(0.0, float(getattr(firm, "max_rental_units", 0.0) or 0.0))
            * max(0.0, float(getattr(CONFIG.firms, "housing_unit_market_value", 0.0) or 0.0))
        )
    return cash + inventory_value + capital_value + housing_value - _firm_debt_remaining(firm)


def build_firm_financial_rows(economy):
    rows = []
    for firm in sorted(list(getattr(economy, "firms", []) or []), key=lambda f: int(getattr(f, "firm_id", 0) or 0)):
        cash = float(getattr(firm, "cash_balance", 0.0) or 0.0)
        debt = _firm_debt_remaining(firm)
        net_worth = _firm_net_worth_proxy(firm)
        wage_bill = sum(
            float((getattr(firm, "actual_wages", {}) or {}).get(employee_id, getattr(firm, "wage_offer", 0.0)) or 0.0)
            for employee_id in (getattr(firm, "employees", []) or [])
        )
        rows.append({
            "firm_id": int(getattr(firm, "firm_id", -1)),
            "sector": str(getattr(firm, "good_category", "unknown") or "unknown").lower(),
            "baseline": bool(getattr(firm, "is_baseline", False)),
            "employees": len(getattr(firm, "employees", []) or []),
            "wage_offer": float(getattr(firm, "wage_offer", 0.0) or 0.0),
            "avg_actual_wage": wage_bill / max(1, len(getattr(firm, "employees", []) or [])),
            "price": float(getattr(firm, "price", 0.0) or 0.0),
            "cash": cash,
            "debt": debt,
            "debt_payment": _firm_debt_payment(firm),
            "net_worth": net_worth,
            "last_revenue": float(getattr(firm, "last_revenue", 0.0) or 0.0),
            "last_profit": float(getattr(firm, "last_profit", 0.0) or 0.0),
            "profit_margin": float(getattr(firm, "smoothed_profit_margin", 0.0) or 0.0),
            "runway": float(getattr(firm, "cash_runway_ticks", 0.0) or 0.0),
            "inventory": float(getattr(firm, "inventory_units", 0.0) or 0.0),
            "inventory_value": max(0.0, float(getattr(firm, "inventory_units", 0.0) or 0.0)) * max(0.0, float(getattr(firm, "price", 0.0) or 0.0)),
            "survival": bool(getattr(firm, "survival_mode", False)),
            "burn": bool(getattr(firm, "burn_mode", False)),
            "negative_cash": cash < 0.0,
            "negative_profit": float(getattr(firm, "last_profit", 0.0) or 0.0) < 0.0,
            "negative_net_worth": net_worth < 0.0,
        })
    return rows


def build_labor_diagnostics(economy, metrics):
    firms = list(getattr(economy, "firms", []) or [])
    households = list(getattr(economy, "households", []) or [])
    labor_diag = dict(getattr(economy, "last_labor_diagnostics", {}) or {})
    firm_diag = dict(getattr(economy, "last_firm_distress_diagnostics", {}) or {})

    planned_hires = [max(0, int(getattr(firm, "planned_hires_count", 0) or 0)) for firm in firms]
    actual_hires = [max(0, int(getattr(firm, "last_tick_actual_hires", 0) or 0)) for firm in firms]
    planned_layoffs = [len(getattr(firm, "planned_layoffs_ids", []) or []) for firm in firms]
    wage_offers = [
        float(getattr(firm, "wage_offer", 0.0) or 0.0)
        for firm in firms
        if float(getattr(firm, "wage_offer", 0.0) or 0.0) > 0.0
    ]
    unemployed_reservations = [
        float(getattr(household, "reservation_wage", 0.0) or 0.0)
        for household in households
        if not bool(getattr(household, "is_employed", False)) and bool(getattr(household, "can_work", True))
    ]
    sell_through_values = [
        float(value)
        for value in (getattr(economy, "last_tick_sell_through_rate", {}) or {}).values()
    ]
    inventory_values = [
        max(0.0, float(getattr(firm, "inventory_units", 0.0) or 0.0))
        for firm in firms
    ]

    failed_matches_count = int(firm_diag.get("failed_hiring_roles_count", 0.0) or 0.0)
    reason_counts = Counter()
    wage_ineligible = int(labor_diag.get("labor_seekers_wage_ineligible", 0.0) or 0.0)
    not_searching = int(labor_diag.get("labor_unemployed_not_searching", 0.0) or 0.0)
    cannot_work = int(labor_diag.get("labor_cannot_work", 0.0) or 0.0)
    if wage_ineligible > 0:
        reason_counts["reservation_above_wage_offer"] += wage_ineligible
    if not_searching > 0:
        reason_counts["unemployed_not_searching"] += not_searching
    if cannot_work > 0:
        reason_counts["cannot_work"] += cannot_work
    if sum(planned_hires) <= 0 and float(metrics.get("unemployment_rate", 0.0) or 0.0) > 0.0:
        reason_counts["no_firms_planning_hires"] += int(float(metrics.get("unemployment_rate", 0.0) or 0.0) * len(households))
    if failed_matches_count > 0 and wage_ineligible <= 0:
        reason_counts["unfilled_planned_roles"] += failed_matches_count
    inventory_pressure = int(firm_diag.get("inventory_pressure_firm_count", 0.0) or 0.0)
    weak_demand = int(firm_diag.get("weak_demand_firm_count", 0.0) or 0.0)
    if inventory_pressure > 0:
        reason_counts["inventory_pressure"] += inventory_pressure
    if weak_demand > 0:
        reason_counts["weak_demand"] += weak_demand

    return {
        "tick": int(getattr(economy, "current_tick", 0)),
        "unemployment": float(metrics.get("unemployment_rate", 0.0) or 0.0),
        "active_firms": len(firms),
        "total_employees": sum(len(getattr(firm, "employees", []) or []) for firm in firms),
        "total_planned_hires": sum(planned_hires),
        "total_actual_hires": sum(actual_hires),
        "total_planned_layoffs": sum(planned_layoffs),
        "firms_planning_hires": sum(1 for value in planned_hires if value > 0),
        "firms_in_burn_mode": sum(1 for firm in firms if bool(getattr(firm, "burn_mode", False))),
        "firms_in_survival_mode": sum(1 for firm in firms if bool(getattr(firm, "survival_mode", False))),
        "median_wage_offer": _median(wage_offers),
        "median_reservation_wage_unemployed": _median(unemployed_reservations),
        "minimum_wage_floor": float(economy.government.get_minimum_wage()),
        "failed_matches_count": failed_matches_count,
        "top_failed_match_reason": reason_counts.most_common(1)[0][0] if reason_counts else "none",
        "avg_sell_through": sum(sell_through_values) / max(1, len(sell_through_values)),
        "avg_inventory": sum(inventory_values) / max(1, len(inventory_values)),
    }


def build_flow_diagnostics(economy):
    firms = list(getattr(economy, "firms", []) or [])
    households = list(getattr(economy, "households", []) or [])
    gov_benefit = float(economy.government.get_unemployment_benefit_level())

    wages = sum(
        max(0.0, float(getattr(household, "wage", 0.0) or 0.0))
        for household in households
        if bool(getattr(household, "is_employed", False))
    )
    benefits = sum(
        gov_benefit
        for household in households
        if not bool(getattr(household, "is_employed", False)) and bool(getattr(household, "can_work", True))
    )
    dividends = sum(max(0.0, float(getattr(household, "last_dividend_income", 0.0) or 0.0)) for household in households)
    income = wages + benefits + dividends

    spend_fraction = sum(
        max(0.0, min(1.0, 1.0 - float(getattr(household, "savings_rate_target", 0.2) or 0.0)))
        for household in households
    ) / max(1, len(households))
    planned_spending_proxy = sum(
        max(0.0, min(
            float(getattr(household, "cash_balance", 0.0) or 0.0),
            (
                (float(getattr(household, "wage", 0.0) or 0.0) if bool(getattr(household, "is_employed", False)) else gov_benefit)
                + max(0.0, float(getattr(household, "last_dividend_income", 0.0) or 0.0))
            ) * max(0.0, min(1.0, 1.0 - float(getattr(household, "savings_rate_target", 0.2) or 0.0)))
        ))
        for household in households
    )
    actual_spending = sum(float(value) for value in (getattr(economy, "last_tick_revenue", {}) or {}).values())
    income_to_planned_spending = income / max(planned_spending_proxy, 1.0)
    planned_to_actual_spending = planned_spending_proxy / max(actual_spending, 1.0)

    sector_inventory = {}
    sector_inventory_baseline = {}
    sector_inventory_private = {}
    sector_expected = {}
    sector_expected_baseline = {}
    sector_expected_private = {}
    sector_sold = {}
    sector_sold_baseline = {}
    sector_sold_private = {}
    sector_forecast_gap = {}
    sector_forecast_gap_baseline = {}
    sector_forecast_gap_private = {}
    for firm in firms:
        sector = str(getattr(firm, "good_category", "unknown") or "unknown").lower()
        is_baseline = bool(getattr(firm, "is_baseline", False))
        inventory = max(0.0, float(getattr(firm, "inventory_units", 0.0) or 0.0))
        expected = max(0.0, float(getattr(firm, "expected_sales_units", 0.0) or 0.0))
        sold = max(0.0, float(getattr(firm, "last_units_sold", 0.0) or 0.0))
        sector_inventory[sector] = sector_inventory.get(sector, 0.0) + inventory
        sector_expected[sector] = sector_expected.get(sector, 0.0) + expected
        sector_sold[sector] = sector_sold.get(sector, 0.0) + sold
        inventory_bucket = sector_inventory_baseline if is_baseline else sector_inventory_private
        expected_bucket = sector_expected_baseline if is_baseline else sector_expected_private
        sold_bucket = sector_sold_baseline if is_baseline else sector_sold_private
        inventory_bucket[sector] = inventory_bucket.get(sector, 0.0) + inventory
        expected_bucket[sector] = expected_bucket.get(sector, 0.0) + expected
        sold_bucket[sector] = sold_bucket.get(sector, 0.0) + sold

    for sector, expected in sector_expected.items():
        sold = sector_sold.get(sector, 0.0)
        sector_forecast_gap[sector] = expected - sold
    for sector, expected in sector_expected_baseline.items():
        sector_forecast_gap_baseline[sector] = expected - sector_sold_baseline.get(sector, 0.0)
    for sector, expected in sector_expected_private.items():
        sector_forecast_gap_private[sector] = expected - sector_sold_private.get(sector, 0.0)

    firm_forecast_gaps = [
        {
            "firm_id": int(getattr(firm, "firm_id", -1)),
            "sector": str(getattr(firm, "good_category", "unknown") or "unknown").lower(),
            "expected": max(0.0, float(getattr(firm, "expected_sales_units", 0.0) or 0.0)),
            "sold": max(0.0, float(getattr(firm, "last_units_sold", 0.0) or 0.0)),
            "gap": max(0.0, float(getattr(firm, "expected_sales_units", 0.0) or 0.0)) - max(0.0, float(getattr(firm, "last_units_sold", 0.0) or 0.0)),
            "baseline": bool(getattr(firm, "is_baseline", False)),
        }
        for firm in firms
    ]
    worst_forecast_gaps = sorted(firm_forecast_gaps, key=lambda item: item["gap"], reverse=True)[:3]
    return {
        "wages": wages,
        "benefits": benefits,
        "dividends": dividends,
        "income": income,
        "planned_spending_proxy": planned_spending_proxy,
        "actual_spending": actual_spending,
        "income_to_planned_spending": income_to_planned_spending,
        "planned_to_actual_spending": planned_to_actual_spending,
        "avg_spend_fraction": spend_fraction,
        "sector_inventory": sector_inventory,
        "sector_inventory_baseline": sector_inventory_baseline,
        "sector_inventory_private": sector_inventory_private,
        "sector_expected": sector_expected,
        "sector_expected_baseline": sector_expected_baseline,
        "sector_expected_private": sector_expected_private,
        "sector_sold": sector_sold,
        "sector_sold_baseline": sector_sold_baseline,
        "sector_sold_private": sector_sold_private,
        "sector_forecast_gap": sector_forecast_gap,
        "sector_forecast_gap_baseline": sector_forecast_gap_baseline,
        "sector_forecast_gap_private": sector_forecast_gap_private,
        "worst_forecast_gaps": worst_forecast_gaps,
    }


def _format_sector_map(values):
    ordered = sorted(values.items(), key=lambda item: item[0])
    return ",".join(f"{key}:{value:.1f}" for key, value in ordered) if ordered else "none"


def build_category_spending_gap_diagnostics(economy):
    audit = getattr(economy, "_last_tick_audit", {}) or {}
    plans = audit.get("household_consumption_plans", {}) or {}
    purchases = audit.get("per_household_purchases", {}) or {}
    firms = list(getattr(economy, "firms", []) or [])
    firm_by_id = {int(getattr(firm, "firm_id", -1)): firm for firm in firms}
    good_to_category = {
        str(getattr(firm, "good_name", "")): str(getattr(firm, "good_category", "unknown") or "unknown").lower()
        for firm in firms
    }
    good_to_price = {
        str(getattr(firm, "good_name", "")): max(0.0, float(getattr(firm, "price", 0.0) or 0.0))
        for firm in firms
    }

    planned_by_category = {}
    cleared_by_category = {}

    for plan in plans.values():
        for target, quantity in (plan.get("planned_purchases", {}) or {}).items():
            qty = max(0.0, float(quantity or 0.0))
            if qty <= 0.0:
                continue
            if isinstance(target, (int, np.integer)):
                firm = firm_by_id.get(int(target))
                if firm is None:
                    category = "unknown"
                    price = 0.0
                else:
                    category = str(getattr(firm, "good_category", "unknown") or "unknown").lower()
                    price = max(0.0, float(getattr(firm, "price", 0.0) or 0.0))
            else:
                good = str(target)
                category = good_to_category.get(good, "unknown")
                price = good_to_price.get(good, 0.0)
            planned_by_category[category] = planned_by_category.get(category, 0.0) + qty * price

    for household_purchases in purchases.values():
        for good, value in (household_purchases or {}).items():
            try:
                quantity, price = value
            except (TypeError, ValueError):
                continue
            category = good_to_category.get(str(good), "unknown")
            cleared_by_category[category] = (
                cleared_by_category.get(category, 0.0)
                + max(0.0, float(quantity or 0.0)) * max(0.0, float(price or 0.0))
            )

    categories = sorted(set(planned_by_category) | set(cleared_by_category))
    return [
        {
            "category": category,
            "planned": planned_by_category.get(category, 0.0),
            "cleared": cleared_by_category.get(category, 0.0),
            "gap": planned_by_category.get(category, 0.0) - cleared_by_category.get(category, 0.0),
        }
        for category in categories
    ]


def _firm_hire_blocker(firm, demand_workers, target_delta):
    if int(getattr(firm, "planned_hires_count", 0) or 0) > 0:
        return "not_blocked"
    if bool(getattr(firm, "survival_mode", False)) or bool(getattr(firm, "burn_mode", False)):
        return "cash_survival_or_burn"
    if float(getattr(firm, "cash_runway_ticks", 0.0) or 0.0) < CONFIG.firms.survival_mode_runway_weeks * 2.0:
        return "cash_runway"
    if float(getattr(firm, "smoothed_profit_margin", 0.0) or 0.0) < 0.0:
        return "profit_margin"
    sell_through = (
        max(0.0, float(getattr(firm, "last_units_sold", 0.0) or 0.0))
        / max(1.0, float(getattr(firm, "last_units_produced", 0.0) or 0.0))
    )
    if demand_workers <= len(getattr(firm, "employees", []) or []):
        return "demand_target_not_above_current"
    if sell_through < 0.65:
        return "demand_sell_through"
    return "unknown_or_hire_limit"


def build_firm_hire_gate_diagnostics(economy):
    rows = []
    for firm in sorted(getattr(economy, "firms", []) or [], key=lambda item: int(getattr(item, "firm_id", -1))):
        current_workers = len(getattr(firm, "employees", []) or [])
        expected_sales = max(0.0, float(getattr(firm, "expected_sales_units", 0.0) or 0.0))
        capacity = max(0.0, float(getattr(firm, "production_capacity_units", 0.0) or 0.0))
        try:
            demand_workers = int(firm._workers_for_sales(min(max(expected_sales, CONFIG.firms.min_expected_sales), capacity)))
        except Exception:
            demand_workers = 0
        target_delta = demand_workers - current_workers
        rows.append({
            "firm_id": int(getattr(firm, "firm_id", -1)),
            "sector": str(getattr(firm, "good_category", "unknown") or "unknown").lower(),
            "baseline": bool(getattr(firm, "is_baseline", False)),
            "expected_sales_units": expected_sales,
            "last_tick_unmet_units": float(getattr(firm, "last_tick_raw_lost_sales_units", 0.0) or 0.0),
            "observed_demand_units": float(getattr(firm, "last_tick_observed_demand_units", 0.0) or 0.0),
            "cash_runway_ticks": float(getattr(firm, "cash_runway_ticks", 0.0) or 0.0),
            "survival_mode": bool(getattr(firm, "survival_mode", False)),
            "burn_mode": bool(getattr(firm, "burn_mode", False)),
            "smoothed_profit_margin": float(getattr(firm, "smoothed_profit_margin", 0.0) or 0.0),
            "demand_workers": demand_workers,
            "current_workers": current_workers,
            "target_delta": target_delta,
            "planned_hires": int(getattr(firm, "planned_hires_count", 0) or 0),
            "blocked_by": _firm_hire_blocker(firm, demand_workers, target_delta),
        })
    return rows


async def main():
    args = parse_args()

    # Configure
    CONFIG.llm.enable_llm_government = True
    CONFIG.llm.government_decision_interval = args.interval
    CONFIG.llm.government_start_tick = args.first_decision_tick
    CONFIG.llm.government_start_after_warmup_ticks = max(0, args.first_decision_tick - args.warmup_ticks)
    CONFIG.llm.government_model = args.model
    CONFIG.llm.provider = args.provider
    if args.provider == "lmstudio" and args.base_url:
        CONFIG.llm.lmstudio_base_url = args.base_url
    if args.provider == "ollama" and args.base_url:
        CONFIG.llm.ollama_base_url = args.base_url
    if args.provider == "openrouter":
        CONFIG.llm.openrouter_model = args.model
    if args.provider == "groq":
        CONFIG.llm.groq_model = args.model
    CONFIG.llm.government_philosophy = args.philosophy
    CONFIG.llm.government_temperature = args.temperature
    if args.top_p is not None:
        CONFIG.llm.government_top_p = args.top_p
    if args.max_tokens is not None:
        CONFIG.llm.government_max_tokens = args.max_tokens
    CONFIG.llm.no_think = args.no_think
    CONFIG.time.warmup_ticks = max(0, args.warmup_ticks)
    CONFIG.random_seed = args.seed
    random.seed(CONFIG.random_seed)
    np.random.seed(CONFIG.random_seed)

    print("=" * 100)
    print(f"  EcoSim LLM Government Runner")
    print(f"  Households: {args.households} | Ticks: {args.ticks} | Decisions every {args.interval} ticks")
    print(f"  Model: {args.model} | Provider: {args.provider} | Philosophy: {args.philosophy} | Temperature: {args.temperature} | top_p: {CONFIG.llm.government_top_p}")
    print(f"  Warmup ticks: {CONFIG.time.warmup_ticks} | First LLM decision tick: {args.first_decision_tick}")
    print(f"  Seed: {CONFIG.random_seed} | max_tokens: {CONFIG.llm.government_max_tokens}")
    print("=" * 100)

    # Create economy
    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households,
        num_firms_per_category=2,
    )
    if args.disable_bailouts:
        economy.government.bailout_policy = "off"
        economy.government.bailout_target = "none"
        economy.government.bailout_budget = 0
        economy.government.sync_bailout_cycle_budget()
    if args.category_gap_diagnostics:
        economy.audit_log_enabled = True
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} firms)")

    # Connect to provider
    print(f"Connecting to {args.provider}...", end=" ", flush=True)
    if args.provider == "lmstudio":
        provider = LMStudioProvider(
            base_url=CONFIG.llm.lmstudio_base_url,
            model=args.model,
            timeout=args.timeout,
            max_tokens=CONFIG.llm.government_max_tokens,
        )
    elif args.provider == "openrouter":
        provider = OpenRouterProvider(
            model=args.model,
            timeout=args.timeout,
            max_tokens=CONFIG.llm.government_max_tokens,
        )
    elif args.provider == "groq":
        provider = GroqProvider(
            model=args.model,
            timeout=args.timeout,
            max_tokens=CONFIG.llm.government_max_tokens,
        )
    else:
        provider = OllamaProvider(base_url=CONFIG.llm.ollama_base_url, model=args.model, timeout=args.timeout)

    if not await provider.health_check():
        if args.provider == "lmstudio":
            print(f"FATAL: OpenAI-compatible local server not reachable on {CONFIG.llm.lmstudio_base_url}")
            print("Make sure LM Studio or llama.cpp server is running and exposes /v1/models")
        elif args.provider == "openrouter":
            print("FATAL: OpenRouter not reachable or OPENROUTER_API_KEY is not set")
        elif args.provider == "groq":
            print("FATAL: Groq not reachable or GROQ_API_KEY is not set")
        else:
            print(f"FATAL: Ollama not reachable or model '{args.model}' not found")
            print(f"  ollama pull {args.model}")
        return
    print(f"connected ({provider.name})")

    advisor = LLMGovernmentAdvisor(provider, CONFIG.llm)

    # Optional warmup probe
    if not args.no_probe:
        print("\nWarming up model (first call loads weights into VRAM)...", flush=True)
        t0 = time.perf_counter()
        try:
            await provider.complete(
                system='Respond with JSON: {"ready": true}',
                user="warmup",
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            print(f"  Model ready ({(time.perf_counter() - t0):.1f}s)")
        except Exception as e:
            print(f"  Probe failed ({e}) - continuing, first decision may be slow")

    # Simulation loop
    first_decision_tick = max(
        CONFIG.llm.government_start_tick,
        CONFIG.time.warmup_ticks + CONFIG.llm.government_start_after_warmup_ticks,
    )
    decision_ticks = [
        tick_n
        for tick_n in range(first_decision_tick, args.ticks + 1)
        if (tick_n - first_decision_tick) % args.interval == 0
    ]
    num_decisions = len(decision_ticks)
    est_time = num_decisions * 90  # rough estimate: ~90s per decision with thinking model
    print(f"\nStarting simulation - ~{num_decisions} LLM decisions expected")
    print(f"Decision ticks: first={first_decision_tick}, interval={args.interval}")
    print(f"Estimated time: ~{est_time // 60}m {est_time % 60}s (depends on model speed)\n")

    print("-" * 100)
    print(f" {'Tick':>4} | {'Unemp':>6} | {'MnWage':>7} | {'MdnCash':>9} | {'Hlth':>5} | {'Happy':>5} | "
          f"{'Morale':>6} | {'Firms':>5} | {'GovCash':>11} | {'GDP':>8} | {'LLM':>6}")
    print("-" * 100)
    if args.labor_diagnostics:
        print("\nLABOR DIAGNOSTICS")
        print(
            "tick | unemployment | active_firms | total_employees | total_planned_hires | "
            "total_actual_hires | total_planned_layoffs | firms_planning_hires | "
            "firms_in_burn_mode | firms_in_survival_mode | median_wage_offer | "
            "median_reservation_wage_unemployed | minimum_wage_floor | failed_matches_count | "
            "top_failed_match_reason | avg_sell_through | avg_inventory"
        )
    if args.flow_diagnostics:
        print("\nFLOW DIAGNOSTICS")
        print(
            "tick | wages | benefits | dividends | income | planned_spending_proxy | actual_spending | "
            "income/planned | planned/actual | avg_spend_fraction | sector_inventory | "
            "baseline_inventory | private_inventory | sector_expected_sales | sector_units_sold | "
            "sector_forecast_gap | baseline_forecast_gap | private_forecast_gap | worst_firm_forecast_gaps"
        )
    if args.category_gap_diagnostics:
        print("\nCATEGORY SPENDING GAP DIAGNOSTICS")
        print("tick | category | aggregate_planned_budget | aggregate_cleared_spending | gap")

    sim_start = time.perf_counter()
    summary_rows = []
    decision_records = []

    for tick in range(args.ticks):
        # Economy tick
        economy.step()

        # Metrics + history
        metrics = economy.get_economic_metrics()
        economy.append_metrics_snapshot(metrics, tick=economy.current_tick)
        summary_rows.append(dict(metrics))
        if args.labor_diagnostics:
            diag = build_labor_diagnostics(economy, metrics)
            print(
                "LABOR | "
                f"{diag['tick']} | "
                f"{diag['unemployment'] * 100.0:.1f}% | "
                f"{diag['active_firms']} | "
                f"{diag['total_employees']} | "
                f"{diag['total_planned_hires']} | "
                f"{diag['total_actual_hires']} | "
                f"{diag['total_planned_layoffs']} | "
                f"{diag['firms_planning_hires']} | "
                f"{diag['firms_in_burn_mode']} | "
                f"{diag['firms_in_survival_mode']} | "
                f"{diag['median_wage_offer']:.1f} | "
                f"{diag['median_reservation_wage_unemployed']:.1f} | "
                f"{diag['minimum_wage_floor']:.1f} | "
                f"{diag['failed_matches_count']} | "
                f"{diag['top_failed_match_reason']} | "
                f"{diag['avg_sell_through']:.3f} | "
                f"{diag['avg_inventory']:.1f}",
                flush=True,
            )
        if args.flow_diagnostics:
            flow = build_flow_diagnostics(economy)
            worst = ";".join(
                f"{item['firm_id']}:{item['sector']}:{'base' if item['baseline'] else 'priv'} exp={item['expected']:.1f} sold={item['sold']:.1f} gap={item['gap']:.1f}"
                for item in flow["worst_forecast_gaps"]
            ) or "none"
            print(
                "FLOW | "
                f"{economy.current_tick} | "
                f"${flow['wages']:,.0f} | "
                f"${flow['benefits']:,.0f} | "
                f"${flow['dividends']:,.0f} | "
                f"${flow['income']:,.0f} | "
                f"${flow['planned_spending_proxy']:,.0f} | "
                f"${flow['actual_spending']:,.0f} | "
                f"{flow['income_to_planned_spending']:.2f} | "
                f"{flow['planned_to_actual_spending']:.2f} | "
                f"{flow['avg_spend_fraction']:.2f} | "
                f"{_format_sector_map(flow['sector_inventory'])} | "
                f"{_format_sector_map(flow['sector_inventory_baseline'])} | "
                f"{_format_sector_map(flow['sector_inventory_private'])} | "
                f"{_format_sector_map(flow['sector_expected'])} | "
                f"{_format_sector_map(flow['sector_sold'])} | "
                f"{_format_sector_map(flow['sector_forecast_gap'])} | "
                f"{_format_sector_map(flow['sector_forecast_gap_baseline'])} | "
                f"{_format_sector_map(flow['sector_forecast_gap_private'])} | "
                f"{worst}",
                flush=True,
            )
        if args.category_gap_diagnostics and 12 <= economy.current_tick <= 15:
            for row in build_category_spending_gap_diagnostics(economy):
                print(
                    "CATGAP | "
                    f"{economy.current_tick} | "
                    f"{row['category']} | "
                    f"${row['planned']:,.0f} | "
                    f"${row['cleared']:,.0f} | "
                    f"${row['gap']:,.0f}",
                    flush=True,
                )

        # LLM decision
        llm_label = ""
        if economy.current_tick in decision_ticks:
            print(f"\n  ... LLM thinking (tick {economy.current_tick}) ...", flush=True)
            t0 = time.perf_counter()
            result = await advisor.decide(economy)
            if args.disable_bailouts:
                bailout_keys = {"bailout_policy", "bailout_target", "bailout_budget"}
                applied_bailout = {
                    key: value
                    for key, value in dict(result.get("applied_changes", result.get("decisions", {})) or {}).items()
                    if key in bailout_keys
                }
                if applied_bailout:
                    economy.government.bailout_policy = "off"
                    economy.government.bailout_target = "none"
                    economy.government.bailout_budget = 0
                    economy.government.sync_bailout_cycle_budget()
                    result.setdefault("runtime_overrides", {})["bailouts_disabled"] = applied_bailout
            economy.record_llm_government_decision(result)
            elapsed_s = time.perf_counter() - t0
            llm_label = f"{elapsed_s:.0f}s"
            summary_metrics = economy.get_economic_metrics()
            raw_changes = result.get("raw_changes", {})
            accepted_changes = result.get("accepted_llm_changes", result.get("decisions", {}))
            mechanical_corrections = result.get("mechanical_corrections", {})
            applied_changes = result.get("applied_changes", result.get("decisions", {}))
            rejected_changes = result.get("rejected_changes", [])
            decision_records.append({
                "tick": economy.current_tick,
                "elapsed_seconds": elapsed_s,
                "parse_ok": bool(result.get("parse_ok", True)),
                "fiscal_mode": result.get("fiscal_mode", "NORMAL"),
                "llm_fiscal_mode": result.get("llm_fiscal_mode", result.get("fiscal_mode", "NORMAL")),
                "computed_fiscal_mode": result.get("computed_fiscal_mode", "NORMAL"),
                "primary_goal": result.get("primary_goal", "hold"),
                "raw_changes": dict(raw_changes or {}),
                "accepted_llm_changes": dict(accepted_changes or {}),
                "mechanical_corrections": dict(mechanical_corrections or {}),
                "applied_changes": dict(applied_changes or {}),
                "accepted_changes": dict(accepted_changes or {}),
                "rejected_changes": list(rejected_changes or []),
                "reasoning": result.get("reasoning", ""),
                "evidence": list(result.get("evidence", []) or []),
                "evidence_audit": list(result.get("evidence_audit", []) or []),
                "current_policy_before": dict(result.get("current_policy_before", {}) or {}),
                "current_policy_after": dict(result.get("current_policy_after", {}) or {}),
                "data_quality_summary": dict(result.get("data_quality_summary", {}) or {}),
                "gov_cash": float(summary_metrics.get("government_cash", 0.0) or 0.0),
                "gdp": float(summary_metrics.get("gdp_this_tick", 0.0) or 0.0),
                "unemployment_rate": float(summary_metrics.get("unemployment_rate", 0.0) or 0.0),
                "mean_health": float(summary_metrics.get("mean_health", 0.0) or 0.0),
                "mean_happiness": float(summary_metrics.get("mean_happiness", 0.0) or 0.0),
                "subsidy_requested": float(summary_metrics.get("gov_subsidy_requested_this_tick", 0.0) or 0.0),
                "subsidy_paid": float(summary_metrics.get("gov_subsidy_spend_this_tick", 0.0) or 0.0),
                "subsidy_denied": float(summary_metrics.get("gov_subsidy_denied_by_cap_this_tick", 0.0) or 0.0),
                "public_works_requested_startup": float(summary_metrics.get("gov_public_works_requested_startup_this_tick", 0.0) or 0.0),
                "public_works_denied_by_budget": float(summary_metrics.get("gov_public_works_denied_by_budget_this_tick", 0.0) or 0.0),
                "gov_bailout_spend_this_tick": float(summary_metrics.get("gov_bailout_spend_this_tick", 0.0) or 0.0),
                "bailout_budget_remaining": float(summary_metrics.get("bailout_budget_remaining", 0.0) or 0.0),
                "bailout_cycle_disbursed": float(summary_metrics.get("bailout_cycle_disbursed", 0.0) or 0.0),
                "last_cycle_bailout_disbursed": float(summary_metrics.get("last_cycle_bailout_disbursed", 0.0) or 0.0),
                "last_cycle_bailout_firms_assisted": float(summary_metrics.get("last_cycle_bailout_firms_assisted", 0.0) or 0.0),
                "bailout_eligible_firms_by_sector": dict(summary_metrics.get("bailout_eligible_firms_by_sector", {}) or {}),
                "bailout_denied_firms_by_reason": dict(summary_metrics.get("bailout_denied_firms_by_reason", {}) or {}),
                "bailout_received_by_firm_id": dict(summary_metrics.get("bailout_received_by_firm_id", {}) or {}),
                "runtime_overrides": dict(result.get("runtime_overrides", {}) or {}),
            })

            if result["decisions"]:
                print(f"  +-- LLM DECISION (tick {economy.current_tick}, {elapsed_s:.1f}s) --")
                for lever, value in result["decisions"].items():
                    before = result['current_policy_before'].get(lever, '?')
                    print(f"  |  {lever}: {before} -> {value}")
                print("  |")
                print(f"  |  \"{result['reasoning']}\"")
                dq = result.get("data_quality_summary", {})
                print(f"  |  [data: {dq.get('reported', 0)} reported, {dq.get('unavailable', 0)} unavailable]")
                print(f"  +{'-' * 70}")
            else:
                reason = result['reasoning'][:120]
                print(f"  -- NO CHANGES ({elapsed_s:.1f}s): {reason}")
            print(
                "  DECISION SUMMARY | "
                f"tick={economy.current_tick} | "
                f"mode={result.get('fiscal_mode', 'NORMAL')} | computed_mode={result.get('computed_fiscal_mode', 'NORMAL')} | goal={result.get('primary_goal', 'hold')} | "
                f"raw={raw_changes} | accepted_llm={accepted_changes} | mechanical={mechanical_corrections} | applied={applied_changes} | rejected={rejected_changes} | "
                f"gov_cash=${summary_metrics.get('government_cash', 0.0):,.0f} | "
                f"gdp=${summary_metrics.get('gdp_this_tick', 0.0):,.0f} | "
                f"unemp={summary_metrics.get('unemployment_rate', 0.0) * 100.0:.1f}% | "
                f"subsidy_requested=${summary_metrics.get('gov_subsidy_requested_this_tick', 0.0):,.0f} | "
                f"subsidy_paid=${summary_metrics.get('gov_subsidy_spend_this_tick', 0.0):,.0f} | "
                f"subsidy_denied=${summary_metrics.get('gov_subsidy_denied_by_cap_this_tick', 0.0):,.0f} | "
                f"public_works_requested_startup=${summary_metrics.get('gov_public_works_requested_startup_this_tick', 0.0):,.0f} | "
                f"public_works_denied_by_budget=${summary_metrics.get('gov_public_works_denied_by_budget_this_tick', 0.0):,.0f} | "
                f"bailout_spend=${summary_metrics.get('gov_bailout_spend_this_tick', 0.0):,.0f} | "
                f"bailout_remaining=${summary_metrics.get('bailout_budget_remaining', 0.0):,.0f} | "
                f"bailout_denials={summary_metrics.get('bailout_denied_firms_by_reason', {})}",
                flush=True,
            )
            print()

        # Metrics row
        unemp = metrics.get("unemployment_rate", 0) * 100
        mean_wage = metrics.get("mean_wage", 0)
        median_cash = metrics.get("median_household_cash", 0)
        health = metrics.get("mean_health", 0)
        happy = metrics.get("mean_happiness", 0)
        morale = metrics.get("mean_morale", 0)
        firms = metrics.get("total_firms", 0)
        gov_cash = metrics.get("government_cash", 0)
        gdp = metrics.get("gdp_this_tick", 0)

        print(
            f" {economy.current_tick:>4} | {unemp:>5.1f}% | {mean_wage:>7.1f} | "
            f"${median_cash:>8,.0f} | {health:>5.3f} | {happy:>5.3f} | "
            f"{morale:>6.3f} | {firms:>5} | ${gov_cash:>10,.0f} | ${gdp:>7,.0f} | {llm_label:>6}",
            flush=True,
        )

    total_time = time.perf_counter() - sim_start

    # Decision history
    print("\n" + "=" * 100)
    print("DECISION HISTORY")
    print("=" * 100)
    total_decisions = len(advisor.decision_history)
    decisions_with_accepts = 0
    raw_change_count = 0
    rejected_change_count = 0
    fiscal_rejection_count = 0
    invalid_enum_rejection_count = 0
    for d in advisor.decision_history:
        tick_n = d["tick"]
        raw_changes = d.get("raw_changes", {})
        decisions = d["decisions"]
        rejected = d.get("rejected_changes", [])
        if decisions:
            decisions_with_accepts += 1
        raw_change_count += len(raw_changes)
        rejected_change_count += len(rejected)
        for r in rejected:
            reason = str(r.get("reason", ""))
            if any(key in reason for key in ("fiscal_stress", "insufficient_cash", "public_works", "tax_cut_during_fiscal_stress", "spending_increase")):
                fiscal_rejection_count += 1
            if reason == "invalid_enum_value":
                invalid_enum_rejection_count += 1
        reasoning = d["reasoning"]
        elapsed = d["elapsed_ms"]
        parse_ok = d["parse_ok"]
        mode = d.get("fiscal_mode", "NORMAL")
        goal = d.get("primary_goal", "hold")
        if decisions:
            changes = ", ".join(f"{k}: {v}" for k, v in decisions.items())
            print(f"  Tick {tick_n:>3} ({elapsed / 1000:.0f}s, {mode}/{goal}): {changes}")
            print(f"           \"{reasoning}\"")
        else:
            status = "hold" if parse_ok else "PARSE FAIL"
            print(f"  Tick {tick_n:>3} ({elapsed / 1000:.0f}s, {mode}/{goal}): [{status}] {reasoning}")
        if rejected:
            rejected_text = "; ".join(f"{r.get('lever')}={r.get('value')} ({r.get('reason')})" for r in rejected[:5])
            print(f"           rejected: {rejected_text}")

    print("\nDECISION QUALITY RATES")
    accepted_decision_rate = decisions_with_accepts / max(1, total_decisions)
    rejection_rate = rejected_change_count / max(1, raw_change_count)
    fiscal_rejection_rate = fiscal_rejection_count / max(1, raw_change_count)
    invalid_enum_rate = invalid_enum_rejection_count / max(1, raw_change_count)
    evidence_audit_counts = Counter(
        str(item.get("status", "unknown"))
        for decision in advisor.decision_history
        for item in (decision.get("evidence_audit", []) or [])
    )
    evidence_audit_total = sum(evidence_audit_counts.values())
    evidence_audit_matched = evidence_audit_counts.get("matched_metric", 0) + evidence_audit_counts.get("matched_policy", 0)
    evidence_audit_match_rate = evidence_audit_matched / max(1, evidence_audit_total)
    print(f"  accepted_decision_rate: {accepted_decision_rate:.1%} ({decisions_with_accepts}/{total_decisions})")
    print(f"  rejection_rate:         {rejection_rate:.1%} ({rejected_change_count}/{raw_change_count})")
    print(f"  fiscal_rejection_rate:  {fiscal_rejection_rate:.1%} ({fiscal_rejection_count}/{raw_change_count})")
    print(f"  invalid_enum_rate:      {invalid_enum_rate:.1%} ({invalid_enum_rejection_count}/{raw_change_count})")
    print(f"  evidence_match_rate:    {evidence_audit_match_rate:.1%} ({evidence_audit_matched}/{evidence_audit_total})")
    if evidence_audit_counts:
        print(f"  evidence_audit_counts:  {dict(evidence_audit_counts)}")

    def avg_metric(key: str) -> float:
        values = [float(row.get(key, 0.0) or 0.0) for row in summary_rows]
        return sum(values) / max(1, len(values))

    def min_metric(key: str) -> float:
        values = [float(row.get(key, 0.0) or 0.0) for row in summary_rows]
        return min(values) if values else 0.0

    final_metrics = summary_rows[-1] if summary_rows else {}
    print("\nECONOMIC SUMMARY")
    print(f"  final_gov_cash:     ${float(final_metrics.get('government_cash', 0.0)):,.0f}")
    print(f"  min_gov_cash:       ${min_metric('government_cash'):,.0f}")
    print(f"  avg_gdp:            ${avg_metric('gdp_this_tick'):,.0f}")
    print(f"  final_gdp:          ${float(final_metrics.get('gdp_this_tick', 0.0)):,.0f}")
    print(f"  avg_unemployment:   {avg_metric('unemployment_rate') * 100.0:.1f}%")
    print(f"  final_unemployment: {float(final_metrics.get('unemployment_rate', 0.0)) * 100.0:.1f}%")
    print(f"  avg_health:         {avg_metric('mean_health'):.3f}")
    print(f"  final_health:       {float(final_metrics.get('mean_health', 0.0)):.3f}")
    print(f"  avg_happiness:      {avg_metric('mean_happiness'):.3f}")
    print(f"  final_happiness:    {float(final_metrics.get('mean_happiness', 0.0)):.3f}")
    private_firms = [
        firm for firm in economy.firms
        if not bool(getattr(firm, "is_baseline", False))
        and (getattr(firm, "good_category", "") or "").lower() in {"food", "services"}
    ]
    max_expected_to_observed = max(
        (
            float(getattr(firm, "expected_sales_units", 0.0) or 0.0)
            / max(1.0, float(getattr(firm, "last_tick_observed_demand_units", 0.0) or 0.0))
            for firm in private_firms
        ),
        default=0.0,
    )
    max_expected_sales = max(
        (float(getattr(firm, "expected_sales_units", 0.0) or 0.0) for firm in private_firms),
        default=0.0,
    )
    reservation_blocked_vacancies = sum(
        int(getattr(firm, "last_tick_unfilled_vacancies", 0) or 0)
        for firm in private_firms
        if getattr(firm, "last_tick_failed_match_reason", "") == "reservation_above_wage_offer"
    )
    rejected_reservations = [
        float(getattr(firm, "last_tick_median_rejected_reservation_wage", 0.0) or 0.0)
        for firm in private_firms
        if float(getattr(firm, "last_tick_median_rejected_reservation_wage", 0.0) or 0.0) > 0.0
    ]
    median_rejected_reservation = float(np.median(rejected_reservations)) if rejected_reservations else 0.0
    max_hire_limit_effective = max(
        (
            int(getattr(firm, "decision_diagnostics", {}).get("hire_limit_effective", 0) or 0)
            for firm in private_firms
        ),
        default=0,
    )
    adaptive_hiring_firms = sum(
        1
        for firm in private_firms
        if bool(getattr(firm, "decision_diagnostics", {}).get("adaptive_hiring_allowed", False))
    )
    reservation_gap_wage_raises = sum(
        1
        for firm in private_firms
        if getattr(firm, "decision_diagnostics", {}).get("wage_raise_reason") == "reservation_blocked_vacancies"
    )
    unemployed_reservations = [
        float(getattr(household, "reservation_wage", 0.0) or 0.0)
        for household in economy.households
        if (not bool(getattr(household, "is_employed", False))) and bool(getattr(household, "can_work", False))
    ]
    median_unemployed_reservation = (
        float(np.median(unemployed_reservations)) if unemployed_reservations else 0.0
    )
    working_capital_candidates = sum(
        bool(getattr(firm, "last_working_capital_candidate", False))
        for firm in private_firms
    )
    working_capital_denial_reasons = Counter(
        getattr(firm, "last_working_capital_denial_reason", "") or "candidate"
        for firm in private_firms
    )
    working_capital_issued_firms = sum(
        float(getattr(firm, "working_capital_loan_received_last_tick", 0.0) or 0.0) > 0.0
        for firm in private_firms
    )
    hiring_block_reasons = Counter(
        getattr(firm, "last_hiring_block_reason", "") or "planned_hires_positive"
        for firm in private_firms
    )
    private_cash_runways = [
        float(getattr(firm, "cash_runway_ticks", 0.0) or 0.0)
        for firm in private_firms
    ]
    avg_private_cash_runway = (
        sum(private_cash_runways) / len(private_cash_runways)
        if private_cash_runways
        else 0.0
    )
    print(f"  max_expected_to_observed:       {max_expected_to_observed:.2f}")
    print(f"  max_expected_sales_private:     {max_expected_sales:,.1f}")
    print(f"  max_hire_limit_effective:       {max_hire_limit_effective}")
    print(f"  adaptive_hiring_firms:          {adaptive_hiring_firms}")
    print(f"  reservation_blocked_vacancies:  {reservation_blocked_vacancies}")
    print(f"  reservation_gap_wage_raises:    {reservation_gap_wage_raises}")
    print(f"  median_rejected_reservation:    {median_rejected_reservation:.1f}")
    print(f"  median_unemployed_reservation:  {median_unemployed_reservation:.1f}")
    wage_summary = build_wage_reservation_summary(economy)
    print("\nWAGE & RESERVATION DIAGNOSTICS")
    print("  distribution format: count | mean | p10/p25/median/p75/p90 | min/max")
    for label, key in (
        ("employed actual wages", "employed_wages"),
        ("all firm wage offers", "all_firm_offers"),
        ("private firm wage offers", "private_firm_offers"),
        ("active hiring private offers", "active_private_firm_offers"),
        ("baseline firm wage offers", "baseline_firm_offers"),
        ("unemployed stored reservation wages", "unemployed_reservations"),
        ("unemployed tick-match reservations", "unemployed_tick_reservations"),
        ("unemployed expected wages", "unemployed_expected_wages"),
        ("cannot-work reservation wages", "cannot_work_reservations"),
    ):
        dist = wage_summary[key]
        print(
            f"  {label}: "
            f"{dist['count']} | {dist['mean']:.1f} | "
            f"{dist['p10']:.1f}/{dist['p25']:.1f}/{dist['median']:.1f}/{dist['p75']:.1f}/{dist['p90']:.1f} | "
            f"{dist['min']:.1f}/{dist['max']:.1f}"
        )
    print(f"  active private firms hiring:    {wage_summary['active_private_firms_hiring']}")
    print(f"  active/private offer anchor:    {wage_summary['offer_anchor']:.1f}")
    print(f"  minimum wage floor:             {wage_summary['minimum_wage_floor']:.1f}")
    print(f"  unemployment benefit:           {wage_summary['unemployment_benefit']:.1f}")
    print(f"  benefit acceptance floor:       {wage_summary['benefit_floor']:.1f}")
    print(
        "  stored reservation <= offer anchor:     "
        f"{wage_summary['share_unemployed_reservation_lte_offer_anchor'] * 100.0:.1f}%"
    )
    print(
        "  stored reservation <= min wage:         "
        f"{wage_summary['share_unemployed_reservation_lte_min_wage'] * 100.0:.1f}%"
    )
    print(
        "  stored reservation <= benefit floor:    "
        f"{wage_summary['share_unemployed_reservation_lte_benefit_floor'] * 100.0:.1f}%"
    )
    print(
        "  tick reservation <= offer anchor:       "
        f"{wage_summary['share_tick_reservation_lte_offer_anchor'] * 100.0:.1f}%"
    )
    print(
        "  tick reservation <= min wage:           "
        f"{wage_summary['share_tick_reservation_lte_min_wage'] * 100.0:.1f}%"
    )
    print(
        "  tick reservation <= benefit floor:      "
        f"{wage_summary['share_tick_reservation_lte_benefit_floor'] * 100.0:.1f}%"
    )

    unmet_summary = build_unmet_demand_summary(economy)
    print("\nUNMET DEMAND DIAGNOSTICS")
    print("  goods-market unmet units are food/services units from market clearing.")
    print("  housing and healthcare are separate counts because they use separate service flows.")
    print(f"  total goods unmet units:        {unmet_summary['total_goods_unmet']:,.1f}")
    print(f"  goods unmet by sector:          {_format_sector_map(unmet_summary['explicit_goods_unmet'])}")
    print(f"  firm-level unmet by sector:     {_format_sector_map(unmet_summary['firm_level_unmet_by_sector'])}")
    print(f"  baseline unmet by sector:       {_format_sector_map(unmet_summary['baseline_unmet_by_sector'])}")
    print(f"  private unmet by sector:        {_format_sector_map(unmet_summary['private_unmet_by_sector'])}")
    print(f"  services unmet by firm:         {_format_sector_map(unmet_summary['service_unmet_by_firm'])}")
    print(
        "  housing failures:              "
        f"total={unmet_summary['housing_failure_count']:.0f}, "
        f"unaffordable={unmet_summary['housing_unaffordable_count']:.0f}, "
        f"no_supply={unmet_summary['housing_no_supply_count']:.0f}, "
        f"homeless={unmet_summary['homeless_household_count']:.0f}, "
        f"shortage_flag={unmet_summary['housing_shortage_flag']:.0f}"
    )
    print(
        "  healthcare:                    "
        f"queue={unmet_summary['healthcare_queue_depth']:.0f}, "
        f"completed={unmet_summary['healthcare_completed_count']:.0f}, "
        f"denied_affordability={unmet_summary['healthcare_denied_count']:.0f}"
    )
    if unmet_summary["top_firms"]:
        print("  top firm-level unmet:")
        for row in unmet_summary["top_firms"]:
            owner = "base" if row["baseline"] else "priv"
            flags = []
            if row["survival"]:
                flags.append("survival")
            if row["burn"]:
                flags.append("burn")
            flag_text = ",".join(flags) if flags else "normal"
            print(
                f"    firm {row['firm_id']} {row['sector']} {owner}: "
                f"unmet={row['unmet']:.1f}, sold={row['sold']:.1f}, observed={row['observed_demand']:.1f}, "
                f"inventory={row['inventory']:.1f}, workers={row['workers']}, hires={row['planned_hires']}, "
                f"runway={row['cash_runway']:.1f}, {flag_text}"
            )

    firm_financial_rows = build_firm_financial_rows(economy)
    print("\nFIRM FINANCIAL DIAGNOSTICS")
    print("  net_worth_proxy = cash + inventory*price + capital value + housing unit value - debt")
    print(
        "  firm | sector | base | emp | wage_offer | avg_wage | price | cash | debt | "
        "net_worth | revenue | profit | margin | runway | inventory | flags"
    )
    negative_cash_count = 0
    negative_profit_count = 0
    negative_net_worth_count = 0
    for row in firm_financial_rows:
        flags = []
        if row["negative_cash"]:
            flags.append("neg_cash")
            negative_cash_count += 1
        if row["negative_profit"]:
            flags.append("neg_profit")
            negative_profit_count += 1
        if row["negative_net_worth"]:
            flags.append("neg_net_worth")
            negative_net_worth_count += 1
        if row["survival"]:
            flags.append("survival")
        if row["burn"]:
            flags.append("burn")
        flag_text = ",".join(flags) if flags else "ok"
        owner = "Y" if row["baseline"] else "N"
        print(
            f"  {row['firm_id']:>4} | {row['sector']:<10} | {owner:^4} | {row['employees']:>3} | "
            f"${row['wage_offer']:>7.1f} | ${row['avg_actual_wage']:>7.1f} | ${row['price']:>7.2f} | "
            f"${row['cash']:>9,.0f} | ${row['debt']:>9,.0f} | ${row['net_worth']:>10,.0f} | "
            f"${row['last_revenue']:>8,.0f} | ${row['last_profit']:>8,.0f} | "
            f"{row['profit_margin']:>6.3f} | {row['runway']:>7.1f} | {row['inventory']:>9.1f} | {flag_text}"
        )
    print(
        "  firm negative counts: "
        f"cash={negative_cash_count}, profit={negative_profit_count}, net_worth={negative_net_worth_count}"
    )

    print(f"  working_capital_budget:         ${float(final_metrics.get('working_capital_budget_this_tick', 0.0)):,.0f}")
    print(f"  working_capital_candidates:     {working_capital_candidates}")
    print(f"  working_capital_issued:         ${float(final_metrics.get('working_capital_issued_this_tick', 0.0)):,.0f}")
    print(f"  working_capital_issued_firms:   {working_capital_issued_firms}")
    print(f"  working_capital_denials:        {dict(working_capital_denial_reasons)}")
    print(f"  hiring_block_reasons:           {dict(hiring_block_reasons)}")
    print("\nBAILOUT DIAGNOSTICS")
    print(f"  gov_bailout_spend_this_tick:    ${float(final_metrics.get('gov_bailout_spend_this_tick', 0.0)):,.0f}")
    print(f"  bailout_budget_remaining:       ${float(final_metrics.get('bailout_budget_remaining', 0.0)):,.0f}")
    print(f"  bailout_cycle_disbursed:        ${float(final_metrics.get('bailout_cycle_disbursed', 0.0)):,.0f}")
    print(f"  last_cycle_bailout_disbursed:   ${float(final_metrics.get('last_cycle_bailout_disbursed', 0.0)):,.0f}")
    print(f"  last_cycle_bailout_firms:       {int(final_metrics.get('last_cycle_bailout_firms_assisted', 0.0) or 0)}")
    print(f"  eligible_firms_by_sector:       {final_metrics.get('bailout_eligible_firms_by_sector', {})}")
    print(f"  denied_firms_by_reason:         {final_metrics.get('bailout_denied_firms_by_reason', {})}")
    print(f"  received_by_firm_id:            {final_metrics.get('bailout_received_by_firm_id', {})}")
    print(f"  firms_in_survival:              {int(final_metrics.get('survival_mode_firm_count', 0.0) or 0)}")
    print(f"  firms_in_burn:                  {int(final_metrics.get('burn_mode_firm_count', 0.0) or 0)}")
    print(f"  avg_private_cash_runway:        {avg_private_cash_runway:.1f}")
    print(f"  cannot_work_count:              {int(final_metrics.get('cannot_work_count', 0.0) or 0)}")
    print(f"  cannot_work_rate:               {float(final_metrics.get('cannot_work_rate', 0.0)) * 100.0:.1f}%")
    print(f"  labor_force_unemployment_rate:  {float(final_metrics.get('labor_force_unemployment_rate', 0.0)) * 100.0:.1f}%")
    print(f"  jobless_rate_total_population:  {float(final_metrics.get('jobless_rate_total_population', 0.0)) * 100.0:.1f}%")

    print("\nBANK HEALTH DIAGNOSTICS")
    if economy.bank is None:
        print("  bank:                         none")
    else:
        reserve_ratio = float(final_metrics.get("bank_reserve_ratio_actual", 0.0) or 0.0)
        can_lend = bool(float(final_metrics.get("bank_can_lend", 0.0) or 0.0) > 0.5)
        print(f"  cash_reserves:                ${float(final_metrics.get('bank_cash_reserves', 0.0)):,.0f}")
        print(f"  total_deposits:               ${float(final_metrics.get('bank_total_deposits', 0.0)):,.0f}")
        print(f"  total_loans_outstanding:      ${float(final_metrics.get('bank_total_loans_outstanding', 0.0)):,.0f}")
        print(f"  lendable_cash:                ${float(final_metrics.get('bank_lendable_cash', 0.0)):,.0f}")
        print(f"  reserve_ratio_actual:         {reserve_ratio:.2%}")
        print(f"  can_lend:                     {can_lend}")
        print(f"  active_loan_count:            {int(final_metrics.get('bank_active_loan_count', 0.0) or 0)}")
        print(f"  loan_loss_provision:          ${float(final_metrics.get('bank_loan_loss_provision', 0.0)):,.0f}")
        print(f"  new_loans_this_tick:          ${float(final_metrics.get('bank_new_loans_this_tick', 0.0)):,.0f}")
        print(f"  defaults_this_tick:           {int(final_metrics.get('bank_defaults_this_tick', 0.0) or 0)}")
        print(f"  repayments_this_tick:         ${float(final_metrics.get('bank_repayments_this_tick', 0.0)):,.0f}")
        print(f"  interest_income_this_tick:    ${float(final_metrics.get('bank_interest_income_this_tick', 0.0)):,.0f}")
        print(f"  deposit_interest_this_tick:   ${float(final_metrics.get('bank_deposit_interest_this_tick', 0.0)):,.0f}")
        print(f"  avg_firm_credit_score:        {float(final_metrics.get('bank_avg_credit_score_firms', 0.0)):.3f}")
        print(f"  avg_household_credit_score:   {float(final_metrics.get('bank_avg_credit_score_households', 0.0)):.3f}")

    if args.firm_hire_gate_diagnostics:
        print("\nFIRM HIRE GATE DIAGNOSTICS")
        print(
            "tick | firm_id | sector | baseline | expected_sales_units | last_tick_unmet_units | "
            "observed_demand_units | cash_runway_ticks | "
            "survival_mode | burn_mode | smoothed_profit_margin | demand_workers | "
            "current_workers | target_workers-current_workers | planned_hires | blocked_by"
        )
        for row in build_firm_hire_gate_diagnostics(economy):
            print(
                "FIRMGATE | "
                f"{economy.current_tick} | "
                f"{row['firm_id']} | "
                f"{row['sector']} | "
                f"{row['baseline']} | "
                f"{row['expected_sales_units']:.1f} | "
                f"{row['last_tick_unmet_units']:.1f} | "
                f"{row['observed_demand_units']:.1f} | "
                f"{row['cash_runway_ticks']:.1f} | "
                f"{row['survival_mode']} | "
                f"{row['burn_mode']} | "
                f"{row['smoothed_profit_margin']:.3f} | "
                f"{row['demand_workers']} | "
                f"{row['current_workers']} | "
                f"{row['target_delta']} | "
                f"{row['planned_hires']} | "
                f"{row['blocked_by']}",
            )

    # Final state
    gov = economy.government
    print(f"\n{'-' * 50}")
    print("FINAL POLICY STATE:")
    print(f"  wage_tax_rate:            {gov.wage_tax_rate:.2%}")
    print(f"  profit_tax_rate:         {gov.profit_tax_rate:.2%}")
    print(f"  investment_tax_rate:     {gov.investment_tax_rate:.2%}")
    print(f"  benefit_level:           {gov.benefit_level}")
    print(f"  public_works:            {gov.public_works_toggle}")
    print(f"  minimum_wage_policy:     {gov.minimum_wage_policy}")
    print(f"  sector_subsidy_target:   {gov.sector_subsidy_target}")
    print(f"  sector_subsidy_level:    {gov.sector_subsidy_level}")
    print(f"  infrastructure_spending: {gov.infrastructure_spending}")
    print(f"  technology_spending:     {gov.technology_spending}")
    print(f"  bailout_policy:          {gov.bailout_policy}")
    print(f"  bailout_target:          {gov.bailout_target}")
    print(f"  bailout_budget:          ${gov.bailout_budget:,.0f}")

    print(f"\nTotal time: {total_time:.0f}s ({total_time / 60:.1f}m)")
    avg_tick_ms = (total_time / max(1, args.ticks)) * 1000.0
    print(f"Simulation ticks: {args.ticks} ({avg_tick_ms:.0f}ms avg)")
    print(f"LLM decisions: {len(advisor.decision_history)}")

    if not args.no_output_files:
        output_dir = Path(args.output_dir)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_stem = f"llm_government_seed{CONFIG.random_seed}_ticks{args.ticks}_{run_id}"
        json_path = output_dir / f"{run_stem}.json"
        md_path = output_dir / f"{run_stem}.md"
        latest_json_path = output_dir / "llm_government_latest.json"
        latest_md_path = output_dir / "llm_government_latest.md"

        final_policy = {
            "wage_tax_rate": gov.wage_tax_rate,
            "profit_tax_rate": gov.profit_tax_rate,
            "investment_tax_rate": gov.investment_tax_rate,
            "benefit_level": gov.benefit_level,
            "unemployment_benefit_level": gov.get_unemployment_benefit_level(),
            "public_works": gov.public_works_toggle,
            "minimum_wage_policy": gov.minimum_wage_policy,
            "sector_subsidy_target": gov.sector_subsidy_target,
            "sector_subsidy_level": gov.sector_subsidy_level,
            "infrastructure_spending": gov.infrastructure_spending,
            "technology_spending": gov.technology_spending,
            "price_stabilization_target": getattr(gov, "price_stabilization_target", "none"),
            "price_stabilization_level": getattr(gov, "price_stabilization_level", "off"),
            "rent_stabilization_level": getattr(gov, "rent_stabilization_level", "off"),
            "bailout_policy": gov.bailout_policy,
            "bailout_target": gov.bailout_target,
            "bailout_budget": gov.bailout_budget,
        }
        economic_summary = {
            "final_gov_cash": float(final_metrics.get("government_cash", 0.0) or 0.0),
            "min_gov_cash": min_metric("government_cash"),
            "avg_gdp": avg_metric("gdp_this_tick"),
            "final_gdp": float(final_metrics.get("gdp_this_tick", 0.0) or 0.0),
            "avg_unemployment_rate": avg_metric("unemployment_rate"),
            "final_unemployment_rate": float(final_metrics.get("unemployment_rate", 0.0) or 0.0),
            "avg_health": avg_metric("mean_health"),
            "final_health": float(final_metrics.get("mean_health", 0.0) or 0.0),
            "avg_happiness": avg_metric("mean_happiness"),
            "final_happiness": float(final_metrics.get("mean_happiness", 0.0) or 0.0),
            "max_expected_to_observed": max_expected_to_observed,
            "max_expected_sales_private": max_expected_sales,
            "max_hire_limit_effective": max_hire_limit_effective,
            "adaptive_hiring_firms": adaptive_hiring_firms,
            "reservation_blocked_vacancies": reservation_blocked_vacancies,
            "reservation_gap_wage_raises": reservation_gap_wage_raises,
            "median_rejected_reservation": median_rejected_reservation,
            "median_unemployed_reservation": median_unemployed_reservation,
            "working_capital_budget": float(final_metrics.get("working_capital_budget_this_tick", 0.0) or 0.0),
            "working_capital_candidates": working_capital_candidates,
            "working_capital_issued": float(final_metrics.get("working_capital_issued_this_tick", 0.0) or 0.0),
            "working_capital_issued_firms": working_capital_issued_firms,
            "working_capital_denials": dict(working_capital_denial_reasons),
            "hiring_block_reasons": dict(hiring_block_reasons),
            "firms_in_survival": int(final_metrics.get("survival_mode_firm_count", 0.0) or 0),
            "firms_in_burn": int(final_metrics.get("burn_mode_firm_count", 0.0) or 0),
            "avg_private_cash_runway": avg_private_cash_runway,
            "cannot_work_count": int(final_metrics.get("cannot_work_count", 0.0) or 0),
            "cannot_work_rate": float(final_metrics.get("cannot_work_rate", 0.0) or 0.0),
            "labor_force_unemployment_rate": float(final_metrics.get("labor_force_unemployment_rate", 0.0) or 0.0),
            "jobless_rate_total_population": float(final_metrics.get("jobless_rate_total_population", 0.0) or 0.0),
            "mean_wage": float(final_metrics.get("mean_wage", 0.0) or 0.0),
            "median_wage": float(final_metrics.get("median_wage", 0.0) or 0.0),
            "mean_price": float(final_metrics.get("mean_price", 0.0) or 0.0),
            "median_price": float(final_metrics.get("median_price", 0.0) or 0.0),
            "housing_rent_to_median_wage": float(final_metrics.get("housing_rent_to_median_wage", 0.0) or 0.0),
            "avg_sector_price_to_median_wage": float(final_metrics.get("avg_sector_price_to_median_wage", 0.0) or 0.0),
            "price_increase_limited_count": int(final_metrics.get("price_increase_limited_count", 0.0) or 0),
            "rent_increase_limited_count": int(final_metrics.get("rent_increase_limited_count", 0.0) or 0),
            "homeless_household_count": int(final_metrics.get("homeless_household_count", 0.0) or 0),
            "housing_unaffordable_count": int(final_metrics.get("housing_unaffordable_count", 0.0) or 0),
            "gov_bailout_spend_this_tick": float(final_metrics.get("gov_bailout_spend_this_tick", 0.0) or 0.0),
            "bailout_budget_remaining": float(final_metrics.get("bailout_budget_remaining", 0.0) or 0.0),
            "bailout_cycle_disbursed": float(final_metrics.get("bailout_cycle_disbursed", 0.0) or 0.0),
            "last_cycle_bailout_disbursed": float(final_metrics.get("last_cycle_bailout_disbursed", 0.0) or 0.0),
            "last_cycle_bailout_firms_assisted": int(final_metrics.get("last_cycle_bailout_firms_assisted", 0.0) or 0),
            "bailout_eligible_firms_by_sector": dict(final_metrics.get("bailout_eligible_firms_by_sector", {}) or {}),
            "bailout_denied_firms_by_reason": dict(final_metrics.get("bailout_denied_firms_by_reason", {}) or {}),
            "bailout_received_by_firm_id": dict(final_metrics.get("bailout_received_by_firm_id", {}) or {}),
        }
        decision_quality = {
            "total_decisions": total_decisions,
            "decisions_with_accepts": decisions_with_accepts,
            "raw_change_count": raw_change_count,
            "rejected_change_count": rejected_change_count,
            "fiscal_rejection_count": fiscal_rejection_count,
            "invalid_enum_rejection_count": invalid_enum_rejection_count,
            "accepted_decision_rate": accepted_decision_rate,
            "rejection_rate": rejection_rate,
            "fiscal_rejection_rate": fiscal_rejection_rate,
            "invalid_enum_rate": invalid_enum_rate,
            "evidence_audit_counts": dict(evidence_audit_counts),
            "evidence_audit_total": evidence_audit_total,
            "evidence_audit_matched": evidence_audit_matched,
            "evidence_audit_match_rate": evidence_audit_match_rate,
        }
        artifact = {
            "run": {
                "run_id": run_id,
                "provider": args.provider,
                "base_url": CONFIG.llm.lmstudio_base_url if args.provider == "lmstudio" else args.base_url,
                "model": args.model,
                "households": args.households,
                "ticks": args.ticks,
                "seed": CONFIG.random_seed,
                "first_decision_tick": first_decision_tick,
                "interval": args.interval,
                "temperature": args.temperature,
                "top_p": CONFIG.llm.government_top_p,
                "max_tokens": CONFIG.llm.government_max_tokens,
                "elapsed_seconds": total_time,
                "avg_tick_ms": avg_tick_ms,
                "disable_bailouts": bool(args.disable_bailouts),
            },
            "decision_quality": decision_quality,
            "economic_summary": economic_summary,
            "final_policy": final_policy,
            "wage_reservation_summary": wage_summary,
            "unmet_demand_summary": unmet_summary,
            "firm_financial_rows": firm_financial_rows,
            "bank_health": {
                "cash_reserves": float(final_metrics.get("bank_cash_reserves", 0.0) or 0.0),
                "total_deposits": float(final_metrics.get("bank_total_deposits", 0.0) or 0.0),
                "total_loans_outstanding": float(final_metrics.get("bank_total_loans_outstanding", 0.0) or 0.0),
                "lendable_cash": float(final_metrics.get("bank_lendable_cash", 0.0) or 0.0),
                "reserve_ratio_actual": float(final_metrics.get("bank_reserve_ratio_actual", 0.0) or 0.0),
                "can_lend": bool(float(final_metrics.get("bank_can_lend", 0.0) or 0.0) > 0.5),
                "active_loan_count": int(final_metrics.get("bank_active_loan_count", 0.0) or 0),
                "loan_loss_provision": float(final_metrics.get("bank_loan_loss_provision", 0.0) or 0.0),
                "new_loans_this_tick": float(final_metrics.get("bank_new_loans_this_tick", 0.0) or 0.0),
                "defaults_this_tick": int(final_metrics.get("bank_defaults_this_tick", 0.0) or 0),
                "repayments_this_tick": float(final_metrics.get("bank_repayments_this_tick", 0.0) or 0.0),
                "interest_income_this_tick": float(final_metrics.get("bank_interest_income_this_tick", 0.0) or 0.0),
                "deposit_interest_this_tick": float(final_metrics.get("bank_deposit_interest_this_tick", 0.0) or 0.0),
                "avg_firm_credit_score": float(final_metrics.get("bank_avg_credit_score_firms", 0.0) or 0.0),
                "avg_household_credit_score": float(final_metrics.get("bank_avg_credit_score_households", 0.0) or 0.0),
            },
            "decision_records": decision_records,
            "decision_history_raw": advisor.decision_history,
            "tick_metrics": summary_rows,
        }
        json_content = json.dumps(_json_safe(artifact), indent=2, sort_keys=True)
        _write_text(json_path, json_content)
        _write_text(latest_json_path, json_content)

        md_lines = [
            "# EcoSim LLM Government Run",
            "",
            f"- Run ID: `{run_id}`",
            f"- Model: `{args.model}` via `{args.provider}`",
            f"- Seed: `{CONFIG.random_seed}`",
            f"- Ticks: `{args.ticks}`",
            f"- Decision interval: `{args.interval}`",
            "",
            "## Summary",
            "",
            f"- Final gov cash: `${economic_summary['final_gov_cash']:,.0f}`",
            f"- Min gov cash: `${economic_summary['min_gov_cash']:,.0f}`",
            f"- Avg GDP: `${economic_summary['avg_gdp']:,.0f}`",
            f"- Final GDP: `${economic_summary['final_gdp']:,.0f}`",
            f"- Avg unemployment: `{economic_summary['avg_unemployment_rate'] * 100.0:.1f}%`",
            f"- Final unemployment: `{economic_summary['final_unemployment_rate'] * 100.0:.1f}%`",
            f"- Avg health: `{economic_summary['avg_health']:.3f}`",
            f"- Final health: `{economic_summary['final_health']:.3f}`",
            f"- Avg happiness: `{economic_summary['avg_happiness']:.3f}`",
            f"- Final happiness: `{economic_summary['final_happiness']:.3f}`",
            f"- Median wage: `${economic_summary['median_wage']:,.1f}`",
            f"- Mean wage: `${economic_summary['mean_wage']:,.1f}`",
            f"- Median firm price: `${economic_summary['median_price']:,.1f}`",
            f"- Mean firm price: `${economic_summary['mean_price']:,.1f}`",
            f"- Housing rent / median wage: `{economic_summary['housing_rent_to_median_wage']:.2f}`",
            f"- Target sector price / median wage: `{economic_summary['avg_sector_price_to_median_wage']:.2f}`",
            f"- Price increases limited: `{economic_summary['price_increase_limited_count']}`",
            f"- Rent increases limited: `{economic_summary['rent_increase_limited_count']}`",
            f"- Homeless households: `{economic_summary['homeless_household_count']}`",
            f"- Housing unaffordable failures: `{economic_summary['housing_unaffordable_count']}`",
            f"- Bailout spend this tick: `${economic_summary['gov_bailout_spend_this_tick']:,.0f}`",
            f"- Bailout budget remaining: `${economic_summary['bailout_budget_remaining']:,.0f}`",
            f"- Bailout cycle disbursed: `${economic_summary['bailout_cycle_disbursed']:,.0f}`",
            f"- Last cycle bailout disbursed: `${economic_summary['last_cycle_bailout_disbursed']:,.0f}`",
            f"- Last cycle bailout firms assisted: `{economic_summary['last_cycle_bailout_firms_assisted']}`",
            "",
            "## Bailout Diagnostics",
            "",
            f"- Eligible firms by sector: `{economic_summary['bailout_eligible_firms_by_sector']}`",
            f"- Denied firms by reason: `{economic_summary['bailout_denied_firms_by_reason']}`",
            f"- Received by firm id: `{economic_summary['bailout_received_by_firm_id']}`",
            "",
            "## Decision Quality",
            "",
            f"- Accepted decision rate: `{accepted_decision_rate:.1%}` ({decisions_with_accepts}/{total_decisions})",
            f"- Rejection rate: `{rejection_rate:.1%}` ({rejected_change_count}/{raw_change_count})",
            f"- Fiscal rejection rate: `{fiscal_rejection_rate:.1%}`",
            f"- Invalid enum rate: `{invalid_enum_rate:.1%}`",
            f"- Evidence match rate: `{evidence_audit_match_rate:.1%}` ({evidence_audit_matched}/{evidence_audit_total})",
            f"- Evidence audit counts: `{dict(evidence_audit_counts)}`",
            "",
            "## Final Policy",
            "",
        ]
        md_lines.extend(f"- `{key}`: `{value}`" for key, value in final_policy.items())
        md_lines.extend([
            "",
            "## LLM Decisions",
            "",
            "| Tick | Mode | Goal | Raw Changes | Accepted LLM | Mechanical | Applied | Rejected | Gov Cash | GDP | Unemp |",
            "|---:|---|---|---|---|---|---|---|---:|---:|---:|",
        ])
        md_lines.extend(_format_decision_for_markdown(item) for item in decision_records)
        md_lines.extend([
            "",
            "## Final Firm Financials",
            "",
            "| Firm | Sector | Base | Emp | Wage Offer | Price | Cash | Debt | Net Worth | Profit | Runway | Flags |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        for row in firm_financial_rows:
            flags = []
            if row["negative_cash"]:
                flags.append("neg_cash")
            if row["negative_profit"]:
                flags.append("neg_profit")
            if row["negative_net_worth"]:
                flags.append("neg_net_worth")
            if row["survival"]:
                flags.append("survival")
            if row["burn"]:
                flags.append("burn")
            md_lines.append(
                f"| {row['firm_id']} | {row['sector']} | {row['baseline']} | {row['employees']} | "
                f"${row['wage_offer']:,.1f} | ${row['price']:,.2f} | ${row['cash']:,.0f} | "
                f"${row['debt']:,.0f} | ${row['net_worth']:,.0f} | ${row['last_profit']:,.0f} | "
                f"{row['runway']:.1f} | {', '.join(flags) or 'ok'} |"
            )
        md_content = "\n".join(md_lines) + "\n"
        _write_text(md_path, md_content)
        _write_text(latest_md_path, md_content)
        print(f"\nSaved run artifacts:")
        print(f"  JSON: {json_path}")
        print(f"  MD:   {md_path}")
        print(f"  Latest JSON: {latest_json_path}")
        print(f"  Latest MD:   {latest_md_path}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
