"""
Quick test to verify the training data generation setup works correctly.

This runs a mini version (5 samples, 100 ticks) to ensure:
1. All dependencies are installed
2. The simulation runs without errors
3. Data is saved correctly

Run this BEFORE starting the full training data generation.

Expected runtime: ~2 minutes
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("="*70)
print("TRAINING SETUP VERIFICATION")
print("="*70)
print()

# Check dependencies
print("Checking dependencies...")
try:
    import numpy as np
    print("  ✓ numpy installed")
except ImportError:
    print("  ✗ numpy NOT installed - run: pip install numpy")
    sys.exit(1)

try:
    import pandas as pd
    print("  ✓ pandas installed")
except ImportError:
    print("  ✗ pandas NOT installed - run: pip install pandas")
    sys.exit(1)

try:
    from scipy.stats import qmc
    print("  ✓ scipy installed (Latin Hypercube Sampling available)")
    has_scipy = True
except ImportError:
    print("  ⚠ scipy NOT installed - will use random sampling (less optimal)")
    print("    Install with: pip install scipy")
    has_scipy = False

print()

# Check simulation imports
print("Checking simulation modules...")
try:
    from run_large_simulation import create_large_economy
    print("  ✓ run_large_simulation module found")
except ImportError as e:
    print(f"  ✗ Error importing simulation: {e}")
    sys.exit(1)

print()

# Test simulation run
print("Running test simulation (5 samples, 100 ticks)...")
print("This should take ~1-2 minutes...")
print()

from generate_training_data import generate_policy_samples, run_simulation_with_policy
import time

try:
    # Generate 5 test policies
    policies = generate_policy_samples(num_samples=5)
    print(f"✓ Generated {len(policies)} test policies")

    # Run simulations
    results = []
    start_time = time.time()

    for i, policy in enumerate(policies):
        sim_start = time.time()

        result = run_simulation_with_policy(
            policy,
            num_ticks=100,  # Shorter for testing
            num_households=500,  # Fewer agents for testing
            num_firms_per_category=3
        )

        sim_time = time.time() - sim_start
        results.append({**policy, **result})

        print(f"  [{i+1}/5] Completed in {sim_time:.1f}s - "
              f"GDP: ${result['gdp']/1e6:.2f}M, "
              f"Unemployment: {result['unemployment_rate']:.1f}%")

    total_time = time.time() - start_time
    avg_time = total_time / len(results)

    print()
    print(f"✓ All test simulations completed")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Average per simulation: {avg_time:.1f}s")
    print()

    # Estimate full run time
    full_samples = 500
    full_ticks = 300
    scaling_factor = (full_ticks / 100) * (1000 / 500)  # Scale for ticks and agents
    estimated_time_per_full_sim = avg_time * scaling_factor
    estimated_total_minutes = (full_samples * estimated_time_per_full_sim) / 60

    print("Estimated runtime for FULL generation (500 samples, 300 ticks, 1000 agents):")
    print(f"  {estimated_total_minutes:.1f} minutes ({estimated_total_minutes/60:.2f} hours)")
    print()

    # Test data saving
    print("Testing data export...")
    df = pd.DataFrame(results)
    test_file = "test_training_data.csv"
    df.to_csv(test_file, index=False)
    print(f"✓ Data saved to {test_file}")
    print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print()

    # Show sample data
    print("Sample data preview:")
    print("-"*70)
    print(df[['wageTax', 'minimumWage', 'universalBasicIncome', 'gdp', 'unemployment_rate']].head())
    print()

    print("="*70)
    print("✓ SETUP VERIFICATION COMPLETE")
    print("="*70)
    print()
    print("Everything looks good! You're ready to run:")
    print("  python generate_training_data.py")
    print()
    print(f"Cleanup: You can delete {test_file} if you want.")

except Exception as e:
    print()
    print("="*70)
    print("✗ SETUP VERIFICATION FAILED")
    print("="*70)
    print(f"Error: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    print("Please fix the error before running full data generation.")
    sys.exit(1)
