"""
Small-scale simulation to validate BankAgent integration.

Runs a 200-household economy for 100 ticks with bank enabled, tracking:
- Household metrics: mean/median cash, wage, health, happiness, employment
- Firm metrics: count, mean cash, mean price, total inventory, survival mode count
- Bank metrics: reserves, deposits, loans outstanding, defaults, credit scores
- Government metrics: cash, deficit ratio, spending efficiency

Usage:
    python run_bank_simulation.py [--ticks 100] [--households 200] [--no-bank]
"""

import argparse
import random
import sys
import time
from collections import defaultdict
from typing import Dict, List

import numpy as np

from agents import BankAgent, FirmAgent, GovernmentAgent, HouseholdAgent
from config import CONFIG
from economy import Economy

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def create_economy(num_households: int = 200, enable_bank: bool = True) -> Economy:
    """Create a small economy with optional bank."""
    seed = 42
    random.seed(seed)
    np.random.seed(seed)

    categories = ["Food", "Housing", "Services", "Healthcare"]
    baseline_prices = dict(CONFIG.baseline_prices)

    gov = GovernmentAgent(
        wage_tax_rate=0.15,
        profit_tax_rate=0.20,
        unemployment_benefit_level=30.0,
        transfer_budget=5_000.0,
        cash_balance=num_households * 3000.0,
    )
    # Set active policy levers for small economy
    gov.set_lever("benefit_level", "high")
    gov.set_lever("public_works", "on")

    firms: List[FirmAgent] = []
    queued_firms: List[FirmAgent] = []
    next_firm_id = 1

    # Baseline firms (1 per category)
    for category in categories:
        firm_rng = random.Random(seed + next_firm_id * 10007)
        max_units = 30 if category == "Housing" else 0
        firm = FirmAgent(
            firm_id=next_firm_id,
            good_name=f"Baseline{category}",
            cash_balance=500_000.0,
            inventory_units=0.0 if category in {"Housing", "Healthcare"} else 5_000.0,
            good_category=category,
            quality_level=3.0 + firm_rng.uniform(-0.05, 0.05),
            wage_offer=CONFIG.firms.minimum_wage_floor * 1.5,
            price=baseline_prices.get(category, 8.0),
            expected_sales_units=num_households * 0.1,
            production_capacity_units=20_000.0,
            units_per_worker=80.0,
            productivity_per_worker=12.0 + firm_rng.uniform(-0.2, 0.2),
            personality="conservative",
            is_baseline=True,
            baseline_production_quota=num_households * 3.0,
            max_rental_units=max_units,
        )
        firm.set_personality("conservative")
        if category == "Services":
            firm.happiness_boost_per_unit = 0.005
        elif category == "Healthcare":
            firm.happiness_boost_per_unit = 0.0
        gov.register_baseline_firm(category, firm.firm_id)
        firms.append(firm)
        next_firm_id += 1

    # Private firms (2 per non-healthcare category)
    personalities = ["aggressive", "moderate", "conservative"]
    for idx, category in enumerate(categories):
        if category == "Healthcare":
            continue
        for i in range(2):
            firm_rng = random.Random(seed + next_firm_id * 10007)
            personality = personalities[(i + idx) % 3]
            firm = FirmAgent(
                firm_id=next_firm_id,
                good_name=f"{category}Co{i+1}",
                cash_balance=200_000.0,
                inventory_units=0.0 if category == "Housing" else 300.0,
                good_category=category,
                quality_level=5.0 + firm_rng.uniform(-0.5, 0.5),
                wage_offer=35.0 + i * 5.0 + firm_rng.uniform(-1.0, 1.0),
                price=baseline_prices.get(category, 8.0) * (0.95 + i * 0.1),
                expected_sales_units=num_households * 0.03,
                production_capacity_units=10_000.0,
                units_per_worker=40.0,
                productivity_per_worker=14.0 + firm_rng.uniform(-0.5, 0.5),
                personality=personality,
                is_baseline=False,
            )
            firm.set_personality(personality)
            if category == "Services":
                firm.happiness_boost_per_unit = random.uniform(0.005, 0.02)
            queued_firms.append(firm)
            next_firm_id += 1

    # Households
    households = []
    for i in range(num_households):
        hh = HouseholdAgent(
            household_id=i,
            skills_level=min(0.95, 0.2 + (i / num_households) * 0.75),
            age=22 + (i % 40),
            cash_balance=500.0 + (i % 100) * 15.0,
        )
        households.append(hh)

    bank = BankAgent(cash_reserves=num_households * 1500.0) if enable_bank else None

    economy = Economy(
        households=households,
        firms=firms,
        government=gov,
        queued_firms=queued_firms,
        bank=bank,
    )
    return economy


def collect_metrics(economy: Economy, tick_time_ms: float) -> Dict[str, float]:
    """Collect all metrics for the current tick."""
    m: Dict[str, float] = {}

    hh = economy.households
    n = len(hh)

    # Household metrics
    cash = sorted(h.cash_balance for h in hh)
    wages = [h.wage for h in hh if h.is_employed and h.wage > 0]
    employed = sum(1 for h in hh if h.is_employed)

    m["hh_count"] = n
    m["hh_mean_cash"] = sum(cash) / n
    m["hh_median_cash"] = cash[n // 2]
    m["hh_p10_cash"] = cash[n // 10]
    m["hh_p90_cash"] = cash[9 * n // 10]
    m["hh_employed"] = employed
    m["hh_unemployment_rate"] = (n - employed) / n if n > 0 else 0
    m["hh_mean_wage"] = sum(wages) / len(wages) if wages else 0
    m["hh_median_wage"] = sorted(wages)[len(wages) // 2] if wages else 0
    m["hh_mean_health"] = sum(h.health for h in hh) / n
    m["hh_mean_happiness"] = sum(h.happiness for h in hh) / n
    m["hh_mean_morale"] = sum(h.morale for h in hh) / n

    # Deposits
    if economy.bank is not None:
        m["hh_total_deposits"] = sum(h.bank_deposit for h in hh)
        m["hh_depositors"] = sum(1 for h in hh if h.bank_deposit > 0)
    else:
        m["hh_total_deposits"] = 0.0
        m["hh_depositors"] = 0

    # Firm metrics
    firms = economy.firms
    m["firm_count"] = len(firms)
    if firms:
        m["firm_mean_cash"] = sum(f.cash_balance for f in firms) / len(firms)
        m["firm_mean_price"] = sum(f.price for f in firms) / len(firms)
        m["firm_total_inventory"] = sum(f.inventory_units for f in firms)
        m["firm_total_employees"] = sum(len(f.employees) for f in firms)
        m["firm_survival_mode_count"] = sum(1 for f in firms if f.survival_mode)
        m["firm_total_govt_debt"] = sum(f.government_loan_remaining for f in firms)
        m["firm_total_bank_debt"] = sum(f.bank_loan_remaining for f in firms)
    else:
        m["firm_mean_cash"] = 0
        m["firm_mean_price"] = 0
        m["firm_total_inventory"] = 0
        m["firm_total_employees"] = 0
        m["firm_survival_mode_count"] = 0
        m["firm_total_govt_debt"] = 0
        m["firm_total_bank_debt"] = 0

    # Government metrics
    gov = economy.government
    m["gov_cash"] = gov.cash_balance
    m["gov_deficit_ratio"] = gov.deficit_ratio
    m["gov_spending_efficiency"] = gov.spending_efficiency
    m["gov_revenue"] = gov.last_tick_revenue
    m["gov_spending"] = gov.last_tick_spending

    # Bank metrics
    if economy.bank is not None:
        bank = economy.bank
        m["bank_reserves"] = bank.cash_reserves
        m["bank_deposits"] = bank.total_deposits
        m["bank_loans_out"] = bank.total_loans_outstanding
        m["bank_loan_count"] = len(bank.active_loans)
        m["bank_can_lend"] = 1 if bank.can_lend() else 0
        m["bank_lendable"] = bank.lendable_cash
        m["bank_new_loans"] = bank.last_tick_new_loans
        m["bank_defaults"] = bank.last_tick_defaults
        m["bank_repayments"] = bank.last_tick_repayments
        m["bank_loss_provision"] = bank.loan_loss_provision
        m["bank_deposit_interest"] = bank.last_tick_deposit_interest_paid

        # Credit score distribution
        firm_scores = [bank.get_firm_credit_score(f.firm_id) for f in firms]
        if firm_scores:
            m["credit_mean_firm"] = sum(firm_scores) / len(firm_scores)
            m["credit_min_firm"] = min(firm_scores)
            m["credit_max_firm"] = max(firm_scores)

    m["tick_ms"] = tick_time_ms

    return m


def format_table_row(tick: int, m: Dict[str, float], has_bank: bool) -> str:
    """Format a single row of the metrics table."""
    parts = [
        f"{tick:>4d}",
        f"{m['hh_unemployment_rate']*100:5.1f}%",
        f"{m['hh_mean_wage']:7.1f}",
        f"{m['hh_median_cash']:9.0f}",
        f"{m['hh_mean_health']:5.2f}",
        f"{m['hh_mean_happiness']:5.2f}",
        f"{m['hh_mean_morale']:5.2f}",
        f"{m['firm_count']:>3d}",
        f"{m['firm_mean_cash']:10.0f}",
        f"{m['firm_survival_mode_count']:>3d}",
        f"{m['gov_cash']:12.0f}",
        f"{m['gov_deficit_ratio']:5.2f}",
    ]
    if has_bank:
        parts.extend([
            f"{m.get('bank_reserves', 0):10.0f}",
            f"{m.get('bank_deposits', 0):10.0f}",
            f"{m.get('bank_loans_out', 0):10.0f}",
            f"{m.get('bank_loan_count', 0):>4.0f}",
            f"{m.get('bank_loss_provision', 0):8.0f}",
            f"{m.get('credit_mean_firm', 0.5):5.2f}",
        ])
    parts.append(f"{m['tick_ms']:6.1f}ms")
    return " | ".join(parts)


def print_header(has_bank: bool):
    cols = [
        "Tick", "Unemp", "MnWage", "MdnCash$", "Hlth", "Happy", "Moral",
        "Frm", "  FrmCash$", "Svl",
        "   GovCash$", "DefR",
    ]
    if has_bank:
        cols.extend([
            "  BnkResv$", "  BnkDeps$", " BnkLoans$", "Lns#", "  Losses", "CrScr",
        ])
    cols.append(" Speed")
    print(" | ".join(cols))
    print("-" * (len(" | ".join(cols)) + 5))


def main():
    parser = argparse.ArgumentParser(description="Bank integration simulation")
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--households", type=int, default=200)
    parser.add_argument("--no-bank", action="store_true")
    args = parser.parse_args()

    has_bank = not args.no_bank
    print(f"\n{'='*80}")
    print(f"  EcoSim Bank Integration Test")
    print(f"  Households: {args.households} | Ticks: {args.ticks} | Bank: {'ON' if has_bank else 'OFF'}")
    print(f"{'='*80}\n")

    economy = create_economy(args.households, enable_bank=has_bank)
    print(f"Economy created: {len(economy.households)} households, {len(economy.firms)} firms")
    if economy.bank:
        print(f"Bank initialized: ${economy.bank.cash_reserves:,.0f} reserves")
    print()

    print_header(has_bank)

    all_metrics = []
    total_time = 0.0

    for tick in range(args.ticks):
        t0 = time.perf_counter()
        economy.step()
        elapsed = (time.perf_counter() - t0) * 1000.0
        total_time += elapsed

        m = collect_metrics(economy, elapsed)
        all_metrics.append(m)

        # Print every 5 ticks or on first/last tick
        if tick % 5 == 0 or tick == args.ticks - 1:
            print(format_table_row(tick, m, has_bank))

    # Summary
    print(f"\n{'='*80}")
    print("FINAL STATE SUMMARY")
    print(f"{'='*80}")

    final = all_metrics[-1]
    print(f"\n--- Households ({int(final['hh_count'])}) ---")
    print(f"  Unemployment rate:  {final['hh_unemployment_rate']*100:.1f}%")
    print(f"  Mean wage:          ${final['hh_mean_wage']:.2f}")
    print(f"  Median wage:        ${final['hh_median_wage']:.2f}")
    print(f"  Mean cash:          ${final['hh_mean_cash']:.2f}")
    print(f"  Median cash:        ${final['hh_median_cash']:.2f}")
    print(f"  P10/P90 cash:       ${final['hh_p10_cash']:.0f} / ${final['hh_p90_cash']:.0f}")
    print(f"  Mean health:        {final['hh_mean_health']:.3f}")
    print(f"  Mean happiness:     {final['hh_mean_happiness']:.3f}")
    print(f"  Mean morale:        {final['hh_mean_morale']:.3f}")

    print(f"\n--- Firms ({int(final['firm_count'])}) ---")
    print(f"  Mean cash:          ${final['firm_mean_cash']:.0f}")
    print(f"  Mean price:         ${final['firm_mean_price']:.2f}")
    print(f"  Total employees:    {int(final['firm_total_employees'])}")
    print(f"  Total inventory:    {final['firm_total_inventory']:.0f}")
    print(f"  In survival mode:   {int(final['firm_survival_mode_count'])}")
    print(f"  Govt debt total:    ${final['firm_total_govt_debt']:.0f}")
    print(f"  Bank debt total:    ${final['firm_total_bank_debt']:.0f}")

    print(f"\n--- Government ---")
    print(f"  Cash balance:       ${final['gov_cash']:.0f}")
    print(f"  Deficit ratio:      {final['gov_deficit_ratio']:.3f}")
    print(f"  Spending efficiency: {final['gov_spending_efficiency']:.2f}")

    if has_bank:
        print(f"\n--- Bank ---")
        print(f"  Cash reserves:      ${final.get('bank_reserves', 0):.0f}")
        print(f"  Total deposits:     ${final.get('bank_deposits', 0):.0f}")
        print(f"  Loans outstanding:  ${final.get('bank_loans_out', 0):.0f}")
        print(f"  Active loan count:  {int(final.get('bank_loan_count', 0))}")
        print(f"  Can lend:           {'Yes' if final.get('bank_can_lend', 0) else 'No'}")
        print(f"  Lendable cash:      ${final.get('bank_lendable', 0):.0f}")
        print(f"  Loss provision:     ${final.get('bank_loss_provision', 0):.0f}")
        print(f"  Mean firm credit:   {final.get('credit_mean_firm', 0.5):.3f}")
        print(f"  Min firm credit:    {final.get('credit_min_firm', 0.5):.3f}")
        print(f"  Max firm credit:    {final.get('credit_max_firm', 0.5):.3f}")
        print(f"  Depositors:         {int(final.get('hh_depositors', 0))}/{int(final['hh_count'])}")

    print(f"\n--- Performance ---")
    print(f"  Total time:         {total_time:.0f}ms")
    print(f"  Mean tick:          {total_time/args.ticks:.1f}ms")
    print(f"  Ticks/sec:          {args.ticks/(total_time/1000.0):.1f}")

    # Trend check: is the economy collapsing?
    if len(all_metrics) >= 20:
        early = all_metrics[10]
        late = all_metrics[-1]
        print(f"\n--- Trend Check (tick 10 vs tick {args.ticks-1}) ---")
        print(f"  Unemployment:  {early['hh_unemployment_rate']*100:.1f}% -> {late['hh_unemployment_rate']*100:.1f}%")
        print(f"  Mean health:   {early['hh_mean_health']:.3f} -> {late['hh_mean_health']:.3f}")
        print(f"  Mean wage:     {early['hh_mean_wage']:.1f} -> {late['hh_mean_wage']:.1f}")
        print(f"  Firm count:    {int(early['firm_count'])} -> {int(late['firm_count'])}")
        print(f"  Gov cash:      ${early['gov_cash']:.0f} -> ${late['gov_cash']:.0f}")
        if has_bank:
            print(f"  Bank reserves: ${early.get('bank_reserves', 0):.0f} -> ${late.get('bank_reserves', 0):.0f}")
            print(f"  Bank deposits: ${early.get('bank_deposits', 0):.0f} -> ${late.get('bank_deposits', 0):.0f}")


if __name__ == "__main__":
    main()
