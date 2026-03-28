"""
Migration 001: Create Data Warehouse Schema

Creates the current SQLite warehouse tables:
- simulation_runs
- tick_metrics
- sector_tick_metrics
- firm_snapshots
- household_snapshots
- tracked_household_history
- decision_features
- labor_events
- healthcare_events
- policy_actions
- policy_config

Safe to run multiple times (uses IF NOT EXISTS).
"""

import sqlite3
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def run_migration():
    """Execute the migration"""
    # Get paths
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(migrations_dir)
    schema_path = os.path.join(data_dir, 'schema.sql')
    db_path = os.path.join(data_dir, 'ecosim.db')

    print("="*70)
    print("EcoSim Data Warehouse Migration 001")
    print("="*70)
    print()
    print(f"Database: {db_path}")
    print(f"Schema: {schema_path}")
    print()

    # Check if schema file exists
    if not os.path.exists(schema_path):
        print(f"✗ Schema file not found: {schema_path}")
        sys.exit(1)

    # Read schema
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        print("✓ Connected to database")

        # Execute schema
        conn.executescript(schema_sql)
        conn.commit()
        print("✓ Schema executed successfully")

        # Verify tables created
        cursor = conn.cursor()
        tables = cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        print()
        print(f"✓ Created {len(tables)} tables:")
        for table in tables:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
            print(f"  - {table[0]:25s} ({count} rows)")

        # Verify indexes
        indexes = cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        print()
        print(f"✓ Created {len(indexes)} indexes:")
        for idx in indexes:
            print(f"  - {idx[0]}")

        # Verify views
        views = cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='view'
            ORDER BY name
        """).fetchall()

        if views:
            print()
            print(f"✓ Created {len(views)} views:")
            for view in views:
                print(f"  - {view[0]}")

        conn.close()

        print()
        print("="*70)
        print("✓ Migration completed successfully!")
        print("="*70)

    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
