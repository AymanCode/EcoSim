
"""LLM-controlled single-firm advisor for local simulation experiments.

The design goal is narrow and testable:

1. observe one target firm's local state
2. compute the heuristic baseline plan on a cloned firm
3. ask a local model for a small override in JSON
4. validate the response and hand it back to the runner

The economy core stays synchronous. The runner performs async provider calls
between ticks, then injects the validated decision for the next few ticks.
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

import copy
import json
import logging
import time
from typing import Any, Dict, List, Optional

from llm_provider import LLMProvider, extract_json_from_response

logger = logging.getLogger(__name__)


ALLOWED_DECISION_FIELDS = {
    "price",
    "wage_offer",
    "expected_sales_units",
    "rd_spending_rate",
    "target_inventory_weeks",
}


def _safe_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in {float("inf"), float("-inf")}:
        return None
    return numeric


def _firm_state_snapshot(firm: Any) -> Dict[str, Any]:
    current_workers = len(getattr(firm, "employees", []) or [])
    wage_bill = sum(
        float(getattr(firm, "actual_wages", {}).get(employee_id, firm.wage_offer))
        for employee_id in getattr(firm, "employees", [])
    )
    cash_runway_ticks = None
    if current_workers > 0 and wage_bill > 0.0:
        cash_runway_ticks = round(float(firm.cash_balance) / max(wage_bill, 1.0), 2)

    return {
        "firm_id": int(firm.firm_id),
        "good_name": str(firm.good_name),
        "category": str(firm.good_category),
        "cash_balance": round(float(firm.cash_balance), 2),
        "inventory_units": round(float(firm.inventory_units), 2),
        "employees": current_workers,
        "expected_sales_units": round(float(firm.expected_sales_units), 2),
        "last_units_sold": round(float(getattr(firm, "last_units_sold", 0.0)), 2),
        "last_revenue": round(float(getattr(firm, "last_revenue", 0.0)), 2),
        "last_profit": round(float(getattr(firm, "last_profit", 0.0)), 2),
        "price": round(float(firm.price), 4),
        "wage_offer": round(float(firm.wage_offer), 4),
        "quality_level": round(float(firm.quality_level), 4),
        "production_capacity_units": round(float(firm.production_capacity_units), 2),
        "target_inventory_weeks": round(float(getattr(firm, "target_inventory_weeks", 0.0)), 4),
        "price_adjustment_rate": round(float(getattr(firm, "price_adjustment_rate", 0.0)), 4),
        "wage_adjustment_rate": round(float(getattr(firm, "wage_adjustment_rate", 0.0)), 4),
        "survival_mode": bool(getattr(firm, "survival_mode", False)),
        "burn_mode": bool(getattr(firm, "burn_mode", False)),
        "bank_loan_remaining": round(float(getattr(firm, "bank_loan_remaining", 0.0)), 2),
        "government_loan_remaining": round(float(getattr(firm, "government_loan_remaining", 0.0)), 2),
        "rd_spending_rate": round(float(getattr(firm, "rd_spending_rate", 0.0)), 4),
        "cash_runway_ticks": cash_runway_ticks,
    }


def _format_recent_memory(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "No prior firm decisions recorded."

    lines: List[str] = []
    for item in history:
        outcome = item.get("observed_outcome")
        if outcome:
            outcome_text = (
                f"cash_delta={outcome.get('cash_delta')}, "
                f"revenue_delta={outcome.get('revenue_delta')}, "
                f"profit_delta={outcome.get('profit_delta')}, "
                f"inventory_delta={outcome.get('inventory_delta')}, "
                f"employees_now={outcome.get('employees_now')}"
            )
        else:
            outcome_text = "pending outcome"
        lines.append(
            f"- tick {item.get('tick')}: {item.get('decisions', {})} | {outcome_text} | "
            f"reasoning={item.get('reasoning', '')}"
        )
    return "\n".join(lines)


def _build_system_prompt(decision_duration_ticks: int) -> str:
    return f"""You are controlling one private firm inside a simulated economy as a cautious beta tester for a new decision app.
SIMULATION CONTEXT: This is a closed computer simulation. All data provided is complete and authoritative. Do not ask for more information. After your reasoning, output valid JSON.

Your job is to improve this firm's survival, cash flow, and medium-term competitiveness without making reckless one-tick swings.
The simulation already has a heuristic planner. Treat that heuristic as the baseline and only nudge the firm's existing state when you have a concrete reason.

Your state changes will persist for about {decision_duration_ticks} tick(s) unless replaced.

You may return only these decision fields:
- price: float or null
- wage_offer: float or null
- expected_sales_units: float or null
- rd_spending_rate: float or null
- target_inventory_weeks: float or null

Rules:
- Prefer changing 0-2 fields per decision cycle.
- If liquidity is tight, protect cash first.
- These values modify the firm's current state before the next tick.
- price and wage_offer are absolute values, not multipliers.
- If the baseline already looks sensible, keep the override empty.

Respond with JSON only:
{{
  "decisions": {{
    "price": null,
    "wage_offer": null,
    "expected_sales_units": null,
    "rd_spending_rate": null,
    "target_inventory_weeks": null
  }},
  "reasoning": "2-4 concise sentences about what the firm thinks is happening",
  "player_explanation": "plain-English explanation of what the firm is trying to do",
  "debugger_explanation": "debugging explanation tied to the firm's observable inputs",
  "debug_flags": ["short phrases for anything that seems odd or worth debugging"]
}}"""


class LLMFirmAdvisor:
    """Single-firm decision controller backed by a local or remote LLM provider."""

    def __init__(
        self,
        provider: LLMProvider,
        config: Any,
        decision_duration_ticks: int = 1,
    ):
        self.provider = provider
        self.config = config
        self.decision_duration_ticks = max(1, int(decision_duration_ticks))
        self._decision_history: List[Dict[str, Any]] = []

    def _observable_inputs(self, economy: Any, firm: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Return the signals this firm can reasonably react to inside the sim."""
        category = (firm.good_category or "").lower()
        private_housing_inventory = sum(
            float(candidate.inventory_units)
            for candidate in getattr(economy, "firms", [])
            if (candidate.good_category or "").lower() == "housing" and not candidate.is_baseline
        )
        return {
            "tick": int(getattr(economy, "current_tick", 0)),
            "warmup_active": bool(getattr(economy, "in_warmup", False)),
            "large_market": bool(getattr(economy, "large_market", False)),
            "post_warmup_cooldown": bool(getattr(economy, "post_warmup_cooldown", 0) > 0),
            "total_households": int(len(getattr(economy, "households", []) or [])),
            "last_tick_sales_units": round(float(economy.last_tick_sales_units.get(firm.firm_id, 0.0)), 2),
            "last_tick_sell_through_rate": round(float(economy.last_tick_sell_through_rate.get(firm.firm_id, 0.5)), 4),
            "unemployment_rate": round(float(metrics.get("unemployment_rate", 0.0)), 4),
            "unemployment_benefit": round(float(economy.government.get_unemployment_benefit_level()), 4),
            "minimum_wage_floor": round(float(economy.government.get_minimum_wage()), 4),
            "private_housing_inventory": round(private_housing_inventory, 2) if category == "housing" else None,
        }

    @staticmethod
    def _fallback_explanations(
        firm_state_before: Dict[str, Any],
        observable_inputs: Dict[str, Any],
        baseline_plan: Dict[str, Any],
        decisions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Produce deterministic explanations when the model omits them."""
        debug_flags: List[str] = []
        if observable_inputs.get("warmup_active"):
            debug_flags.append("warmup_phase")
        if firm_state_before.get("survival_mode"):
            debug_flags.append("survival_mode")
        if float(firm_state_before.get("last_profit", 0.0)) < 0:
            debug_flags.append("negative_profit")
        if (
            float(firm_state_before.get("inventory_units", 0.0))
            > max(1.0, float(firm_state_before.get("expected_sales_units", 0.0))) * 2.0
        ):
            debug_flags.append("inventory_overhang")
        if (
            float(firm_state_before.get("cash_runway_ticks") or 999.0)
            < max(1.0, len(debug_flags))
        ):
            debug_flags.append("short_cash_runway")

        decision_text = "hold the current state"
        if decisions:
            parts = [f"{key}={value}" for key, value in decisions.items()]
            decision_text = "adjust " + ", ".join(parts)

        player_explanation = (
            f"The firm is trying to {decision_text}. "
            f"It sees sales={observable_inputs.get('last_tick_sales_units')}, "
            f"sell-through={observable_inputs.get('last_tick_sell_through_rate')}, "
            f"cash=${firm_state_before.get('cash_balance')}, and inventory={firm_state_before.get('inventory_units')}."
        )
        debugger_explanation = (
            f"Baseline heuristic wanted production={baseline_plan.get('planned_production_units')}, "
            f"price_next={baseline_plan.get('price_next')}, wage_next={baseline_plan.get('wage_offer_next')}. "
            f"Observable inputs were unemployment={observable_inputs.get('unemployment_rate')} "
            f"and benefit={observable_inputs.get('unemployment_benefit')}."
        )
        return {
            "player_explanation": player_explanation,
            "debugger_explanation": debugger_explanation,
            "debug_flags": debug_flags,
        }

    def _baseline_plan(self, economy: Any, firm: Any) -> Dict[str, Any]:
        """Compute the heuristic baseline on a cloned firm so prompts stay side-effect free."""
        firm_clone = copy.deepcopy(firm)

        total_households = len(getattr(economy, "households", []) or [])
        private_housing_inventory = sum(
            float(candidate.inventory_units)
            for candidate in getattr(economy, "firms", [])
            if (candidate.good_category or "").lower() == "housing" and not candidate.is_baseline
        )
        baseline_production = firm_clone.plan_production_and_labor(
            economy.last_tick_sales_units.get(firm.firm_id, 0.0),
            in_warmup=bool(getattr(economy, "in_warmup", False)),
            total_households=total_households,
            global_unsold_inventory=private_housing_inventory,
            private_housing_inventory=private_housing_inventory,
            large_market=bool(getattr(economy, "large_market", False)),
            post_warmup_cooldown=bool(getattr(economy, "post_warmup_cooldown", 0) > 0),
        )

        unemployment_rate = 0.0
        metrics = {}
        if hasattr(economy, "get_economic_metrics"):
            metrics = economy.get_economic_metrics()
            unemployment_rate = float(metrics.get("unemployment_rate", 0.0))

        category_offers = [
            float(candidate.wage_offer)
            for candidate in getattr(economy, "firms", [])
            if not candidate.is_baseline and (candidate.good_category or "") == (firm.good_category or "")
        ]
        category_wage_anchor_p75 = max(category_offers) if category_offers else float(firm.wage_offer)
        health_snapshot = firm_clone.refresh_health_snapshot(
            sell_through_rate=float(economy.last_tick_sell_through_rate.get(firm.firm_id, 0.5)),
            category_wage_anchor_p75=category_wage_anchor_p75,
        )

        baseline_price = firm_clone.plan_pricing(
            economy.last_tick_sell_through_rate.get(firm.firm_id, 0.5),
            unemployment_rate=unemployment_rate,
            in_warmup=bool(getattr(economy, "in_warmup", False)),
            health_snapshot=health_snapshot,
        )
        baseline_wage = firm_clone.plan_wage(
            unemployment_rate=unemployment_rate,
            unemployment_benefit=float(economy.government.get_unemployment_benefit_level()),
            in_warmup=bool(getattr(economy, "in_warmup", False)),
            health_snapshot=health_snapshot,
        )

        target_headcount = (
            len(getattr(firm, "employees", []) or [])
            + int(baseline_production.get("planned_hires_count", 0))
            - len(baseline_production.get("planned_layoffs_ids", []) or [])
        )

        return {
            "planned_production_units": round(float(baseline_production.get("planned_production_units", 0.0)), 2),
            "target_headcount": int(target_headcount),
            "planned_hires_count": int(baseline_production.get("planned_hires_count", 0)),
            "planned_layoffs_count": len(baseline_production.get("planned_layoffs_ids", []) or []),
            "price_next": round(float(baseline_price.get("price_next", firm.price)), 4),
            "wage_offer_next": round(float(baseline_wage.get("wage_offer_next", firm.wage_offer)), 4),
            "rd_spending_rate": round(float(getattr(firm, "rd_spending_rate", 0.0)), 4),
            "economy_metrics": metrics,
        }

    def _build_user_prompt(
        self,
        economy: Any,
        firm: Any,
        baseline_plan: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> str:
        history_window = max(1, int(getattr(self.config, "agent_history_window", 4)))
        recent_history = self._decision_history[-history_window:]
        baseline_for_prompt = dict(baseline_plan)
        baseline_for_prompt.pop("economy_metrics", None)
        observable_inputs = self._observable_inputs(economy, firm, metrics)

        return (
            f"Observable firm inputs:\n{json.dumps(observable_inputs, indent=2)}\n\n"
            f"Target firm snapshot:\n{json.dumps(_firm_state_snapshot(firm), indent=2)}\n\n"
            f"Heuristic baseline for next tick:\n{json.dumps(baseline_for_prompt, indent=2)}\n\n"
            f"Recent firm memory:\n{_format_recent_memory(recent_history)}\n\n"
            "Decide whether to nudge the firm's state for the next decision window."
        )

    def _update_last_outcome(self, firm: Any) -> None:
        """Record one-step observed outcome for the previous decision, if missing."""
        self.finalize_last_outcome(_firm_state_snapshot(firm))

    @staticmethod
    def _build_observed_outcome(
        before: Dict[str, Any],
        after: Optional[Dict[str, Any]],
        status: Optional[str] = None,
        bankrupt_tick: Optional[int] = None,
    ) -> Dict[str, Any]:
        outcome: Dict[str, Any] = {
            "cash_delta": None,
            "revenue_delta": None,
            "profit_delta": None,
            "inventory_delta": None,
            "employees_now": None,
            "survival_mode_now": None,
        }
        if after is not None:
            outcome.update(
                {
                    "cash_delta": round(float(after.get("cash_balance", 0.0)) - float(before.get("cash_balance", 0.0)), 2),
                    "revenue_delta": round(float(after.get("last_revenue", 0.0)) - float(before.get("last_revenue", 0.0)), 2),
                    "profit_delta": round(float(after.get("last_profit", 0.0)) - float(before.get("last_profit", 0.0)), 2),
                    "inventory_delta": round(float(after.get("inventory_units", 0.0)) - float(before.get("inventory_units", 0.0)), 2),
                    "employees_now": int(after.get("employees", 0)),
                    "survival_mode_now": bool(after.get("survival_mode", False)),
                }
            )
        if status is not None:
            outcome["status_now"] = status
        if bankrupt_tick is not None:
            outcome["bankrupt_tick"] = int(bankrupt_tick)
        return outcome

    def finalize_last_outcome(
        self,
        after_state: Optional[Dict[str, Any]],
        status: Optional[str] = None,
        bankrupt_tick: Optional[int] = None,
    ) -> None:
        if not self._decision_history:
            return
        last = self._decision_history[-1]
        if last.get("observed_outcome") is not None:
            return

        before = last.get("firm_state_before", {})
        if not before:
            return
        last["observed_outcome"] = self._build_observed_outcome(
            before=before,
            after=after_state,
            status=status,
            bankrupt_tick=bankrupt_tick,
        )

    def record_applied_decision(self, applied: Dict[str, Any]) -> None:
        if not self._decision_history:
            return
        self._decision_history[-1]["applied_decision"] = dict(applied or {})

    def _validate_decisions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        decisions_blob = payload.get("decisions", payload)
        if not isinstance(decisions_blob, dict):
            return {}

        decisions: Dict[str, Any] = {}
        for field in ALLOWED_DECISION_FIELDS:
            value = decisions_blob.get(field)
            if value is None:
                continue
            numeric = _safe_float(value)
            if numeric is None:
                continue
            decisions[field] = float(numeric)
        return decisions

    async def decide(self, economy: Any, firm_id: int) -> Dict[str, Any]:
        """Run one decision cycle for a single active firm."""
        firm = getattr(economy, "firm_lookup", {}).get(int(firm_id))
        if firm is None:
            raise ValueError(f"Firm {firm_id} is not active in the economy.")

        self._update_last_outcome(firm)

        t0 = time.perf_counter()
        metrics = economy.get_economic_metrics() if hasattr(economy, "get_economic_metrics") else {}
        baseline_plan = self._baseline_plan(economy, firm)
        observable_inputs = self._observable_inputs(economy, firm, metrics)
        firm_state_before = _firm_state_snapshot(firm)
        system_prompt = _build_system_prompt(self.decision_duration_ticks)
        user_prompt = self._build_user_prompt(economy, firm, baseline_plan, metrics)

        parsed: Optional[Dict[str, Any]] = None
        reasoning = ""
        player_explanation = ""
        debugger_explanation = ""
        debug_flags: List[str] = []
        try:
            raw = await self.provider.complete(
                system=system_prompt,
                user=user_prompt,
                temperature=float(
                    getattr(
                        self.config,
                        "agent_temperature",
                        getattr(self.config, "government_temperature", 0.3),
                    )
                ),
                response_format={"type": "json_object"},
            )
            parsed = extract_json_from_response(raw)
            if parsed is None:
                raise ValueError("model returned non-JSON content")
            decisions = self._validate_decisions(parsed)
            reasoning = str(parsed.get("reasoning", "")).strip()
            player_explanation = str(parsed.get("player_explanation", "")).strip()
            debugger_explanation = str(parsed.get("debugger_explanation", "")).strip()
            if isinstance(parsed.get("debug_flags"), list):
                debug_flags = [str(flag).strip() for flag in parsed["debug_flags"] if str(flag).strip()]
            parse_ok = True
        except Exception as exc:
            logger.warning("Firm LLM call failed for firm %s: %s", firm_id, exc)
            decisions = {}
            reasoning = f"LLM call failed: {exc}"
            parse_ok = False

        fallback = self._fallback_explanations(
            firm_state_before=firm_state_before,
            observable_inputs=observable_inputs,
            baseline_plan={k: v for k, v in baseline_plan.items() if k != "economy_metrics"},
            decisions=decisions,
        )
        if not player_explanation:
            player_explanation = fallback["player_explanation"]
        if not debugger_explanation:
            debugger_explanation = fallback["debugger_explanation"]
        if not debug_flags:
            debug_flags = list(fallback["debug_flags"])

        result = {
            "tick": int(getattr(economy, "current_tick", 0)),
            "firm_id": int(firm_id),
            "decisions": decisions,
            "reasoning": reasoning,
            "player_explanation": player_explanation,
            "debugger_explanation": debugger_explanation,
            "debug_flags": debug_flags,
            "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
            "parse_ok": parse_ok,
            "provider": getattr(self.provider, "name", "unknown"),
            "firm_state_before": firm_state_before,
            "observable_inputs": observable_inputs,
            "baseline_plan": {k: v for k, v in baseline_plan.items() if k != "economy_metrics"},
        }
        self._decision_history.append(result)
        return result

    @property
    def decision_history(self) -> List[Dict[str, Any]]:
        return list(self._decision_history)

    @property
    def last_decision(self) -> Optional[Dict[str, Any]]:
        return self._decision_history[-1] if self._decision_history else None


