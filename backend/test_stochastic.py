"""
Test script to verify that the simulation produces different outcomes
when run with the same policy configuration.

This demonstrates the stochastic nature of the simulation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run_large_simulation import create_large_economy

def run_simulation_sample(num_ticks=100):
    """Run simulation for num_ticks and return final metrics."""
    print("Creating economy...")
    economy = create_large_economy(
        num_households=500,  # Smaller for faster testing
        num_firms_per_category=3  # Fewer firms for faster testing
    )

    # Apply policy settings
    economy.government.wage_tax_rate = 0.10
    economy.government.profit_tax_rate = 0.25

    print(f"Running simulation for {num_ticks} ticks...")
    for tick in range(num_ticks):
        economy.step()
        if (tick + 1) % 20 == 0:
            print(f"  Tick {tick + 1}/{num_ticks}")

    # Calculate final metrics
    total_cash = sum(h.cash_balance for h in economy.households)
    unemployed = sum(1 for h in economy.households if not h.is_employed)
    unemployment_rate = unemployed / len(economy.households) * 100
    mean_happiness = sum(h.happiness for h in economy.households) / len(economy.households)

    return {
        "total_cash": total_cash,
        "unemployment_rate": unemployment_rate,
        "mean_happiness": mean_happiness
    }

if __name__ == "__main__":
    print("=" * 60)
    print("STOCHASTICITY TEST")
    print("Running 3 simulations with identical policy configurations")
    print("=" * 60)
    print()

    results = []
    for run_num in range(1, 4):
        print(f"\n{'='*60}")
        print(f"RUN {run_num}")
        print(f"{'='*60}")
        metrics = run_simulation_sample(num_ticks=100)
        results.append(metrics)
        print(f"\nRun {run_num} Results:")
        print(f"  Total Household Cash: ${metrics['total_cash']:,.2f}")
        print(f"  Unemployment Rate: {metrics['unemployment_rate']:.2f}%")
        print(f"  Mean Happiness: {metrics['mean_happiness']:.4f}")

    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print("\nAll three runs used IDENTICAL policy settings:")
    print("  - Households: 500")
    print("  - Wage Tax: 10%")
    print("  - Profit Tax: 25%")
    print()

    # Check if results differ
    cash_values = [r['total_cash'] for r in results]
    unemp_values = [r['unemployment_rate'] for r in results]

    cash_variation = max(cash_values) - min(cash_values)
    unemp_variation = max(unemp_values) - min(unemp_values)

    print(f"Total Cash Variation: ${cash_variation:,.2f}")
    print(f"Unemployment Variation: {unemp_variation:.2f}%")
    print()

    if cash_variation > 1000 or unemp_variation > 0.5:
        print("✓ SUCCESS: Simulation exhibits stochastic behavior!")
        print("  Different runs with same policy produce different outcomes.")
    else:
        print("✗ WARNING: Results are too similar - may still be deterministic")
