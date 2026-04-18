from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""
EcoSim All-Archetype Runner
============================
Runs run_household_llm_tester.py 5 times, one per archetype:
  1. frugal       â€” high saver, high frugality
  2. average      â€” closest to population median
  3. spendthrift  â€” low saver, spends freely
  4. random_a     â€” random household (seed 42)
  5. random_b     â€” a different random household (seed 99)

Each run is fully independent: separate economy, separate log file.
All rich per-tick output is preserved â€” this script just sequences them.

Output files:
  household_llm_run_log_frugal.json
  household_llm_run_log_average.json
  household_llm_run_log_spendthrift.json
  household_llm_run_log_random_a.json   (seed 42)
  household_llm_run_log_random_b.json   (seed 99)

Usage:
    python run_all_archetypes.py
    python run_all_archetypes.py --ticks 60 --households 250 --feedback-every 10
    python run_all_archetypes.py --model qwen3:8b --skip frugal average
"""

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy
from llm_provider import LMStudioProvider
from agents import HouseholdAgent
from run_household_llm_tester import (
    SYSTEM_PROMPT,
    BETA_TESTER_PROMPT,
    build_identity_block,
    build_tick_prompt,
    snapshot_household,
    select_household,
)

RUNS = [
    # (label shown in output, archetype arg, seed)
    ("frugal",      "frugal",      42),
    ("average",     "average",     42),
    ("spendthrift", "spendthrift", 42),
    ("random_a",    "random",      42),
    ("random_b",    "random",      99),
]


async def run_one(
    label: str,
    archetype: str,
    seed: int,
    args,
    provider: LMStudioProvider,
) -> dict:
    """Run a single archetype through the full tick loop. Returns summary dict."""

    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  RUN: {label.upper()}  (archetype={archetype}, seed={seed})")
    print(sep)

    CONFIG.time.warmup_ticks = args.warmup_ticks

    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households, num_firms_per_category=2
    )
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} firms)")

    target_hh: HouseholdAgent = select_household(economy.households, archetype, seed=seed)
    hh_id = target_hh.household_id

    print(f"\nShadowing household #{hh_id} [{label.upper()}]")
    print(f"  Skills: {target_hh.skills_level:.2f} | Saving: {target_hh.saving_tendency:.2f} | "
          f"Spending tend: {target_hh.spending_tendency:.2f} | Frugality: {target_hh.frugality:.2f}")
    print(f"  Drawdown rate: {target_hh.savings_drawdown_rate:.3f}/tick | "
          f"Reservation wage: ${target_hh.reservation_wage:.0f}")
    print(f"  Food pref: {target_hh.food_preference:.2f} | "
          f"Housing pref: {target_hh.housing_preference:.2f} | "
          f"Services pref: {target_hh.services_preference:.2f}")

    identity_block = build_identity_block(target_hh)
    full_system = SYSTEM_PROMPT + "\n\n" + identity_block

    conversation_history = []
    run_log = []
    prev_state = None
    post_warmup_tick = 0

    print("\n" + "â”€" * 70)
    print(f" {'Tick':>4} | {'Cash':>8} | {'Deposit':>8} | {'Employment':>20} | {'Health':>6} | LLM")
    print("â”€" * 70)

    for tick in range(args.ticks):
        economy.step()

        hh = economy.household_lookup[hh_id]
        metrics = economy.get_economic_metrics()
        metrics["private_firms"] = sum(1 for f in economy.firms if not f.is_baseline)

        in_warmup = economy.in_warmup
        emp_str = f"employed @${hh.wage:.0f}" if hh.is_employed else f"unemployed {hh.unemployment_duration}t"
        warmup_tag = " [warmup]" if in_warmup else ""

        print(
            f" {economy.current_tick:>4} | ${hh.cash_balance:>7.0f} | ${hh.bank_deposit:>7.0f} | "
            f"{emp_str:>20} | {hh.health:>6.2f} |{warmup_tag}",
            end=" ", flush=True,
        )

        if in_warmup:
            print("(warmup)")
            prev_state = snapshot_household(hh)
            continue

        post_warmup_tick += 1
        user_msg = build_tick_prompt(hh, metrics, economy.current_tick, prev_state)

        t0 = time.perf_counter()
        try:
            response = await provider.complete(
                system=full_system,
                user=user_msg,
                temperature=0.75,
            )
            elapsed = time.perf_counter() - t0
            print(f"{elapsed:.1f}s")
            print(f"  ðŸ’¬ {response.strip()[:200]}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"FAIL ({elapsed:.1f}s): {e}")
            response = "(LLM call failed)"

        conversation_history = (conversation_history + [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": response},
        ])[-12:]

        run_log.append({
            "tick": economy.current_tick,
            "state": snapshot_household(hh),
            "response": response,
        })

        prev_state = snapshot_household(hh)

        # Beta feedback
        if post_warmup_tick > 0 and post_warmup_tick % args.feedback_every == 0:
            print(f"\n{'â”€' * 70}")
            print(f"  BETA FEEDBACK â€” tick {economy.current_tick} ({post_warmup_tick} post-warmup ticks as {label})")
            print(f"{'â”€' * 70}")

            event_summary = "\n".join(
                f"  tick {e['tick']}: cash=${e['state']['cash']:.0f}, "
                f"{'employed' if e['state']['employed'] else 'unemployed'}, "
                f"health={e['state']['health']:.2f}, happiness={e['state']['happiness']:.2f}"
                for e in run_log[-args.feedback_every:]
                if e.get("state")
            )
            feedback_prompt = (
                BETA_TESTER_PROMPT.format(n_ticks=post_warmup_tick)
                + f"\n\nYour last {args.feedback_every} ticks (ground truth):\n{event_summary}"
            )
            try:
                feedback = await provider.complete(
                    system=full_system,
                    user=feedback_prompt,
                    temperature=0.8,
                )
                print(feedback.strip())
                run_log.append({
                    "tick": economy.current_tick,
                    "type": "beta_feedback",
                    "feedback": feedback,
                })
            except Exception as e:
                print(f"Feedback call failed: {e}")

            print(f"{'â”€' * 70}\n")
            conversation_history = []

    # Final state
    hh = economy.household_lookup[hh_id]
    print(f"\n{'=' * 70}")
    print(f"  FINAL STATE â€” {label.upper()}")
    print(f"{'=' * 70}")
    print(f"  Cash:        ${hh.cash_balance:.0f}")
    print(f"  Savings:     ${hh.bank_deposit:.0f}")
    print(f"  Employment:  {'Yes @ $' + str(round(hh.wage)) + '/tick' if hh.is_employed else 'No'}")
    print(f"  Skills:      {hh.skills_level:.2f}")
    print(f"  Health:      {hh.health:.2f}")
    print(f"  Happiness:   {hh.happiness:.2f}")
    print(f"  Morale:      {hh.morale:.2f}")

    final_snap = snapshot_household(hh)

    # Save log
    log_path = f"household_llm_run_log_{label}.json"
    log_data = {
        "meta": {
            "label": label,
            "archetype": archetype,
            "seed": seed,
            "household_id": hh_id,
            "model": args.model,
            "ticks": args.ticks,
            "economy_households": args.households,
        },
        "trait_card": {
            "skills_level": round(target_hh.skills_level, 3),
            "saving_tendency": round(target_hh.saving_tendency, 3),
            "spending_tendency": round(target_hh.spending_tendency, 3),
            "frugality": round(target_hh.frugality, 3),
            "savings_drawdown_rate": round(target_hh.savings_drawdown_rate, 4),
            "reservation_wage": round(target_hh.reservation_wage, 2),
            "food_preference": round(target_hh.food_preference, 3),
            "housing_preference": round(target_hh.housing_preference, 3),
            "services_preference": round(target_hh.services_preference, 3),
        },
        "final_state": final_snap,
        "tick_log": run_log,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)
    print(f"\n  Log saved: {log_path}")

    return {
        "label": label,
        "archetype": archetype,
        "log_file": log_path,
        "final_state": final_snap,
        "trait_card": log_data["trait_card"],
        "post_warmup_ticks": post_warmup_tick,
    }


async def main():
    parser = argparse.ArgumentParser(description="Run all 5 household archetypes sequentially")
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--ticks", type=int, default=60)
    parser.add_argument("--feedback-every", type=int, default=8)
    parser.add_argument("--model", type=str, default="qwen3.5-4b-claude-4.6-opus-reasoning-distilled")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--warmup-ticks", type=int, default=12)
    parser.add_argument(
        "--skip", nargs="*",
        choices=[r[0] for r in RUNS],
        default=[],
        help="Archetypes to skip (e.g. --skip frugal random_b)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  EcoSim All-Archetype Behaviour Runs")
    print(f"  Runs: {[r[0] for r in RUNS if r[0] not in args.skip]}")
    print(f"  Each: {args.households} households | {args.ticks} ticks | model={args.model}")
    print("=" * 70)

    print(f"\nConnecting to LM Studio ({args.model})...", end=" ", flush=True)
    provider = LMStudioProvider(model=args.model, timeout=args.timeout, max_tokens=1000)
    if not await provider.health_check():
        print("FATAL: LM Studio not reachable on localhost:1234")
        return
    print("connected")

    results = []
    total_start = time.perf_counter()

    for label, archetype, seed in RUNS:
        if label in args.skip:
            print(f"\n  Skipping {label}")
            continue
        result = await run_one(label, archetype, seed, args, provider)
        results.append(result)

    await provider.close()

    # Combined summary
    summary = {
        "meta": {
            "model": args.model,
            "ticks": args.ticks,
            "economy_households": args.households,
            "total_wall_time_s": round(time.perf_counter() - total_start, 1),
        },
        "runs": results,
        "cross_archetype_comparison": {
            r["label"]: {
                **r["trait_card"],
                "final_cash":      round(r["final_state"]["cash"], 2),
                "final_savings":   round(r["final_state"]["deposit"], 2),
                "employed":        r["final_state"]["employed"],
                "final_health":    round(r["final_state"]["health"], 3),
                "final_happiness": round(r["final_state"]["happiness"], 3),
                "final_morale":    round(r["final_state"]["morale"], 3),
            }
            for r in results
        },
    }

    summary_path = "household_llm_all_archetypes_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'=' * 70}")
    print("  ALL RUNS COMPLETE")
    print(f"{'=' * 70}")
    for r in results:
        hh = r["final_state"]
        print(f"  {r['label']:<12}  cash=${hh['cash']:.0f}  "
              f"{'employed' if hh['employed'] else 'unemployed':>12}  "
              f"health={hh['health']:.2f}  happiness={hh['happiness']:.2f}")
    print(f"\n  Summary saved: {summary_path}")
    print(f"  Total time:    {summary['meta']['total_wall_time_s']}s")


if __name__ == "__main__":
    asyncio.run(main())

