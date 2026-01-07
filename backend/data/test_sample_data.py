"""
Sample Data Test - Demonstrates data warehouse functionality

Creates a mock simulation run with realistic data to verify:
- Creating runs
- Inserting tick metrics
- Policy configuration
- Querying and aggregation
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import DatabaseManager, SimulationRun, TickMetrics, PolicyConfig
from datetime import datetime
import random


def generate_sample_simulation():
    """Generate a sample simulation run with realistic data"""

    db = DatabaseManager()

    # Create simulation run
    run_id = f"sample_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run = SimulationRun(
        run_id=run_id,
        status='running',
        num_households=1000,
        num_firms=30,
        description='Sample simulation for testing data warehouse',
        tags='test,sample,demonstration'
    )

    print(f"Creating simulation run: {run_id}")
    db.create_run(run)

    # Create policy configuration
    policy = PolicyConfig(
        run_id=run_id,
        wage_tax=0.20,
        profit_tax=0.30,
        wealth_tax_rate=0.02,
        wealth_tax_threshold=100000.0,
        universal_basic_income=250.0,
        unemployment_benefit_rate=0.60,
        minimum_wage=35.0,
        inflation_rate=0.02,
        birth_rate=0.01,
        agent_stabilizers_enabled=True
    )

    print("Inserting policy configuration...")
    db.insert_policy_config(policy)

    # Generate 500 ticks of metrics
    print("Generating 500 ticks of economic data...")

    base_gdp = 50000.0
    base_unemployment = 8.0
    base_gini = 0.42

    metrics_batch = []

    for tick in range(500):
        # Simulate economic fluctuations
        gdp_variation = random.gauss(0, 1000)
        unemployment_variation = random.gauss(0, 0.5)
        gini_variation = random.gauss(0, 0.01)

        # Add growth trend
        gdp_trend = tick * 50
        unemployment_trend = -tick * 0.005  # Improving over time

        metrics = TickMetrics(
            run_id=run_id,
            tick=tick,
            gdp=base_gdp + gdp_trend + gdp_variation,
            unemployment_rate=max(0, base_unemployment + unemployment_trend + unemployment_variation),
            mean_wage=45.0 + tick * 0.05 + random.gauss(0, 1),
            median_wage=42.0 + tick * 0.04 + random.gauss(0, 0.8),
            avg_happiness=75.0 + random.gauss(0, 2),
            avg_health=80.0 + random.gauss(0, 1.5),
            avg_morale=70.0 + random.gauss(0, 3),
            total_net_worth=1000000.0 + tick * 1000,
            gini_coefficient=base_gini + gini_variation,
            top10_wealth_share=35.0 + random.gauss(0, 1),
            bottom50_wealth_share=15.0 + random.gauss(0, 0.5),
            gov_cash_balance=20000.0 + tick * 100 + random.gauss(0, 500),
            gov_profit=500.0 + random.gauss(0, 100),
            total_firms=30 + random.randint(-2, 2),
            struggling_firms=max(0, 3 + random.randint(-1, 2)),
            avg_food_price=10.0 + random.gauss(0, 0.5),
            avg_housing_price=50.0 + random.gauss(0, 2),
            avg_services_price=25.0 + random.gauss(0, 1)
        )

        metrics_batch.append(metrics)

        # Batch insert every 50 ticks
        if (tick + 1) % 50 == 0:
            db.insert_tick_metrics(metrics_batch)
            print(f"  Inserted ticks {tick - 49} to {tick}")
            metrics_batch = []

    # Insert any remaining
    if metrics_batch:
        db.insert_tick_metrics(metrics_batch)

    # Mark run as completed
    final_metrics = {
        'gdp': metrics.gdp,
        'unemployment_rate': metrics.unemployment_rate,
        'gini_coefficient': metrics.gini_coefficient,
        'avg_happiness': metrics.avg_happiness,
        'avg_health': metrics.avg_health,
        'gov_cash_balance': metrics.gov_cash_balance
    }

    db.update_run_status(run_id, 'completed', total_ticks=500, final_metrics=final_metrics)
    print("✓ Simulation run completed")

    # Query and display results
    print("\n" + "="*70)
    print("SIMULATION RESULTS")
    print("="*70)

    # Get run summary
    summary = db.get_run_summary(run_id)
    print(f"\nRun ID: {run_id}")
    print(f"Total Ticks: {summary['tick_count']}")
    print(f"Average GDP: ${summary['avg_gdp']:,.2f}")
    print(f"Average Unemployment: {summary['avg_unemployment']:.2f}%")
    print(f"Average Gini: {summary['avg_gini']:.4f}")
    print(f"Average Happiness: {summary['avg_happiness']:.2f}")
    print(f"Peak GDP: ${summary['peak_gdp']:,.2f}")
    print(f"Min Unemployment: {summary['min_unemployment']:.2f}%")

    # Get policy config
    policy_fetched = db.get_policy_config(run_id)
    print(f"\nPolicy Configuration:")
    print(f"  UBI: ${policy_fetched.universal_basic_income:.2f}")
    print(f"  Minimum Wage: ${policy_fetched.minimum_wage:.2f}")
    print(f"  Wage Tax: {policy_fetched.wage_tax * 100:.1f}%")
    print(f"  Profit Tax: {policy_fetched.profit_tax * 100:.1f}%")

    # Show database stats
    stats = db.get_database_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total Runs: {stats['total_runs']}")
    print(f"  Completed Runs: {stats['completed_runs']}")
    print(f"  Total Tick Records: {stats['total_ticks']}")
    print(f"  Database Size: {stats['db_size_mb']:.2f} MB")

    print("\n✓ Sample data test completed successfully!")
    print(f"✓ Database: {db.db_path}")

    db.close()


if __name__ == "__main__":
    generate_sample_simulation()
