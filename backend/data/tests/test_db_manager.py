"""
Unit tests for DatabaseManager

Tests database operations including:
- Creating runs
- Inserting tick metrics
- Querying data
- Policy configuration
"""

import unittest
import os
import sys
import tempfile
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.db_manager import (
    DatabaseManager,
    SimulationRun,
    TickMetrics,
    PolicyConfig
)


class TestDatabaseManager(unittest.TestCase):
    """Test cases for DatabaseManager"""

    def setUp(self):
        """Create temporary database for testing"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize database with schema
        self.db = DatabaseManager(self.db_path)
        self._create_schema()

    def tearDown(self):
        """Clean up temporary database"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_schema(self):
        """Create database schema"""
        schema_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'schema.sql'
        )
        with open(schema_path) as f:
            self.db.conn.executescript(f.read())
        self.db.conn.commit()

    # =========================================================================
    # Test Simulation Run Operations
    # =========================================================================

    def test_create_run(self):
        """Test creating a simulation run"""
        run = SimulationRun(
            run_id='test_run_001',
            status='running',
            num_households=1000,
            num_firms=30,
            description='Test simulation',
            tags='test,automated'
        )

        run_id = self.db.create_run(run)
        self.assertEqual(run_id, 'test_run_001')

        # Verify run was created
        fetched = self.db.get_run('test_run_001')
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.num_households, 1000)
        self.assertEqual(fetched.status, 'running')

    def test_update_run_status(self):
        """Test updating run status"""
        run = SimulationRun(run_id='test_run_002', status='running')
        self.db.create_run(run)

        # Update to completed with final metrics
        final_metrics = {
            'gdp': 50000.0,
            'unemployment_rate': 8.5,
            'gini_coefficient': 0.42,
            'avg_happiness': 75.3,
            'avg_health': 82.1,
            'gov_cash_balance': 15000.0
        }

        self.db.update_run_status(
            'test_run_002',
            'completed',
            total_ticks=1000,
            final_metrics=final_metrics
        )

        # Verify update
        fetched = self.db.get_run('test_run_002')
        self.assertEqual(fetched.status, 'completed')
        self.assertEqual(fetched.total_ticks, 1000)
        self.assertEqual(fetched.final_gdp, 50000.0)
        self.assertEqual(fetched.final_unemployment, 8.5)
        self.assertIsNotNone(fetched.ended_at)

    def test_get_runs_with_filter(self):
        """Test getting runs with status filter"""
        # Create multiple runs
        for i in range(5):
            status = 'completed' if i < 3 else 'running'
            run = SimulationRun(
                run_id=f'test_run_{i:03d}',
                status=status
            )
            self.db.create_run(run)

        # Get completed runs
        completed = self.db.get_runs(status='completed')
        self.assertEqual(len(completed), 3)

        # Get running runs
        running = self.db.get_runs(status='running')
        self.assertEqual(len(running), 2)

        # Get all runs
        all_runs = self.db.get_runs(limit=10)
        self.assertEqual(len(all_runs), 5)

    # =========================================================================
    # Test Tick Metrics Operations
    # =========================================================================

    def test_insert_tick_metrics(self):
        """Test batch inserting tick metrics"""
        # Create a run first
        run = SimulationRun(run_id='test_metrics_run')
        self.db.create_run(run)

        # Create metrics for 100 ticks
        metrics = []
        for tick in range(100):
            metrics.append(TickMetrics(
                run_id='test_metrics_run',
                tick=tick,
                gdp=50000.0 + tick * 100,
                unemployment_rate=8.0 + (tick % 5) * 0.1,
                mean_wage=45.0,
                median_wage=42.0,
                avg_happiness=75.0,
                avg_health=80.0,
                avg_morale=70.0,
                total_net_worth=1000000.0,
                gini_coefficient=0.42,
                top10_wealth_share=35.0,
                bottom50_wealth_share=15.0,
                gov_cash_balance=20000.0,
                gov_profit=500.0,
                total_firms=30,
                struggling_firms=3,
                avg_food_price=10.0,
                avg_housing_price=50.0,
                avg_services_price=25.0
            ))

        # Batch insert
        self.db.insert_tick_metrics(metrics)

        # Verify all inserted
        fetched = self.db.get_tick_metrics('test_metrics_run')
        self.assertEqual(len(fetched), 100)

        # Verify first and last tick
        self.assertEqual(fetched[0]['tick'], 0)
        self.assertEqual(fetched[99]['tick'], 99)
        self.assertEqual(fetched[0]['gdp'], 50000.0)
        self.assertEqual(fetched[99]['gdp'], 59900.0)

    def test_get_tick_metrics_range(self):
        """Test getting tick metrics for specific range"""
        run = SimulationRun(run_id='test_range_run')
        self.db.create_run(run)

        # Insert 500 ticks
        metrics = [
            TickMetrics(
                run_id='test_range_run',
                tick=t,
                gdp=float(t * 100),
                unemployment_rate=8.0,
                mean_wage=45.0,
                median_wage=42.0,
                avg_happiness=75.0,
                avg_health=80.0,
                avg_morale=70.0,
                total_net_worth=1000000.0,
                gini_coefficient=0.42,
                top10_wealth_share=35.0,
                bottom50_wealth_share=15.0,
                gov_cash_balance=20000.0,
                gov_profit=500.0,
                total_firms=30,
                struggling_firms=3
            )
            for t in range(500)
        ]
        self.db.insert_tick_metrics(metrics)

        # Get range 100-200
        range_metrics = self.db.get_tick_metrics(
            'test_range_run',
            tick_start=100,
            tick_end=200
        )
        self.assertEqual(len(range_metrics), 101)  # Inclusive
        self.assertEqual(range_metrics[0]['tick'], 100)
        self.assertEqual(range_metrics[-1]['tick'], 200)

    def test_get_run_summary(self):
        """Test getting aggregate statistics"""
        run = SimulationRun(run_id='test_summary_run')
        self.db.create_run(run)

        # Insert metrics with known values
        metrics = [
            TickMetrics(
                run_id='test_summary_run',
                tick=t,
                gdp=50000.0 + t * 100,  # Increasing
                unemployment_rate=8.0,
                mean_wage=45.0,
                median_wage=42.0,
                avg_happiness=75.0,
                avg_health=80.0,
                avg_morale=70.0,
                total_net_worth=1000000.0,
                gini_coefficient=0.40 + t * 0.001,  # Slowly increasing
                top10_wealth_share=35.0,
                bottom50_wealth_share=15.0,
                gov_cash_balance=20000.0,
                gov_profit=500.0,
                total_firms=30,
                struggling_firms=3
            )
            for t in range(100)
        ]
        self.db.insert_tick_metrics(metrics)

        # Get summary
        summary = self.db.get_run_summary('test_summary_run')

        self.assertEqual(summary['tick_count'], 100)
        self.assertEqual(summary['avg_unemployment'], 8.0)
        self.assertEqual(summary['avg_happiness'], 75.0)
        self.assertGreater(summary['peak_gdp'], 50000.0)
        self.assertLess(summary['avg_gini'], 0.5)

    # =========================================================================
    # Test Policy Config Operations
    # =========================================================================

    def test_insert_policy_config(self):
        """Test inserting policy configuration"""
        run = SimulationRun(run_id='test_policy_run')
        self.db.create_run(run)

        policy = PolicyConfig(
            run_id='test_policy_run',
            wage_tax=0.20,
            profit_tax=0.30,
            wealth_tax_rate=0.05,
            wealth_tax_threshold=100000.0,
            universal_basic_income=200.0,
            unemployment_benefit_rate=0.50,
            minimum_wage=30.0,
            inflation_rate=0.02,
            birth_rate=0.01,
            agent_stabilizers_enabled=True
        )

        self.db.insert_policy_config(policy)

        # Verify
        fetched = self.db.get_policy_config('test_policy_run')
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.wage_tax, 0.20)
        self.assertEqual(fetched.universal_basic_income, 200.0)
        self.assertTrue(fetched.agent_stabilizers_enabled)

    # =========================================================================
    # Test Utility Methods
    # =========================================================================

    def test_database_stats(self):
        """Test getting database statistics"""
        # Create some data
        for i in range(5):
            run = SimulationRun(run_id=f'stats_run_{i}')
            self.db.create_run(run)

        # Update some to completed
        self.db.update_run_status('stats_run_0', 'completed', total_ticks=100)
        self.db.update_run_status('stats_run_1', 'completed', total_ticks=200)

        stats = self.db.get_database_stats()

        self.assertEqual(stats['total_runs'], 5)
        self.assertEqual(stats['completed_runs'], 2)
        self.assertGreaterEqual(stats['db_size_mb'], 0)

    def test_execute_query(self):
        """Test executing arbitrary queries"""
        # Create test data
        run = SimulationRun(run_id='query_test_run')
        self.db.create_run(run)

        # Execute custom query
        results = self.db.execute_query(
            "SELECT run_id, status FROM simulation_runs WHERE run_id = ?",
            ('query_test_run',)
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['run_id'], 'query_test_run')


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDatabaseManager)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
