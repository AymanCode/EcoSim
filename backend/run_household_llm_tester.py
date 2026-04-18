"""
EcoSim Household LLM Beta Tester
=================================
Runs a real EcoSim economy with N households. One household is shadowed
by an LLM that observes its real state each tick, reflects on the decisions
the simulation made for it, and gives beta tester feedback periodically.

The household participates in the real economy (rule-based decisions still run).
The LLM is a commentator/observer for now — Phase 2 will let it override decisions.

Usage:
    python run_household_llm_tester.py
    python run_household_llm_tester.py --households 200 --ticks 60 --feedback-every 8
    python run_household_llm_tester.py --model nemotron-mini-4b --household-index 5
"""

import argparse
import asyncio
import copy
import json
import random
import sys
import os
import time
import textwrap
from typing import Optional, Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from run_large_simulation import create_large_economy
from llm_provider import LMStudioProvider
from agents import HouseholdAgent


# ──────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    /no_think
    You are a specific household living inside EcoSim — a running agent-based macroeconomic simulation.
    The simulation makes all decisions for you. Your job is to react as the person this household represents.

    RESPONSE RULES — follow exactly:
    - Answer the 4 numbered questions below each tick. One sentence each. No preamble.
    - Stay in character based on your personality traits.
    - Plain prose only. No JSON, no bullet points, no headers.
    - If asked for beta feedback, switch to developer mode and be blunt and specific.
""")


def _format_signed_money(amount: float) -> str:
    sign = "+" if amount >= 0 else "-"
    return f"{sign}${abs(amount):.0f}"


def build_identity_block(hh: HouseholdAgent) -> str:
    """Build a stable identity description from household personality fields."""
    skill_desc = "low-skilled worker" if hh.skills_level < 0.35 else \
                 "average worker" if hh.skills_level < 0.65 else \
                 "highly skilled worker"

    saver_desc = "spends most of what you earn" if hh.saving_tendency < 0.35 else \
                 "balances spending and saving" if hh.saving_tendency < 0.65 else \
                 "strong saver who hoards cash"

    style = getattr(hh, 'purchase_styles', {})
    style_str = ", ".join(f"{k}: {v}" for k, v in style.items()) if style else "value buyer across the board"

    top_pref = max(
        {"food": hh.food_preference, "housing": hh.housing_preference, "services": hh.services_preference}.items(),
        key=lambda x: x[1]
    )[0]

    # Job-switching fields only apply when employed — show labor market reality when unemployed
    if hh.is_employed:
        job_search_line = (
            f"- Won't switch jobs unless offered {hh.job_switch_threshold:.0%} more than current wage\n"
            f"        - Won't accept a job below ${hh.reservation_wage:.0f}/tick"
        )
    else:
        job_search_line = (
            f"- Actively seeking any job above ${hh.reservation_wage:.0f}/tick (no switch threshold applies when unemployed)\n"
            f"        - Searching the labor market every tick — no cooldown when unemployed"
        )

    return textwrap.dedent(f"""\
        YOUR PERSONALITY (fixed — this is who you are):
        - You are a {skill_desc} (skills: {hh.skills_level:.2f}/1.0)
        - You {saver_desc} (saving tendency: {hh.saving_tendency:.2f}/1.0)
        - Price sensitivity: {hh.price_sensitivity:.2f} (higher = more bothered by price changes)
        - Frugality: {hh.frugality:.2f} (higher = spend less overall)
        - Top spending priority: {top_pref} (food: {hh.food_preference:.2f}, housing: {hh.housing_preference:.2f}, services: {hh.services_preference:.2f})
        {job_search_line}
        - Purchase style: {style_str}\
    """)


def build_tick_prompt(
    hh: HouseholdAgent,
    metrics: Dict[str, Any],
    tick: int,
    prev_state: Optional[Dict] = None,
) -> str:
    """Build the per-tick observation prompt from real household + economy state."""

    employed = hh.is_employed
    employer_firm = None

    # Explain simulation context the LLM would otherwise be confused about
    housing_context = (
        "you own your home (no rent)" if hh.owns_housing else
        f"renting from a firm at ${hh.monthly_rent:.0f}/tick" if hh.monthly_rent > 0 else
        "you have a baseline government housing allocation (rent is $0 — this is a simulation mechanic, not free market housing)"
    )

    # What changed since last tick — with reasons where the sim knows them
    events = []
    if prev_state:
        if prev_state["employed"] and not employed:
            events.append("you were laid off this tick (your employer reduced headcount or went bankrupt)")
        elif not prev_state["employed"] and employed:
            events.append(f"you found a new job this tick at ${hh.wage:.0f}/tick")
        if abs(hh.cash_balance - prev_state["cash"]) > 5:
            delta = hh.cash_balance - prev_state["cash"]
            events.append(f"cash {'rose' if delta > 0 else 'fell'} by ${abs(delta):.0f}")
        if hh.health < prev_state["health"] - 0.01:
            # Explain the specific cause of health decline
            food_ok = hh.food_consumed_this_tick >= hh.min_food_per_tick
            if not food_ok:
                events.append(
                    f"health declined to {hh.health:.2f} "
                    f"(insufficient food — consumed {hh.food_consumed_this_tick:.1f} units, need {hh.min_food_per_tick:.1f})"
                )
            else:
                events.append(
                    f"health declined slightly to {hh.health:.2f} "
                    f"(natural decay — food was adequate but health recovers slowly)"
                )
        if hh.happiness < prev_state["happiness"] - 0.05:
            events.append("happiness dropped noticeably (likely from unmet needs or poverty)")

    events_str = " | ".join(events) if events else "no major changes"

    # Market context from real economy metrics
    unemp_pct = metrics.get("unemployment_rate", 0) * 100
    mean_wage = metrics.get("mean_wage", 0)
    unemployment_benefit = metrics.get("unemployment_benefit", 0.0)
    food_price = metrics.get("mean_food_price", metrics.get("price_food", 8.0))
    housing_price = metrics.get("mean_housing_price", metrics.get("price_housing", 14.0))
    services_price = metrics.get("mean_services_price", metrics.get("price_services", 8.0))
    total_firms = metrics.get("total_firms", 0)
    private_firms = metrics.get("private_firms", 0)

    # What the simulation did for this household this tick
    wage_income = hh.last_wage_income
    transfer = hh.last_transfer_income
    spending = hh.last_consumption_spending
    dividend = hh.last_dividend_income
    taxes = abs(hh.last_other_income)
    ledger = getattr(hh, "last_tick_ledger", {}) or {}
    owned_firm_ids = list(getattr(hh, "owned_firm_ids", []) or [])
    dividend_firm_ids = list(getattr(hh, "last_dividend_firm_ids", []) or [])
    misc_beneficiary = bool(getattr(hh, "is_misc_beneficiary", False))
    education_active = bool(getattr(hh, "education_active_this_tick", False))

    # Build structured purchase receipt from per-category fields (set by economy after market clearing)
    food_bought = hh.last_food_units
    food_needed = hh.min_food_per_tick
    food_status = (
        f"bought {food_bought:.1f} units (${hh.last_food_spend:.0f}) — adequate (need {food_needed:.1f})"
        if food_bought >= food_needed
        else f"bought {food_bought:.1f} units (${hh.last_food_spend:.0f}) — SHORTAGE (need {food_needed:.1f}, health at risk)"
        if food_bought > 0
        else f"bought nothing (SHORTAGE — need {food_needed:.1f} units, health at risk)"
    )
    housing_status = (
        f"bought {hh.last_housing_units:.1f} units (${hh.last_housing_spend:.0f})"
        if hh.last_housing_units > 0
        else "not purchased this tick"
    ) + (" — need met" if hh.met_housing_need else " — need NOT met")
    services_status = (
        f"bought {hh.last_services_units:.1f} units (${hh.last_services_spend:.0f})"
        if hh.last_services_units > 0
        else "none purchased this tick"
    )
    healthcare_status = (
        f"completed {hh.last_healthcare_units:.1f} visits (${hh.last_healthcare_spend:.0f} out of pocket)"
        if hh.last_healthcare_units > 0
        else f"queued for care at firm #{hh.queued_healthcare_firm_id}"
        if hh.queued_healthcare_firm_id is not None
        else "no healthcare visit completed this tick"
    )
    purchase_breakdown = getattr(hh, "last_purchase_breakdown", {}) or {}
    purchase_detail = (
        "; ".join(
            f"{good}: {details.get('units', 0):.1f}u/${details.get('spend', 0):.0f}"
            for good, details in sorted(purchase_breakdown.items())
        )
        if purchase_breakdown
        else "no recorded purchases"
    )
    # Consumed this tick (from pantry, may differ from purchased if buying from last tick's stock)
    food_consumed = hh.food_consumed_this_tick

    medical_debt = hh.medical_loan_remaining + hh.medical_school_debt_remaining
    employer_info = (
        f"Employed (firm #{hh.employer_id}, {getattr(hh, 'employer_category', 'unknown')} sector), earning ${hh.wage:.0f}/tick"
        if employed else
        f"UNEMPLOYED for {hh.unemployment_duration} ticks (searching for work above ${hh.reservation_wage:.0f}/tick)"
    )
    ownership_status = (
        "yes — owner of firms " + ", ".join(f"#{firm_id}" for firm_id in owned_firm_ids)
        if owned_firm_ids
        else "no"
    )
    dividend_status = (
        f"yes — {_format_signed_money(dividend)} from firms "
        + ", ".join(f"#{firm_id}" for firm_id in dividend_firm_ids)
        if dividend_firm_ids
        else "no"
    )
    education_status = (
        f"yes — spent ${abs(ledger.get('education', 0.0)):.0f} on skill building this tick"
        if education_active
        else "no"
    )
    ledger_rows = [
        ("wage", ledger.get("wage", 0.0)),
        ("transfers", ledger.get("transfers", 0.0)),
        ("stimulus", ledger.get("stimulus", 0.0)),
        ("redistribution", ledger.get("redistribution", 0.0)),
        ("dividends", ledger.get("dividends", 0.0)),
        ("goods", ledger.get("goods", 0.0)),
        ("rent", ledger.get("rent", 0.0)),
        ("healthcare", ledger.get("healthcare", 0.0)),
        ("education", ledger.get("education", 0.0)),
        ("taxes", ledger.get("taxes", 0.0)),
        ("bank", ledger.get("bank", 0.0)),
        ("other", ledger.get("other", 0.0)),
        ("net", ledger.get("net", 0.0)),
    ]
    ledger_block = "\n".join(
        f"            {label:<14} {_format_signed_money(amount)}"
        for label, amount in ledger_rows
    )

    return textwrap.dedent(f"""\
        === TICK {tick} ===

        WHAT HAPPENED THIS TICK: {events_str}

        YOUR CURRENT SITUATION:
        - Cash on hand: ${hh.cash_balance:.0f}
        - Bank savings: ${hh.bank_deposit:.0f}
        - Employment: {employer_info}
        - Health: {hh.health:.2f}/1.0  |  Happiness: {hh.happiness:.2f}/1.0  |  Morale: {hh.morale:.2f}/1.0
        - Housing: {housing_context}
        - Medical training: {hh.medical_training_status}
        - Debt: ${medical_debt:.0f} remaining
        - Skills: {hh.skills_level:.2f}/1.0 (grows slowly while employed)
        - Job search: {"on cooldown for " + str(hh.job_search_cooldown) + " more ticks (employed — periodic market check)" if hh.is_employed and hh.job_search_cooldown > 0 else "searching every tick (unemployed — no cooldown)" if not hh.is_employed else "ready to check market this tick"}
        - Firm ownership: {ownership_status}
        - Misc redistribution pool beneficiary: {"yes" if misc_beneficiary else "no"}
        - Education this tick: {education_status}

        WHAT HAPPENED TO YOU THIS TICK:
        - Wage income received: ${wage_income:.0f}
        - Government transfer: ${transfer:.0f}
        - Taxes withheld: ${taxes:.0f}
        - Dividend income: ${dividend:.0f} ({dividend_status})
        - Total spent on goods/services: ${spending:.0f}
        - Purchase receipt (bought this tick from market):
            Food:       {food_status}
            Housing:    {housing_status}
            Services:   {services_status}
            Healthcare: {healthcare_status}
        - Purchase detail: {purchase_detail}
        - Cash ledger:
{ledger_block}
        - Consumed this tick (from pantry): food {food_consumed:.1f} units{"  ← adequate" if food_consumed >= hh.min_food_per_tick else "  ← BELOW MINIMUM, health declining"}
        - Reservation wage this tick: ${hh.reservation_wage:.0f} (minimum you'd accept)
        - Health note: health decays ~0.5%/tick naturally; food and healthcare visits restore it

        THE ECONOMY AROUND YOU:
        - Unemployment: {unemp_pct:.1f}%  |  Mean wage: ${mean_wage:.0f}/tick
        - Total firms: {total_firms} ({private_firms} private, rest government-baseline)
        - Food price: ${food_price:.1f}/unit  |  Housing: ${housing_price:.1f}/unit  |  Services: ${services_price:.1f}/unit
        - Unemployment benefit: ${unemployment_benefit:.0f}/tick (what you'd receive if you lost your job)
        - GDP this tick: ${metrics.get("gdp_this_tick", 0):.0f}
        - Mean household cash: ${metrics.get("mean_household_cash", 0):.0f}
        - Gini coefficient: {metrics.get("gini_coefficient", 0):.3f} (0=perfect equality, 1=total inequality)
        - Mean happiness: {metrics.get("mean_happiness", 0):.3f}  |  Mean health: {metrics.get("mean_health", 0):.3f}

        GOVERNMENT POLICY (affects you directly):
        - Wage tax rate: {metrics.get("wage_tax_rate", metrics.get("gov_wage_tax_rate", 0.15)):.0%}
        - Profit tax rate: {metrics.get("profit_tax_rate", metrics.get("gov_profit_tax_rate", 0.20)):.0%}
        - Benefit level: {metrics.get("gov_benefit_level", "neutral")}
        - Minimum wage floor: ${metrics.get("minimum_wage_floor", 36):.0f}/tick
        - Infrastructure investment: {metrics.get("gov_infrastructure_spending", "none")}
        - Government cash: ${metrics.get("government_cash", 0):.0f} (fiscal health indicator)

        YOUR SAVINGS MECHANICS:
        - Bank deposit: ${hh.bank_deposit:.0f} (earning {getattr(hh, '_last_deposit_rate', 0.01):.2%} annual interest)
        - Deposit buffer: you keep {hh.deposit_buffer_weeks:.0f} weeks of spending liquid before depositing excess
        - Deposit fraction: when you have excess cash, you deposit {hh.deposit_fraction:.0%} of it per tick
        - Savings drawdown: you draw {hh.savings_drawdown_rate:.1%}/tick from cash savings to supplement spending
        - Consumption loan debt: ${hh.consumption_loan_remaining:.0f} (repaying ${hh.consumption_loan_payment_per_tick:.0f}/tick)

        BANK HEALTH (affects your deposits and loan access):
        - Bank can lend: {metrics.get("bank_can_lend", "unknown")}
        - Bank deposit rate: {metrics.get("bank_deposit_rate", 0.01):.2%}/year
        - Bank reserve ratio: {metrics.get("bank_reserve_ratio_actual", "unknown")}
        - Total capital stock in economy: {metrics.get("total_capital_stock", 0):.0f}

        Answer these 4 questions in character. One sentence each. No preamble.
        1. How do you feel about your cash and income this week?
        2. Was food, housing, and services adequate — or did something fall short?
        3. What is your biggest concern right now (job, health, debt, prices)?
        4. Does anything about how the simulation handled you feel wrong or unfair?\
    """)


BETA_TESTER_PROMPT = textwrap.dedent("""\
    Step out of character. You are now a beta tester giving feedback to the EcoSim developers.
    You just lived {n_ticks} ticks as a real household inside this simulation.

    Give honest, specific feedback on the HOUSEHOLD MECHANICS:
    - What felt unrealistic or broken about how the simulation managed your decisions?
    - Were there situations where the automatic decision felt absurd for a real person?
    - What information did you need that wasn't available to you?
    - What mechanics felt missing entirely (things a real person would do but couldn't)?
    - Were there any trap states — situations with no good exit?
    - What would make this feel more like a real person's economic life?
    - Rate your experience 1-10 (1=toy simulation, 10=felt real).

    Be specific. Reference actual ticks and situations you experienced.
    Plain prose, no JSON. Be blunt — this is developer feedback.
""")


# ──────────────────────────────────────────────
# Snapshot helper
# ──────────────────────────────────────────────

def snapshot_household(hh: HouseholdAgent) -> Dict:
    return {
        "cash": hh.cash_balance,
        "deposit": hh.bank_deposit,
        "employed": hh.is_employed,
        "wage": hh.wage,
        "health": hh.health,
        "happiness": hh.happiness,
        "morale": hh.morale,
        "last_wage_income": hh.last_wage_income,
        "last_transfer_income": hh.last_transfer_income,
        "last_dividend_income": hh.last_dividend_income,
        "last_other_income": hh.last_other_income,
        "ledger_cash_start": hh.ledger_cash_start,
        "last_tick_ledger": copy.deepcopy(hh.last_tick_ledger),
        "last_dividend_firm_ids": list(hh.last_dividend_firm_ids),
        "owned_firm_ids": list(hh.owned_firm_ids),
        "is_misc_beneficiary": hh.is_misc_beneficiary,
        "education_active_this_tick": hh.education_active_this_tick,
        # Consumption receipt
        "last_food_units": hh.last_food_units,
        "last_food_spend": hh.last_food_spend,
        "last_services_units": hh.last_services_units,
        "last_services_spend": hh.last_services_spend,
        "last_healthcare_units": hh.last_healthcare_units,
        "last_healthcare_spend": hh.last_healthcare_spend,
        "last_healthcare_provider_id": hh.last_healthcare_provider_id,
        "last_purchase_breakdown": copy.deepcopy(hh.last_purchase_breakdown),
        "last_consumption_spending": hh.last_consumption_spending,
        "food_consumed_this_tick": hh.food_consumed_this_tick,
        "services_consumed_this_tick": hh.services_consumed_this_tick,
        "healthcare_consumed_this_tick": hh.healthcare_consumed_this_tick,
        # Housing
        "housing_satisfied": hh.met_housing_need,
        "last_housing_units": hh.last_housing_units,
        "last_housing_spend": hh.last_housing_spend,
        "owns_housing": hh.owns_housing,
        "monthly_rent": hh.monthly_rent,
        "renting_from_firm_id": hh.renting_from_firm_id,
        # Healthcare / queue context
        "pending_healthcare_visits": hh.pending_healthcare_visits,
        "queued_healthcare_firm_id": hh.queued_healthcare_firm_id,
        "healthcare_queue_enter_tick": hh.healthcare_queue_enter_tick,
        "medical_training_status": hh.medical_training_status,
    }


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def _compute_medians(households: List[HouseholdAgent]) -> Dict[str, float]:
    def med(vals: list) -> float:
        s = sorted(vals)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {
        "saving_tendency":   med([h.saving_tendency for h in households]),
        "frugality":         med([h.frugality for h in households]),
        "spending_tendency": med([h.spending_tendency for h in households]),
        "skills_level":      med([h.skills_level for h in households]),
    }


def select_household(
    households: List[HouseholdAgent],
    archetype: str,
    seed: int = 42,
) -> HouseholdAgent:
    """
    Return the best household for the requested archetype.

    Archetypes:
      frugal      — highest saving_tendency + frugality − spending_tendency
      spendthrift — lowest saving_tendency + frugality, highest spending_tendency
      average     — traits closest to population medians, employed, no debt
      random      — randomly chosen from the full pool
    """
    rng = random.Random(seed)

    if archetype == "random":
        return rng.choice(households)

    if archetype == "frugal":
        return max(households, key=lambda h: h.saving_tendency + h.frugality - h.spending_tendency * 0.5)

    if archetype == "spendthrift":
        return max(households, key=lambda h: (1.0 - h.saving_tendency) + (1.0 - h.frugality) + h.spending_tendency * 0.5)

    if archetype == "average":
        medians = _compute_medians(households)
        def avg_score(h: HouseholdAgent) -> float:
            trait_diff = (
                abs(h.saving_tendency   - medians["saving_tendency"])
                + abs(h.frugality       - medians["frugality"])
                + abs(h.spending_tendency - medians["spending_tendency"])
                + abs(h.skills_level    - medians["skills_level"])
            )
            # Prefer employed, no debt, no medical training — richest starting experience
            bonus = 0.0
            if h.is_employed: bonus += 0.5
            if h.medical_loan_remaining == 0 and h.medical_school_debt_remaining == 0: bonus += 0.3
            if h.medical_training_status == "none": bonus += 0.2
            return bonus - trait_diff
        return max(households, key=avg_score)

    # Fallback — same as original "normal" heuristic
    def normality_score(h: HouseholdAgent) -> float:
        score = 0.0
        if h.is_employed: score += 3.0
        if 0.35 <= h.skills_level <= 0.65: score += 2.0
        if not h.owns_housing and h.monthly_rent > 0: score += 1.0
        if h.medical_loan_remaining == 0 and h.medical_school_debt_remaining == 0: score += 1.0
        if h.medical_training_status == "none": score += 1.0
        return score
    return max(households, key=normality_score)


async def main():
    parser = argparse.ArgumentParser(description="EcoSim Household LLM Beta Tester")
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--ticks", type=int, default=60)
    parser.add_argument("--feedback-every", type=int, default=8)
    parser.add_argument("--model", type=str, default="microsoft/phi-4-mini-reasoning")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:1234")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--warmup-ticks", type=int, default=12)
    parser.add_argument(
        "--archetype",
        type=str,
        default="average",
        choices=["frugal", "average", "spendthrift", "random"],
        help="Which type of household to shadow (default: average)",
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for 'random' archetype selection")
    args = parser.parse_args()

    CONFIG.time.warmup_ticks = args.warmup_ticks

    print("=" * 70)
    print("  EcoSim Household LLM Beta Tester")
    print(f"  Economy: {args.households} households | {args.ticks} ticks")
    print(f"  Archetype: {args.archetype} | Model: {args.model}")
    print(f"  Feedback every {args.feedback_every} ticks")
    print("=" * 70)

    # Build economy
    print("\nCreating economy...", end=" ", flush=True)
    economy = create_large_economy(num_households=args.households, num_firms_per_category=2)
    print(f"done ({len(economy.households)} HH, {len(economy.firms)} firms)")

    target_hh = select_household(economy.households, args.archetype, seed=args.seed)
    hh_id = target_hh.household_id
    print(f"\nShadowing household #{hh_id} [{args.archetype.upper()}]")
    print(f"  Skills: {target_hh.skills_level:.2f} | Saving: {target_hh.saving_tendency:.2f} | "
          f"Spending tend: {target_hh.spending_tendency:.2f} | Frugality: {target_hh.frugality:.2f}")
    print(f"  Drawdown rate: {target_hh.savings_drawdown_rate:.3f}/tick | "
          f"Reservation wage: ${target_hh.reservation_wage:.0f}")
    print(f"  Food pref: {target_hh.food_preference:.2f} | "
          f"Housing pref: {target_hh.housing_preference:.2f} | "
          f"Services pref: {target_hh.services_preference:.2f}")

    # Connect to LM Studio
    print(f"\nConnecting to LM Studio ({args.model})...", end=" ", flush=True)
    provider = LMStudioProvider(base_url=args.base_url, model=args.model, timeout=args.timeout, max_tokens=40000)
    if not await provider.health_check():
        print(f"FATAL: LM Studio not reachable on {args.base_url}")
        print("Make sure LM Studio is running with the local server enabled.")
        return
    print("connected")

    identity_block = build_identity_block(target_hh)
    full_system = SYSTEM_PROMPT + "\n\n" + identity_block

    conversation_history = []
    run_log = []
    prev_state = None

    print("\n" + "─" * 70)
    print(f" {'Tick':>4} | {'Cash':>8} | {'Deposit':>8} | {'Employment':>20} | {'Health':>6} | LLM")
    print("─" * 70)

    warmup_ticks = CONFIG.time.warmup_ticks
    post_warmup_tick = 0  # counts ticks after warmup ends

    for tick in range(args.ticks):
        # Run real economy tick
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
            end=" ", flush=True
        )

        # Skip LLM narration during warmup — state isn't meaningful yet
        if in_warmup:
            print("(warmup)")
            prev_state = snapshot_household(hh)
            continue

        post_warmup_tick += 1

        # Build prompt from real state
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
            print(f"  💬 {response.strip()[:200]}")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"FAIL ({elapsed:.1f}s): {e}")
            response = "(LLM call failed)"

        # Rolling 6-turn history
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

        # Beta tester feedback — only after warmup, using real event log
        if post_warmup_tick > 0 and post_warmup_tick % args.feedback_every == 0:
            print(f"\n{'─' * 70}")
            print(f"  BETA TESTER FEEDBACK — after tick {economy.current_tick} ({post_warmup_tick} post-warmup)")
            print(f"{'─' * 70}")

            # Build a grounded event summary from the real run log
            real_events = [
                f"tick {e['tick']}: {e['state']}"
                for e in run_log[-args.feedback_every:]
                if e.get("state")
            ]
            event_summary = "\n".join(
                f"  tick {e['tick']}: cash=${e['state']['cash']:.0f}, "
                f"{'employed' if e['state']['employed'] else 'unemployed'}, "
                f"health={e['state']['health']:.2f}, happiness={e['state']['happiness']:.2f}"
                for e in run_log[-args.feedback_every:]
                if e.get("state")
            )
            feedback_prompt = (
                BETA_TESTER_PROMPT.format(n_ticks=post_warmup_tick)
                + f"\n\nYour last {args.feedback_every} ticks (ground truth from simulation):\n{event_summary}"
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

            print(f"{'─' * 70}\n")

            # Reset conversation so model doesn't OOM on long runs
            conversation_history = []

    # Final summary
    hh = economy.household_lookup[hh_id]
    print(f"\n{'=' * 70}")
    print("  FINAL STATE OF SHADOWED HOUSEHOLD")
    print(f"{'=' * 70}")
    print(f"  Cash:        ${hh.cash_balance:.0f}")
    print(f"  Savings:     ${hh.bank_deposit:.0f}")
    print(f"  Employment:  {'Yes @ $' + str(round(hh.wage)) + '/tick' if hh.is_employed else 'No'}")
    print(f"  Skills:      {hh.skills_level:.2f}")
    print(f"  Health:      {hh.health:.2f}")
    print(f"  Happiness:   {hh.happiness:.2f}")
    print(f"  Owns home:   {hh.owns_housing}")
    print(f"  Med status:  {hh.medical_training_status}")
    print(f"  Debt:        ${hh.medical_loan_remaining + hh.medical_school_debt_remaining:.0f}")

    # Save log
    log_path = f"household_llm_run_log_{args.archetype}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2)
    print(f"\n  Full log saved to: {log_path}")
    print(f"{'=' * 70}\n")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
