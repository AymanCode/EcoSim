"""
Generate training data for ML prediction layer.

This script runs multiple simulations with varied policy configurations
and records the economic outcomes for training ML models.

Configuration:
- 1000 households, 5 firms per category
- 300 ticks per simulation (~12 simulated weeks)
- 500 different policy configurations
- Latin Hypercube Sampling for policy space coverage

Estimated runtime: 2-2.5 hours
"""

import sys
import os
import time
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from run_large_simulation import create_large_economy

def calculate_gini(households):
    """Calculate Gini coefficient for wealth inequality."""
    wealth = np.array([h.cash_balance for h in households])
    wealth = np.sort(wealth)
    n = len(wealth)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * wealth)) / (n * np.sum(wealth)) - (n + 1) / n

def generate_policy_samples(num_samples=500):
    """
    Generate policy configurations using Latin Hypercube Sampling.

    This ensures good coverage of the policy space compared to pure random sampling.
    """
    try:
        from scipy.stats import qmc
        print("Using Latin Hypercube Sampling for policy generation...")

        sampler = qmc.LatinHypercube(d=9, seed=42)
        sample = sampler.random(n=num_samples)

        policies = []
        for i in range(num_samples):
            policies.append({
                'wageTax': float(sample[i, 0] * 0.30),                      # 0% to 30%
                'profitTax': float(sample[i, 1] * 0.40 + 0.10),             # 10% to 50%
                'inflationRate': float(sample[i, 2] * 0.10),                # 0% to 10%
                'birthRate': float(sample[i, 3] * 0.05),                    # 0% to 5%
                'minimumWage': float(sample[i, 4] * 35 + 15),               # $15 to $50
                'unemploymentBenefitRate': float(sample[i, 5] * 0.80),      # 0% to 80%
                'universalBasicIncome': float(sample[i, 6] * 500),          # $0 to $500
                'wealthTaxThreshold': float(sample[i, 7] * 190000 + 10000), # $10K to $200K
                'wealthTaxRate': float(sample[i, 8] * 0.10),                # 0% to 10%
            })

        return policies

    except ImportError:
        print("scipy not available, falling back to random sampling...")
        print("Install scipy for better coverage: pip install scipy")

        # Fallback to random sampling
        policies = []
        for _ in range(num_samples):
            policies.append({
                'wageTax': np.random.uniform(0.0, 0.30),
                'profitTax': np.random.uniform(0.10, 0.50),
                'inflationRate': np.random.uniform(0.0, 0.10),
                'birthRate': np.random.uniform(0.0, 0.05),
                'minimumWage': np.random.uniform(15.0, 50.0),
                'unemploymentBenefitRate': np.random.uniform(0.0, 0.80),
                'universalBasicIncome': np.random.uniform(0.0, 500.0),
                'wealthTaxThreshold': np.random.uniform(10000, 200000),
                'wealthTaxRate': np.random.uniform(0.0, 0.10),
            })

        return policies

def run_simulation_with_policy(policy, num_ticks=300, num_households=1000, num_firms_per_category=5):
    """
    Run a single simulation with the given policy configuration.

    Returns:
        dict: Economic outcomes after num_ticks
    """
    # Create economy
    economy = create_large_economy(
        num_households=num_households,
        num_firms_per_category=num_firms_per_category
    )

    # Apply policy configuration
    economy.government.wage_tax_rate = policy['wageTax']
    economy.government.profit_tax_rate = policy['profitTax']
    economy.government.target_inflation_rate = policy['inflationRate']
    economy.government.birth_rate = policy['birthRate']
    economy.config.labor_market.minimum_wage_floor = policy['minimumWage']
    economy.government.ubi_amount = policy['universalBasicIncome']
    economy.government.wealth_tax_threshold = policy['wealthTaxThreshold']
    economy.government.wealth_tax_rate = policy['wealthTaxRate']

    # Calculate unemployment benefit based on rate
    total_wages = sum(h.wage for h in economy.households if h.is_employed)
    employed_count = sum(1 for h in economy.households if h.is_employed)
    avg_wage = total_wages / employed_count if employed_count > 0 else 30.0
    economy.government.unemployment_benefit_level = avg_wage * policy['unemploymentBenefitRate']

    # Also update all firms' minimum wage
    for firm in economy.firms:
        if firm.wage_offer < policy['minimumWage']:
            firm.wage_offer = policy['minimumWage']

    # Run simulation
    for tick in range(num_ticks):
        economy.step()

    # Extract final metrics
    unemployed = sum(1 for h in economy.households if not h.is_employed)
    unemployment_rate = unemployed / len(economy.households)

    total_gdp = sum(getattr(f, 'last_revenue', 0.0) for f in economy.firms)
    mean_happiness = np.mean([h.happiness for h in economy.households])
    mean_health = np.mean([h.health for h in economy.households])
    mean_wage = np.mean([h.wage for h in economy.households if h.is_employed]) if employed_count > 0 else 0
    median_wage = np.median([h.wage for h in economy.households if h.is_employed]) if employed_count > 0 else 0

    gini = calculate_gini(economy.households)

    gov_balance = economy.government.cash_balance
    gov_debt = -gov_balance if gov_balance < 0 else 0.0

    total_wealth = sum(h.cash_balance for h in economy.households)
    num_firms = len([f for f in economy.firms if f.cash_balance > 0])

    return {
        'gdp': total_gdp,
        'unemployment_rate': unemployment_rate * 100,  # Convert to percentage
        'mean_happiness': mean_happiness,
        'mean_health': mean_health,
        'mean_wage': mean_wage,
        'median_wage': median_wage,
        'gini_coefficient': gini,
        'government_debt': gov_debt,
        'government_balance': gov_balance,
        'total_household_wealth': total_wealth,
        'num_active_firms': num_firms,
    }

def main():
    """Generate training dataset."""
    print("="*70)
    print("TRAINING DATA GENERATION")
    print("="*70)
    print()

    # Configuration
    NUM_SAMPLES = 500
    NUM_TICKS = 300
    NUM_HOUSEHOLDS = 1000
    NUM_FIRMS_PER_CATEGORY = 5

    print(f"Configuration:")
    print(f"  Samples: {NUM_SAMPLES}")
    print(f"  Ticks per simulation: {NUM_TICKS}")
    print(f"  Households: {NUM_HOUSEHOLDS}")
    print(f"  Firms per category: {NUM_FIRMS_PER_CATEGORY}")
    print()

    # Estimate runtime
    estimated_time_per_sim = 15  # seconds (conservative estimate)
    estimated_total_minutes = (NUM_SAMPLES * estimated_time_per_sim) / 60
    print(f"Estimated runtime: {estimated_total_minutes:.1f} minutes ({estimated_total_minutes/60:.1f} hours)")
    print()

    # Generate policy samples
    print("Generating policy configurations...")
    policies = generate_policy_samples(NUM_SAMPLES)
    print(f"✓ Generated {len(policies)} policy configurations")
    print()

    # Run simulations
    print("Starting simulations...")
    print("(Progress will be saved every 50 samples)")
    print()

    training_data = []
    start_time = time.time()

    for i, policy in enumerate(policies):
        sim_start = time.time()

        try:
            # Run simulation
            result = run_simulation_with_policy(
                policy,
                num_ticks=NUM_TICKS,
                num_households=NUM_HOUSEHOLDS,
                num_firms_per_category=NUM_FIRMS_PER_CATEGORY
            )

            # Combine policy and results
            sample = {**policy, **result}
            training_data.append(sample)

            sim_time = time.time() - sim_start

            # Progress update
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                avg_time_per_sim = elapsed / (i + 1)
                remaining_sims = NUM_SAMPLES - (i + 1)
                eta_seconds = remaining_sims * avg_time_per_sim
                eta_minutes = eta_seconds / 60

                print(f"[{i+1}/{NUM_SAMPLES}] "
                      f"Sim time: {sim_time:.1f}s | "
                      f"Avg: {avg_time_per_sim:.1f}s | "
                      f"ETA: {eta_minutes:.1f}m | "
                      f"GDP: ${result['gdp']/1e6:.2f}M | "
                      f"Unemp: {result['unemployment_rate']:.1f}%")

            # Save checkpoint every 50 samples
            if (i + 1) % 50 == 0:
                checkpoint_df = pd.DataFrame(training_data)
                checkpoint_file = f"training_data_checkpoint_{i+1}.csv"
                checkpoint_df.to_csv(checkpoint_file, index=False)
                print(f"  ✓ Checkpoint saved: {checkpoint_file}")
                print()

        except Exception as e:
            print(f"  ✗ Error in simulation {i+1}: {e}")
            print(f"    Policy: {policy}")
            continue

    # Final save
    total_time = time.time() - start_time
    print()
    print("="*70)
    print("COMPLETE")
    print("="*70)
    print(f"Total simulations: {len(training_data)}/{NUM_SAMPLES}")
    print(f"Total time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"Average time per simulation: {total_time/len(training_data):.1f} seconds")
    print()

    # Save final dataset
    df = pd.DataFrame(training_data)
    output_file = f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)

    print(f"✓ Training data saved: {output_file}")
    print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print()

    # Show summary statistics
    print("Dataset Summary:")
    print("-" * 70)
    print(df.describe())
    print()

    print("✓ Ready for model training!")

if __name__ == "__main__":
    main()
