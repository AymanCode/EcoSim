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
    python run_llm_government_test.py --warmup-ticks 12        # shorter bootstrap period
    python run_llm_government_test.py --no-probe               # skip warmup probe
"""

import argparse
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy
from llm_provider import OllamaProvider, LMStudioProvider
from llm_government import LLMGovernmentAdvisor


def parse_args():
    parser = argparse.ArgumentParser(description="EcoSim LLM Government Runner")
    parser.add_argument("--ticks", type=int, default=24, help="Number of ticks to run (default: 24)")
    parser.add_argument("--households", type=int, default=200, help="Number of households (default: 200)")
    parser.add_argument("--interval", type=int, default=4, help="Ticks between LLM decisions (default: 4)")
    parser.add_argument("--philosophy", type=str, default="capitalist",
                        choices=["capitalist", "keynesian", "balanced"],
                        help="Government philosophy (default: capitalist)")
    parser.add_argument("--model", type=str, default="phi4-mini-reasoning", help="Model name (default: phi4-mini-reasoning)")
    parser.add_argument("--provider", type=str, default="ollama", choices=["ollama", "lmstudio"],
                        help="LLM provider (default: ollama)")
    parser.add_argument("--temperature", type=float, default=0.4, help="LLM temperature (default: 0.4)")
    parser.add_argument("--warmup-ticks", type=int, default=12,
                        help="Warmup ticks before queued firms activate (default: 12 for LLM tests)")
    parser.add_argument("--no-probe", action="store_true", help="Skip the warmup LLM probe")
    parser.add_argument("--timeout", type=float, default=300.0, help="LLM call timeout in seconds (default: 300)")
    parser.add_argument("--max-tokens", type=int, default=8192, help="Max tokens per LLM call (default: 8192)")
    parser.add_argument("--no-think", action="store_true", help="Append /no_think to disable DeepSeek R1 thinking")
    return parser.parse_args()


async def main():
    args = parse_args()

    # Configure
    CONFIG.llm.enable_llm_government = True
    CONFIG.llm.government_decision_interval = args.interval
    CONFIG.llm.government_model = args.model
    CONFIG.llm.government_philosophy = args.philosophy
    CONFIG.llm.government_temperature = args.temperature
    CONFIG.llm.no_think = args.no_think
    CONFIG.time.warmup_ticks = max(0, args.warmup_ticks)

    print("=" * 100)
    print(f"  EcoSim LLM Government Runner")
    print(f"  Households: {args.households} | Ticks: {args.ticks} | Decisions every {args.interval} ticks")
    print(f"  Model: {args.model} | Provider: {args.provider} | Philosophy: {args.philosophy} | Temperature: {args.temperature}")
    print(f"  Warmup ticks: {CONFIG.time.warmup_ticks}")
    print("=" * 100)

    # Create economy
    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households,
        num_firms_per_category=2,
    )
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} firms)")

    # Connect to provider
    print(f"Connecting to {args.provider}...", end=" ", flush=True)
    if args.provider == "lmstudio":
        provider = LMStudioProvider(model=args.model, timeout=args.timeout, max_tokens=args.max_tokens)
    else:
        provider = OllamaProvider(model=args.model, timeout=args.timeout)

    if not await provider.health_check():
        if args.provider == "lmstudio":
            print(f"FATAL: LM Studio not reachable on localhost:1234")
            print("Make sure LM Studio is running with the local server enabled (port 1234)")
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
            print(f"  Probe failed ({e}) â€” continuing, first decision may be slow")

    # Simulation loop
    num_decisions = args.ticks // args.interval
    est_time = num_decisions * 90  # rough estimate: ~90s per decision with thinking model
    print(f"\nStarting simulation â€” ~{num_decisions} LLM decisions expected")
    print(f"Estimated time: ~{est_time // 60}m {est_time % 60}s (depends on model speed)\n")

    print("-" * 100)
    print(f" {'Tick':>4} | {'Unemp':>6} | {'MnWage':>7} | {'MdnCash':>9} | {'Hlth':>5} | {'Happy':>5} | "
          f"{'Morale':>6} | {'Firms':>5} | {'GovCash':>11} | {'GDP':>8} | {'LLM':>6}")
    print("-" * 100)

    sim_start = time.perf_counter()

    for tick in range(args.ticks):
        # Economy tick
        economy.step()

        # Metrics + history
        metrics = economy.get_economic_metrics()
        economy.append_metrics_snapshot(metrics, tick=economy.current_tick)

        # LLM decision
        llm_label = ""
        if economy.current_tick > 0 and economy.current_tick % args.interval == 0:
            print(f"\n  ... LLM thinking (tick {economy.current_tick}) ...", flush=True)
            t0 = time.perf_counter()
            result = await advisor.decide(economy)
            economy.record_llm_government_decision(result)
            elapsed_s = time.perf_counter() - t0
            llm_label = f"{elapsed_s:.0f}s"

            if result["decisions"]:
                print(f"  â”Œâ”€â”€ LLM DECISION (tick {economy.current_tick}, {elapsed_s:.1f}s) â”€â”€")
                for lever, value in result["decisions"].items():
                    before = result['current_policy_before'].get(lever, '?')
                    print(f"  â”‚  {lever}: {before} â†’ {value}")
                print(f"  â”‚")
                print(f"  â”‚  \"{result['reasoning']}\"")
                dq = result.get("data_quality_summary", {})
                print(f"  â”‚  [data: {dq.get('reported', 0)} reported, {dq.get('unavailable', 0)} unavailable]")
                print(f"  â””{'â”€' * 70}")
            else:
                reason = result['reasoning'][:120]
                print(f"  â”€â”€ NO CHANGES ({elapsed_s:.1f}s): {reason}")
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
    for d in advisor.decision_history:
        tick_n = d["tick"]
        decisions = d["decisions"]
        reasoning = d["reasoning"]
        elapsed = d["elapsed_ms"]
        parse_ok = d["parse_ok"]
        if decisions:
            changes = ", ".join(f"{k}: {v}" for k, v in decisions.items())
            print(f"  Tick {tick_n:>3} ({elapsed / 1000:.0f}s): {changes}")
            print(f"           \"{reasoning}\"")
        else:
            status = "hold" if parse_ok else "PARSE FAIL"
            print(f"  Tick {tick_n:>3} ({elapsed / 1000:.0f}s): [{status}] {reasoning}")

    # Final state
    gov = economy.government
    print(f"\n{'â”€' * 50}")
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
    print(f"Simulation ticks: {args.ticks} ({args.ticks * (total_time / args.ticks):.0f}ms avg)")
    print(f"LLM decisions: {len(advisor.decision_history)}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())

