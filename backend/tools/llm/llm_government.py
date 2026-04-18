
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

import json
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
    observed_metrics: Dict[str, Any]
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

# indicator_name -> (lag_ticks, noise_std_pct, coverage_pct)
INDICATOR_CONSTRAINTS: Dict[str, tuple[int, float, float]] = {
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

PHILOSOPHY_PROMPTS = {
    "capitalist": "You believe in free-market capitalism: private enterprise drives growth, government should keep taxes competitive, avoid heavy-handed intervention, and step in only when markets are clearly failing. You favor fiscal discipline, supply-side conditions for investment, and targeted intervention over broad permanent expansion.",
    "keynesian": "You believe active fiscal policy is necessary to stabilize demand during downturns. You favor counter-cyclical spending, strong safety nets during recessions, and public investment when private demand is weak.",
    "balanced": "You are pragmatic rather than ideological. You balance market efficiency, fiscal discipline, employment, and social stability, adjusting intervention based on current conditions.",
}


def _build_system_prompt(philosophy: str, num_households: int, num_firms: int) -> str:
    """Build the system prompt for the government agent."""

    philosophy_text = PHILOSOPHY_PROMPTS.get(philosophy, PHILOSOPHY_PROMPTS["balanced"])
    return f"""SIMULATION CONTEXT: You are the AI government of a computer-simulated economy. This is a closed simulation â€” not a real economy. Every piece of data you receive is a complete, authoritative snapshot of the simulation state. Do not ask for additional information. Do not ask clarifying questions. Do not say you need more data. You have everything you need to make a decision right now.

Your economic philosophy: {philosophy_text}

SIMULATION PARAMETERS: {num_households} households, {num_firms} firms. One simulation tick = one week.

POLICY LEVERS â€” you control 13 levers:

Continuous (any float in range):
  wage_tax_rate:       [0.00 â€“ 0.50]  Fraction of household wages taxed
  profit_tax_rate:     [0.00 â€“ 0.50]  Fraction of firm profits taxed
  investment_tax_rate: [0.00 â€“ 0.30]  Fraction of firm R&D/investment taxed

Discrete (exact values only):
  benefit_level:          low | neutral | high | crisis
  public_works:           off | on
  minimum_wage_policy:    low | neutral | high
  sector_subsidy_target:  none | food | housing | services | healthcare
  sector_subsidy_level:   0 | 10 | 25 | 50          (integer, percent govt pays)
  infrastructure_spending: none | low | medium | high
  technology_spending:    none | low | medium | high
  bailout_policy:         off | sector | all
  bailout_target:         none | food | housing | services | healthcare
  bailout_budget:         0 | 5000 | 10000 | 25000 | 50000  (integer)

LEVER EFFECTS:
  wage_tax_rate â†‘       â†’ govt revenue â†‘, household take-home â†“, consumption â†“
  profit_tax_rate â†‘     â†’ govt revenue â†‘, firm cash â†“, investment â†“
  investment_tax_rate â†‘ â†’ R&D spending â†“, quality growth â†“
  benefit_level â†‘       â†’ unemployed income â†‘, reservation wages â†‘, fiscal cost â†‘
  public_works on       â†’ unemployment â†“ fast, govt cash â†“ fast
  minimum_wage â†‘        â†’ low-wage workers earn more, some firms shed jobs
  sector_subsidy â†‘      â†’ demand in that sector â†‘, affordability â†‘, fiscal cost â†‘
  infrastructure â†‘      â†’ economy-wide productivity â†‘ slowly (20+ ticks)
  technology â†‘          â†’ product quality â†‘ slowly, shifts demand toward quality
  bailout_budget â†‘      â†’ failing firms get rescue loans, prevents sector collapse

HARD RULES:
  - Only include levers you want to CHANGE from their current value.
  - Discrete ordered levers (benefit_level, minimum_wage_policy, infrastructure_spending, technology_spending) can move by at most ONE step per decision cycle.
  - sector_subsidy_level and bailout_budget must be integers.
  - If you have no changes to make, return {{"decisions": {{}}, "reasoning": "holding current policy"}}.
  - Do NOT ask questions. Do NOT request more data. Make a decision or hold.

OUTPUT FORMAT â€” respond with valid JSON and nothing else after your reasoning:
{{
  "decisions": {{
    "lever_name": value
  }},
  "reasoning": "2-4 sentences: what you observed, what you changed, why"
}}"""


def _format_observed_metrics(observed_metrics: Dict[str, Any]) -> str:
    """Render constrained observations for the user prompt."""

    if not observed_metrics:
        return "No observations available."

    lines: List[str] = []
    for key in sorted(observed_metrics):
        entry = observed_metrics[key]
        status = entry.get("status", "unknown")
        if status != "reported":
            lines.append(
                f"- {key}: unavailable (last_available_tick={entry.get('last_available_tick')})"
            )
            continue
        lines.append(
            "- "
            f"{key}: value={entry.get('value')} "
            f"(age={entry.get('data_age_ticks', 0)} ticks, "
            f"accuracy={entry.get('estimated_accuracy', 'unknown')})"
        )
    return "\n".join(lines)


def _format_recent_policy_memory(memory: List[Dict[str, Any]]) -> str:
    """Render compact recent policy decisions and observed deltas."""

    if not memory:
        return "No recent policy actions recorded."

    lines: List[str] = []
    for item in memory:
        impact = item.get("impact", {})
        lines.append(
            "- "
            f"tick {item.get('tick')}: {item.get('decisions')} | "
            f"delta unemployment={impact.get('unemployment_rate_delta')} pp, "
            f"delta GDP={impact.get('gdp_delta')}, "
            f"delta health={impact.get('mean_health_delta')}, "
            f"delta distress={impact.get('consumer_distress_delta')} | "
            f"reasoning={item.get('reasoning')}"
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


def _build_user_prompt(
    observed_metrics: Dict[str, Any],
    current_policy: Dict[str, Any],
    budget_state: Dict[str, Any],
    regime_state: Dict[str, Any],
    tick: int,
    recent_policy_memory: List[Dict[str, Any]],
) -> str:
    """Build the user prompt for the government agent."""

    current_policy_lines = "\n".join(
        f"- {lever}: {current_policy[lever]}" for lever in sorted(current_policy)
    )
    budget_lines = "\n".join(
        f"- {field}: {round(float(value), 4) if isinstance(value, (int, float)) else value}"
        for field, value in sorted(budget_state.items())
    )

    return f"""=== SIMULATION TICK {tick} ===

CURRENT POLICY SETTINGS:
{current_policy_lines}

GOVERNMENT BUDGET:
{budget_lines}

SIMULATION REGIME:
{_format_regime_state(regime_state)}

ECONOMIC INDICATORS (noisy, may be lagged â€” see age/accuracy):
{_format_observed_metrics(observed_metrics)}

RECENT POLICY HISTORY (action â†’ observed outcome):
{_format_recent_policy_memory(recent_policy_memory)}

This is all the data available. Reason through the state of the simulation, then output your JSON decision. Do not ask for more information â€” the simulation cannot respond to questions. Output valid JSON now."""


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

        def delta(field: str) -> Optional[float]:
            if baseline is None or evaluation is None:
                return None
            if baseline.get(field) is None or evaluation.get(field) is None:
                return None
            return round(float(evaluation[field]) - float(baseline[field]), 4)

        result.append(
            {
                "tick": action_tick,
                "decisions": dict(item.get("decisions", {})),
                "reasoning": item.get("reasoning", ""),
                "impact": {
                    "baseline_tick": baseline_tick,
                    "evaluation_tick": evaluation_tick,
                    "unemployment_rate_delta": delta("unemployment_rate"),
                    "gdp_delta": delta("gdp_this_tick"),
                    "mean_health_delta": delta("mean_health"),
                    "consumer_distress_delta": delta("labor_seekers_wage_ineligible"),
                },
            }
        )
    return result


def observe_node(state: GovernmentState, economy: Any) -> Dict[str, Any]:
    """Pull raw metrics and current policy surface from the economy."""

    metrics = economy.get_economic_metrics()
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
    """Apply lag, noise, and coverage gaps to raw economic observations."""

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

    recent_policy_memory = _build_recent_policy_memory(
        decision_history=decision_history,
        economy=economy,
        target_tick=tick,
        lookback=max(1, int(getattr(config, "government_history_window", 6))),
        impact_horizon=max(1, int(getattr(config, "government_impact_horizon", 8))),
    )
    return {
        "observed_metrics": observed,
        "recent_policy_memory": recent_policy_memory,
        "data_quality_summary": data_quality_summary,
    }


def _validate_decisions(
    raw_decisions: Dict[str, Any],
    current_policy: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate proposed decisions against the action space and step limits."""

    validated: Dict[str, Any] = {}
    for lever, value in raw_decisions.items():
        # Handle continuous levers (tax rates)
        if lever in CONTINUOUS_LEVERS:
            lo, hi = CONTINUOUS_LEVERS[lever]
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
    return validated


async def decide_node(state: GovernmentState, provider: LLMProvider, config: Any) -> Dict[str, Any]:
    """Run the LLM decision step and validate the returned JSON."""

    started_at = time.perf_counter()
    system_prompt = _build_system_prompt(
        getattr(config, "government_philosophy", "balanced"),
        num_households=int(state["raw_metrics"].get("total_households", 0)),
        num_firms=int(state["raw_metrics"].get("total_firms", 0)),
    )
    user_prompt = _build_user_prompt(
        observed_metrics=state["observed_metrics"],
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

    raw_decisions = parsed.get("decisions", {})
    if not isinstance(raw_decisions, dict):
        raw_decisions = {}
    reasoning = str(parsed.get("reasoning", "No reasoning provided"))
    validated = _validate_decisions(raw_decisions, state["current_policy"])
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


