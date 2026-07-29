
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
import re
import time
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from config import CONFIG
from fiscal_guards import (
    annualized_debt_to_gdp,
    can_fund_public_works_startup,
    fiscal_reserve_floor,
    projected_public_works_startup_cost,
    trailing_gdp,
)
from llm_provider import LLMProvider, extract_json_from_response
from policy_schema import (
    MAX_SUBSTANTIVE_CHANGES,
    ORDERED_LEVERS as POLICY_ORDERED_LEVERS,
    POLICY_GROUPS,
    POLICY_SCHEMA,
    PROMPT_POLICY_LEVERS,
    SIMPLE_ENUM_LEVERS,
    SPENDING_LEVERS,
    TAX_LIMITS,
    TAX_MAX_STEP,
    is_ordered_increase,
    is_spending_increase,
    is_tax_decrease,
    normalize_current_policy,
    render_policy_schema_for_prompt,
)

try:  # pragma: no cover - optional dependency
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - exercised through fallback path
    END = None
    StateGraph = None
    HAS_LANGGRAPH = False

logger = logging.getLogger(__name__)

LLM_HIDDEN_POLICY_LEVERS = set()


class GovernmentState(TypedDict, total=False):
    """State exchanged between observation / reasoning / apply nodes."""

    raw_metrics: Dict[str, Any]
    sector_diagnostics: Dict[str, Any]
    observed_metrics: Dict[str, Any]
    rolling_summaries: Dict[str, Dict[str, float]]
    current_policy: Dict[str, Any]
    allowed_action_mask: Dict[str, Any]
    budget_state: Dict[str, Any]
    regime_state: Dict[str, Any]
    recent_policy_memory: List[Dict[str, Any]]
    llm_response: str
    raw_changes: Dict[str, Any]
    accepted_llm_changes: Dict[str, Any]
    mechanical_corrections: Dict[str, Any]
    applied_changes: Dict[str, Any]
    decisions: Dict[str, Any]
    rejected_changes: List[Dict[str, Any]]
    llm_fiscal_mode: str
    computed_fiscal_mode: str
    fiscal_mode: str
    primary_goal: str
    rationale: str
    evidence: List[str]
    evidence_audit: List[Dict[str, Any]]
    reasoning: str
    decision_summary: str
    parse_ok: bool
    elapsed_ms: float
    tick: int
    data_seen: Dict[str, Any]
    short_term_impact: Dict[str, Any]
    mature_impact: Dict[str, Any]
    data_quality_summary: Dict[str, int]
    rolling_windows_used: List[int]
    decision_interval: int
    start_tick: int
    current_policy_before: Dict[str, Any]
    current_policy_after: Dict[str, Any]


CONTINUOUS_LEVERS: Dict[str, tuple] = dict(TAX_LIMITS)

VALID_LEVERS: Dict[str, set] = {
    **{lever: set(values) for lever, values in POLICY_ORDERED_LEVERS.items()},
    **{lever: set(values) for lever, values in SIMPLE_ENUM_LEVERS.items()},
}

ORDERED_LEVERS: Dict[str, List[Any]] = dict(POLICY_ORDERED_LEVERS)

# indicator_name -> (lag_ticks, noise_std_pct, coverage_pct)
INDICATOR_CONSTRAINTS: Dict[str, tuple] = {
    "government_cash": (0, 0.01, 1.0),
    "gov_revenue_this_tick": (1, 0.03, 1.0),
    "gov_spending_this_tick": (0, 0.01, 1.0),
    "gov_net_flow_this_tick": (0, 0.01, 1.0),
    "gov_transfer_spend_this_tick": (0, 0.01, 1.0),
    "gov_subsidy_spend_this_tick": (0, 0.03, 1.0),
    "gov_social_spend_this_tick": (0, 0.01, 1.0),
    "gov_infrastructure_spend_this_tick": (0, 0.01, 1.0),
    "gov_technology_spend_this_tick": (0, 0.01, 1.0),
    "gov_subsidy_cap_this_tick": (0, 0.01, 1.0),
    "gov_subsidy_denied_by_cap_this_tick": (0, 0.03, 1.0),
    "gov_post_warmup_stimulus_this_tick": (0, 0.01, 1.0),
    "gov_public_works_requested_startup_this_tick": (0, 0.01, 1.0),
    "gov_public_works_denied_by_budget_this_tick": (0, 0.01, 1.0),
    "gov_public_works_affordable_budget_this_tick": (0, 0.01, 1.0),
    "gov_public_works_jobs_authorized": (0, 0.01, 1.0),
    "annualized_debt_to_gdp": (0, 0.01, 1.0),
    "public_debt": (0, 0.01, 1.0),
    "unemployment_rate": (2, 0.05, 0.95),
    "mean_wage": (2, 0.08, 0.90),
    "median_wage": (2, 0.08, 0.90),
    "mean_price": (1, 0.06, 0.95),
    "median_price": (1, 0.06, 0.95),
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
    "social_happiness": (0, 0.01, 1.0),
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
    "price_increase_limited_count": (0, 0.01, 1.0),
    "rent_increase_limited_count": (0, 0.01, 1.0),
    "avg_sector_price_to_median_wage": (0, 0.03, 1.0),
    "housing_rent_to_median_wage": (0, 0.03, 1.0),
    "housing_unaffordable_count": (1, 0.05, 0.95),
    "homeless_household_count": (1, 0.05, 0.95),
}

RATE_LIKE_INDICATORS = {
    "unemployment_rate",
    "gini_coefficient",
    "mean_health",
    "mean_happiness",
    "wage_floor_binding_share",
}

COUNT_LIKE_INDICATORS = {
    "labor_seekers_wage_ineligible",
    "labor_cannot_work",
    "healthcare_queue_depth",
    "healthcare_denied_count",
    "public_works_jobs",
    "total_firms",
    "bank_defaults_this_tick",
    "distressed_firm_count",
    "distressed_food_firms",
    "distressed_housing_firms",
    "distressed_services_firms",
    "distressed_healthcare_firms",
    "bankruptcy_count",
    "last_cycle_bailout_firms_assisted",
    "price_increase_limited_count",
    "rent_increase_limited_count",
    "housing_unaffordable_count",
    "homeless_household_count",
}

ROLLING_WINDOWS: tuple = (13, 26, 52)

TIER_1_CORE: tuple = (
    "unemployment_rate", "gdp_this_tick", "mean_health", "mean_happiness",
    "gini_coefficient", "government_cash", "mean_wage", "median_wage",
    "mean_price", "median_price", "wage_floor_binding_share",
)

TIER_2_DISTRESS: tuple = (
    "distressed_food_firms", "distressed_housing_firms", "distressed_services_firms",
    "distressed_healthcare_firms", "bankruptcy_count", "bank_defaults_this_tick",
    "healthcare_queue_depth", "healthcare_denied_count",
    "labor_seekers_wage_ineligible", "labor_cannot_work",
    "gov_subsidy_denied_by_cap_this_tick", "gov_public_works_denied_by_budget_this_tick",
    "price_increase_limited_count", "rent_increase_limited_count",
    "housing_unaffordable_count", "homeless_household_count",
)

TIER_3_SLOW: tuple = (
    "infrastructure_productivity", "technology_quality", "total_firms",
    "effective_mean_quality", "public_works_jobs", "minimum_wage_floor",
    "unemployment_benefit", "annualized_debt_to_gdp", "public_debt",
    "social_happiness",
    "gov_subsidy_cap_this_tick", "gov_post_warmup_stimulus_this_tick",
    "gov_public_works_requested_startup_this_tick", "gov_public_works_affordable_budget_this_tick",
    "gov_public_works_jobs_authorized",
    "avg_sector_price_to_median_wage", "housing_rent_to_median_wage",
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
    return dict(CONTINUOUS_LEVERS)


def government_rolling_windows(config: Any = None) -> tuple:
    """Return LLM observation rolling windows aligned to decision cadence."""
    cfg = config or getattr(CONFIG, "llm", None)
    configured = getattr(cfg, "government_rolling_windows_ticks", None)
    if configured:
        return tuple(int(window) for window in configured if int(window) > 0)
    interval = max(1, int(getattr(cfg, "government_decision_interval", 26) or 26))
    return (
        max(4, interval // 2),
        interval,
        interval * 2,
    )


def _compute_rolling_summary(economy: Any, indicator: str, windows: Optional[tuple] = None) -> Dict[str, float]:
    """Compute unweighted rolling averages for one indicator from metrics_history."""
    windows = windows or government_rolling_windows(getattr(CONFIG, "llm", None))
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

    philosophy_label = str(philosophy or "balanced").strip() or "balanced"
    schema_text = render_policy_schema_for_prompt()

    return f"""ROLE: You are the AI Central Government of a simulated economy.
PHILOSOPHY: {philosophy_label}
OBJECTIVE: Maximize GDP and mean happiness while keeping unemployment low and maintaining a sustainable government cash balance.

CRITICAL SIMULATION RULES:
1. ONE-STEP LIMIT: You may only change a qualitative ordered lever by one step per decision cycle.
2. BOUNDARIES: Do not output values outside the specified valid ranges.
3. GROUPED LEVERS: Linked lever groups must form a coherent resulting policy state.
4. TAX STEP LIMIT: Tax levers may move by at most 0.05 per decision.
5. ACTIONS: Include at most 2 substantive policy instrument changes. Mechanical corrections do not count as LLM choices.
6. PUBLIC WORKS: public_works=on requires unemployment >= 25% and treasury cash sufficient for startup plus reserve.
7. OUTPUT: Return only valid JSON. Do not use markdown, comments, <think> tags, or text outside the JSON object.

POLICY SCHEMA:
{schema_text}

LEVER EFFECTS:
- wage_tax_rate higher: government revenue up, household take-home and consumption down.
- profit_tax_rate higher: government revenue up, firm cash and investment capacity down.
- investment_tax_rate higher: Higher investment_tax_rate taxes firm R&D directly; quality growth and R&D spending down.
- benefit_level higher: unemployed income up, reservation wages and fiscal cost up.
- public_works on: unemployment can fall quickly, government cash falls quickly.
- minimum_wage_policy higher: wage floor up; workers may earn more but fragile firms may hire less.
- infrastructure_spending: productivity rises slowly over many ticks.
- technology_spending: effective quality rises slowly, may improve demand.
- social_spending: happiness-only public-good support rises with funding, decays toward neutral when underfunded, and does not directly improve health.
- price_stabilization_level monitor/soft/strict: non-fiscal price-inflation control for the selected sector. Monitor only observes; soft/strict limit per-tick increases. It never cuts prices or forces below cost.
- rent_stabilization_level monitor/soft/strict: non-fiscal rent-inflation control. Monitor only observes; soft/strict slow rent increases. It never creates housing supply or subsidies.
- bailout_budget: rescue loans to failing firms; use only for specific distress.

CONSISTENCY RULES:
- bailout_policy=off requires bailout_target=none and bailout_budget=0.
- bailout_policy=sector requires bailout_target in [food, housing, services, healthcare] and bailout_budget > 0.
- bailout_policy=all requires bailout_target=none and bailout_budget > 0.
- price_stabilization_level=off requires price_stabilization_target=none.
- price_stabilization_level=monitor, soft, or strict requires price_stabilization_target not none.
- sector_subsidy_level=0 requires sector_subsidy_target=none.
- sector_subsidy_target not none requires sector_subsidy_level > 0.

RESPONSE FORMAT:
{{
  "fiscal_mode": "CASH_CRISIS|LOW_CASH|NORMAL|STRONG_SURPLUS",
  "primary_goal": "hold|stabilize_cash|essential_sector_support|reduce_unemployment|support_growth|unwind_spending",
  "rationale": "Short public explanation grounded in supplied data; do not include hidden chain-of-thought.",
  "evidence": ["2-5 exact metric_name=value references copied from the prompt"],
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
        """Render one observed metric line if it is available and meaningful."""
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
            avg_parts = []
            numeric_windows: List[int] = []
            for label, avg_value in sorted(rs.items(), key=lambda item: int(item[0].split("_")[1][:-1])):
                window = int(label.split("_")[1][:-1])
                numeric_windows.append(window)
                avg_parts.append(f"{window}t={avg_value}")
            trend = ""
            if len(numeric_windows) >= 2:
                short = rs.get(f"avg_{numeric_windows[0]}t")
                long = rs.get(f"avg_{numeric_windows[-1]}t")
                trend = _trend_arrow(value, short, long)
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
    """Render compact recent policy decision cards with data, rationale, and impact."""

    if not memory:
        return "No recent policy actions recorded."

    def fmt_delta(impact: Dict[str, Any], key: str, unit: str = "") -> str:
        """Format one stored policy-impact delta for prompt memory."""
        if not impact or impact.get("status") == "pending":
            return "pending"
        val = impact.get(key)
        if val is None:
            return "n/a"
        sign = "+" if float(val) >= 0 else ""
        return f"{sign}{val}{unit}"

    lines: List[str] = []
    for item in memory:
        short = item.get("short_term_impact", {}) or item.get("impact", {})
        mature = item.get("mature_impact", {}) or {}
        rationale = str(item.get("rationale", item.get("reasoning", "")))[:180]
        evidence = item.get("evidence") or []
        evidence_text = "; ".join(str(value) for value in evidence[:3]) if evidence else "none"
        rejected = item.get("rejected_changes") or []
        rejection_text = ""
        if rejected:
            parts = [
                f"{r.get('lever')}={r.get('value')} ({r.get('reason')})"
                for r in rejected[:3]
            ]
            rejection_text = f" rejected={'; '.join(parts)} |"
        short_label = "short_term_since_last_decision"
        if short.get("provisional"):
            short_label += " (provisional)"
        mature_status = mature.get("status", "pending")
        if mature_status == "pending":
            mature_text = "pending"
        else:
            mature_text = (
                f"GDP={fmt_delta(mature, 'gdp_delta_pct', '%')}, "
                f"unemployment={fmt_delta(mature, 'unemployment_delta_pp', 'pp')}, "
                f"happiness={fmt_delta(mature, 'mean_happiness_delta_pp', 'pp')}, "
                f"health={fmt_delta(mature, 'mean_health_delta_pp', 'pp')}, "
                f"cash={fmt_delta(mature, 'government_cash_delta')}, "
                f"net_flow={fmt_delta(mature, 'net_fiscal_flow_delta')}"
            )
        lines.extend(
            [
                f"- tick {item.get('tick')}: actions={item.get('decisions')} | accepted={item.get('accepted_llm_changes', {})} |{rejection_text}",
                f"  data_seen: {_format_data_seen(item.get('data_seen', {}))}",
                f"  rationale_then: {rationale or 'none'}",
                f"  evidence_then: {evidence_text}",
                (
                    f"  {short_label}: GDP={fmt_delta(short, 'gdp_delta_pct', '%')}, "
                    f"unemployment={fmt_delta(short, 'unemployment_delta_pp', 'pp')}, "
                    f"happiness={fmt_delta(short, 'mean_happiness_delta_pp', 'pp')}, "
                    f"health={fmt_delta(short, 'mean_health_delta_pp', 'pp')}, "
                    f"cash={fmt_delta(short, 'government_cash_delta')}, "
                    f"net_flow={fmt_delta(short, 'net_fiscal_flow_delta')}"
                ),
                f"  mature_after_impact_horizon: {mature_text}",
            ]
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


def _format_action_mask(mask: Dict[str, Any]) -> tuple[str, str]:
    """Render dynamic allowed and blocked policy moves for the prompt."""

    allowed = mask.get("allowed", {}) if mask else {}
    blocked = mask.get("blocked", {}) if mask else {}
    allowed_simple = allowed.get("simple", allowed)
    allowed_groups = allowed.get("groups", {})
    blocked_simple = blocked.get("simple", blocked)
    blocked_groups = blocked.get("groups", {})
    allowed_lines = []
    for lever in PROMPT_POLICY_LEVERS:
        if lever in LLM_HIDDEN_POLICY_LEVERS:
            continue
        values = allowed_simple.get(lever)
        if values:
            allowed_lines.append(f"- {lever}: {values}")
    for group, combos in sorted(allowed_groups.items()):
        if combos:
            rendered = "; ".join(str(combo) for combo in combos[:8])
            allowed_lines.append(f"- group {group}: {rendered}")
    blocked_lines = []
    for lever in PROMPT_POLICY_LEVERS:
        if lever in LLM_HIDDEN_POLICY_LEVERS:
            continue
        values = blocked_simple.get(lever)
        if values:
            rendered = "; ".join(f"{item.get('value')} ({item.get('reason')})" for item in values[:4])
            blocked_lines.append(f"- {lever}: {rendered}")
    for group, values in sorted(blocked_groups.items()):
        if values:
            rendered = "; ".join(f"{item.get('value')} ({item.get('reason')})" for item in values[:4])
            blocked_lines.append(f"- group {group}: {rendered}")
    return (
        "\n".join(allowed_lines) if allowed_lines else "No validator-accepted changes from the candidate set.",
        "\n".join(blocked_lines) if blocked_lines else "No blocked candidate moves from the one-step action space.",
    )


def _format_recent_rejections(memory: List[Dict[str, Any]]) -> str:
    """Render recent sanitizer rejections without policy retry advice."""

    lines: List[str] = []
    for item in memory[-6:]:
        for rejection in item.get("rejected_changes", []) or []:
            lever = rejection.get("lever")
            value = rejection.get("value")
            reason = str(rejection.get("reason", ""))
            lines.append(
                f"- tick {item.get('tick')}: {lever}={value}; reason={reason}"
            )
    if lines:
        return "\n".join(lines)
    return "No recent rejected changes. Only values shown as validator-accepted are structurally available this cycle."


def _format_policy_impact_memory(memory: List[Dict[str, Any]]) -> str:
    """Render raw policy impact memory without recommendations."""

    lines: List[str] = []
    for item in memory[-6:]:
        applied = item.get("applied_changes") or item.get("decisions")
        if not applied:
            continue
        short = item.get("short_term_impact", {}) or item.get("impact", {})
        mature = item.get("mature_impact", {})
        lines.append(
            f"- tick {item.get('tick')}: accepted={item.get('accepted_llm_changes', item.get('decisions', {}))}, "
            f"mechanical={item.get('mechanical_corrections', {})}, rejected={item.get('rejected_changes', [])} | "
            f"short={short.get('status', 'available')}@{short.get('evaluation_tick', 'n/a')} | "
            f"GDP {short.get('gdp_delta_pct', 'n/a')}%, "
            f"unemployment {short.get('unemployment_delta_pp', 'n/a')}pp, "
            f"happiness {short.get('mean_happiness_delta_pp', 'n/a')}pp, "
            f"health {short.get('mean_health_delta_pp', 'n/a')}pp, "
            f"gov_cash {short.get('government_cash_delta', 'n/a')}, "
            f"net_flow {short.get('net_fiscal_flow_delta', 'n/a')} | "
            f"mature={mature.get('status', 'pending')}@{mature.get('evaluation_tick', mature.get('available_at_tick', 'n/a'))}"
        )
    return "\n".join(lines) if lines else "No accepted policy impact available yet."


FISCAL_MODES = {"CASH_CRISIS", "LOW_CASH", "NORMAL", "STRONG_SURPLUS"}
PRIMARY_GOALS = {
    "hold",
    "stabilize_cash",
    "essential_sector_support",
    "reduce_unemployment",
    "support_growth",
    "unwind_spending",
}


def _normalize_fiscal_mode(value: Any) -> str:
    """Return a known fiscal mode, defaulting invalid model output to NORMAL."""
    mode = str(value or "NORMAL").strip().upper()
    return mode if mode in FISCAL_MODES else "NORMAL"


def _normalize_primary_goal(value: Any) -> str:
    """Return a known primary policy goal, defaulting invalid output to hold."""
    goal = str(value or "hold").strip().lower()
    return goal if goal in PRIMARY_GOALS else "hold"


def _decision_summary_reasoning(
    fiscal_mode: str,
    primary_goal: str,
    validated: Dict[str, Any],
    rejected: List[Dict[str, Any]],
) -> str:
    """Build a short human-readable summary of accepted and rejected changes."""
    accepted_text = ", ".join(f"{key}={value}" for key, value in validated.items()) or "no accepted changes"
    if rejected:
        rejected_text = "; ".join(
            f"{r.get('lever')}={r.get('value')} ({r.get('reason')})"
            for r in rejected[:3]
        )
        return f"{fiscal_mode}/{primary_goal}; accepted: {accepted_text}; rejected: {rejected_text}"
    return f"{fiscal_mode}/{primary_goal}; accepted: {accepted_text}"


def computed_fiscal_mode_from_state(government: Any, recent_gdp: float, fiscal_pressure: float = 0.0) -> str:
    """Classify fiscal state for evaluation logging without overriding the LLM."""
    cash = float(getattr(government, "cash_balance", 0.0) or 0.0)
    reserve = fiscal_reserve_floor(max(1.0, float(recent_gdp or 0.0)))
    debt_ratio = annualized_debt_to_gdp(government, max(1.0, float(recent_gdp or 0.0)))
    pressure = float(fiscal_pressure or 0.0)
    if cash < 0.0 or debt_ratio >= 1.0 or pressure >= 0.30:
        return "CASH_CRISIS"
    if cash < reserve or pressure >= 0.15:
        return "LOW_CASH"
    if cash >= reserve * 3.0 and debt_ratio < 0.50:
        return "STRONG_SURPLUS"
    return "NORMAL"



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


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to float for compact fiscal/memory summaries."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _round_metric(value: Any, digits: int = 4) -> Optional[float]:
    """Return a rounded float or None when the metric is unavailable."""
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _net_fiscal_flow(metrics: Dict[str, Any]) -> float:
    """Revenue minus spending for one tick/window metrics row."""
    if metrics.get("gov_net_flow_this_tick") is not None:
        return _safe_float(metrics.get("gov_net_flow_this_tick"))
    return _safe_float(metrics.get("gov_revenue_this_tick")) - _safe_float(metrics.get("gov_spending_this_tick"))


def _normalize_evidence(value: Any) -> List[str]:
    """Normalize model evidence into 2-5 short strings when available."""
    if isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = [value]
    else:
        return []

    evidence: List[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        evidence.append(text[:160])
        if len(evidence) >= 5:
            break
    return evidence


def _extract_evidence_key_value(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract a metric/policy key and optional cited value from one evidence string."""
    if re.search(r"\b[A-Za-z]+_\s+[A-Za-z]", text):
        return None, None, "whitespace_inside_key"
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|:)\s*(.+?)\s*$", text)
    if not match:
        return None, None, "missing_key_value_separator"
    return match.group(1), match.group(2), None


def _numeric_prefix(value: Any) -> Optional[float]:
    """Return the first numeric token in a value-like string, if present."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = re.search(r"[-+]?\$?\s*([-+]?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _values_close(cited: Any, actual: Any) -> bool:
    """Loose equality for evidence citations; audit only, never validation."""
    cited_num = _numeric_prefix(cited)
    actual_num = _numeric_prefix(actual)
    if cited_num is not None and actual_num is not None:
        tolerance = max(0.05, abs(actual_num) * 0.02)
        return abs(cited_num - actual_num) <= tolerance
    cited_text = str(cited).strip().lower()
    actual_text = str(actual).strip().lower()
    return cited_text == actual_text or actual_text in cited_text


def _audit_evidence(
    evidence: List[str],
    state: GovernmentState,
) -> List[Dict[str, Any]]:
    """Classify whether model evidence refers to data/policy shown to it."""
    raw_metrics = state.get("raw_metrics", {}) or {}
    observed_metrics = state.get("observed_metrics", {}) or {}
    budget_state = state.get("budget_state", {}) or {}
    sector_diagnostics = state.get("sector_diagnostics", {}) or {}
    current_policy = state.get("current_policy", {}) or {}
    data_seen = state.get("data_seen", {}) or {}

    metric_values: Dict[str, Any] = {}
    for key, value in raw_metrics.items():
        metric_values[str(key)] = value
    for key, value in budget_state.items():
        if key == "spending_breakdown":
            continue
        metric_values[str(key)] = value
    for key, value in data_seen.items():
        metric_values[str(key)] = value
    for key, entry in observed_metrics.items():
        if isinstance(entry, dict) and entry.get("status") == "reported":
            metric_values[str(key)] = entry.get("value")
    for key, value in sector_diagnostics.items():
        metric_values[str(key)] = value

    audit: List[Dict[str, Any]] = []
    for item in evidence:
        text = str(item)
        key, cited_value, format_issue = _extract_evidence_key_value(text)
        record: Dict[str, Any] = {"evidence": text}
        if format_issue:
            record.update({"status": "format_issue", "issue": format_issue})
        elif key in metric_values:
            actual = metric_values.get(key)
            status = (
                "matched_metric"
                if cited_value is None or isinstance(actual, dict) or _values_close(cited_value, actual)
                else "value_mismatch"
            )
            record.update({"status": status, "key": key, "actual_value": actual})
        elif key in current_policy:
            actual = current_policy.get(key)
            status = "matched_policy" if cited_value is None or _values_close(cited_value, actual) else "value_mismatch"
            record.update({"status": status, "key": key, "actual_value": actual})
        else:
            record.update({"status": "unknown_key", "key": key})
        audit.append(record)
    return audit


def _spending_breakdown_from_metrics(raw_metrics: Dict[str, Any], budget_state: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Build compact policy-bucket spending attribution from current telemetry."""
    budget_state = budget_state or {}
    existing = budget_state.get("spending_breakdown")
    if isinstance(existing, dict) and existing:
        return {str(key): _safe_float(value) for key, value in existing.items()}

    infrastructure_technology = (
        _safe_float(raw_metrics.get("gov_infrastructure_spend_this_tick"))
        + _safe_float(raw_metrics.get("gov_technology_spend_this_tick"))
    )
    stimulus = _safe_float(raw_metrics.get("gov_post_warmup_stimulus_this_tick"))
    bond_purchases = _safe_float(raw_metrics.get("gov_bond_purchases_this_tick"))
    breakdown = {
        "unemployment_benefits_transfers": _safe_float(raw_metrics.get("gov_transfer_spend_this_tick")),
        "social_spending": _safe_float(raw_metrics.get("gov_social_spend_this_tick")),
        "sector_subsidies": _safe_float(raw_metrics.get("gov_subsidy_spend_this_tick")),
        "public_works": _safe_float(raw_metrics.get("gov_public_works_capitalization_this_tick")),
        "bailouts": _safe_float(raw_metrics.get("gov_bailout_spend_this_tick")),
        "infrastructure_technology": infrastructure_technology,
        "bond_purchases": bond_purchases,
        "stimulus": stimulus,
    }
    return breakdown


def _build_data_seen_snapshot(raw_metrics: Dict[str, Any], budget_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Capture the compact state shown to the model for later before/after judgement."""
    budget_state = budget_state or {}
    revenue = _safe_float(budget_state.get("last_tick_revenue", raw_metrics.get("gov_revenue_this_tick")))
    spending = _safe_float(budget_state.get("last_tick_spending", raw_metrics.get("gov_spending_this_tick")))
    net_flow = _safe_float(budget_state.get("net_flow", raw_metrics.get("gov_net_flow_this_tick", revenue - spending)))
    return {
        "gdp_this_tick": _round_metric(raw_metrics.get("gdp_this_tick"), 2),
        "unemployment_rate": _round_metric(raw_metrics.get("unemployment_rate"), 4),
        "mean_happiness": _round_metric(raw_metrics.get("mean_happiness"), 4),
        "mean_health": _round_metric(raw_metrics.get("mean_health"), 4),
        "government_cash": _round_metric(raw_metrics.get("government_cash", budget_state.get("cash_balance")), 2),
        "gov_revenue_this_tick": round(revenue, 2),
        "gov_spending_this_tick": round(spending, 2),
        "gov_net_flow_this_tick": round(net_flow, 2),
        "fiscal_pressure_ratio": _round_metric(
            budget_state.get("fiscal_pressure", raw_metrics.get("fiscal_pressure")),
            4,
        ),
        "instant_deficit_to_gdp_ratio": _round_metric(
            budget_state.get("fiscal_pressure_instant_ratio", raw_metrics.get("fiscal_pressure_instant_ratio")),
            4,
        ),
    }


def _format_data_seen(data_seen: Dict[str, Any]) -> str:
    """Render compact data snapshot inside decision memory."""
    if not data_seen:
        return "data_seen=unavailable"
    keys = (
        "gdp_this_tick",
        "unemployment_rate",
        "mean_happiness",
        "mean_health",
        "government_cash",
        "gov_revenue_this_tick",
        "gov_spending_this_tick",
        "gov_net_flow_this_tick",
        "fiscal_pressure_ratio",
        "instant_deficit_to_gdp_ratio",
    )
    parts = [f"{key}={data_seen.get(key)}" for key in keys if data_seen.get(key) is not None]
    return ", ".join(parts) if parts else "data_seen=unavailable"


def _format_spending_breakdown(breakdown: Dict[str, float]) -> str:
    """Render fiscal policy-bucket spending compactly."""
    ordered_keys = (
        "unemployment_benefits_transfers",
        "social_spending",
        "sector_subsidies",
        "public_works",
        "bailouts",
        "infrastructure_technology",
        "bond_purchases",
        "stimulus",
    )
    lines = []
    for key in ordered_keys:
        lines.append(f"- {key}: {_format_money(breakdown.get(key, 0.0))}")
    return "\n".join(lines)


def _format_fiscal_context(
    raw_metrics: Dict[str, Any],
    budget_state: Dict[str, Any],
) -> str:
    """Render compact fiscal context for decisions without dumping ledgers."""
    revenue = _safe_float(budget_state.get("last_tick_revenue", raw_metrics.get("gov_revenue_this_tick")))
    spending = _safe_float(budget_state.get("last_tick_spending", raw_metrics.get("gov_spending_this_tick")))
    net_flow = _safe_float(budget_state.get("net_flow", raw_metrics.get("gov_net_flow_this_tick", revenue - spending)))
    cash = _safe_float(budget_state.get("cash_balance", raw_metrics.get("government_cash")))
    breakdown = _spending_breakdown_from_metrics(raw_metrics, budget_state)
    return (
        f"- Revenue this tick/window: {_format_money(revenue)}\n"
        f"- Spending this tick/window: {_format_money(spending)}\n"
        f"- Net fiscal flow: {_format_money(net_flow)}\n"
        f"- Current cash balance: {_format_money(cash)}\n"
        f"- fiscal_pressure_ratio: {_safe_float(budget_state.get('fiscal_pressure')):.4f}\n"
        f"- instant_deficit_to_gdp_ratio: {_safe_float(budget_state.get('fiscal_pressure_instant_ratio')):.4f}\n"
        f"- fiscal_pressure_denominator_gdp: {_format_money(budget_state.get('fiscal_pressure_denominator_gdp'))}\n"
        f"- Spending efficiency: {_safe_float(budget_state.get('spending_efficiency'), 1.0):.3f}\n"
        "Spending Breakdown:\n"
        f"{_format_spending_breakdown(breakdown)}"
    )


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
    cached_wages = getattr(economy, "cached_wage_percentiles", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
    median_wage = float(cached_wages[1] if len(cached_wages) > 1 else 0.0) if cached_wages else 0.0
    baseline_prices = getattr(CONFIG, "baseline_prices", {}) or {}

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
        baseline_key = sector.capitalize()
        baseline_price = float(baseline_prices.get(baseline_key, avg_price or 1.0) or 1.0)
        price_to_baseline = avg_price / max(1.0, baseline_price)
        price_to_median_wage = avg_price / max(1.0, median_wage)
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
            "baseline_price": baseline_price,
            "price_to_baseline": price_to_baseline,
            "price_to_median_wage": price_to_median_wage,
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
        if sector == "housing":
            housing_diag = getattr(economy, "last_housing_diagnostics", {}) or {}
            out[sector]["homeless_households"] = int(float(housing_diag.get("homeless_household_count", 0.0) or 0.0))
            out[sector]["unaffordable_failures"] = int(float(housing_diag.get("housing_unaffordable_count", 0.0) or 0.0))
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
            f"Price: avg={_format_money(data.get('avg_price', 0.0))}, baseline={_format_money(data.get('baseline_price', 0.0))}, "
            f"price/baseline={float(data.get('price_to_baseline', 0.0)):.2f}, "
            f"price/median_wage={float(data.get('price_to_median_wage', 0.0)):.2f} | "
            f"Labor: {labor.get('employees', 0)} workers, {labor.get('vacancies', 0)} vacancies, "
            f"vacancy_pressure={_format_pct(labor.get('vacancy_pressure', 0.0))} | "
            f"Inventory: {float(inv.get('units', 0.0)):.1f} units, sold={float(inv.get('sold_last_tick', 0.0)):.1f}, "
            f"sell_through={_format_pct(inv.get('sell_through', 0.0))}, "
            f"inventory_pressure={_format_pct(inv.get('inventory_pressure', 0.0))} | "
            f"Shortage: active={bool(shortage.get('active', False))}, "
            f"severity={float(shortage.get('severity', 0.0)):.1f}, driver={shortage.get('driver', 'stable')}"
            + (
                f" | Housing: homeless={data.get('homeless_households', 0)}, unaffordable_failures={data.get('unaffordable_failures', 0)}"
                if sector == "housing" else ""
            )
        )
    return "\n".join(lines)


def _build_affordability_diagnostics(
    raw_metrics: Dict[str, Any],
    sector_diagnostics: Dict[str, Dict[str, Any]],
) -> str:
    """Render wage, price, and rent burden diagnostics for the LLM."""
    mean_wage = float(raw_metrics.get("mean_wage", 0.0) or 0.0)
    median_wage = float(raw_metrics.get("median_wage", 0.0) or 0.0)
    wage_floor = float(raw_metrics.get("minimum_wage_floor", 0.0) or 0.0)
    benefit = float(raw_metrics.get("unemployment_benefit", 0.0) or 0.0)
    mean_price = float(raw_metrics.get("mean_price", 0.0) or 0.0)
    median_price = float(raw_metrics.get("median_price", 0.0) or 0.0)
    lines = [
        f"- Wages: mean={_format_money(mean_wage)}, median={_format_money(median_wage)}, "
        f"wage_floor={_format_money(wage_floor)}, unemployment_benefit={_format_money(benefit)}",
        f"- Global Firm Prices: mean={_format_money(mean_price)}, median={_format_money(median_price)}",
    ]
    for sector in ("food", "housing", "services", "healthcare"):
        data = sector_diagnostics.get(sector, {})
        avg_price = float(data.get("avg_price", 0.0) or 0.0)
        baseline = float(data.get("baseline_price", 0.0) or 0.0)
        lines.append(
            f"- {sector}: avg_price={_format_money(avg_price)}, baseline={_format_money(baseline)}, "
            f"price/baseline={float(data.get('price_to_baseline', 0.0) or 0.0):.2f}, "
            f"price/median_wage={float(data.get('price_to_median_wage', 0.0) or 0.0):.2f}"
        )
    lines.append(
        f"- Housing Rent Burden: rent/median_wage={float(raw_metrics.get('housing_rent_to_median_wage', 0.0) or 0.0):.2f}, "
        f"homeless={int(float(raw_metrics.get('homeless_household_count', 0.0) or 0.0))}, "
        f"homeless/population={float(raw_metrics.get('homeless_household_count', 0.0) or 0.0) / max(1.0, float(raw_metrics.get('total_households', 0.0) or 0.0)):.1%}, "
        f"unaffordable_failures={int(float(raw_metrics.get('housing_unaffordable_count', 0.0) or 0.0))}"
    )
    lines.append(
        f"- Stabilization Telemetry: price_level={raw_metrics.get('price_stabilization_level', 'off')}, "
        f"price_target={raw_metrics.get('price_stabilization_active_sector', 'none')}, "
        f"rent_level={raw_metrics.get('rent_stabilization_level', 'off')}, "
        f"price_caps_triggered={int(float(raw_metrics.get('price_increase_limited_count', 0.0) or 0.0))}, "
        f"rent_caps_triggered={int(float(raw_metrics.get('rent_increase_limited_count', 0.0) or 0.0))}"
    )
    lines.append(
        "- Meaning: price/baseline compares current sector price to normal starting price; "
        "price/median_wage and rent/median_wage compare one unit of cost to the typical wage; "
        "homeless/population is the share of households without housing; "
        "caps_triggered counts firms whose attempted price or rent increase was slowed this tick."
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
    allowed_action_mask: Optional[Dict[str, Any]] = None,
    observed_metrics: Optional[Dict[str, Any]] = None,
    rolling_summaries: Optional[Dict[str, Dict[str, float]]] = None,
    data_quality_summary: Optional[Dict[str, int]] = None,
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
    labor_force_unemployment_pct = float(raw_metrics.get("labor_force_unemployment_rate", raw_metrics.get("unemployment_rate", 0.0)) or 0.0) * 100.0
    jobless_total_pct = float(raw_metrics.get("jobless_rate_total_population", raw_metrics.get("unemployment_rate", 0.0)) or 0.0) * 100.0
    cannot_work_pct = float(raw_metrics.get("cannot_work_rate", 0.0) or 0.0) * 100.0
    cannot_work_count = int(float(raw_metrics.get("cannot_work_count", 0.0) or 0.0))
    labor_force_size = int(float(raw_metrics.get("labor_force_size", 0.0) or 0.0))
    mean_health = float(raw_metrics.get("mean_health", 0.0) or 0.0)
    mean_happiness = float(raw_metrics.get("mean_happiness", 0.0) or 0.0)
    gini = float(raw_metrics.get("gini_coefficient", 0.0) or 0.0)
    gdp_trend = _metric_trend(list(raw_metrics.get("_metrics_history", []) or []), "gdp_this_tick", gdp)
    allowed_text, blocked_text = _format_action_mask(allowed_action_mask or {})
    affordability_text = _build_affordability_diagnostics(raw_metrics, sector_diagnostics)
    observed_text = _format_observed_metrics(observed_metrics or {}, rolling_summaries or {})
    fiscal_context_text = _format_fiscal_context(raw_metrics, budget_state)
    data_quality_summary = data_quality_summary or {}

    current_policy_lines = "\n".join(
        f"- {lever}: {current_policy.get(lever)}"
        for lever in PROMPT_POLICY_LEVERS
        if lever not in LLM_HIDDEN_POLICY_LEVERS
        if lever in current_policy
    )

    return f"""[OBSERVED ECONOMIC DATA]
Use these as the government's observed indicators. They may be lagged, noisy, unavailable, or averaged.
Data quality: reported={data_quality_summary.get('reported', 0)}, unavailable={data_quality_summary.get('unavailable', 0)}
{observed_text}

[CURRENT ECONOMIC STATE]
REGIME: {regime_state.get('phase', 'unknown')}
ACTIVE FIRMS: {active_firms} | HOUSEHOLDS: {households} | TICK: {tick}
Regime state: warmup_active={regime_state.get('warmup_active', False)}, warmup_ticks_remaining={regime_state.get('warmup_ticks_remaining', 0)}, queued_firms_count={regime_state.get('queued_firms_count', 0)}

MACRO INDICATORS:
- GDP (Trend): {_format_money(gdp)} ({gdp_trend})
- Recent GDP Estimate: {_format_money(budget_state.get('recent_gdp', raw_metrics.get('recent_gdp', gdp)))}
- Headline Unemployment Metric: {unemployment_pct:.1f}%
- Labor Force Unemployment: {labor_force_unemployment_pct:.1f}%
- Jobless Total Population: {jobless_total_pct:.1f}%
- Cannot Work: {cannot_work_pct:.1f}% ({cannot_work_count} households) | Labor Force Size: {labor_force_size}
- Government Cash: {_format_money(gov_cash)} (Deficit/Surplus last tick: {_format_money(deficit)})
- Public Debt: {_format_money(raw_metrics.get('public_debt', budget_state.get('public_debt', 0.0)))} (Debt/GDP annualized: {float(raw_metrics.get('annualized_debt_to_gdp', budget_state.get('annualized_debt_to_gdp', 0.0)) or 0.0):.3f})
- Subsidy Cap: {_format_money(raw_metrics.get('gov_subsidy_cap_this_tick', 0.0))} (denied by cap: {_format_money(raw_metrics.get('gov_subsidy_denied_by_cap_this_tick', 0.0))})
- Public Works Budget Denied: {_format_money(raw_metrics.get('gov_public_works_denied_by_budget_this_tick', 0.0))}
- Post-Warmup Stimulus: {_format_money(raw_metrics.get('gov_post_warmup_stimulus_this_tick', 0.0))}
- Mean Health: {mean_health:.3f}
- Mean Happiness: {mean_happiness:.3f}
- Gini Coefficient: {gini:.3f}
- fiscal_pressure_ratio: {float(budget_state.get('fiscal_pressure', 0.0) or 0.0):.4f}
- instant_deficit_to_gdp_ratio: {float(budget_state.get('fiscal_pressure_instant_ratio', 0.0) or 0.0):.4f}
- Spending Efficiency: {float(budget_state.get('spending_efficiency', 1.0) or 1.0):.3f}

[FISCAL CONTEXT]
{fiscal_context_text}

[LABOR METRIC DEFINITIONS]
- labor_force_unemployment_rate: can-work households without jobs divided by labor-force households.
- jobless_rate_total_population: all households without jobs divided by total households.
- cannot_work_rate: households unavailable for work due to health, training, or similar constraints divided by total households.

[SECTOR DIAGNOSTICS]
{_format_sector_diagnostics(sector_diagnostics)}

[AFFORDABILITY DIAGNOSTICS]
{affordability_text}

[CURRENT POLICY SETTINGS]
{current_policy_lines}

[RECENT MEMORY & IMPACT]
Recent policy memory:
Short-term outcomes are provisional when the decision interval is shorter than the configured impact horizon; mature outcomes appear only after enough ticks have elapsed.
{_format_recent_policy_memory(recent_policy_memory)}

[RECENT REJECTED CHANGES]
{_format_recent_rejections(recent_policy_memory)}

[RECENT POLICY IMPACT]
{_format_policy_impact_memory(recent_policy_memory)}

[ALLOWED NEXT POLICY CHANGES]
Validator-accepted next raw changes. For grouped instruments, output a complete combination if changing that instrument.
{allowed_text}

[BLOCKED POLICY CHANGES]
Candidate changes currently rejected by the validator.
{blocked_text}

[RESPONSE FORMAT]
Respond with only valid JSON:
Do not include markdown, <think>, hidden chain-of-thought, or keys other than fiscal_mode, primary_goal, rationale, evidence, changes.
{{
  "fiscal_mode": "CASH_CRISIS|LOW_CASH|NORMAL|STRONG_SURPLUS",
  "primary_goal": "hold|stabilize_cash|essential_sector_support|reduce_unemployment|support_growth|unwind_spending",
  "rationale": "Concise public explanation grounded in the data shown above.",
  "evidence": ["2-5 exact metric_name=value references copied from the prompt"],
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
    """Build compact before/after judgement cards for recent policy decisions."""

    recent = [
        item for item in decision_history
        if (
            item.get("decisions")
            or item.get("rejected_changes")
            or item.get("rationale")
            or item.get("reasoning")
        )
    ][-lookback:]
    history = list(getattr(economy, "metrics_history", []) or [])

    def row_at_or_before(tick: int) -> Optional[Dict[str, Any]]:
        """Return the newest metrics row at or before a requested tick."""
        for row in reversed(history):
            if int(row.get("tick", -1)) <= tick:
                return row.get("metrics", {})
        return None

    def metric_net_flow(row: Optional[Dict[str, Any]]) -> Optional[float]:
        """Read net fiscal flow from a stored metrics row when available."""
        if row is None:
            return None
        return _net_fiscal_flow(row)

    def build_impact(
        baseline: Optional[Dict[str, Any]],
        evaluation: Optional[Dict[str, Any]],
        baseline_tick: int,
        evaluation_tick: int,
        status: str,
        provisional: bool = False,
        available_at_tick: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compare baseline and evaluation rows into a policy-impact summary."""
        impact = {
            "status": status,
            "baseline_tick": baseline_tick,
            "evaluation_tick": evaluation_tick,
            "ticks_observed": max(0, evaluation_tick - baseline_tick),
            "provisional": bool(provisional),
        }
        if available_at_tick is not None:
            impact["available_at_tick"] = int(available_at_tick)
        if status == "pending" or baseline is None or evaluation is None:
            return impact

        def delta_pp(field: str) -> Optional[float]:
            """Return a percentage-point delta for rate-like fields."""
            b, e = baseline.get(field), evaluation.get(field)
            if b is None or e is None:
                return None
            return round((float(e) - float(b)) * 100, 2)

        def delta_pct(field: str) -> Optional[float]:
            """Return a percent change against the absolute baseline value."""
            b, e = baseline.get(field), evaluation.get(field)
            if b is None or e is None:
                return None
            b_float = float(b)
            if b_float == 0.0:
                return None
            return round((float(e) - b_float) / abs(b_float) * 100, 1)

        def delta_abs(field: str) -> Optional[float]:
            """Return an absolute numeric delta between evaluation and baseline."""
            b, e = baseline.get(field), evaluation.get(field)
            if b is None or e is None:
                return None
            return round(float(e) - float(b), 2)

        baseline_flow = metric_net_flow(baseline)
        evaluation_flow = metric_net_flow(evaluation)
        net_flow_delta = (
            round(float(evaluation_flow) - float(baseline_flow), 2)
            if baseline_flow is not None and evaluation_flow is not None
            else None
        )
        impact.update(
            {
                "unemployment_delta_pp": delta_pp("unemployment_rate"),
                "gdp_delta_pct": delta_pct("gdp_this_tick"),
                "mean_health_delta_pp": delta_pp("mean_health"),
                "mean_happiness_delta_pp": delta_pp("mean_happiness"),
                "government_cash_delta": delta_abs("government_cash"),
                "net_fiscal_flow_delta": net_flow_delta,
                "consumer_distress_delta_pct": delta_pct("labor_seekers_wage_ineligible"),
            }
        )
        return impact

    result: List[Dict[str, Any]] = []
    for item in recent:
        action_tick = int(item.get("tick", 0))
        baseline_tick = max(0, action_tick - 1)
        short_evaluation_tick = max(baseline_tick, target_tick)
        mature_evaluation_tick = action_tick + impact_horizon
        baseline = row_at_or_before(baseline_tick)
        short_evaluation = row_at_or_before(short_evaluation_tick)
        short_impact = build_impact(
            baseline,
            short_evaluation,
            baseline_tick,
            short_evaluation_tick,
            status="available" if baseline is not None and short_evaluation is not None else "pending",
            provisional=(target_tick - action_tick) < impact_horizon,
        )
        if target_tick >= mature_evaluation_tick:
            mature_evaluation = row_at_or_before(mature_evaluation_tick)
            mature_impact = build_impact(
                baseline,
                mature_evaluation,
                baseline_tick,
                mature_evaluation_tick,
                status="available" if baseline is not None and mature_evaluation is not None else "pending",
            )
        else:
            mature_impact = build_impact(
                baseline,
                None,
                baseline_tick,
                min(target_tick, mature_evaluation_tick),
                status="pending",
                available_at_tick=mature_evaluation_tick,
            )

        legacy_impact = mature_impact if mature_impact.get("status") == "available" else short_impact
        rationale = str(item.get("rationale", item.get("reasoning", "")))
        evidence = _normalize_evidence(item.get("evidence", []))

        result.append(
            {
                "tick": action_tick,
                "decisions": dict(item.get("applied_changes", item.get("decisions", {}))),
                "accepted_llm_changes": dict(item.get("accepted_llm_changes", item.get("decisions", {}))),
                "mechanical_corrections": dict(item.get("mechanical_corrections", {})),
                "applied_changes": dict(item.get("applied_changes", item.get("decisions", {}))),
                "rejected_changes": list(item.get("rejected_changes", [])),
                "rationale": rationale,
                "reasoning": rationale,
                "evidence": evidence,
                "data_seen": dict(item.get("data_seen", {})),
                "short_term_impact": short_impact,
                "mature_impact": mature_impact,
                "impact": legacy_impact,
            }
        )
    return result


def observe_node(state: GovernmentState, economy: Any) -> Dict[str, Any]:
    """Pull raw metrics and current policy surface from the economy."""

    metrics = economy.get_economic_metrics()
    metrics["_metrics_history"] = list(getattr(economy, "metrics_history", []) or [])
    gov = economy.government
    recent_gdp = trailing_gdp(economy)
    metrics["recent_gdp"] = recent_gdp
    metrics["public_debt"] = float(getattr(gov, "public_debt", 0.0))
    metrics["annualized_debt_to_gdp"] = annualized_debt_to_gdp(gov, recent_gdp)
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
        "social_spending": gov.social_spending,
        "price_stabilization_target": gov.price_stabilization_target,
        "price_stabilization_level": gov.price_stabilization_level,
        "rent_stabilization_level": gov.rent_stabilization_level,
        "bailout_policy": gov.bailout_policy,
        "bailout_target": gov.bailout_target,
        "bailout_budget": gov.bailout_budget,
    }
    allowed_action_mask = build_allowed_government_actions(
        current_policy,
        gov,
        recent_gdp,
        float(metrics.get("unemployment_rate", 0.0) or 0.0),
        economy,
    )
    spending_breakdown = _spending_breakdown_from_metrics(metrics)
    budget_state = {
        "cash_balance": float(gov.cash_balance),
        "last_tick_revenue": float(gov.last_tick_revenue),
        "last_tick_spending": float(gov.last_tick_spending),
        "net_flow": float(gov.last_tick_revenue) - float(gov.last_tick_spending),
        "spending_breakdown": spending_breakdown,
        "deficit_ratio": float(metrics.get("deficit_ratio", 0.0)),
        "recent_gdp": float(recent_gdp),
        "public_debt": float(metrics.get("public_debt", 0.0)),
        "annualized_debt_to_gdp": float(metrics.get("annualized_debt_to_gdp", 0.0)),
        "fiscal_pressure": float(gov.fiscal_pressure),
        "fiscal_pressure_instant_ratio": float(metrics.get("fiscal_pressure_instant_ratio", 0.0) or 0.0),
        "fiscal_pressure_denominator_gdp": float(metrics.get("fiscal_pressure_denominator_gdp", recent_gdp) or 0.0),
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
    data_seen = _build_data_seen_snapshot(metrics, budget_state)
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
        "allowed_action_mask": allowed_action_mask,
        "budget_state": budget_state,
        "regime_state": regime_state,
        "tick": int(economy.current_tick),
        "data_seen": data_seen,
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
            elif indicator in COUNT_LIKE_INDICATORS:
                noisy_value = int(max(0.0, round(noisy_value)))

        observed[indicator] = {
            "value": round(noisy_value, 4) if isinstance(noisy_value, float) else noisy_value,
            "status": "reported",
            "data_age_ticks": int(lag),
            "estimated_accuracy": f"+/-{int(noise_std * 100)}%",
        }
        data_quality_summary["reported"] += 1

    # Compute rolling summaries for Tier-1 core indicators
    rolling_summaries: Dict[str, Dict[str, float]] = {}
    windows_used = government_rolling_windows(config)
    for indicator in TIER_1_CORE:
        rs = _compute_rolling_summary(economy, indicator, windows=windows_used)
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
        "rolling_windows_used": list(windows_used),
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

    price_level = merged.get("price_stabilization_level", "off")
    price_target = merged.get("price_stabilization_target", "none")
    if price_level == "off":
        validated["price_stabilization_target"] = "none"
    elif price_level in {"soft", "strict"} and price_target == "none":
        logger.warning(
            "Cross-lever: price_stabilization_level=%s with target=none - dropping price stabilization.",
            price_level,
        )
        validated.pop("price_stabilization_level", None)
        validated.pop("price_stabilization_target", None)

    return validated


def _validate_decisions(
    raw_decisions: Dict[str, Any],
    current_policy: Dict[str, Any],
    philosophy: str = "balanced",
) -> Dict[str, Any]:
    """Validate proposed decisions against the action space, step limits, and ideology ranges."""

    class _Gov:
        """Minimal government stand-in for schema validation helpers."""
        cash_balance = 0.0

    gov = _Gov()
    for key, value in normalize_current_policy(current_policy).items():
        setattr(gov, "public_works_toggle" if key == "public_works" else key, value)
    decisions, _rejected = sanitize_llm_government_changes(
        raw_decisions,
        current_policy,
        gov,
        gdp=1.0,
        unemployment_rate=0.0,
        economy=None,
    )
    return decisions

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


def _government_current_value(government: Any, lever: str) -> Any:
    """Read a current action-space value from GovernmentAgent when a snapshot is incomplete."""

    attr = "public_works_toggle" if lever == "public_works" else lever
    return getattr(government, attr, None)


def _append_rejection(
    rejected: List[Dict[str, Any]],
    lever: str,
    value: Any,
    reason: str,
    group: Optional[str] = None,
    raw_changes: Optional[Dict[str, Any]] = None,
) -> None:
    """Record one rejected model change with enough context for audit logs."""
    item = {"lever": lever, "value": value, "reason": reason}
    if group is not None:
        item["group"] = group
    if raw_changes is not None:
        item["raw_changes"] = dict(raw_changes)
    rejected.append(item)
    logger.info("Rejected LLM government change %s=%s: %s", lever, value, reason)


def _coerce_ordered_value(lever: str, value: Any) -> Any:
    """Coerce numeric enum values while preserving exact string enum matching."""

    if lever in {"sector_subsidy_level", "bailout_budget"}:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return value
    return value


def _lever_group(lever: str) -> str:
    """Return substantive policy group for one lever."""
    for group, levers in POLICY_GROUPS.items():
        if lever in levers:
            return group
    return lever


def _group_raw_changes(raw_changes: Dict[str, Any]) -> List[tuple[str, Dict[str, Any]]]:
    """Group raw LLM changes while preserving first-seen group order."""
    grouped: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for raw_lever, value in (raw_changes or {}).items():
        lever = "public_works" if raw_lever == "public_works_toggle" else str(raw_lever)
        group = _lever_group(lever)
        if group not in grouped:
            grouped[group] = {}
            order.append(group)
        grouped[group][lever] = value
    return [(group, grouped[group]) for group in order]


def _values_differ(left: Any, right: Any) -> bool:
    """Compare values numerically when possible, otherwise by exact equality."""
    try:
        return float(left) != float(right)
    except (TypeError, ValueError):
        return left != right


def _validate_one_lever_value(
    lever: str,
    raw_value: Any,
    current_policy: Dict[str, Any],
    fiscal_stress: bool,
    unemployment_rate: float,
    government: Any,
    recent_gdp: float,
    firms: List[Any],
) -> tuple[bool, Any, str]:
    """Validate one raw lever value without applying cross-lever invariants."""
    if lever not in TAX_LIMITS and lever not in ORDERED_LEVERS and lever not in SIMPLE_ENUM_LEVERS:
        return False, raw_value, "unknown_lever"

    current = current_policy.get(lever, _government_current_value(government, lever))
    if current is None:
        return False, raw_value, "unknown_or_unavailable_current_policy"

    if lever in TAX_LIMITS:
        lo, hi = TAX_LIMITS[lever]
        try:
            proposed = round(float(raw_value), 4)
            current_float = float(current)
        except (TypeError, ValueError):
            return False, raw_value, "tax_value_not_numeric"
        if not (lo <= proposed <= hi):
            return False, raw_value, "tax_out_of_bounds"
        if abs(proposed - current_float) > TAX_MAX_STEP + 1e-9:
            return False, proposed, "tax_step_too_large"
        if fiscal_stress and is_tax_decrease(lever, current_float, proposed):
            return False, proposed, "tax_cut_during_fiscal_stress"
        return True, proposed, ""

    if lever in ORDERED_LEVERS:
        order = ORDERED_LEVERS[lever]
        proposed = _coerce_ordered_value(lever, raw_value)
        if proposed not in order:
            return False, raw_value, "invalid_enum_value"
        if current not in order:
            return False, current, "invalid_current_policy_value"
        if abs(order.index(proposed) - order.index(current)) > 1:
            return False, proposed, "ordered_step_too_large"
        if fiscal_stress and lever in SPENDING_LEVERS and is_spending_increase(lever, current, proposed):
            return False, proposed, "spending_increase_during_fiscal_stress"
        if lever == "minimum_wage_policy" and unemployment_rate >= 0.30 and order.index(proposed) > order.index(current):
            return False, proposed, "minimum_wage_increase_during_extreme_unemployment"
        return True, proposed, ""

    valid_values = SIMPLE_ENUM_LEVERS[lever]
    proposed = raw_value
    if proposed not in valid_values:
        return False, raw_value, "invalid_enum_value"
    if fiscal_stress and lever in SPENDING_LEVERS and is_spending_increase(lever, current, proposed):
        return False, proposed, "spending_increase_during_fiscal_stress"
    if lever == "public_works" and proposed == "on" and current != "on":
        if unemployment_rate < 0.25:
            return False, proposed, "public_works_requires_severe_unemployment"
        if not can_fund_public_works_startup(government, recent_gdp, firms):
            startup_cost = projected_public_works_startup_cost(firms)
            reserve = fiscal_reserve_floor(recent_gdp)
            return False, proposed, f"insufficient_cash_for_public_works_startup:{startup_cost:.2f}+reserve:{reserve:.2f}"
    return True, proposed, ""


def _validate_group_invariants(
    group: str,
    candidate_policy: Dict[str, Any],
    raw_group: Dict[str, Any],
) -> tuple[bool, Dict[str, Any], str]:
    """Validate cross-lever invariants and return mechanical corrections."""
    mechanical: Dict[str, Any] = {}

    if group == "price_stabilization":
        level = candidate_policy.get("price_stabilization_level", "off")
        target = candidate_policy.get("price_stabilization_target", "none")
        if level == "off":
            if target != "none":
                if "price_stabilization_level" in raw_group and raw_group.get("price_stabilization_level") == "off":
                    mechanical["price_stabilization_target"] = "none"
                else:
                    return False, {}, "price_stabilization_target_requires_active_level"
        elif level in {"monitor", "soft", "strict"}:
            if target == "none":
                return False, {}, "price_stabilization_requires_target"
        else:
            return False, {}, "invalid_price_stabilization_state"

    if group == "sector_subsidy":
        target = candidate_policy.get("sector_subsidy_target", "none")
        try:
            level = int(candidate_policy.get("sector_subsidy_level", 0) or 0)
        except (TypeError, ValueError):
            return False, {}, "invalid_sector_subsidy_level"
        if level == 0:
            if target != "none":
                if "sector_subsidy_level" in raw_group and int(_coerce_ordered_value("sector_subsidy_level", raw_group.get("sector_subsidy_level"))) == 0:
                    mechanical["sector_subsidy_target"] = "none"
                else:
                    return False, {}, "target_without_subsidy_level_has_no_effect"
        elif target == "none":
            return False, {}, "subsidy_level_without_target_has_no_effect"

    if group == "bailout":
        policy = candidate_policy.get("bailout_policy", "off")
        target = candidate_policy.get("bailout_target", "none")
        try:
            budget = int(candidate_policy.get("bailout_budget", 0) or 0)
        except (TypeError, ValueError):
            return False, {}, "invalid_bailout_budget"
        if policy == "off":
            if target != "none":
                if raw_group.get("bailout_policy") == "off":
                    mechanical["bailout_target"] = "none"
                else:
                    return False, {}, "bailout_target_without_active_bailout_has_no_effect"
            if budget != 0:
                if raw_group.get("bailout_policy") == "off":
                    mechanical["bailout_budget"] = 0
                else:
                    return False, {}, "bailout_budget_without_active_bailout_has_no_effect"
        elif policy == "sector":
            if target == "none" or budget <= 0:
                return False, {}, "sector_bailout_requires_target_and_budget"
        elif policy == "all":
            if budget <= 0:
                return False, {}, "all_bailout_requires_budget"
            if target != "none":
                mechanical["bailout_target"] = "none"
        else:
            return False, {}, "invalid_bailout_policy_state"

    return True, mechanical, ""


def sanitize_llm_government_changes_detailed(
    raw_changes: Dict[str, Any],
    current_policy: Dict[str, Any],
    government: Any,
    gdp: float,
    unemployment_rate: float,
    economy: Any = None,
) -> Dict[str, Any]:
    """Validate raw LLM government changes with grouped policy instruments."""

    current_policy = normalize_current_policy(current_policy)
    accepted: Dict[str, Any] = {}
    mechanical: Dict[str, Any] = {}
    rejected: List[Dict[str, Any]] = []
    substantive_groups = 0

    recent_gdp = max(float(gdp or 0.0), 1.0)
    debt_to_gdp = annualized_debt_to_gdp(government, recent_gdp)
    fiscal_stress = float(getattr(government, "cash_balance", 0.0) or 0.0) < 0.0 or debt_to_gdp >= 1.0
    firms = getattr(economy, "firms", []) if economy is not None else []

    for group, raw_group in _group_raw_changes(raw_changes or {}):
        policy_before_group = dict(current_policy)
        policy_before_group.update(accepted)
        policy_before_group.update(mechanical)
        validated_group: Dict[str, Any] = {}
        group_rejected = False

        for lever, raw_value in raw_group.items():
            ok, proposed, reason = _validate_one_lever_value(
                lever,
                raw_value,
                policy_before_group,
                fiscal_stress,
                unemployment_rate,
                government,
                recent_gdp,
                firms,
            )
            if not ok:
                _append_rejection(rejected, lever, proposed, reason, group=group, raw_changes=raw_group)
                group_rejected = True
                break
            validated_group[lever] = proposed

        if group_rejected:
            continue

        candidate_policy = dict(policy_before_group)
        candidate_policy.update(validated_group)
        ok, mechanical_group, reason = _validate_group_invariants(group, candidate_policy, validated_group)
        if not ok:
            _append_rejection(
                rejected,
                group,
                dict(validated_group),
                reason,
                group=group,
                raw_changes=raw_group,
            )
            continue

        changed_group = {
            lever: value
            for lever, value in validated_group.items()
            if _values_differ(policy_before_group.get(lever), value)
        }
        changed_mechanical = {
            lever: value
            for lever, value in mechanical_group.items()
            if _values_differ(candidate_policy.get(lever), value)
        }
        if not changed_group and not changed_mechanical:
            continue

        if substantive_groups >= MAX_SUBSTANTIVE_CHANGES:
            _append_rejection(
                rejected,
                group,
                dict(validated_group),
                "max_substantive_changes_exceeded",
                group=group,
                raw_changes=raw_group,
            )
            continue

        accepted.update(changed_group)
        mechanical.update(changed_mechanical)
        substantive_groups += 1

    applied = dict(accepted)
    applied.update(mechanical)
    return {
        "accepted_llm_changes": accepted,
        "mechanical_corrections": mechanical,
        "applied_changes": applied,
        "rejected_changes": rejected,
    }


def sanitize_llm_government_changes(
    raw_changes: Dict[str, Any],
    current_policy: Dict[str, Any],
    government: Any,
    gdp: float,
    unemployment_rate: float,
    economy: Any = None,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Compatibility wrapper returning applied changes and rejections."""
    detailed = sanitize_llm_government_changes_detailed(
        raw_changes,
        current_policy,
        government,
        gdp,
        unemployment_rate,
        economy=economy,
    )
    return dict(detailed["applied_changes"]), list(detailed["rejected_changes"])


def build_allowed_government_actions(
    current_policy: Dict[str, Any],
    government: Any,
    recent_gdp: float,
    unemployment_rate: float,
    economy: Any,
) -> Dict[str, Any]:
    """Generate a dynamic action mask by testing candidates through the sanitizer."""

    current_policy = normalize_current_policy(current_policy)
    candidates: Dict[str, List[Any]] = {}
    grouped_levers = {lever for levers in POLICY_GROUPS.values() for lever in levers}

    for lever, (lo, hi) in TAX_LIMITS.items():
        try:
            current = float(current_policy[lever])
        except (KeyError, TypeError, ValueError):
            continue
        values = []
        for proposed in (current - TAX_MAX_STEP, current + TAX_MAX_STEP):
            proposed = round(proposed, 4)
            if lo <= proposed <= hi:
                values.append(proposed)
        candidates[lever] = values

    for lever, order in ORDERED_LEVERS.items():
        if lever in LLM_HIDDEN_POLICY_LEVERS or lever in grouped_levers:
            continue
        current = current_policy.get(lever)
        if current not in order:
            continue
        idx = order.index(current)
        values = []
        if idx > 0:
            values.append(order[idx - 1])
        if idx < len(order) - 1:
            values.append(order[idx + 1])
        candidates[lever] = values

    for lever, values in SIMPLE_ENUM_LEVERS.items():
        if lever in LLM_HIDDEN_POLICY_LEVERS or lever in grouped_levers:
            continue
        current = current_policy.get(lever)
        ordered_values = sorted(values)
        candidates[lever] = [value for value in ordered_values if value != current]

    allowed_simple: Dict[str, List[Any]] = {}
    blocked_simple: Dict[str, List[Dict[str, Any]]] = {}
    for lever, values in candidates.items():
        for value in values:
            clean, rejected = sanitize_llm_government_changes(
                {lever: value},
                current_policy,
                government,
                recent_gdp,
                unemployment_rate,
                economy=economy,
            )
            if lever in clean:
                allowed_simple.setdefault(lever, []).append(value)
            else:
                reason = rejected[0]["reason"] if rejected else "not_allowed"
                blocked_simple.setdefault(lever, []).append({"value": value, "reason": reason})

    def group_candidates(group: str) -> List[Dict[str, Any]]:
        """Generate nearby valid action candidates for one substantive lever group."""
        current_level = current_policy.get("price_stabilization_level", "off")
        if group == "price_stabilization":
            levels = POLICY_ORDERED_LEVERS["price_stabilization_level"]
            idx = levels.index(current_level) if current_level in levels else 0
            level_values = {current_level}
            if idx > 0:
                level_values.add(levels[idx - 1])
            if idx < len(levels) - 1:
                level_values.add(levels[idx + 1])
            combos = []
            for level in level_values:
                targets = ["none"] if level == "off" else ["food", "services", "healthcare"]
                current_target = current_policy.get("price_stabilization_target", "none")
                if level != "off" and current_target != "none":
                    targets.append(current_target)
                for target in dict.fromkeys(targets):
                    combos.append({"price_stabilization_target": target, "price_stabilization_level": level})
            return combos

        if group == "rent_stabilization":
            levels = POLICY_ORDERED_LEVERS["rent_stabilization_level"]
            current = current_policy.get("rent_stabilization_level", "off")
            idx = levels.index(current) if current in levels else 0
            values = []
            if idx > 0:
                values.append(levels[idx - 1])
            if idx < len(levels) - 1:
                values.append(levels[idx + 1])
            return [{"rent_stabilization_level": value} for value in values]

        if group == "sector_subsidy":
            levels = POLICY_ORDERED_LEVERS["sector_subsidy_level"]
            current_level_int = int(current_policy.get("sector_subsidy_level", 0) or 0)
            idx = levels.index(current_level_int) if current_level_int in levels else 0
            level_values = {current_level_int}
            if idx > 0:
                level_values.add(levels[idx - 1])
            if idx < len(levels) - 1:
                level_values.add(levels[idx + 1])
            combos = []
            for level in level_values:
                targets = ["none"] if int(level) == 0 else ["food", "housing", "services", "healthcare"]
                current_target = current_policy.get("sector_subsidy_target", "none")
                if int(level) > 0 and current_target != "none":
                    targets.append(current_target)
                for target in dict.fromkeys(targets):
                    combos.append({"sector_subsidy_target": target, "sector_subsidy_level": int(level)})
            return combos

        if group == "bailout":
            policies = POLICY_ORDERED_LEVERS["bailout_policy"]
            budgets = POLICY_ORDERED_LEVERS["bailout_budget"]
            current_policy_value = current_policy.get("bailout_policy", "off")
            current_budget = int(current_policy.get("bailout_budget", 0) or 0)
            policy_idx = policies.index(current_policy_value) if current_policy_value in policies else 0
            budget_idx = budgets.index(current_budget) if current_budget in budgets else 0
            policy_values = {current_policy_value}
            budget_values = {current_budget}
            if policy_idx > 0:
                policy_values.add(policies[policy_idx - 1])
            if policy_idx < len(policies) - 1:
                policy_values.add(policies[policy_idx + 1])
            if budget_idx > 0:
                budget_values.add(budgets[budget_idx - 1])
            if budget_idx < len(budgets) - 1:
                budget_values.add(budgets[budget_idx + 1])
            combos = [{"bailout_policy": "off", "bailout_target": "none", "bailout_budget": 0}]
            for policy in policy_values:
                if policy == "sector":
                    for target in ("food", "housing", "services", "healthcare"):
                        for budget in budget_values:
                            if int(budget) > 0:
                                combos.append({"bailout_policy": "sector", "bailout_target": target, "bailout_budget": int(budget)})
                elif policy == "all":
                    for budget in budget_values:
                        if int(budget) > 0:
                            combos.append({"bailout_policy": "all", "bailout_target": "none", "bailout_budget": int(budget)})
            return combos
        return []

    allowed_groups: Dict[str, List[Dict[str, Any]]] = {}
    blocked_groups: Dict[str, List[Dict[str, Any]]] = {}
    for group in ("price_stabilization", "rent_stabilization", "sector_subsidy", "bailout"):
        for combo in group_candidates(group):
            if all(not _values_differ(current_policy.get(lever), value) for lever, value in combo.items()):
                continue
            detailed = sanitize_llm_government_changes_detailed(
                combo,
                current_policy,
                government,
                recent_gdp,
                unemployment_rate,
                economy=economy,
            )
            if detailed["accepted_llm_changes"] or detailed["mechanical_corrections"]:
                allowed_groups.setdefault(group, []).append(combo)
            elif detailed["rejected_changes"]:
                blocked_groups.setdefault(group, []).append({
                    "value": combo,
                    "reason": detailed["rejected_changes"][0]["reason"],
                })

    return {
        "allowed": {"simple": allowed_simple, "groups": allowed_groups},
        "blocked": {"simple": blocked_simple, "groups": blocked_groups},
    }


async def decide_node(state: GovernmentState, provider: LLMProvider, config: Any, economy: Any = None) -> Dict[str, Any]:
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
        allowed_action_mask=state.get("allowed_action_mask", {}),
        observed_metrics=state.get("observed_metrics", {}),
        rolling_summaries=state.get("rolling_summaries", {}),
        data_quality_summary=state.get("data_quality_summary", {}),
    )
    if getattr(config, "no_think", False):
        user_prompt = user_prompt + "\n/no_think"

    try:
        response = await provider.complete(
            system=system_prompt,
            user=user_prompt,
            temperature=float(getattr(config, "government_temperature", 0.4)),
            top_p=float(getattr(config, "government_top_p", 0.8)),
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        logger.error("Government LLM call failed: %s", exc)
        return {
            "llm_response": "",
            "raw_changes": {},
            "accepted_llm_changes": {},
            "mechanical_corrections": {},
            "applied_changes": {},
            "decisions": {},
            "rejected_changes": [],
            "llm_fiscal_mode": "NORMAL",
            "computed_fiscal_mode": "NORMAL",
            "fiscal_mode": "NORMAL",
            "primary_goal": "hold",
            "rationale": f"LLM call failed: {exc}",
            "evidence": [],
            "evidence_audit": [],
            "reasoning": f"LLM call failed: {exc}",
            "decision_summary": f"LLM call failed: {exc}",
            "parse_ok": False,
            "elapsed_ms": elapsed_ms,
        }

    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    parsed = extract_json_from_response(response)
    provider_name = str(getattr(provider, "name", ""))
    repairable_provider = provider_name.startswith("groq/openai/gpt-oss") or provider_name.startswith(
        "openrouter/inclusionai/ring-"
    )
    if parsed is None and repairable_provider:
        repair_prompt = (
            user_prompt
            + "\n\n[RETRY AFTER INVALID OUTPUT]\n"
            + "Your previous response was blank or could not be parsed as JSON. Return exactly one JSON object and no prose. "
            + "Use this shape: "
            + '{"fiscal_mode":"NORMAL","primary_goal":"hold","rationale":"...","evidence":["metric=value"],"changes":{}}'
        )
        try:
            response = await provider.complete(
                system=system_prompt,
                user=repair_prompt,
                temperature=0.0,
                top_p=float(getattr(config, "government_top_p", 0.8)),
                response_format={"type": "json_object"},
            )
            parsed = extract_json_from_response(response)
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        except Exception as exc:
            logger.warning("Government LLM JSON repair retry failed: %s", exc)
    if parsed is None:
        logger.warning("Government LLM returned non-JSON content.")
        return {
            "llm_response": response,
            "raw_changes": {},
            "accepted_llm_changes": {},
            "mechanical_corrections": {},
            "applied_changes": {},
            "decisions": {},
            "rejected_changes": [],
            "llm_fiscal_mode": "NORMAL",
            "computed_fiscal_mode": "NORMAL",
            "fiscal_mode": "NORMAL",
            "primary_goal": "hold",
            "rationale": "Parse error - no changes applied",
            "evidence": [],
            "evidence_audit": [],
            "reasoning": "Parse error - no changes applied",
            "decision_summary": "Parse error - no changes applied",
            "parse_ok": False,
            "elapsed_ms": elapsed_ms,
        }

    raw_decisions = parsed.get("changes", parsed.get("decisions", {}))
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
    fiscal_mode = _normalize_fiscal_mode(parsed.get("fiscal_mode"))
    primary_goal = _normalize_primary_goal(parsed.get("primary_goal"))
    rationale = str(parsed.get("rationale", parsed.get("reasoning", "")) or "").strip()[:500]
    evidence = _normalize_evidence(parsed.get("evidence", []))
    evidence_audit = _audit_evidence(evidence, state)
    recent_gdp = float(state.get("budget_state", {}).get("recent_gdp", state["raw_metrics"].get("recent_gdp", 0.0)) or 0.0)
    if economy is not None:
        recent_gdp = trailing_gdp(economy)
    unemployment_rate = float(state["raw_metrics"].get("unemployment_rate", 0.0) or 0.0)
    government = getattr(economy, "government", None) if economy is not None else None
    if government is None:
        class _FallbackGovernment:
            """Fallback object used when parsing decisions without a live economy."""
            cash_balance = 0.0
        government = _FallbackGovernment()
    detailed = sanitize_llm_government_changes_detailed(
        raw_decisions,
        state["current_policy"],
        government,
        recent_gdp,
        unemployment_rate,
        economy=economy,
    )
    validated = dict(detailed["applied_changes"])
    rejected = list(detailed["rejected_changes"])
    computed_mode = computed_fiscal_mode_from_state(
        government,
        recent_gdp,
        float(state.get("budget_state", {}).get("fiscal_pressure", 0.0) or 0.0),
    )
    decision_summary = _decision_summary_reasoning(fiscal_mode, primary_goal, validated, rejected)
    if not rationale:
        rationale = decision_summary
    return {
        "llm_response": response,
        "raw_changes": dict(raw_decisions),
        "accepted_llm_changes": dict(detailed["accepted_llm_changes"]),
        "mechanical_corrections": dict(detailed["mechanical_corrections"]),
        "applied_changes": validated,
        "decisions": validated,
        "rejected_changes": rejected,
        "llm_fiscal_mode": fiscal_mode,
        "computed_fiscal_mode": computed_mode,
        "fiscal_mode": fiscal_mode,
        "primary_goal": primary_goal,
        "rationale": rationale,
        "evidence": evidence,
        "evidence_audit": evidence_audit,
        "reasoning": rationale,
        "decision_summary": decision_summary,
        "parse_ok": True,
        "elapsed_ms": elapsed_ms,
    }


def fallback_node(state: GovernmentState) -> Dict[str, Any]:
    """Return a no-op decision state after an LLM failure."""

    return {
        "accepted_llm_changes": {},
        "mechanical_corrections": {},
        "applied_changes": {},
        "decisions": {},
        "rejected_changes": state.get("rejected_changes", []),
        "llm_fiscal_mode": state.get("llm_fiscal_mode", state.get("fiscal_mode", "NORMAL")),
        "computed_fiscal_mode": state.get("computed_fiscal_mode", "NORMAL"),
        "fiscal_mode": state.get("fiscal_mode", "NORMAL"),
        "primary_goal": state.get("primary_goal", "hold"),
        "rationale": state.get("rationale", state.get("reasoning", "Fallback - no policy changes applied")),
        "evidence": list(state.get("evidence", [])),
        "evidence_audit": list(state.get("evidence_audit", [])),
        "reasoning": state.get("reasoning", state.get("rationale", "Fallback - no policy changes applied")),
        "decision_summary": state.get("decision_summary", "Fallback - no policy changes applied"),
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
    rejected = state.get("rejected_changes", [])
    if decisions:
        logger.info("Tick %d | government_llm %.0fms | decisions=%s rejected=%s", tick, elapsed_ms, decisions, rejected)
    else:
        logger.info("Tick %d | government_llm %.0fms | no changes rejected=%s", tick, elapsed_ms, rejected)
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
        """Capture raw economy observations for the graph state."""
        return observe_node(state, economy)

    def constrain_step(state: GovernmentState) -> Dict[str, Any]:
        """Apply prompt-visible information constraints to graph state."""
        return apply_info_constraints_node(state, economy, config, decision_history)

    async def decide_step(state: GovernmentState) -> Dict[str, Any]:
        """Ask the provider for a constrained government decision."""
        return await decide_node(state, provider, config, economy=economy)

    def apply_step(state: GovernmentState) -> Dict[str, Any]:
        """Validate model output and derive accepted policy changes."""
        return apply_node(state, economy)

    def log_step(state: GovernmentState) -> Dict[str, Any]:
        """Persist final graph metadata into the decision state."""
        return log_node(state)

    def fallback_step(state: GovernmentState) -> Dict[str, Any]:
        """Produce a safe fallback decision when parsing or validation fails."""
        return fallback_node(state)

    def parse_success_check(state: GovernmentState) -> str:
        """Route the graph based on whether the model response parsed cleanly."""
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
            state.update(await decide_node(state, self.provider, self.config, economy=economy))
            if not state.get("parse_ok", False):
                state.update(fallback_node(state))
            else:
                apply_node(state, economy)
            log_node(state)

        economy.government.begin_decision_cycle()
        current_policy_after = {
            lever: economy.government.to_dict().get(lever)
            for lever in PROMPT_POLICY_LEVERS
            if lever in economy.government.to_dict()
        }
        start_tick = max(
            int(getattr(CONFIG.llm, "government_start_tick", 15)),
            int(getattr(CONFIG.time, "warmup_ticks", 10)) + int(getattr(CONFIG.llm, "government_start_after_warmup_ticks", 5)),
        )

        result = {
            "tick": int(state.get("tick", economy.current_tick)),
            "raw_changes": dict(state.get("raw_changes", {})),
            "accepted_llm_changes": dict(state.get("accepted_llm_changes", {})),
            "mechanical_corrections": dict(state.get("mechanical_corrections", {})),
            "applied_changes": dict(state.get("applied_changes", state.get("decisions", {}))),
            "decisions": dict(state.get("decisions", {})),
            "rejected_changes": list(state.get("rejected_changes", [])),
            "llm_fiscal_mode": str(state.get("llm_fiscal_mode", state.get("fiscal_mode", "NORMAL"))),
            "computed_fiscal_mode": str(state.get("computed_fiscal_mode", "NORMAL")),
            "fiscal_mode": str(state.get("fiscal_mode", "NORMAL")),
            "primary_goal": str(state.get("primary_goal", "hold")),
            "rationale": str(state.get("rationale", state.get("reasoning", ""))),
            "evidence": list(state.get("evidence", [])),
            "evidence_audit": list(state.get("evidence_audit", [])),
            "reasoning": str(state.get("reasoning", state.get("rationale", ""))),
            "decision_summary": str(state.get("decision_summary", "")),
            "elapsed_ms": float(state.get("elapsed_ms", 0.0)),
            "parse_ok": bool(state.get("parse_ok", False)),
            "decision_interval": int(getattr(CONFIG.llm, "government_decision_interval", 26)),
            "start_tick": int(start_tick),
            "provider": getattr(self.provider, "name", "unknown"),
            "observed_metrics": state.get("observed_metrics", {}),
            "rolling_summaries": state.get("rolling_summaries", {}),
            "rolling_windows_used": list(state.get("rolling_windows_used", government_rolling_windows(self.config))),
            "data_quality_summary": state.get("data_quality_summary", {}),
            "data_seen": dict(state.get("data_seen", {})),
            "current_policy_before": dict(state.get("current_policy", {})),
            "current_policy_after": current_policy_after,
            "allowed_action_mask": dict(state.get("allowed_action_mask", {})),
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
