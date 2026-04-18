
"""EcoSim runner for one LLM-controlled private firm.

Usage:
    python run_llm_firm_test.py
    python run_llm_firm_test.py --category Services --firm-index 0
    python run_llm_firm_test.py --firm-id 7 --model your_local_4b_model
    python run_llm_firm_test.py --provider lmstudio --model local-model
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

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from llm_firm import LLMFirmAdvisor
from llm_provider import LMStudioProvider, OllamaProvider
from run_large_simulation import create_large_economy


def parse_args():
    parser = argparse.ArgumentParser(description="EcoSim single-firm LLM runner")
    parser.add_argument("--ticks", type=int, default=90, help="Number of ticks to run (default: 90)")
    parser.add_argument("--households", type=int, default=200, help="Number of households (default: 200)")
    parser.add_argument("--firms-per-category", type=int, default=2, help="Private firms per category target (default: 2)")
    parser.add_argument("--interval", type=int, default=2, help="Ticks between LLM decisions (default: 2)")
    parser.add_argument("--warmup-ticks", type=int, default=None, help="Optional warmup override; otherwise use the simulation config value")
    parser.add_argument("--category", type=str, default="Food", help="Private firm category when firm-id is omitted")
    parser.add_argument("--firm-index", type=int, default=0, help="Zero-based private firm index within the category")
    parser.add_argument("--firm-id", type=int, default=None, help="Explicit firm_id to control")
    parser.add_argument("--provider", type=str, default="lmstudio", choices=["ollama", "lmstudio"], help="LLM provider")
    parser.add_argument("--model", type=str, default="microsoft/phi-4-mini-reasoning", help="Model name to use")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:1234", help="LM Studio base URL")
    parser.add_argument("--temperature", type=float, default=0.3, help="Sampling temperature (default: 0.3)")
    parser.add_argument("--timeout", type=float, default=600.0, help="Provider timeout in seconds (default: 600)")
    parser.add_argument("--max-tokens", type=int, default=40000, help="LM Studio max tokens (default: 40000)")
    parser.add_argument("--log-file", type=str, default="backend/firm_llm_run_log.json", help="JSON run log path")
    parser.add_argument("--no-probe", action="store_true", help="Skip the warmup request")
    return parser.parse_args()


def resolve_target_firm_id(economy: Any, firm_id: Optional[int], category: str, firm_index: int) -> int:
    if firm_id is not None:
        known_ids = {firm.firm_id for firm in economy.firms}
        known_ids.update(firm.firm_id for firm in economy.queued_firms)
        if firm_id not in known_ids:
            raise ValueError(f"Firm id {firm_id} not found in active or queued firms.")
        return int(firm_id)

    wanted_category = category.strip().lower()
    candidates = [
        firm
        for firm in list(economy.firms) + list(economy.queued_firms)
        if not firm.is_baseline and (firm.good_category or "").lower() == wanted_category
    ]
    candidates.sort(key=lambda candidate: candidate.firm_id)
    if not candidates:
        raise ValueError(f"No private firms found for category '{category}'.")
    if firm_index < 0 or firm_index >= len(candidates):
        raise ValueError(
            f"firm-index {firm_index} is out of range for category '{category}' "
            f"(available: 0..{len(candidates) - 1})."
        )
    return int(candidates[firm_index].firm_id)


def make_provider(args) -> Any:
    if args.provider == "lmstudio":
        return LMStudioProvider(base_url=args.base_url, model=args.model, timeout=args.timeout, max_tokens=args.max_tokens)
    return OllamaProvider(model=args.model, timeout=args.timeout)


def target_firm_label(economy: Any, firm_id: int) -> str:
    firm = economy.firm_lookup.get(firm_id)
    if firm is None:
        queued = next((candidate for candidate in economy.queued_firms if candidate.firm_id == firm_id), None)
        if queued is None:
            return f"firm {firm_id}"
        return f"{queued.good_name} ({queued.good_category}, queued)"
    return f"{firm.good_name} ({firm.good_category}, active)"


def apply_state_decision(firm: Any, decision: Dict[str, float], minimum_wage: float) -> Dict[str, float]:
    """Apply a conservative state-level nudge to one firm between ticks."""
    applied: Dict[str, float] = {}

    price = decision.get("price")
    if price is not None:
        current_price = max(float(firm.price), 0.01)
        floor = max(float(firm.min_price), current_price * 0.85)
        ceiling = max(floor, current_price * 1.15)
        firm.price = max(floor, min(ceiling, float(price)))
        applied["price"] = round(float(firm.price), 4)

    wage_offer = decision.get("wage_offer")
    if wage_offer is not None:
        current_wage = max(float(firm.wage_offer), minimum_wage)
        floor = max(minimum_wage, current_wage * 0.85)
        ceiling = max(floor, current_wage * 1.15)
        firm.wage_offer = max(floor, min(ceiling, float(wage_offer)))
        applied["wage_offer"] = round(float(firm.wage_offer), 4)

    expected_sales_units = decision.get("expected_sales_units")
    if expected_sales_units is not None:
        floor = max(float(CONFIG.firms.min_expected_sales), float(firm.expected_sales_units) * 0.75)
        ceiling = max(floor, float(firm.production_capacity_units) * 1.25)
        firm.expected_sales_units = max(floor, min(ceiling, float(expected_sales_units)))
        applied["expected_sales_units"] = round(float(firm.expected_sales_units), 2)

    rd_spending_rate = decision.get("rd_spending_rate")
    if rd_spending_rate is not None:
        firm.rd_spending_rate = max(0.0, min(0.25, float(rd_spending_rate)))
        applied["rd_spending_rate"] = round(float(firm.rd_spending_rate), 4)

    target_inventory_weeks = decision.get("target_inventory_weeks")
    if target_inventory_weeks is not None:
        firm.target_inventory_weeks = max(0.5, min(8.0, float(target_inventory_weeks)))
        applied["target_inventory_weeks"] = round(float(firm.target_inventory_weeks), 4)

    return applied


def format_row(tick: int, firm: Optional[Any], metrics: Dict[str, float], llm_label: str) -> str:
    if firm is None:
        return (
            f"{tick:>4} | {'WAIT':>9} | {'-':>8} | {'-':>8} | {'-':>8} | {'-':>4} | "
            f"{'-':>7} | {'-':>7} | {'-':>4} | {metrics.get('unemployment_rate', 0.0) * 100:>5.1f}% | {llm_label:>7}"
        )

    return (
        f"{tick:>4} | "
        f"{firm.cash_balance:>9.0f} | "
        f"{firm.inventory_units:>8.0f} | "
        f"{getattr(firm, 'last_revenue', 0.0):>8.0f} | "
        f"{getattr(firm, 'last_profit', 0.0):>8.0f} | "
        f"{len(firm.employees):>4d} | "
        f"{firm.price:>7.2f} | "
        f"{firm.wage_offer:>7.2f} | "
        f"{'Y' if getattr(firm, 'survival_mode', False) else 'N':>4} | "
        f"{metrics.get('unemployment_rate', 0.0) * 100:>5.1f}% | "
        f"{llm_label:>7}"
    )


def serialize_firm_state(firm: Optional[Any]) -> Optional[Dict[str, Any]]:
    if firm is None:
        return None
    return {
        "firm_id": int(firm.firm_id),
        "good_name": str(firm.good_name),
        "category": str(firm.good_category),
        "cash_balance": float(firm.cash_balance),
        "inventory_units": float(firm.inventory_units),
        "last_revenue": float(getattr(firm, "last_revenue", 0.0)),
        "last_profit": float(getattr(firm, "last_profit", 0.0)),
        "employees": int(len(firm.employees)),
        "price": float(firm.price),
        "wage_offer": float(firm.wage_offer),
        "survival_mode": bool(getattr(firm, "survival_mode", False)),
    }


def resolve_target_status(firm: Optional[Any], activation_tick: Optional[int], bankrupt_tick: Optional[int]) -> str:
    if firm is not None:
        return "active"
    if activation_tick is None:
        return "pending"
    return "bankrupt"


def append_tick_log(
    log_rows: list,
    tick: int,
    firm: Optional[Any],
    phase: str,
    status: str,
    bankrupt_tick: Optional[int],
    note: str = "",
    llm_result: Optional[Dict[str, Any]] = None,
    applied: Optional[Dict[str, float]] = None,
    firm_state_before_apply: Optional[Dict[str, Any]] = None,
    firm_state_after_apply: Optional[Dict[str, Any]] = None,
) -> None:
    row: Dict[str, Any] = {
        "tick": int(tick),
        "phase": phase,
        "status": status,
        "bankrupt_tick": int(bankrupt_tick) if bankrupt_tick is not None else None,
        "note": note,
        "firm_state": serialize_firm_state(firm),
    }
    if llm_result is not None:
        row["firm_state_before_apply"] = firm_state_before_apply or row["firm_state"]
        row["firm_state_after_apply"] = firm_state_after_apply or row["firm_state"]
        row["llm_decision"] = {
            "decisions": dict(llm_result.get("decisions", {})),
            "applied": dict(applied or {}),
            "reasoning": llm_result.get("reasoning", ""),
            "player_explanation": llm_result.get("player_explanation", ""),
            "debugger_explanation": llm_result.get("debugger_explanation", ""),
            "debug_flags": list(llm_result.get("debug_flags", [])),
            "observable_inputs": dict(llm_result.get("observable_inputs", {})),
            "baseline_plan": dict(llm_result.get("baseline_plan", {})),
        }
    log_rows.append(row)


async def main():
    args = parse_args()

    if args.warmup_ticks is not None:
        CONFIG.time.warmup_ticks = max(0, args.warmup_ticks)
    CONFIG.llm.enable_llm_agents = True
    CONFIG.llm.provider = args.provider
    CONFIG.llm.agent_model = args.model
    CONFIG.llm.agent_temperature = args.temperature
    CONFIG.llm.agent_history_window = 4

    print("=" * 100)
    print("  EcoSim Single-Firm LLM Runner")
    print(
        f"  Households: {args.households} | Ticks: {args.ticks} | "
        f"Decision interval: {args.interval} | Warmup ticks: {CONFIG.time.warmup_ticks}"
    )
    print(f"  Provider: {args.provider} | Model: {args.model} | Temperature: {args.temperature}")
    print("=" * 100)

    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households,
        num_firms_per_category=args.firms_per_category,
    )
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} active firms, {len(economy.queued_firms)} queued)")
    active_warmup_ticks = int(getattr(economy, "warmup_ticks", CONFIG.time.warmup_ticks))

    print(
        f"Warmup source: {'CLI override' if args.warmup_ticks is not None else 'simulation config'} "
        f"({active_warmup_ticks} ticks)"
    )

    target_id = resolve_target_firm_id(economy, args.firm_id, args.category, args.firm_index)
    print(f"Target firm: {target_firm_label(economy, target_id)} [firm_id={target_id}]")
    if args.ticks <= active_warmup_ticks:
        print(f"Warning: ticks={args.ticks} does not extend past warmup={active_warmup_ticks}; no private-firm decisions will run.")

    print(f"Connecting to {args.provider}...", end=" ", flush=True)
    provider = make_provider(args)
    if not await provider.health_check():
        if args.provider == "lmstudio":
            print("FATAL: LM Studio not reachable on localhost:1234")
        else:
            print(f"FATAL: Ollama not reachable or model '{args.model}' not found")
            print(f"  ollama pull {args.model}")
        return
    print(f"connected ({provider.name})")

    advisor = LLMFirmAdvisor(provider, CONFIG.llm, decision_duration_ticks=args.interval)

    if not args.no_probe:
        print("\nWarming up model...", flush=True)
        t0 = time.perf_counter()
        try:
            await provider.complete(
                system='Respond with JSON: {"ready": true}',
                user="warmup",
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            print(f"  Model ready ({(time.perf_counter() - t0):.1f}s)")
        except Exception as exc:
            print(f"  Probe failed ({exc}) - continuing")

    print("\n" + "-" * 100)
    print(
        f"{'Tick':>4} | {'Cash':>9} | {'Inv':>8} | {'Rev':>8} | {'Profit':>8} | {'Wrk':>4} | "
        f"{'Price':>7} | {'Wage':>7} | {'Surv':>4} | {'Unemp':>6} | {'LLM':>7}"
    )
    print("-" * 100)

    announced_active = False
    activation_tick: Optional[int] = None
    bankrupt_tick: Optional[int] = None
    last_seen_firm_state: Optional[Dict[str, Any]] = None
    sim_start = time.perf_counter()
    log_rows = []
    log_path = Path(args.log_file)

    for _ in range(args.ticks):
        economy.step()
        metrics = economy.get_economic_metrics()
        economy.append_metrics_snapshot(metrics, tick=economy.current_tick)

        firm = economy.firm_lookup.get(target_id)
        llm_label = ""
        phase = "warmup" if bool(getattr(economy, "in_warmup", False)) else "post_warmup"
        note = ""

        if firm is not None and not announced_active:
            announced_active = True
            activation_tick = economy.current_tick
            print(f"\n  Target firm activated on tick {economy.current_tick}: {target_firm_label(economy, target_id)}\n")
        if firm is not None:
            bankrupt_tick = None
            last_seen_firm_state = serialize_firm_state(firm)
        elif activation_tick is not None and bankrupt_tick is None:
            bankrupt_tick = economy.current_tick

        status = resolve_target_status(firm, activation_tick, bankrupt_tick)

        if phase == "warmup":
            note = "Warmup phase: observing only."
        elif status == "pending":
            note = "Target private firm not active yet."
        elif status == "bankrupt":
            note = "Target private firm is no longer active."

        if (
            firm is not None
            and not bool(getattr(economy, "in_warmup", False))
            and economy.current_tick % args.interval == 0
        ):
            print(f"\n  ... LLM thinking for firm {target_id} at tick {economy.current_tick} ...", flush=True)
            result = await advisor.decide(economy, target_id)
            llm_label = f"{result['elapsed_ms'] / 1000.0:.1f}s"
            firm_state_before_apply = serialize_firm_state(firm)
            applied = apply_state_decision(
                firm,
                result["decisions"],
                minimum_wage=float(economy.government.get_minimum_wage()),
            )
            firm_state_after_apply = serialize_firm_state(firm)
            advisor.record_applied_decision(applied)
            last_seen_firm_state = firm_state_after_apply

            if applied:
                print(f"  Applied state nudge: {applied}")
                if result.get("reasoning"):
                    print(f"  Reasoning: {result['reasoning']}")
                if result.get("player_explanation"):
                    print(f"  Player view: {result['player_explanation']}")
                if result.get("debugger_explanation"):
                    print(f"  Debug view:  {result['debugger_explanation']}")
                if result.get("debug_flags"):
                    print(f"  Flags: {', '.join(result['debug_flags'])}")
            else:
                print(f"  No override: {result['reasoning']}")
            print()
            append_tick_log(
                log_rows,
                tick=economy.current_tick,
                firm=firm,
                phase=phase,
                status=status,
                bankrupt_tick=bankrupt_tick,
                note=note,
                llm_result=result,
                applied=applied,
                firm_state_before_apply=firm_state_before_apply,
                firm_state_after_apply=firm_state_after_apply,
            )
        else:
            append_tick_log(
                log_rows,
                tick=economy.current_tick,
                firm=firm,
                phase=phase,
                status=status,
                bankrupt_tick=bankrupt_tick,
                note=note,
            )

        print(format_row(economy.current_tick, firm, metrics, llm_label), flush=True)

    total_time = time.perf_counter() - sim_start
    final_firm = economy.firm_lookup.get(target_id)
    final_status = resolve_target_status(final_firm, activation_tick, bankrupt_tick)
    advisor.finalize_last_outcome(
        after_state=serialize_firm_state(final_firm) if final_firm is not None else last_seen_firm_state,
        status=final_status,
        bankrupt_tick=bankrupt_tick,
    )

    print("\n" + "=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)

    firm = final_firm
    if firm is not None:
        print(f"Target firm: {firm.good_name} [{firm.firm_id}]")
        print(f"  Cash:       ${firm.cash_balance:,.2f}")
        print(f"  Inventory:  {firm.inventory_units:,.2f}")
        print(f"  Revenue:    ${getattr(firm, 'last_revenue', 0.0):,.2f}")
        print(f"  Profit:     ${getattr(firm, 'last_profit', 0.0):,.2f}")
        print(f"  Employees:  {len(firm.employees)}")
        print(f"  Price:      ${firm.price:,.2f}")
        print(f"  Wage offer: ${firm.wage_offer:,.2f}")
        print(f"  Survival:   {'on' if getattr(firm, 'survival_mode', False) else 'off'}")
    elif activation_tick is None:
        print(f"Target firm {target_id} never activated.")
    else:
        print(f"Target firm {target_id} is no longer active.")
        print(f"  Status:     bankrupt")
        print(f"  Bankrupt:   tick {bankrupt_tick}")

    print(f"\nDecision count: {len(advisor.decision_history)}")
    print(f"Total time: {total_time:.1f}s")
    log_rows.append(
        {
            "type": "run_summary",
            "target_firm_id": int(target_id),
            "target_firm_label": target_firm_label(economy, target_id),
            "status": final_status,
            "activation_tick": activation_tick,
            "bankrupt_tick": bankrupt_tick,
            "warmup_ticks": active_warmup_ticks,
            "ticks_run": int(args.ticks),
            "decision_count": int(len(advisor.decision_history)),
            "decision_history": advisor.decision_history,
        }
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log_rows, indent=2), encoding="utf-8")
    print(f"Run log: {log_path}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())


