"""
EcoSim Household LLM Behaviour Tests
======================================
Runs 5 households simultaneously in one shared economy, each representing a
different economic archetype:

  1. frugal     — high saving_tendency, high frugality, low spending_tendency
  2. average    — traits closest to the population median
  3. spendthrift— low saving_tendency, low frugality, high spending_tendency
  4. random_a   — randomly selected
  5. random_b   — a second random, different from random_a

All 5 live in the same economy (same firms, same wages, same shocks).
Every tick: economy steps once, then each household gets one LLM narration.
Beta feedback fires every N ticks for all households.

Output:
  behaviour_log_<archetype>.json  — per-archetype detailed run log
  behaviour_summary.json          — combined overview with trait cards,
                                    per-tick state, and cross-archetype comparison

Usage:
    python run_household_behavior_tests.py
    python run_household_behavior_tests.py --households 300 --ticks 60 --feedback-every 10
    python run_household_behavior_tests.py --model qwen3:8b --timeout 90
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
import textwrap
from typing import Any, Dict, List, Optional, Tuple

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
)


# ──────────────────────────────────────────────
# Archetype definitions and selection
# ──────────────────────────────────────────────

ARCHETYPES = ["frugal", "average", "spendthrift", "random_a", "random_b"]

ARCHETYPE_DESCRIPTIONS = {
    "frugal":      "High saving tendency, high frugality — builds cash, spends only on essentials",
    "average":     "Traits closest to population median — the representative household",
    "spendthrift": "Low saving tendency, low frugality — spends freely, keeps little in reserve",
    "random_a":    "Randomly selected — unfiltered perspective",
    "random_b":    "A second random household — different from random_a",
}


def _trait_score_frugal(hh: HouseholdAgent) -> float:
    """Score how frugal a household is. Higher = more frugal."""
    return hh.saving_tendency + hh.frugality - hh.spending_tendency * 0.5


def _trait_score_spendthrift(hh: HouseholdAgent) -> float:
    """Score how spendthrift a household is. Higher = more spendy."""
    return (1.0 - hh.saving_tendency) + (1.0 - hh.frugality) + hh.spending_tendency * 0.5


def _trait_score_average(hh: HouseholdAgent, medians: Dict[str, float]) -> float:
    """Score closeness to population medians. Higher = closer to average."""
    diff = (
        abs(hh.saving_tendency - medians["saving_tendency"])
        + abs(hh.frugality - medians["frugality"])
        + abs(hh.spending_tendency - medians["spending_tendency"])
        + abs(hh.skills_level - medians["skills_level"])
    )
    return -diff  # negate: least deviation = highest score


def _compute_medians(households: List[HouseholdAgent]) -> Dict[str, float]:
    def med(vals):
        s = sorted(vals)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

    return {
        "saving_tendency":  med([h.saving_tendency for h in households]),
        "frugality":        med([h.frugality for h in households]),
        "spending_tendency": med([h.spending_tendency for h in households]),
        "skills_level":     med([h.skills_level for h in households]),
    }


def select_archetypes(
    households: List[HouseholdAgent],
    rng: random.Random,
) -> Dict[str, HouseholdAgent]:
    """Pick one household per archetype. Each household is used at most once."""
    medians = _compute_medians(households)
    pool = list(households)
    selected: Dict[str, HouseholdAgent] = {}

    def pick_best(score_fn) -> HouseholdAgent:
        remaining = [h for h in pool if h not in selected.values()]
        return max(remaining, key=score_fn)

    selected["frugal"]      = pick_best(_trait_score_frugal)
    selected["spendthrift"] = pick_best(_trait_score_spendthrift)
    selected["average"]     = pick_best(lambda h: _trait_score_average(h, medians))

    remaining = [h for h in pool if h not in selected.values()]
    r_a = rng.choice(remaining)
    selected["random_a"] = r_a

    remaining = [h for h in pool if h not in selected.values()]
    selected["random_b"] = rng.choice(remaining)

    return selected


def trait_card(hh: HouseholdAgent, archetype: str) -> Dict[str, Any]:
    """Compact trait summary for the summary JSON."""
    return {
        "archetype": archetype,
        "household_id": hh.household_id,
        "description": ARCHETYPE_DESCRIPTIONS[archetype],
        "skills_level": round(hh.skills_level, 3),
        "saving_tendency": round(hh.saving_tendency, 3),
        "spending_tendency": round(hh.spending_tendency, 3),
        "frugality": round(hh.frugality, 3),
        "savings_drawdown_rate": round(hh.savings_drawdown_rate, 4),
        "reservation_wage": round(hh.reservation_wage, 2),
        "food_preference": round(hh.food_preference, 3),
        "housing_preference": round(hh.housing_preference, 3),
        "services_preference": round(hh.services_preference, 3),
        "initial_employment": hh.is_employed,
        "owns_housing": hh.owns_housing,
    }


# ──────────────────────────────────────────────
# Per-archetype run state
# ──────────────────────────────────────────────

class ArchetypeRunner:
    """Tracks conversation history, log, and previous state for one archetype."""

    def __init__(self, archetype: str, hh: HouseholdAgent):
        self.archetype = archetype
        self.hh_id = hh.household_id
        self.identity_block = build_identity_block(hh)
        self.full_system = SYSTEM_PROMPT + "\n\n" + self.identity_block
        self.conversation_history: List[Dict] = []
        self.run_log: List[Dict] = []
        self.prev_state: Optional[Dict] = None
        self.post_warmup_ticks = 0


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="EcoSim Household Behaviour Tests")
    parser.add_argument("--households", type=int, default=300)
    parser.add_argument("--ticks", type=int, default=60)
    parser.add_argument("--feedback-every", type=int, default=10)
    parser.add_argument("--model", type=str, default="qwen3.5-4b-claude-4.6-opus-reasoning-distilled")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--warmup-ticks", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    CONFIG.time.warmup_ticks = args.warmup_ticks
    rng = random.Random(args.seed)

    print("=" * 70)
    print("  EcoSim Household Behaviour Tests")
    print(f"  Economy: {args.households} households | {args.ticks} ticks")
    print(f"  Archetypes: {', '.join(ARCHETYPES)}")
    print(f"  Model: {args.model} | Feedback every {args.feedback_every} ticks")
    print("=" * 70)

    # Build economy
    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(
        num_households=args.households, num_firms_per_category=2
    )
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} firms)")

    # Select archetypes
    selected = select_archetypes(economy.households, rng)
    runners: Dict[str, ArchetypeRunner] = {
        name: ArchetypeRunner(name, hh) for name, hh in selected.items()
    }

    print("\nSelected households:")
    for name, hh in selected.items():
        print(
            f"  {name:<12} HH#{hh.household_id:>4}  "
            f"skills={hh.skills_level:.2f}  "
            f"saving={hh.saving_tendency:.2f}  "
            f"frugality={hh.frugality:.2f}  "
            f"spending_tend={hh.spending_tendency:.2f}  "
            f"drawdown={hh.savings_drawdown_rate:.3f}"
        )

    # Connect to LM Studio
    print(f"\nConnecting to LM Studio ({args.model})...", end=" ", flush=True)
    provider = LMStudioProvider(model=args.model, timeout=args.timeout)
    if not await provider.health_check():
        print("FATAL: LM Studio not reachable on localhost:1234")
        return
    print("connected")

    # Column header
    col_w = 14
    header = f" {'Tick':>4} | {'Warmup':>6}"
    for name in ARCHETYPES:
        header += f" | {name:>{col_w}}"
    print("\n" + "─" * len(header))
    print(header)
    print("─" * len(header))

    # Main tick loop
    for tick in range(args.ticks):
        economy.step()
        metrics = economy.get_economic_metrics()
        metrics["private_firms"] = sum(1 for f in economy.firms if not f.is_baseline)

        in_warmup = economy.in_warmup
        warmup_tag = "warmup" if in_warmup else "      "
        row_prefix = f" {economy.current_tick:>4} | {warmup_tag}"
        row_suffix = ""

        for name in ARCHETYPES:
            runner = runners[name]
            hh = economy.household_lookup[runner.hh_id]

            if in_warmup:
                runner.prev_state = snapshot_household(hh)
                row_suffix += f" | {'(warmup)':>{col_w}}"
                continue

            runner.post_warmup_ticks += 1
            user_msg = build_tick_prompt(hh, metrics, economy.current_tick, runner.prev_state)

            t0 = time.perf_counter()
            try:
                response = await provider.complete(
                    system=runner.full_system,
                    user=user_msg,
                    temperature=0.75,
                )
                elapsed = time.perf_counter() - t0
                short = response.strip().replace("\n", " ")[:col_w]
                row_suffix += f" | {short:>{col_w}}"
            except Exception as e:
                elapsed = time.perf_counter() - t0
                response = f"(LLM failed: {e})"
                row_suffix += f" | {'ERROR':>{col_w}}"

            # Rolling 6-turn history per archetype
            runner.conversation_history = (runner.conversation_history + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": response},
            ])[-12:]

            runner.run_log.append({
                "tick": economy.current_tick,
                "archetype": name,
                "state": snapshot_household(hh),
                "response": response,
                "elapsed_s": round(elapsed, 2),
            })

            runner.prev_state = snapshot_household(hh)

        print(row_prefix + row_suffix)

        # Beta tester feedback — all archetypes, every N post-warmup ticks
        if not in_warmup:
            # Use the first runner's counter (all increment together)
            first_runner = runners[ARCHETYPES[0]]
            if first_runner.post_warmup_ticks > 0 and first_runner.post_warmup_ticks % args.feedback_every == 0:
                print(f"\n{'─' * 70}")
                print(f"  BETA FEEDBACK — tick {economy.current_tick} ({first_runner.post_warmup_ticks} post-warmup)")
                print(f"{'─' * 70}")

                for name in ARCHETYPES:
                    runner = runners[name]
                    hh = economy.household_lookup[runner.hh_id]
                    event_summary = "\n".join(
                        f"  tick {e['tick']}: cash=${e['state']['cash']:.0f}, "
                        f"{'employed' if e['state']['employed'] else 'unemployed'}, "
                        f"health={e['state']['health']:.2f}, happiness={e['state']['happiness']:.2f}"
                        for e in runner.run_log[-args.feedback_every:]
                        if e.get("state")
                    )
                    feedback_prompt = (
                        BETA_TESTER_PROMPT.format(n_ticks=runner.post_warmup_ticks)
                        + f"\n\nYour last {args.feedback_every} ticks (ground truth):\n{event_summary}"
                    )
                    try:
                        feedback = await provider.complete(
                            system=runner.full_system,
                            user=feedback_prompt,
                            temperature=0.8,
                        )
                        print(f"\n  [{name.upper()}]")
                        print(textwrap.indent(feedback.strip(), "    "))
                        runner.run_log.append({
                            "tick": economy.current_tick,
                            "archetype": name,
                            "type": "beta_feedback",
                            "feedback": feedback,
                        })
                    except Exception as e:
                        print(f"  [{name.upper()}] feedback failed: {e}")

                    runner.conversation_history = []

                print(f"{'─' * 70}\n")

    # ── Save per-archetype logs ──────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  FINAL STATES")
    print(f"{'=' * 70}")

    per_archetype_files = {}
    for name in ARCHETYPES:
        runner = runners[name]
        hh = economy.household_lookup[runner.hh_id]

        final_snap = snapshot_household(hh)
        print(f"\n  [{name.upper()}] HH#{hh.household_id}")
        print(f"    Cash: ${hh.cash_balance:.0f}  |  Savings: ${hh.bank_deposit:.0f}")
        print(f"    Employment: {'Yes @ $' + str(round(hh.wage)) + '/tick' if hh.is_employed else 'No'}")
        print(f"    Health: {hh.health:.2f}  |  Happiness: {hh.happiness:.2f}  |  Morale: {hh.morale:.2f}")
        print(f"    Skills: {hh.skills_level:.2f}  |  Debt: ${hh.medical_loan_remaining + hh.medical_school_debt_remaining:.0f}")

        archetype_log = {
            "meta": {
                "archetype": name,
                "description": ARCHETYPE_DESCRIPTIONS[name],
                "household_id": hh.household_id,
                "model": args.model,
                "ticks": args.ticks,
                "economy_households": args.households,
            },
            "trait_card": trait_card(hh, name),
            "final_state": final_snap,
            "tick_log": runner.run_log,
        }

        log_path = f"behaviour_log_{name}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(archetype_log, f, indent=2)
        per_archetype_files[name] = log_path
        print(f"    Log: {log_path}")

    # ── Save combined summary ────────────────────────────────────────────────
    summary = {
        "meta": {
            "run_type": "household_behaviour_tests",
            "model": args.model,
            "ticks": args.ticks,
            "economy_households": args.households,
            "feedback_every": args.feedback_every,
            "archetypes_tested": ARCHETYPES,
            "per_archetype_log_files": per_archetype_files,
        },
        "trait_cards": {
            name: trait_card(economy.household_lookup[runners[name].hh_id], name)
            for name in ARCHETYPES
        },
        "final_states": {
            name: snapshot_household(economy.household_lookup[runners[name].hh_id])
            for name in ARCHETYPES
        },
        "cross_archetype_comparison": _build_comparison(economy, runners),
        "per_tick_overview": _build_per_tick_overview(runners),
        "beta_feedback_summary": _collect_feedback(runners),
    }

    summary_path = "behaviour_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Combined summary: {summary_path}")
    print(f"{'=' * 70}\n")

    await provider.close()


# ──────────────────────────────────────────────
# Summary helpers
# ──────────────────────────────────────────────

def _build_comparison(economy, runners: Dict[str, "ArchetypeRunner"]) -> Dict[str, Any]:
    """Side-by-side final metric comparison across all archetypes."""
    comparison = {}
    for name, runner in runners.items():
        hh = economy.household_lookup[runner.hh_id]
        comparison[name] = {
            "final_cash": round(hh.cash_balance, 2),
            "final_savings": round(hh.bank_deposit, 2),
            "final_health": round(hh.health, 3),
            "final_happiness": round(hh.happiness, 3),
            "final_morale": round(hh.morale, 3),
            "final_skills": round(hh.skills_level, 3),
            "employed": hh.is_employed,
            "final_wage": round(hh.wage, 2),
            "debt_remaining": round(
                hh.medical_loan_remaining + hh.medical_school_debt_remaining, 2
            ),
            "unemployment_duration": hh.unemployment_duration,
            "post_warmup_ticks_narrated": runner.post_warmup_ticks,
            "llm_responses_recorded": sum(
                1 for e in runner.run_log if e.get("response") and e.get("type") != "beta_feedback"
            ),
        }
    return comparison


def _build_per_tick_overview(runners: Dict[str, "ArchetypeRunner"]) -> List[Dict]:
    """
    One entry per tick, showing all archetypes' state side by side.
    Useful for spotting when archetypes diverged.
    """
    # Collect all ticks from any runner's log
    tick_set = sorted({
        e["tick"] for runner in runners.values()
        for e in runner.run_log
        if e.get("state") and e.get("type") != "beta_feedback"
    })

    # Build lookup: archetype -> tick -> state
    lookup: Dict[str, Dict[int, Dict]] = {name: {} for name in runners}
    for name, runner in runners.items():
        for e in runner.run_log:
            if e.get("state") and e.get("type") != "beta_feedback":
                lookup[name][e["tick"]] = e["state"]

    overview = []
    for tick in tick_set:
        entry: Dict[str, Any] = {"tick": tick}
        for name in runners:
            state = lookup[name].get(tick)
            if state:
                entry[name] = {
                    "cash": round(state["cash"], 0),
                    "employed": state["employed"],
                    "health": round(state["health"], 3),
                    "happiness": round(state["happiness"], 3),
                    "morale": round(state["morale"], 3),
                }
        overview.append(entry)
    return overview


def _collect_feedback(runners: Dict[str, "ArchetypeRunner"]) -> Dict[str, List[str]]:
    """Extract all beta feedback responses per archetype."""
    feedback: Dict[str, List[str]] = {name: [] for name in runners}
    for name, runner in runners.items():
        for e in runner.run_log:
            if e.get("type") == "beta_feedback" and e.get("feedback"):
                feedback[name].append(e["feedback"])
    return feedback


if __name__ == "__main__":
    asyncio.run(main())
