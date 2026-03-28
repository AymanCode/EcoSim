"""
Unit tests for DatabaseManager

Tests database operations including:
- Creating runs
- Inserting tick metrics
- Querying data
- Policy configuration
"""

import os
import sqlite3
import sys
import tempfile
import unittest

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.db_manager import (
    DatabaseManager,
)
from data.models import (
    DecisionFeature,
    FirmSnapshot,
    HealthcareEvent,
    HouseholdSnapshot,
    LaborEvent,
    PolicyAction,
    PolicyConfig,
    RegimeEvent,
    SectorShortageDiagnostic,
    SectorTickMetrics,
    SimulationRun,
    TickDiagnostic,
    TrackedHouseholdHistory,
    TickMetrics,
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
            seed=42,
            num_households=1000,
            num_firms=30,
            config_json='{"num_households":1000,"seed":42}',
            code_version='working-tree',
            schema_version='test-schema',
            decision_feature_version='v1',
            diagnostics_version='v1',
            description='Test simulation',
            tags='test,automated'
        )

        run_id = self.db.create_run(run)
        self.assertEqual(run_id, 'test_run_001')

        # Verify run was created
        fetched = self.db.get_run('test_run_001')
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.seed, 42)
        self.assertEqual(fetched.num_households, 1000)
        self.assertEqual(fetched.status, 'running')
        self.assertEqual(fetched.config_json, '{"num_households":1000,"seed":42}')
        self.assertEqual(fetched.schema_version, 'test-schema')
        self.assertEqual(fetched.diagnostics_version, 'v1')
        self.assertFalse(fetched.analysis_ready)
        self.assertEqual(fetched.last_fully_persisted_tick, 0)

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

    def test_update_run_status_analysis_fields(self):
        """Test updating reliability/lifecycle fields on a run."""
        run = SimulationRun(run_id='test_run_analysis', status='running')
        self.db.create_run(run)

        self.db.update_run_status(
            'test_run_analysis',
            'completed',
            total_ticks=12,
            last_fully_persisted_tick=12,
            analysis_ready=True,
            termination_reason='completed',
        )

        fetched = self.db.get_run('test_run_analysis')
        self.assertEqual(fetched.status, 'completed')
        self.assertEqual(fetched.last_fully_persisted_tick, 12)
        self.assertTrue(fetched.analysis_ready)
        self.assertEqual(fetched.termination_reason, 'completed')

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
                tick_duration_ms=120.0 + tick,
                labor_force_participation=68.0,
                open_vacancies=12,
                total_hires=5,
                total_layoffs=2,
                healthcare_queue_depth=7,
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
        self.assertEqual(fetched[0]['open_vacancies'], 12)
        self.assertEqual(fetched[0]['healthcare_queue_depth'], 7)
        self.assertEqual(fetched[99]['tick_duration_ms'], 219.0)

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

    def test_insert_sector_tick_metrics(self):
        """Test batch inserting per-sector metrics."""
        run = SimulationRun(run_id='test_sector_run')
        self.db.create_run(run)

        metrics = [
            SectorTickMetrics(
                run_id='test_sector_run',
                tick=1,
                sector='Food',
                firm_count=12,
                employees=340,
                vacancies=18,
                mean_wage_offer=31.5,
                mean_price=9.2,
                mean_inventory=450.0,
                total_output=900.0,
                total_revenue=8200.0,
                total_profit=1200.0,
            ),
            SectorTickMetrics(
                run_id='test_sector_run',
                tick=1,
                sector='Housing',
                firm_count=8,
                employees=120,
                vacancies=4,
                mean_wage_offer=42.0,
                mean_price=54.0,
                mean_inventory=60.0,
                total_output=120.0,
                total_revenue=9100.0,
                total_profit=1800.0,
            ),
        ]

        self.db.insert_sector_tick_metrics(metrics)
        fetched = self.db.get_sector_tick_metrics('test_sector_run', tick_start=1, tick_end=1)

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['sector'], 'Food')
        self.assertEqual(fetched[0]['vacancies'], 18)
        self.assertEqual(fetched[1]['sector'], 'Housing')
        self.assertEqual(fetched[1]['total_profit'], 1800.0)

    def test_insert_firm_snapshots(self):
        """Test batch inserting firm snapshots."""
        run = SimulationRun(run_id='test_firm_snapshot_run')
        self.db.create_run(run)

        snapshots = [
            FirmSnapshot(
                run_id='test_firm_snapshot_run',
                tick=5,
                firm_id=3,
                firm_name='FoodCo1',
                sector='Food',
                is_baseline=False,
                employee_count=18,
                doctor_employee_count=0,
                medical_employee_count=0,
                planned_hires_count=4,
                planned_layoffs_count=1,
                actual_hires_count=2,
                wage_offer=32.5,
                price=9.1,
                inventory_units=440.0,
                output_units=120.0,
                cash_balance=125000.0,
                revenue=8100.0,
                profit=950.0,
                quality_level=6.2,
                queue_depth=0,
                visits_completed=0.0,
                burn_mode=False,
                zero_cash_streak=0,
            ),
            FirmSnapshot(
                run_id='test_firm_snapshot_run',
                tick=5,
                firm_id=4,
                firm_name='BaselineHealthcare',
                sector='Healthcare',
                is_baseline=True,
                employee_count=11,
                doctor_employee_count=9,
                medical_employee_count=11,
                planned_hires_count=0,
                planned_layoffs_count=0,
                actual_hires_count=0,
                wage_offer=55.0,
                price=12.0,
                inventory_units=0.0,
                output_units=48.0,
                cash_balance=225000.0,
                revenue=3200.0,
                profit=400.0,
                quality_level=4.0,
                queue_depth=7,
                visits_completed=48.0,
                burn_mode=False,
                zero_cash_streak=0,
            ),
        ]

        self.db.insert_firm_snapshots(snapshots)
        fetched = self.db.get_firm_snapshots('test_firm_snapshot_run', tick_start=5, tick_end=5)

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['firm_name'], 'FoodCo1')
        self.assertEqual(fetched[1]['sector'], 'Healthcare')
        self.assertEqual(fetched[1]['doctor_employee_count'], 9)
        self.assertEqual(fetched[1]['queue_depth'], 7)

    def test_insert_household_snapshots(self):
        """Test batch inserting sampled household snapshots."""
        run = SimulationRun(run_id='test_household_snapshot_run')
        self.db.create_run(run)

        snapshots = [
            HouseholdSnapshot(
                run_id='test_household_snapshot_run',
                tick=5,
                household_id=10,
                state='WORKING',
                medical_status='none',
                employer_id=3,
                is_employed=True,
                can_work=True,
                cash_balance=1250.0,
                wage=42.0,
                last_wage_income=42.0,
                last_transfer_income=0.0,
                last_dividend_income=3.0,
                reservation_wage=28.0,
                expected_wage=44.0,
                skill_level=0.62,
                health=0.88,
                happiness=0.76,
                morale=0.72,
                food_security=1.0,
                housing_security=True,
                unemployment_duration=0,
                pending_healthcare_visits=0,
            ),
            HouseholdSnapshot(
                run_id='test_household_snapshot_run',
                tick=5,
                household_id=11,
                state='UNEMPLOYED',
                medical_status='none',
                employer_id=None,
                is_employed=False,
                can_work=True,
                cash_balance=340.0,
                wage=0.0,
                last_wage_income=0.0,
                last_transfer_income=20.0,
                last_dividend_income=0.0,
                reservation_wage=18.0,
                expected_wage=26.0,
                skill_level=0.41,
                health=0.67,
                happiness=0.51,
                morale=0.44,
                food_security=0.7,
                housing_security=False,
                unemployment_duration=4,
                pending_healthcare_visits=2,
            ),
        ]

        self.db.insert_household_snapshots(snapshots)
        fetched = self.db.get_household_snapshots('test_household_snapshot_run', tick_start=5, tick_end=5)

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['household_id'], 10)
        self.assertEqual(fetched[1]['state'], 'UNEMPLOYED')
        self.assertEqual(fetched[1]['pending_healthcare_visits'], 2)

    def test_insert_tracked_household_history(self):
        """Test batch inserting tracked-household history rows."""
        run = SimulationRun(run_id='test_tracked_household_run')
        self.db.create_run(run)

        history_rows = [
            TrackedHouseholdHistory(
                run_id='test_tracked_household_run',
                tick=1,
                household_id=21,
                state='WORKING',
                medical_status='none',
                employer_id=4,
                is_employed=True,
                can_work=True,
                cash_balance=980.0,
                wage=39.0,
                expected_wage=41.0,
                reservation_wage=30.0,
                health=0.84,
                happiness=0.71,
                morale=0.69,
                skill_level=0.58,
                unemployment_duration=0,
                pending_healthcare_visits=0,
            ),
            TrackedHouseholdHistory(
                run_id='test_tracked_household_run',
                tick=2,
                household_id=21,
                state='WORKING',
                medical_status='none',
                employer_id=4,
                is_employed=True,
                can_work=True,
                cash_balance=1014.0,
                wage=39.0,
                expected_wage=41.0,
                reservation_wage=30.0,
                health=0.83,
                happiness=0.72,
                morale=0.70,
                skill_level=0.581,
                unemployment_duration=0,
                pending_healthcare_visits=0,
            ),
        ]

        self.db.insert_tracked_household_history(history_rows)
        fetched = self.db.get_tracked_household_history('test_tracked_household_run', household_id=21)

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['tick'], 1)
        self.assertEqual(fetched[1]['cash_balance'], 1014.0)

    def test_insert_decision_features(self):
        """Test batch inserting per-tick decision features."""
        run = SimulationRun(run_id='test_decision_features_run')
        self.db.create_run(run)

        features = [
            DecisionFeature(
                run_id='test_decision_features_run',
                tick=1,
                unemployment_short_ma=11.5,
                unemployment_long_ma=11.5,
                inflation_short_ma=0.0,
                hiring_momentum=0.0,
                layoff_momentum=0.0,
                vacancy_fill_ratio=0.82,
                wage_pressure=8.4,
                healthcare_pressure=0.6,
                consumer_distress_score=18.0,
                fiscal_stress_score=4.0,
                inequality_pressure_score=39.0,
            ),
            DecisionFeature(
                run_id='test_decision_features_run',
                tick=2,
                unemployment_short_ma=11.2,
                unemployment_long_ma=11.4,
                inflation_short_ma=1.7,
                hiring_momentum=0.3,
                layoff_momentum=-0.1,
                vacancy_fill_ratio=0.88,
                wage_pressure=7.9,
                healthcare_pressure=0.4,
                consumer_distress_score=17.5,
                fiscal_stress_score=3.5,
                inequality_pressure_score=38.8,
            ),
        ]

        self.db.insert_decision_features(features)
        fetched = self.db.get_decision_features('test_decision_features_run', tick_start=1, tick_end=2)

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['tick'], 1)
        self.assertAlmostEqual(fetched[1]['inflation_short_ma'], 1.7)
        self.assertAlmostEqual(fetched[1]['vacancy_fill_ratio'], 0.88)

    def test_insert_tick_diagnostics(self):
        """Test batch inserting compact per-tick diagnostic rows."""
        run = SimulationRun(run_id='test_tick_diag_run')
        self.db.create_run(run)

        rows = [
            TickDiagnostic(
                run_id='test_tick_diag_run',
                tick=2,
                unemployment_change_pp=1.5,
                unemployment_primary_driver='failed_hiring',
                layoffs_count=4,
                hires_count=2,
                failed_hiring_firm_count=3,
                failed_hiring_roles_count=7,
                wage_mismatch_seeker_count=12,
                health_blocked_worker_count=5,
                inactive_work_capable_count=8,
                avg_health_change_pp=-2.0,
                health_primary_driver='healthcare_denial',
                low_health_share=18.0,
                food_insecure_share=9.0,
                cash_stressed_share=22.0,
                pending_healthcare_visits_total=14,
                healthcare_queue_depth=11,
                healthcare_completed_count=6,
                healthcare_denied_count=3,
                firm_distress_primary_driver='burn_mode',
                burn_mode_firm_count=2,
                survival_mode_firm_count=1,
                zero_cash_firm_count=1,
                weak_demand_firm_count=4,
                inventory_pressure_firm_count=3,
                bankruptcy_count=1,
                housing_primary_driver='unaffordable',
                eviction_count=2,
                housing_failure_count=5,
                housing_unaffordable_count=3,
                housing_no_supply_count=2,
                homeless_household_count=7,
                shortage_active_sector_count=2,
            )
        ]

        self.db.insert_tick_diagnostics(rows)
        fetched = self.db.execute_query(
            "SELECT * FROM tick_diagnostics WHERE run_id = ?",
            ('test_tick_diag_run',),
        )
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0]['unemployment_primary_driver'], 'failed_hiring')
        self.assertEqual(fetched[0]['shortage_active_sector_count'], 2)

    def test_insert_sector_shortage_diagnostics(self):
        """Test batch inserting sector shortage diagnostic rows."""
        run = SimulationRun(run_id='test_sector_shortage_run')
        self.db.create_run(run)

        rows = [
            SectorShortageDiagnostic(
                run_id='test_sector_shortage_run',
                tick=2,
                sector='Healthcare',
                shortage_active=True,
                shortage_severity=63.5,
                primary_driver='queue',
                mean_sell_through_rate=0.0,
                vacancy_pressure=0.2,
                inventory_pressure=0.9,
                price_pressure=0.1,
                queue_pressure=0.8,
                occupancy_pressure=0.0,
            )
        ]

        self.db.insert_sector_shortage_diagnostics(rows)
        fetched = self.db.execute_query(
            "SELECT * FROM sector_shortage_diagnostics WHERE run_id = ?",
            ('test_sector_shortage_run',),
        )
        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0]['sector'], 'Healthcare')
        self.assertEqual(fetched[0]['primary_driver'], 'queue')

    def test_insert_labor_events(self):
        """Test batch inserting labor events."""
        run = SimulationRun(run_id='test_labor_event_run')
        self.db.create_run(run)

        events = [
            LaborEvent(
                run_id='test_labor_event_run',
                tick=2,
                household_id=10,
                firm_id=7,
                event_type='hire',
                actual_wage=42.5,
                wage_offer=40.0,
                reservation_wage=30.0,
                skill_level=0.8,
            ),
            LaborEvent(
                run_id='test_labor_event_run',
                tick=2,
                household_id=11,
                firm_id=7,
                event_type='layoff',
                actual_wage=39.0,
                wage_offer=40.0,
                reservation_wage=28.0,
                skill_level=0.4,
            ),
        ]

        self.db.insert_labor_events(events)
        fetched = self.db.execute_query(
            "SELECT * FROM labor_events WHERE run_id = ? ORDER BY event_id",
            ('test_labor_event_run',),
        )

        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]['event_type'], 'hire')
        self.assertEqual(fetched[1]['household_id'], 11)
        self.assertIsNotNone(fetched[0]['event_key'])

    def test_insert_labor_events_is_idempotent(self):
        """Duplicate labor event inserts should be ignored by event key."""
        run = SimulationRun(run_id='test_labor_event_idempotent')
        self.db.create_run(run)

        events = [
            LaborEvent(
                run_id='test_labor_event_idempotent',
                tick=2,
                household_id=10,
                firm_id=7,
                event_type='hire',
                actual_wage=42.5,
                wage_offer=40.0,
                reservation_wage=30.0,
                skill_level=0.8,
            )
        ]

        self.db.insert_labor_events(events)
        self.db.insert_labor_events(events)
        fetched = self.db.execute_query(
            "SELECT * FROM labor_events WHERE run_id = ?",
            ('test_labor_event_idempotent',),
        )
        self.assertEqual(len(fetched), 1)

    def test_insert_healthcare_events(self):
        """Test batch inserting healthcare events."""
        run = SimulationRun(run_id='test_health_event_run')
        self.db.create_run(run)

        events = [
            HealthcareEvent(
                run_id='test_health_event_run',
                tick=3,
                household_id=21,
                firm_id=4,
                event_type='visit_completed',
                queue_wait_ticks=2,
                visit_price=15.0,
                household_cost=9.0,
                government_cost=6.0,
                health_before=0.55,
                health_after=0.72,
            )
        ]

        self.db.insert_healthcare_events(events)
        fetched = self.db.execute_query(
            "SELECT * FROM healthcare_events WHERE run_id = ?",
            ('test_health_event_run',),
        )

        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0]['queue_wait_ticks'], 2)
        self.assertEqual(fetched[0]['event_type'], 'visit_completed')
        self.assertIsNotNone(fetched[0]['event_key'])

    def test_insert_healthcare_events_is_idempotent(self):
        """Duplicate healthcare event inserts should be ignored by event key."""
        run = SimulationRun(run_id='test_health_event_idempotent')
        self.db.create_run(run)

        events = [
            HealthcareEvent(
                run_id='test_health_event_idempotent',
                tick=3,
                household_id=21,
                firm_id=4,
                event_type='visit_completed',
                queue_wait_ticks=2,
                visit_price=15.0,
                household_cost=9.0,
                government_cost=6.0,
                health_before=0.55,
                health_after=0.72,
            )
        ]

        self.db.insert_healthcare_events(events)
        self.db.insert_healthcare_events(events)
        fetched = self.db.execute_query(
            "SELECT * FROM healthcare_events WHERE run_id = ?",
            ('test_health_event_idempotent',),
        )
        self.assertEqual(len(fetched), 1)

    def test_insert_policy_actions(self):
        """Test batch inserting policy actions."""
        run = SimulationRun(run_id='test_policy_action_run')
        self.db.create_run(run)

        actions = [
            PolicyAction(
                run_id='test_policy_action_run',
                tick=4,
                actor='user',
                action_type='minimumWage',
                payload_json='{"value": 35.0}',
                reason_summary='User updated minimum wage',
            )
        ]

        self.db.insert_policy_actions(actions)
        fetched = self.db.execute_query(
            "SELECT * FROM policy_actions WHERE run_id = ?",
            ('test_policy_action_run',),
        )

        self.assertEqual(len(fetched), 1)
        self.assertEqual(fetched[0]['actor'], 'user')
        self.assertIn('35.0', fetched[0]['payload_json'])
        self.assertIsNotNone(fetched[0]['event_key'])

    def test_insert_policy_actions_is_idempotent(self):
        """Duplicate policy action inserts should be ignored by event key."""
        run = SimulationRun(run_id='test_policy_action_idempotent')
        self.db.create_run(run)

        actions = [
            PolicyAction(
                run_id='test_policy_action_idempotent',
                tick=4,
                actor='user',
                action_type='minimumWage',
                payload_json='{"value": 35.0}',
                reason_summary='User updated minimum wage',
            )
        ]

        self.db.insert_policy_actions(actions)
        self.db.insert_policy_actions(actions)
        fetched = self.db.execute_query(
            "SELECT * FROM policy_actions WHERE run_id = ?",
            ('test_policy_action_idempotent',),
        )
        self.assertEqual(len(fetched), 1)

    def test_insert_regime_events_is_idempotent(self):
        """Duplicate regime event inserts should be ignored by event key."""
        run = SimulationRun(run_id='test_regime_event_idempotent')
        self.db.create_run(run)

        events = [
            RegimeEvent(
                run_id='test_regime_event_idempotent',
                tick=4,
                event_type='firm_bankrupt',
                entity_type='firm',
                entity_id=11,
                sector='Services',
                reason_code='cash_threshold',
                severity=10.0,
                metric_value=-500.0,
                payload_json='{"cash_balance": -500.0}',
            )
        ]

        self.db.insert_regime_events(events)
        self.db.insert_regime_events(events)
        fetched = self.db.execute_query(
            "SELECT * FROM regime_events WHERE run_id = ?",
            ('test_regime_event_idempotent',),
        )
        self.assertEqual(len(fetched), 1)

    def test_persist_flush_bundle_is_atomic_on_error(self):
        """A failed bundle flush should not partially commit any table."""
        run = SimulationRun(run_id='test_atomic_flush_run')
        self.db.create_run(run)

        original_insert_sector_rows = self.db._insert_sector_tick_metrics_rows

        def raising_sector_insert(cursor, metrics):
            raise sqlite3.IntegrityError("synthetic failure during sector insert")

        self.db._insert_sector_tick_metrics_rows = raising_sector_insert
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.persist_flush_bundle(
                    run_id='test_atomic_flush_run',
                    last_fully_persisted_tick=3,
                    tick_metrics=[
                        TickMetrics(
                            run_id='test_atomic_flush_run',
                            tick=3,
                            gdp=123.0,
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
                            struggling_firms=3,
                        )
                    ],
                    sector_tick_metrics=[
                        SectorTickMetrics(
                            run_id='test_atomic_flush_run',
                            tick=3,
                            sector='Food',
                            firm_count=4,
                            employees=20,
                            vacancies=2,
                            mean_wage_offer=31.0,
                            mean_price=8.5,
                            mean_inventory=100.0,
                            total_output=200.0,
                            total_revenue=1000.0,
                            total_profit=100.0,
                        )
                    ],
                )
        finally:
            self.db._insert_sector_tick_metrics_rows = original_insert_sector_rows

        tick_rows = self.db.execute_query(
            "SELECT * FROM tick_metrics WHERE run_id = ?",
            ('test_atomic_flush_run',),
        )
        run_row = self.db.get_run('test_atomic_flush_run')
        self.assertEqual(len(tick_rows), 0)
        self.assertEqual(run_row.last_fully_persisted_tick, 0)

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
        self.assertIn('total_firm_snapshots', stats)
        self.assertIn('total_household_snapshots', stats)
        self.assertIn('total_tracked_household_rows', stats)
        self.assertIn('total_decision_feature_rows', stats)
        self.assertIn('total_tick_diagnostic_rows', stats)
        self.assertIn('total_sector_shortage_rows', stats)
        self.assertIn('total_labor_events', stats)
        self.assertIn('total_healthcare_events', stats)
        self.assertIn('total_policy_actions', stats)
        self.assertIn('total_regime_events', stats)
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
