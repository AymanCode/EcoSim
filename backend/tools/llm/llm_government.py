
"""LLM government agent with optional LangGraph orchestration.

This module keeps the government decision loop narrow and testable:

1. observe current economy state
2. apply noisy / lagged / incomplete information constraints
3. include a compact window of recent policy decisions and observed outcomes
4. call the provider for a JSON decision
5. validate lever names, values, and one-step movement constraints
6. apply approved changes

LangGraph is used when installed. The runtime falls back to the same explicit
node sequence when LangGraph is unavailable so local development and tests do
not depend on that package being present.
"""

from __future__ import annotations

from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)

import logging
import random
import time
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from llm_provider import LLMProvider, extract_json_from_response

try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - exercised through fallback path
    END = None
    StateGraph = None
    HAS_LANGGRAPH = False

logger = logging.getLogger(__name__)


class GovernmentState(TypedDict, total=False):
    """State exchanged between observation / reasoning / apply nodes."""

    raw_metrics: Dict[str, Any]
    sector_diagnostics: Dict[str, Any]
    observed_metrics: Dict[str, Any]
    rolling_summaries: Dict[str, Dict[str, float]]
    current_policy: Dict[str, Any]
    budget_state: Dict[str, Any]
    regime_state: Dict[str, Any]
    recent_policy_memory: List[Dict[str, Any]]
    llm_response: str
    decisions: Dict[str, Any]
    reasoning: str
    parse_ok: bool
    elapsed_ms: float
    tick: int
    data_quality_summary: Dict[str, int]


CONTINUOUS_LEVERS: Dict[str, tuple] = {
    "wage_tax_rate": (0.0, 0.50),        # fraction of wages taxed
    "profit_tax_rate": (0.0, 0.50),      # fraction of firm profits taxed
    "investment_tax_rate": (0.0, 0.30),  # fraction of R&D/investment taxed
}

VALID_LEVERS: Dict[str, set] = {
    "benefit_level": {"low", "neutral", "high", "crisis"},
    "public_works": {"off", "on"},
    "minimum_wage_policy": {"low", "neutral", "high"},
    "sector_subsidy_target": {"none", "food", "housing", "services", "healthcare"},
    "sector_subsidy_level": {0, 10, 25, 50},
    "infrastructure_spending": {"none", "low", "medium", "high"},
    "technology_spending": {"none", "low", "medium", "high"},
    "bailout_policy": {"off", "sector", "all"},
    "bailout_target": {"none", "food", "housing", "services", "healthcare"},
    "bailout_budget": {0, 5000, 10000, 25000, 50000},
}

ORDERED_LEVERS: Dict[str, List[Any]] = {
    "benefit_level": ["low", "neutral", "high", "crisis"],
    "public_works": ["off", "on"],
    "minimum_wage_policy": ["low", "neutral", "high"],
    "sector_subsidy_level": [0, 10, 25, 50],
    "infrastructure_spending": ["none", "low", "medium", "high"],
    "technology_spending": ["none", "low", "medium", "high"],
    "bailout_policy": ["off", "sector", "all"],
    "bailout_budget": [0, 5000, 10000, 25000, 50000],
}

PROMPT_POLICY_LEVERS: tuple = (
    "wage_tax_rate",
    "profit_tax_rate",
    "investment_tax_rate",
    "benefit_level",
    "public_works",
    "minimum_wage_policy",
    "sector_subsidy_target",
    "sector_subsidy_level",
    "infrastructure_spending",
    "technology_spending",
    "bailout_policy",
    "bailout_target",
    "bailout_budget",
)

# indicator_name -> (lag_ticks, noise_std_pct, coverage_pct)
INDICATOR_CONSTRAINTS: Dict[str, tuple] = {
    "government_cash": (0, 0.01, 1.0),
    "gov_revenue_this_tick": (1, 0.03, 1.0),
    "gov_spending_this_tick": (0, 0.01, 1.0),
    "gov_subsidy_spend_this_tick": (0, 0.03, 1.0),
    "unemployment_rate": (2, 0.05, 0.95),
    "mean_wage": (2, 0.08, 0.90),
    "gdp_this_tick": (3, 0.10, 1.0),
    "mean_health": (1, 0.05, 0.90),
    "mean_happiness": (1, 0.06, 0.85),
    "wage_floor_binding_share": (1, 0.05, 0.95),
    "minimum_wage_floor": (0, 0.01, 1.0),
    "unemployment_benefit": (0, 0.01, 1.0),
    "gini_coefficient": (4, 0.12, 0.80),
    "labor_seekers_wage_ineligible": (1, 0.10, 0.85),
    "labor_cannot_work": (1, 0.08, 0.90),
    "healthcare_queue_depth": (1, 0.05, 0.95),
    "healthcare_denied_count": (1, 0.05, 0.95),
    "public_works_jobs": (1, 0.02, 1.0),
    "total_firms": (1, 0.02, 1.0),
    "effective_mean_quality": (1, 0.03, 0.95),
    "infrastructure_productivity": (0, 0.01, 1.0),
    "technology_quality": (0, 0.01, 1.0),
    "bank_defaults_this_tick": (1, 0.05, 0.90),
    "distressed_firm_count": (1, 0.05, 0.95),
    "distressed_food_firms": (1, 0.05, 0.95),
    "distressed_housing_firms": (1, 0.05, 0.95),
    "distressed_services_firms": (1, 0.05, 0.95),
    "distressed_healthcare_firms": (1, 0.05, 0.95),
    "bankruptcy_count": (1, 0.05, 0.95),
    "gov_bailout_spend_this_tick": (0, 0.03, 1.0),
    "bailout_budget_remaining": (0, 0.01, 1.0),
    "bailout_cycle_disbursed": (0, 0.01, 1.0),
    "last_cycle_bailout_disbursed": (0, 0.01, 1.0),
    "last_cycle_bailout_firms_assisted": (0, 0.02, 1.0),
}

RATE_LIKE_INDICATORS = {
    "unemployment_rate",
    "gini_coefficient",
    "mean_health",
    "mean_happiness",
    "wage_floor_binding_share",
}

ROLLING_WINDOWS: tuple = (4, 12)

TIER_1_CORE: tuple = (
    "unemployment_rate", "gdp_this_tick", "mean_health", "mean_happiness",
    "gini_coefficient", "government_cash", "mean_wage", "wage_floor_binding_share",
)

TIER_2_DISTRESS: tuple = (
    "distressed_food_firms", "distressed_housing_firms", "distressed_services_firms",
    "distressed_healthcare_firms", "bankruptcy_count", "bank_defaults_this_tick",
    "healthcare_queue_depth", "healthcare_denied_count",
    "labor_seekers_wage_ineligible", "labor_cannot_work",
)

TIER_3_SLOW: tuple = (
    "infrastructure_productivity", "technology_quality", "total_firms",
    "effective_mean_quality", "public_works_jobs", "minimum_wage_floor",
    "unemployment_benefit",
)

IDEOLOGY_LEVER_OVERRIDES: Dict[str, Dict[str, tuple]] = {
    "capitalist": {},
    "keynesian": {},
    "balanced": {},
    "socialist": {
        "wage_tax_rate": (0.0, 0.65),
        "profit_tax_rate": (0.0, 0.65),
        "investment_tax_rate": (0.0, 0.40),
    },
    "communist": {
        "wage_tax_rate": (0.0, 0.85),
        "profit_tax_rate": (0.0, 0.90),
        "investment_tax_rate": (0.0, 0.60),
    },
}

PHILOSOPHY_PROMPTS = {
    "capitalist": (
        "You believe in free-market capitalism: private enterprise drives growth, government should keep taxes "
        "competitive, avoid heavy-handed intervention, and step in only when markets are clearly failing. "
        "You favor fiscal discipline, supply-side conditions for investment, and targeted intervention over "
        "broad permanent expansion."
    ),
    "keynesian": (
        "You believe active fiscal policy is necessary to stabilize demand during downturns. You favor "
        "counter-cyclical spending, strong safety nets during recessions, and public investment when "
        "private demand is weak."
    ),
    "balanced": (
        "You are pragmatic rather than ideological. You balance market efficiency, fiscal discipline, "
        "employment, and social stability, adjusting intervention based on current conditions."
    ),
    "socialist": (
        "You believe the state should actively redistribute wealth and guarantee basic needs. You favor high "
        "taxation on profits and wages, robust public services, strong labor protections, and direct government "
        "investment to ensure equitable outcomes over growth alone."
    ),
    "communist": (
        "You believe private ownership of the means of production must be minimized. You favor near-total "
        "taxation of profits and wages, universal state provision of housing, healthcare, and employment, "
        "and central coordination over market competition."
    ),
}


def _resolve_continuous_levers(philosophy: str) -> Dict[str, tuple]:
    """Return ideology-adjusted continuous lever ranges."""
    base = dict(CONTINUOUS_LEVERS)
    base.update(IDEOLOGY_LEVER_OVERRIDES.get(philosophy, {}))
    return base


def _compute_rolling_summary(economy: Any, indicator: str, windows: tuple = ROLLING_WINDOWS) -> Dict[str, float]:
    """Compute unweighted rolling averages for one indicator from metrics_history."""
    history = list(getattr(economy, "metrics_history", []) or [])
    out: Dict[str, float] = {}
    for window in windows:
        slice_ = history[-window:] if len(history) >= window else history
        values = [
            row["metrics"].get(indicator)
            for row in slice_
            if isinstance(row.get("metrics", {}).get(indicator), (int, float))
        ]
        if values:
            out[f"avg_{window}t"] = round(sum(values) / len(values), 4)
    return out


def _trend_arrow(current: Any, avg_short: Any, avg_long: Any) -> str:
    """Return a trend arrow comparing current value against short and long rolling averages."""
    if not all(isinstance(x, (int, float)) for x in (current, avg_short, avg_long)):
        return ""
    if current > avg_short > avg_long:
        return " ↑"
    if current < avg_short < avg_long:
        return " ↓"
    return " →"


def _is_meaningful(indicator: str, value: Any) -> bool:
    """Return False for Tier-2 distress indicators when value is zero — suppresses noise."""
    if indicator not in TIER_2_DISTRESS:
        return True
    if isinstance(value, (int, float)):
        return value > 0
    return value not in (None, "", "none", 0)


def _build_system_prompt(philosophy: str, num_households: int, num_firms: int) -> str:
    """Build the system prompt for the government agent."""

    levers = _resolve_continuous_levers(philosophy)
    wt_lo, wt_hi = levers["wage_tax_rate"]
    pt_lo, pt_hi = levers["profit_tax_rate"]
    it_lo, it_hi = levers["investment_tax_rate"]

    return f"""ROLE: You are the AI Central Government of a simulated economy.
PHILOSOPHY: Balanced / Pragmatic
OBJECTIVE: Maximize GDP and mean happiness while keeping unemployment low and maintaining a sustainable government cash balance.

CRITICAL SIMULATION RULES:
1. ONE-STEP LIMIT: You may only change a qualitative ordered lever by one step per decision cycle.
2. BOUNDARIES: Do not output values outside the specified valid ranges.
3. BAILOUTS: Bailout budgets must be realistic and target specific distress.
4. ACTIONS: Only include levers you want to change. Hold policy by returning an empty changes object.
5. OUTPUT: Return only valid JSON. Do not use markdown, comments, <think> tags, or text outside the JSON object.

AVAILABLE LEVERS AND REAL CODE RANGES:
- wage_tax_rate: Float [{wt_lo:.2f} to {wt_hi:.2f}]
- profit_tax_rate: Float [{pt_lo:.2f} to {pt_hi:.2f}]
- investment_tax_rate: Float [{it_lo:.2f} to {it_hi:.2f}]
- benefit_level: Enum [low, neutral, high, crisis]
- public_works: Enum [off, on]
- minimum_wage_policy: Enum [low, neutral, high]
- sector_subsidy_target: Enum [none, food, housing, services, healthcare]
- sector_subsidy_level: Integer [0, 10, 25, 50]
- infrastructure_spending: Enum [none, low, medium, high]
- technology_spending: Enum [none, low, medium, high]
- bailout_policy: Enum [off, sector, all]
- bailout_target: Enum [none, food, housing, services, healthcare]
- bailout_budget: Integer [0, 5000, 10000, 25000, 50000]

REFERENCE ENUMS:
- technology_spending: none | low | medium | high
- bailout_policy: off | sector | all
- bailout_budget: 0 | 5000 | 10000 | 25000 | 50000

LEVER EFFECTS:
- wage_tax_rate higher: government revenue up, household take-home and consumption down.
- profit_tax_rate higher: government revenue up, firm cash and investment capacity down.
- investment_tax_rate higher: Higher investment_tax_rate taxes firm R&D directly; quality growth and R&D spending down.
- benefit_level higher: unemployed income up, reservation wages and fiscal cost up.
- public_works on: unemployment can fall quickly, government cash falls quickly.
- minimum_wage_policy higher: wage floor up; workers may earn more but fragile firms may hire less.
- sector_subsidy: targeted affordability/demand support, fiscal cost up.
- infrastructure_spending: productivity rises slowly over many ticks.
- technology_spending: effective quality rises slowly, may improve demand.
- bailout_budget: rescue loans to failing firms; use only for specific distress.

CONSISTENCY RULES:
- sector_subsidy_target=none requires sector_subsidy_level=0.
- A sector_subsidy_target other than none requires sector_subsidy_level > 0.
- bailout_policy=off requires bailout_target=none and bailout_budget=0.
- bailout_policy=sector requires a non-none bailout_target.

RESPONSE FORMAT:
{{
  "reasoning": "Brief, 1-2 sentence explanation connecting sector diagnostics to the lever changes.",
  "changes": {{
    "lever_name": "new_value"
  }}
}}"""

def _format_observed_metrics(
    observed_metrics: Dict[str, Any],
    rolling_summaries: Optional[Dict[str, Dict[str, float]]] = None,
) -> str:
    """Render constrained observations in a tiered format for the user prompt."""

    if not observed_metrics:
        return "No observations available."

    rolling_summaries = rolling_summaries or {}
    lines: List[str] = []

    def render_indicator(key: str, show_rolling: bool = False, skip_unavailable: bool = False) -> Optional[str]:
        entry = observed_metrics.get(key)
        if entry is None:
            return None
        status = entry.get("status", "unknown")
        if status != "reported":
            if skip_unavailable:
                return None
            return f"  {key}: unavailable"
        value = entry.get("value")
        if not _is_meaningful(key, value):
            return None
        age = entry.get("data_age_ticks", 0)
        acc = entry.get("estimated_accuracy", "?")
        age_str = f"age={age}t, " if age > 0 else ""
        line = f"  {key}: {value} ({age_str}{acc})"
        if show_rolling and key in rolling_summaries:
            rs = rolling_summaries[key]
            avg4 = rs.get("avg_4t")
            avg12 = rs.get("avg_12t")
            trend = _trend_arrow(value, avg4, avg12)
            avg_parts = []
            if avg4 is not None:
                avg_parts.append(f"4t={avg4}")
            if avg12 is not None:
                avg_parts.append(f"12t={avg12}")
            if avg_parts:
                line += f" [avg: {', '.join(avg_parts)}{trend}]"
        return line

    # Tier 1: core indicators — always show (including unavailable), with rolling averages + trend
    tier1_lines = [line for key in TIER_1_CORE if (line := render_indicator(key, show_rolling=True)) is not None]
    if tier1_lines:
        lines.append("CORE INDICATORS:")
        lines.extend(tier1_lines)

    # Tier 2: distress signals — only show when nonzero/meaningful
    tier2_lines = [
        line for key in TIER_2_DISTRESS
        if (line := render_indicator(key, skip_unavailable=True)) is not None
    ]
    if tier2_lines:
        lines.append("DISTRESS SIGNALS (nonzero only):")
        lines.extend(tier2_lines)

    # Tier 3: slow-moving factors — compact, no rolling averages
    tier3_lines = [
        line for key in TIER_3_SLOW
        if (line := render_indicator(key, skip_unavailable=True)) is not None
    ]
    if tier3_lines:
        lines.append("SLOW-MOVING FACTORS:")
        lines.extend(tier3_lines)

    return "\n".join(lines) if lines else "No observations available."


def _format_recent_policy_memory(memory: List[Dict[str, Any]]) -> str:
    """Render compact recent policy decisions with normalized impact deltas."""

    if not memory:
        return "No recent policy actions recorded."

    def fmt(val: Any, unit: str) -> str:
        if val is None:
            return "n/a"
        sign = "+" if float(val) >= 0 else ""
        return f"{sign}{val}{unit}"

    lines: List[str] = []
    for item in memory:
        impact = item.get("impact", {})
        reasoning = str(item.get("reasoning", ""))[:100]
        lines.append(
            f"- tick {item.get('tick')}: {item.get('decisions')} | "
            f"Δunemployment={fmt(impact.get('unemployment_delta_pp'), 'pp')}, "
            f"ΔGDP={fmt(impact.get('gdp_delta_pct'), '%')}, "
            f"Δhealth={fmt(impact.get('mean_health_delta_pp'), 'pp')}, "
            f"Δdistress={fmt(impact.get('consumer_distress_delta_pct'), '%')} | "
            f"reason={reasoning}"
        )
    return "\n".join(lines)


def _format_regime_state(regime_state: Dict[str, Any]) -> str:
    """Render non-noisy simulation regime context for the policy agent."""

    if not regime_state:
        return "No regime context available."

    lines: List[str] = []
    for field, value in sorted(regime_state.items()):
        lines.append(f"- {field}: {value}")
    return "\n".join(lines)



def _format_money(value: Any) -> str:
    """Format a numeric value as compact dollars for the prompt."""
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _format_pct(value: Any) -> str:
    """Format a rate or pressure value as a percentage."""
    try:
        return f"{float(value) * 100.0:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _metric_trend(metrics_history: List[Dict[str, Any]], key: str, current: float) -> str:
    """Return a compact trend label comparing current value against recent history."""
    values = [
        row.get("metrics", {}).get(key)
        for row in metrics_history[-6:]
        if isinstance(row.get("metrics", {}).get(key), (int, float))
    ]
    if len(values) < 2:
        return "flat"
    baseline = sum(float(v) for v in values[:-1]) / max(1, len(values) - 1)
    if baseline == 0.0:
        return "flat"
    change = (float(current) - baseline) / abs(baseline)
    if change > 0.05:
        return "rising"
    if change < -0.05:
        return "falling"
    return "flat"


def _sector_status(distressed: int, shortage_active: bool, shortage_severity: float, avg_cash: float) -> str:
    """Map sector diagnostics to a stable status label."""
    if distressed > 0 or shortage_severity >= 60.0 or avg_cash <= 0.0:
        return "critical"
    if shortage_active or shortage_severity >= 25.0:
        return "watch"
    return "stable"


def _dominant_sector_driver(
    *,
    distressed: int,
    zero_cash: int,
    survival: int,
    burn: int,
    weak_demand: int,
    inventory_pressure: float,
    vacancy_pressure: float,
    shortage_driver: str,
    shortage_active: bool,
) -> str:
    """Choose a human-readable primary sector driver for the prompt."""
    if zero_cash > 0:
        return "zero_cash"
    if survival > 0:
        return "survival_mode"
    if burn > 0:
        return "burn_mode"
    if shortage_active and shortage_driver and shortage_driver != "stable":
        return f"shortage_{shortage_driver}"
    if weak_demand > 0:
        return "weak_demand"
    if inventory_pressure >= 0.35:
        return "low_inventory"
    if vacancy_pressure >= 0.10:
        return "labor_vacancies"
    if distressed > 0:
        return "general_distress"
    return "stable"


def build_sector_diagnostics(economy: Any) -> Dict[str, Dict[str, Any]]:
    """Build compact sector diagnostics for the LLM policy prompt."""
    shortage_by_sector = {
        str(row.get("sector", "")).lower(): row
        for row in (getattr(economy, "last_sector_shortage_diagnostics", []) or [])
    }
    sectors = ("food", "housing", "services", "healthcare")
    out: Dict[str, Dict[str, Any]] = {}

    for sector in sectors:
        firms = [f for f in economy.firms if (getattr(f, "good_category", "") or "").lower() == sector]
        shortage = shortage_by_sector.get(sector, {})
        distressed = 0
        zero_cash = 0
        survival = 0
        burn = 0
        weak_demand = 0
        total_cash = 0.0
        total_inventory = 0.0
        total_sold = 0.0
        total_employees = 0
        total_vacancies = 0
        total_price = 0.0

        for firm in firms:
            firm_cash = float(getattr(firm, "cash_balance", 0.0))
            total_cash += firm_cash
            total_inventory += max(0.0, float(getattr(firm, "inventory_units", 0.0)))
            total_sold += max(0.0, float(getattr(economy, "last_tick_sales_units", {}).get(firm.firm_id, 0.0)))
            total_employees += len(getattr(firm, "employees", []) or [])
            total_vacancies += max(0, int(getattr(firm, "planned_hires_count", 0) or 0))
            total_price += float(getattr(firm, "price", 0.0))
            is_survival = bool(getattr(firm, "survival_mode", False))
            is_burn = bool(getattr(firm, "burn_mode", False))
            is_zero_cash = firm_cash <= 0.0
            if is_survival:
                survival += 1
            if is_burn:
                burn += 1
            if is_zero_cash:
                zero_cash += 1
            if float(getattr(economy, "last_tick_sell_through_rate", {}).get(firm.firm_id, 0.5)) < 0.5:
                weak_demand += 1
            if is_survival or is_burn or is_zero_cash:
                distressed += 1

        firm_count = len(firms)
        avg_cash = total_cash / firm_count if firm_count else 0.0
        avg_price = total_price / firm_count if firm_count else 0.0
        sell_through = float(shortage.get("mean_sell_through_rate", 0.0) or 0.0)
        vacancy_pressure = float(shortage.get("vacancy_pressure", 0.0) or 0.0)
        inventory_pressure = float(shortage.get("inventory_pressure", 0.0) or 0.0)
        shortage_active = bool(shortage.get("shortage_active", False))
        shortage_severity = float(shortage.get("shortage_severity", 0.0) or 0.0)
        shortage_driver = str(shortage.get("primary_driver", "stable") or "stable")
        driver = _dominant_sector_driver(
            distressed=distressed,
            zero_cash=zero_cash,
            survival=survival,
            burn=burn,
            weak_demand=weak_demand,
            inventory_pressure=inventory_pressure,
            vacancy_pressure=vacancy_pressure,
            shortage_driver=shortage_driver,
            shortage_active=shortage_active,
        )

        out[sector] = {
            "status": _sector_status(distressed, shortage_active, shortage_severity, avg_cash),
            "driver": driver,
            "firms": firm_count,
            "distressed_firms": distressed,
            "zero_cash_firms": zero_cash,
            "survival_mode_firms": survival,
            "burn_mode_firms": burn,
            "weak_demand_firms": weak_demand,
            "avg_cash": avg_cash,
            "avg_price": avg_price,
            "labor": {
                "employees": total_employees,
                "vacancies": total_vacancies,
                "vacancy_pressure": vacancy_pressure,
            },
            "inventory": {
                "units": total_inventory,
                "sold_last_tick": total_sold,
                "sell_through": sell_through,
                "inventory_pressure": inventory_pressure,
            },
            "shortage": {
                "active": shortage_active,
                "severity": shortage_severity,
                "driver": shortage_driver,
            },
        }
    return out


def _format_sector_diagnostics(sector_diagnostics: Dict[str, Dict[str, Any]]) -> str:
    """Render sector diagnostics in the compact prompt format."""
    lines: List[str] = []
    for sector in ("food", "housing", "services", "healthcare"):
        data = sector_diagnostics.get(sector, {})
        labor = data.get("labor", {})
        inv = data.get("inventory", {})
        shortage = data.get("shortage", {})
        lines.append(
            f"- {sector.upper()}: Status: {data.get('status', 'unknown')} | "
            f"Driver: {data.get('driver', 'unknown')} | "
            f"Firms: {data.get('firms', 0)} active, {data.get('distressed_firms', 0)} distressed | "
            f"Cash: {_format_money(data.get('avg_cash', 0.0))} avg | "
            f"Labor: {labor.get('employees', 0)} workers, {labor.get('vacancies', 0)} vacancies, "
            f"vacancy_pressure={_format_pct(labor.get('vacancy_pressure', 0.0))} | "
            f"Inventory: {float(inv.get('units', 0.0)):.1f} units, sold={float(inv.get('sold_last_tick', 0.0)):.1f}, "
            f"sell_through={_format_pct(inv.get('sell_through', 0.0))}, "
            f"inventory_pressure={_format_pct(inv.get('inventory_pressure', 0.0))} | "
            f"Shortage: active={bool(shortage.get('active', False))}, "
            f"severity={float(shortage.get('severity', 0.0)):.1f}, driver={shortage.get('driver', 'stable')}"
        )
    return "\n".join(lines)

def _build_user_prompt(
    raw_metrics: Dict[str, Any],
    sector_diagnostics: Dict[str, Dict[str, Any]],
    current_policy: Optional[Dict[str, Any]] = None,
    budget_state: Optional[Dict[str, Any]] = None,
    regime_state: Optional[Dict[str, Any]] = None,
    tick: int = 0,
    recent_policy_memory: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build the user prompt for the government agent."""

    current_policy = current_policy or {}
    budget_state = budget_state or {}
    regime_state = regime_state or {}
    recent_policy_memory = recent_policy_memory or []
    active_firms = int(regime_state.get("active_firms_count", raw_metrics.get("total_firms", 0)) or 0)
    households = int(raw_metrics.get("total_households", 0) or 0)
    gdp = float(raw_metrics.get("gdp_this_tick", 0.0) or 0.0)
    gov_cash = float(raw_metrics.get("government_cash", budget_state.get("cash_balance", 0.0)) or 0.0)
    deficit = float(budget_state.get("last_tick_revenue", 0.0) or 0.0) - float(budget_state.get("last_tick_spending", 0.0) or 0.0)
    unemployment_pct = float(raw_metrics.get("unemployment_rate", 0.0) or 0.0) * 100.0
    mean_health = float(raw_metrics.get("mean_health", 0.0) or 0.0)
    mean_happiness = float(raw_metrics.get("mean_happiness", 0.0) or 0.0)
    gini = float(raw_metrics.get("gini_coefficient", 0.0) or 0.0)
    gdp_trend = _metric_trend(list(raw_metrics.get("_metrics_history", []) or []), "gdp_this_tick", gdp)

    current_policy_lines = "\n".join(
        f"- {lever}: {current_policy.get(lever)}"
        for lever in PROMPT_POLICY_LEVERS
        if lever in current_policy
    )

    return f"""[CURRENT ECONOMIC STATE]
REGIME: {regime_state.get('phase', 'unknown')}
ACTIVE FIRMS: {active_firms} | HOUSEHOLDS: {households} | TICK: {tick}
Regime state: warmup_active={regime_state.get('warmup_active', False)}, warmup_ticks_remaining={regime_state.get('warmup_ticks_remaining', 0)}, queued_firms_count={regime_state.get('queued_firms_count', 0)}

MACRO INDICATORS:
- GDP (Trend): {_format_money(gdp)} ({gdp_trend})
- Unemployment: {unemployment_pct:.1f}%
- Government Cash: {_format_money(gov_cash)} (Deficit/Surplus last tick: {_format_money(deficit)})
- Mean Health: {mean_health:.3f}
- Mean Happiness: {mean_happiness:.3f}
- Gini Coefficient: {gini:.3f}
- Fiscal Pressure: {float(budget_state.get('fiscal_pressure', 0.0) or 0.0):.3f}
- Spending Efficiency: {float(budget_state.get('spending_efficiency', 1.0) or 1.0):.3f}

[SECTOR DIAGNOSTICS]
{_format_sector_diagnostics(sector_diagnostics)}

[CURRENT POLICY SETTINGS]
{current_policy_lines}

[RECENT MEMORY & IMPACT]
Recent policy memory:
{_format_recent_policy_memory(recent_policy_memory)}

[RESPONSE FORMAT]
Respond with only valid JSON:
{{
  "reasoning": "Brief, 1-2 sentence explanation connecting sector diagnostics to your lever changes.",
  "changes": {{}}
}}"""

def _deterministic_rng(seed: int, tick: int, indicator: str) -> random.Random:
    """Return a deterministic RNG for one indicator observation."""

    indicator_seed = sum((idx + 1) * ord(ch) for idx, ch in enumerate(indicator))
    return random.Random(seed + tick * 104729 + indicator_seed * 17)


def _lookup_lagged_metric(economy: Any, indicator: str, lag: int, current_metrics: Dict[str, Any]) -> Any:
    """Read a metric from the history buffer with the requested lag."""

    if lag <= 0:
        return current_metrics.get(indicator)

    history = list(getattr(economy, "metrics_history", []) or [])
    if len(history) >= lag + 1:
        return history[-(lag + 1)]["metrics"].get(indicator)
    if history:
        return history[0]["metrics"].get(indicator)
    return current_metrics.get(indicator)


def _build_recent_policy_memory(
    decision_history: List[Dict[str, Any]],
    economy: Any,
    target_tick: int,
    lookback: int,
    impact_horizon: int,
) -> List[Dict[str, Any]]:
    """Build a compact memory of recent policy actions and observed follow-through."""

    recent = [item for item in decision_history if item.get("decisions")][-lookback:]
    history = list(getattr(economy, "metrics_history", []) or [])

    def row_at_or_before(tick: int) -> Optional[Dict[str, Any]]:
        for row in reversed(history):
            if int(row.get("tick", -1)) <= tick:
                return row.get("metrics", {})
        return None

    result: List[Dict[str, Any]] = []
    for item in recent:
        action_tick = int(item.get("tick", 0))
        baseline_tick = max(0, action_tick - 1)
        evaluation_tick = min(target_tick, action_tick + impact_horizon)
        baseline = row_at_or_before(baseline_tick)
        evaluation = row_at_or_before(evaluation_tick)

        def delta_pp(field: str) -> Optional[float]:
            """Delta for rate-like indicators expressed in percentage points."""
            if baseline is None or evaluation is None:
                return None
            b, e = baseline.get(field), evaluation.get(field)
            if b is None or e is None:
                return None
            return round((float(e) - float(b)) * 100, 2)

        def delta_pct(field: str) -> Optional[float]:
            """Delta for level indicators expressed as percent change."""
            if baseline is None or evaluation is None:
                return None
            b, e = baseline.get(field), evaluation.get(field)
            if b is None or e is None:
                return None
            b_float = float(b)
            if b_float == 0.0:
                return None
            return round((float(e) - b_float) / abs(b_float) * 100, 1)

        result.append(
            {
                "tick": action_tick,
                "decisions": dict(item.get("decisions", {})),
                "reasoning": item.get("reasoning", ""),
                "impact": {
                    "baseline_tick": baseline_tick,
                    "evaluation_tick": evaluation_tick,
                    "unemployment_delta_pp": delta_pp("unemployment_rate"),
                    "gdp_delta_pct": delta_pct("gdp_this_tick"),
                    "mean_health_delta_pp": delta_pp("mean_health"),
                    "consumer_distress_delta_pct": delta_pct("labor_seekers_wage_ineligible"),
                },
            }
        )
    return result


def observe_node(state: GovernmentState, economy: Any) -> Dict[str, Any]:
    """Pull raw metrics and current policy surface from the economy."""

    metrics = economy.get_economic_metrics()
    metrics["_metrics_history"] = list(getattr(economy, "metrics_history", []) or [])
    gov = economy.government
    current_policy = {
        "wage_tax_rate": gov.wage_tax_rate,
        "profit_tax_rate": gov.profit_tax_rate,
        "investment_tax_rate": gov.investment_tax_rate,
        "benefit_level": gov.benefit_level,
        "public_works": gov.public_works_toggle,
        "minimum_wage_policy": gov.minimum_wage_policy,
        "sector_subsidy_target": gov.sector_subsidy_target,
        "sector_subsidy_level": gov.sector_subsidy_level,
        "infrastructure_spending": gov.infrastructure_spending,
        "technology_spending": gov.technology_spending,
        "bailout_policy": gov.bailout_policy,
        "bailout_target": gov.bailout_target,
        "bailout_budget": gov.bailout_budget,
    }
    budget_state = {
        "cash_balance": float(gov.cash_balance),
        "last_tick_revenue": float(gov.last_tick_revenue),
        "last_tick_spending": float(gov.last_tick_spending),
        "deficit_ratio": float(metrics.get("deficit_ratio", 0.0)),
        "fiscal_pressure": float(gov.fiscal_pressure),
        "spending_efficiency": float(gov.spending_efficiency),
        "bailout_budget": float(gov.bailout_budget),
        "bailout_budget_remaining": float(gov.bailout_budget_remaining),
        "bailout_cycle_disbursed": float(gov.bailout_cycle_disbursed),
        "bailout_cycle_firms_assisted": int(gov.bailout_cycle_firms_assisted),
        "bailout_cycle_sector_spend": dict(gov.bailout_cycle_sector_spend),
        "last_cycle_bailout_authorized": float(gov.last_cycle_bailout_authorized),
        "last_cycle_bailout_disbursed": float(gov.last_cycle_bailout_disbursed),
        "last_cycle_bailout_remaining": float(gov.last_cycle_bailout_remaining),
        "last_cycle_bailout_firms_assisted": int(gov.last_cycle_bailout_firms_assisted),
        "last_cycle_bailout_sector_spend": dict(gov.last_cycle_bailout_sector_spend),
    }
    warmup_ticks = int(getattr(economy, "warmup_ticks", 0))
    regime_state = {
        "phase": "warmup" if bool(getattr(economy, "in_warmup", False)) else "open_market",
        "warmup_active": bool(getattr(economy, "in_warmup", False)),
        "warmup_ticks_remaining": max(0, warmup_ticks - int(economy.current_tick)),
        "queued_firms_count": int(len(getattr(economy, "queued_firms", []) or [])),
        "active_firms_count": int(len(getattr(economy, "firms", []) or [])),
    }
    return {
        "raw_metrics": metrics,
        "sector_diagnostics": build_sector_diagnostics(economy),
        "current_policy": current_policy,
        "budget_state": budget_state,
        "regime_state": regime_state,
        "tick": int(economy.current_tick),
    }


def apply_info_constraints_node(
    state: GovernmentState,
    economy: Any,
    config: Any,
    decision_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply lag, noise, and coverage gaps to raw economic observations; compute rolling summaries."""

    raw_metrics = state["raw_metrics"]
    tick = int(state["tick"])
    base_seed = int(getattr(getattr(economy, "config", None), "random_seed", 0) or 0)
    observed: Dict[str, Any] = {}
    data_quality_summary = {"reported": 0, "unavailable": 0}

    for indicator, (lag, noise_std, coverage) in INDICATOR_CONSTRAINTS.items():
        if indicator not in raw_metrics and not getattr(economy, "metrics_history", None):
            continue

        rng = _deterministic_rng(base_seed, tick, indicator)
        if rng.random() > coverage:
            observed[indicator] = {
                "value": None,
                "status": "unavailable",
                "last_available_tick": max(0, tick - lag - 1),
            }
            data_quality_summary["unavailable"] += 1
            continue

        true_value = _lookup_lagged_metric(economy, indicator, lag, raw_metrics)
        noisy_value = true_value
        if isinstance(true_value, (int, float)):
            scale = abs(float(true_value)) if float(true_value) != 0.0 else 1.0
            noisy_value = float(true_value) + rng.gauss(0.0, noise_std * scale)
            if indicator in RATE_LIKE_INDICATORS:
                noisy_value = max(0.0, min(1.0, noisy_value))
            elif indicator in {"total_firms", "bank_defaults_this_tick", "labor_cannot_work", "labor_seekers_wage_ineligible"}:
                noisy_value = max(0.0, round(noisy_value))

        observed[indicator] = {
            "value": round(noisy_value, 4) if isinstance(noisy_value, float) else noisy_value,
            "status": "reported",
            "data_age_ticks": int(lag),
            "estimated_accuracy": f"+/-{int(noise_std * 100)}%",
        }
        data_quality_summary["reported"] += 1

    # Compute rolling summaries for Tier-1 core indicators
    rolling_summaries: Dict[str, Dict[str, float]] = {}
    for indicator in TIER_1_CORE:
        rs = _compute_rolling_summary(economy, indicator)
        if rs:
            rolling_summaries[indicator] = rs

    recent_policy_memory = _build_recent_policy_memory(
        decision_history=decision_history,
        economy=economy,
        target_tick=tick,
        lookback=max(1, int(getattr(config, "government_history_window", 6))),
        impact_horizon=max(1, int(getattr(config, "government_impact_horizon", 8))),
    )
    return {
        "observed_metrics": observed,
        "rolling_summaries": rolling_summaries,
        "recent_policy_memory": recent_policy_memory,
        "data_quality_summary": data_quality_summary,
    }


def _enforce_cross_lever_consistency(
    validated: Dict[str, Any],
    current_policy: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove incoherent subsidy/bailout combinations from the validated decision dict."""

    merged = {**current_policy, **validated}

    # Subsidy coherence: target=none with level>0, or sector target with level=0
    target = merged.get("sector_subsidy_target")
    level = merged.get("sector_subsidy_level")
    if target == "none" and isinstance(level, int) and level > 0:
        logger.warning("Cross-lever: sector_subsidy_target=none with level=%s — dropping subsidy changes.", level)
        validated.pop("sector_subsidy_target", None)
        validated.pop("sector_subsidy_level", None)
    elif target in {"food", "housing", "services", "healthcare"} and isinstance(level, int) and level == 0:
        logger.warning("Cross-lever: sector_subsidy_target=%s with level=0 — dropping subsidy changes.", target)
        validated.pop("sector_subsidy_target", None)
        validated.pop("sector_subsidy_level", None)

    # Bailout coherence: policy=off with non-none target, or policy=sector with none target
    policy = merged.get("bailout_policy")
    bailout_target = merged.get("bailout_target")
    budget = merged.get("bailout_budget")
    if policy == "off":
        if bailout_target != "none" or (isinstance(budget, int) and budget > 0):
            logger.warning("Cross-lever: bailout_policy=off with active target/budget — dropping bailout changes.")
            validated.pop("bailout_policy", None)
            validated.pop("bailout_target", None)
            validated.pop("bailout_budget", None)
    elif policy == "sector" and bailout_target == "none":
        logger.warning("Cross-lever: bailout_policy=sector with target=none — dropping bailout changes.")
        validated.pop("bailout_policy", None)
        validated.pop("bailout_target", None)
        validated.pop("bailout_budget", None)

    return validated


def _validate_decisions(
    raw_decisions: Dict[str, Any],
    current_policy: Dict[str, Any],
    philosophy: str = "balanced",
) -> Dict[str, Any]:
    """Validate proposed decisions against the action space, step limits, and ideology ranges."""

    validated: Dict[str, Any] = {}
    resolved_levers = _resolve_continuous_levers(philosophy)

    for lever, value in raw_decisions.items():
        # Handle continuous levers (tax rates) with ideology-adjusted ranges
        if lever in resolved_levers:
            lo, hi = resolved_levers[lever]
            try:
                numeric_value = round(float(value), 4)
            except (TypeError, ValueError):
                logger.warning("Ignoring non-numeric value '%s' for continuous lever '%s'.", value, lever)
                continue
            if not (lo <= numeric_value <= hi):
                logger.warning(
                    "Ignoring out-of-range value %s for lever '%s' (valid: [%s, %s]).",
                    numeric_value, lever, lo, hi,
                )
                continue
            current_value = current_policy.get(lever)
            if current_value is not None and abs(numeric_value - float(current_value)) < 0.0001:
                continue
            validated[lever] = numeric_value
            continue

        # Handle discrete levers
        if lever not in VALID_LEVERS:
            logger.warning("Ignoring unknown government lever '%s'.", lever)
            continue
        if lever in {"sector_subsidy_level", "bailout_budget"}:
            try:
                value = int(value)
            except (TypeError, ValueError):
                logger.warning("Ignoring non-integer value '%s' for lever '%s'.", value, lever)
                continue
        if value not in VALID_LEVERS[lever]:
            logger.warning("Ignoring invalid value '%s' for lever '%s'.", value, lever)
            continue

        current_value = current_policy.get(lever)
        if value == current_value:
            continue

        ordered_values = ORDERED_LEVERS.get(lever)
        if ordered_values and current_value in ordered_values:
            if abs(ordered_values.index(value) - ordered_values.index(current_value)) > 1:
                logger.warning(
                    "Ignoring jump for lever '%s': %s -> %s exceeds one-step limit.",
                    lever,
                    current_value,
                    value,
                )
                continue

        validated[lever] = value

    validated = _enforce_cross_lever_consistency(validated, current_policy)
    return validated


async def decide_node(state: GovernmentState, provider: LLMProvider, config: Any) -> Dict[str, Any]:
    """Run the LLM decision step and validate the returned JSON."""

    started_at = time.perf_counter()
    philosophy = getattr(config, "government_philosophy", "balanced")
    system_prompt = _build_system_prompt(
        philosophy,
        num_households=int(state["raw_metrics"].get("total_households", 0)),
        num_firms=int(state["raw_metrics"].get("total_firms", 0)),
    )
    user_prompt = _build_user_prompt(
        raw_metrics=state["raw_metrics"],
        sector_diagnostics=state.get("sector_diagnostics", {}),
        current_policy=state["current_policy"],
        budget_state=state["budget_state"],
        regime_state=state.get("regime_state", {}),
        tick=int(state["tick"]),
        recent_policy_memory=state.get("recent_policy_memory", []),
    )
    if getattr(config, "no_think", False):
        user_prompt = user_prompt + "\n/no_think"

    try:
        response = await provider.complete(
            system=system_prompt,
            user=user_prompt,
            temperature=float(getattr(config, "government_temperature", 0.4)),
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        logger.error("Government LLM call failed: %s", exc)
        return {
            "llm_response": "",
            "decisions": {},
            "reasoning": f"LLM call failed: {exc}",
            "parse_ok": False,
            "elapsed_ms": elapsed_ms,
        }

    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    parsed = extract_json_from_response(response)
    if parsed is None:
        logger.warning("Government LLM returned non-JSON content.")
        return {
            "llm_response": response,
            "decisions": {},
            "reasoning": "Parse error - no changes applied",
            "parse_ok": False,
            "elapsed_ms": elapsed_ms,
        }

    raw_decisions = parsed.get("changes", parsed.get("decisions", {}))
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
    reasoning = str(parsed.get("reasoning", "No reasoning provided"))[:500]
    validated = _validate_decisions(raw_decisions, state["current_policy"], philosophy)
    return {
        "llm_response": response,
        "decisions": validated,
        "reasoning": reasoning,
        "parse_ok": True,
        "elapsed_ms": elapsed_ms,
    }


def fallback_node(state: GovernmentState) -> Dict[str, Any]:
    """Return a no-op decision state after an LLM failure."""

    return {
        "decisions": {},
        "reasoning": state.get("reasoning", "Fallback - no policy changes applied"),
        "parse_ok": False,
    }


def apply_node(state: GovernmentState, economy: Any) -> Dict[str, Any]:
    """Apply validated lever changes to the economy government object."""

    for lever, value in state.get("decisions", {}).items():
        economy.government.set_lever(lever, value)
    return state


def log_node(state: GovernmentState) -> Dict[str, Any]:
    """Emit a compact log line for the government cycle."""

    tick = int(state.get("tick", -1))
    elapsed_ms = float(state.get("elapsed_ms", 0.0))
    decisions = state.get("decisions", {})
    if decisions:
        logger.info("Tick %d | government_llm %.0fms | decisions=%s", tick, elapsed_ms, decisions)
    else:
        logger.info("Tick %d | government_llm %.0fms | no changes", tick, elapsed_ms)
    return state


def build_government_graph(
    provider: LLMProvider,
    config: Any,
    economy: Any,
    decision_history: List[Dict[str, Any]],
):
    """Build a LangGraph state machine when LangGraph is installed."""

    if not HAS_LANGGRAPH:
        return None

    graph = StateGraph(GovernmentState)

    def observe_step(state: GovernmentState) -> Dict[str, Any]:
        return observe_node(state, economy)

    def constrain_step(state: GovernmentState) -> Dict[str, Any]:
        return apply_info_constraints_node(state, economy, config, decision_history)

    async def decide_step(state: GovernmentState) -> Dict[str, Any]:
        return await decide_node(state, provider, config)

    def apply_step(state: GovernmentState) -> Dict[str, Any]:
        return apply_node(state, economy)

    def log_step(state: GovernmentState) -> Dict[str, Any]:
        return log_node(state)

    def fallback_step(state: GovernmentState) -> Dict[str, Any]:
        return fallback_node(state)

    def parse_success_check(state: GovernmentState) -> str:
        return "success" if state.get("parse_ok", False) else "failure"

    graph.add_node("observe", observe_step)
    graph.add_node("apply_info_constraints", constrain_step)
    graph.add_node("decide", decide_step)
    graph.add_node("apply", apply_step)
    graph.add_node("log", log_step)
    graph.add_node("fallback", fallback_step)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "apply_info_constraints")
    graph.add_edge("apply_info_constraints", "decide")
    graph.add_conditional_edges(
        "decide",
        parse_success_check,
        {"success": "apply", "failure": "fallback"},
    )
    graph.add_edge("apply", "log")
    graph.add_edge("fallback", "log")
    graph.add_edge("log", END)
    return graph.compile()


class LLMGovernmentAdvisor:
    """Government decision controller with optional LangGraph orchestration."""

    def __init__(self, provider: LLMProvider, config: Any):
        self.provider = provider
        self.config = config
        self._decision_history: List[Dict[str, Any]] = []

    async def decide(self, economy: Any) -> Dict[str, Any]:
        """Run one government decision cycle."""

        if HAS_LANGGRAPH:
            graph = build_government_graph(self.provider, self.config, economy, self._decision_history)
            state: GovernmentState = await graph.ainvoke({})
        else:
            state = observe_node({}, economy)
            state.update(apply_info_constraints_node(state, economy, self.config, self._decision_history))
            state.update(await decide_node(state, self.provider, self.config))
            if not state.get("parse_ok", False):
                state.update(fallback_node(state))
            else:
                apply_node(state, economy)
            log_node(state)

        economy.government.begin_decision_cycle()

        result = {
            "tick": int(state.get("tick", economy.current_tick)),
            "decisions": dict(state.get("decisions", {})),
            "reasoning": str(state.get("reasoning", "")),
            "elapsed_ms": float(state.get("elapsed_ms", 0.0)),
            "parse_ok": bool(state.get("parse_ok", False)),
            "provider": getattr(self.provider, "name", "unknown"),
            "observed_metrics": state.get("observed_metrics", {}),
            "rolling_summaries": state.get("rolling_summaries", {}),
            "data_quality_summary": state.get("data_quality_summary", {}),
            "current_policy_before": dict(state.get("current_policy", {})),
            "recent_policy_memory": list(state.get("recent_policy_memory", [])),
        }
        self._decision_history.append(result)
        return result

    @property
    def decision_history(self) -> List[Dict[str, Any]]:
        """Return all prior government decision cycles."""

        return list(self._decision_history)

    @property
    def last_decision(self) -> Optional[Dict[str, Any]]:
        """Return the most recent decision cycle."""

        return self._decision_history[-1] if self._decision_history else None
