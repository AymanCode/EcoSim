# EcoSim Data Warehouse - Phase 1 Complete ✅

Minimal, production-ready data warehouse for storing and querying simulation runs.

---

## Overview

The data warehouse consists of **3 core tables** that capture all essential simulation data:

1. **simulation_runs** - Metadata for each simulation run
2. **tick_metrics** - Economic metrics at each tick (time-series data)
3. **policy_config** - Policy configuration per run

Plus 2 views for common queries:
- **run_summary** - Join runs with their policies
- **run_averages** - Aggregate statistics per run

---

## Quick Start

### 1. Initialize Database

```bash
python backend/data/migrations/001_create_warehouse.py
```

This creates `backend/data/ecosim.db` with the complete schema.

### 1b. Initialize PostgreSQL + TimescaleDB (Optional)

```bash
# Start local DB (from repo root)
docker compose -f docker-compose.timescale.yml up -d

# Set DSN for migration and runtime
# PowerShell example:
$env:ECOSIM_WAREHOUSE_DSN="postgresql://ecosim:ecosim@localhost:5432/ecosim"

# Apply PostgreSQL/Timescale schema
python backend/data/migrations/002_create_timescale_warehouse.py
```

Runtime backend selection is controlled by:
- `ECOSIM_ENABLE_WAREHOUSE` (`0` or `1`)
- `ECOSIM_WAREHOUSE_BACKEND` (`sqlite`, `postgres`, or `timescale`)
- `ECOSIM_SQLITE_PATH` (optional SQLite file path)
- `ECOSIM_WAREHOUSE_DSN` (required for PostgreSQL/Timescale)

### 2. Use DatabaseManager

```python
from data.db_manager import DatabaseManager, SimulationRun, TickMetrics, PolicyConfig

# Initialize
db = DatabaseManager()

# Create a run
run = SimulationRun(
    run_id='my_run_001',
    num_households=1000,
    num_firms=30,
    description='Test simulation'
)
db.create_run(run)

# Insert tick metrics (batch)
metrics = [TickMetrics(...) for tick in range(500)]
db.insert_tick_metrics(metrics)

# Add policy config
policy = PolicyConfig(run_id='my_run_001', wage_tax=0.20, ...)
db.insert_policy_config(policy)

# Mark completed
db.update_run_status('my_run_001', 'completed', total_ticks=500)

# Query
summary = db.get_run_summary('my_run_001')
print(f"Average GDP: {summary['avg_gdp']}")
```

### 3. Run Tests

```bash
# Unit tests (9 tests)
python backend/data/tests/test_db_manager.py

# Sample data test
python backend/data/test_sample_data.py
```

---

## Database Schema

### simulation_runs
```sql
run_id TEXT PRIMARY KEY
created_at TIMESTAMP
ended_at TIMESTAMP
status TEXT ('running', 'completed', 'failed', 'stopped')
num_households INTEGER
num_firms INTEGER
total_ticks INTEGER
final_gdp REAL
final_unemployment REAL
final_gini REAL
final_avg_happiness REAL
final_avg_health REAL
final_gov_balance REAL
description TEXT
tags TEXT
```

**Indexes**: created_at, status, tags

### tick_metrics
```sql
id INTEGER PRIMARY KEY
run_id TEXT (FK → simulation_runs)
tick INTEGER
created_at TIMESTAMP
gdp REAL
unemployment_rate REAL
mean_wage REAL
median_wage REAL
avg_happiness REAL
avg_health REAL
avg_morale REAL
total_net_worth REAL
gini_coefficient REAL
top10_wealth_share REAL
bottom50_wealth_share REAL
gov_cash_balance REAL
gov_profit REAL
total_firms INTEGER
struggling_firms INTEGER
avg_food_price REAL
avg_housing_price REAL
avg_services_price REAL
```

**Indexes**: run_id, (run_id, tick), tick
**Unique**: (run_id, tick)

### policy_config
```sql
id INTEGER PRIMARY KEY
run_id TEXT UNIQUE (FK → simulation_runs)
wage_tax REAL
profit_tax REAL
wealth_tax_rate REAL
wealth_tax_threshold REAL
universal_basic_income REAL
unemployment_benefit_rate REAL
minimum_wage REAL
inflation_rate REAL
birth_rate REAL
agent_stabilizers_enabled BOOLEAN
```

**Indexes**: run_id, universal_basic_income, minimum_wage

---

## API Reference

### DatabaseManager

#### Simulation Runs
- `create_run(run: SimulationRun) -> str` - Create new run
- `get_run(run_id: str) -> SimulationRun` - Get run by ID
- `get_runs(status=None, limit=100, offset=0) -> List[SimulationRun]` - List runs
- `update_run_status(run_id, status, total_ticks=None, final_metrics=None)` - Update status

#### Tick Metrics
- `insert_tick_metrics(metrics: List[TickMetrics])` - Batch insert (use for 50-100 ticks at a time)
- `get_tick_metrics(run_id, tick_start=0, tick_end=999999, columns=None) -> List[Dict]` - Get time series
- `get_run_summary(run_id) -> Dict` - Get aggregate stats (avg_gdp, avg_unemployment, etc.)

#### Policy Config
- `insert_policy_config(policy: PolicyConfig)` - Insert policy
- `get_policy_config(run_id) -> PolicyConfig` - Get policy

#### Utilities
- `execute_query(query: str, params: tuple) -> List[Dict]` - Run custom SQL
- `get_database_stats() -> Dict` - Get DB statistics

---

## Data Models

### SimulationRun
```python
@dataclass
class SimulationRun:
    run_id: str
    status: str = 'running'  # 'running', 'completed', 'failed', 'stopped'
    num_households: int = 0
    num_firms: int = 0
    total_ticks: int = 0
    created_at: Optional[str] = None
    ended_at: Optional[str] = None
    final_gdp: Optional[float] = None
    final_unemployment: Optional[float] = None
    final_gini: Optional[float] = None
    final_avg_happiness: Optional[float] = None
    final_avg_health: Optional[float] = None
    final_gov_balance: Optional[float] = None
    description: Optional[str] = None
    tags: Optional[str] = None  # Comma-separated
```

### TickMetrics
```python
@dataclass
class TickMetrics:
    run_id: str
    tick: int
    gdp: float
    unemployment_rate: float
    mean_wage: float
    median_wage: float
    avg_happiness: float
    avg_health: float
    avg_morale: float
    total_net_worth: float
    gini_coefficient: float
    top10_wealth_share: float
    bottom50_wealth_share: float
    gov_cash_balance: float
    gov_profit: float
    total_firms: int
    struggling_firms: int
    avg_food_price: Optional[float] = None
    avg_housing_price: Optional[float] = None
    avg_services_price: Optional[float] = None
```

### PolicyConfig
```python
@dataclass
class PolicyConfig:
    run_id: str
    wage_tax: float
    profit_tax: float
    wealth_tax_rate: float
    wealth_tax_threshold: float
    universal_basic_income: float
    unemployment_benefit_rate: float
    minimum_wage: float
    inflation_rate: float
    birth_rate: float
    agent_stabilizers_enabled: bool = False
```

---

## Example Queries

### Get all completed runs
```python
runs = db.get_runs(status='completed', limit=10)
for run in runs:
    print(f"{run.run_id}: GDP={run.final_gdp}, Gini={run.final_gini}")
```

### Get time-series for specific metric
```python
metrics = db.get_tick_metrics('run_001', tick_start=0, tick_end=500, columns=['tick', 'gdp'])
gdp_history = [(m['tick'], m['gdp']) for m in metrics]
```

### Compare multiple runs
```python
for run_id in ['run_001', 'run_002', 'run_003']:
    summary = db.get_run_summary(run_id)
    policy = db.get_policy_config(run_id)
    print(f"{run_id}: UBI=${policy.universal_basic_income}, Avg GDP=${summary['avg_gdp']}")
```

### Custom SQL query
```python
results = db.execute_query("""
    SELECT r.run_id, r.final_gdp, p.universal_basic_income
    FROM simulation_runs r
    JOIN policy_config p ON r.run_id = p.run_id
    WHERE r.status = 'completed'
    AND p.universal_basic_income > 200
    ORDER BY r.final_gdp DESC
    LIMIT 10
""")
```

---

## Performance Notes

### Batch Inserts
Always batch insert tick metrics for optimal performance:

```python
# Good (batch of 50-100)
metrics_batch = []
for tick in range(500):
    metrics_batch.append(TickMetrics(...))
    if len(metrics_batch) >= 50:
        db.insert_tick_metrics(metrics_batch)
        metrics_batch.clear()

# Bad (one at a time - slow)
for tick in range(500):
    db.insert_tick_metrics([TickMetrics(...)])
```

### Indexes
The schema includes optimized indexes for:
- Time-series queries: `(run_id, tick)`
- Filtering by status: `status`
- Sorting by date: `created_at DESC`
- Policy comparisons: `universal_basic_income`, `minimum_wage`

### Query Optimization
Use column filtering for large datasets:
```python
# Only fetch needed columns
metrics = db.get_tick_metrics(
    'run_001',
    columns=['tick', 'gdp', 'unemployment_rate']
)
```

---

## File Structure

```
backend/data/
├── schema.sql                # Database schema
├── postgres_schema.sql       # PostgreSQL + Timescale schema
├── db_manager.py            # DatabaseManager class + data models
├── postgres_manager.py      # PostgreSQL/Timescale manager
├── warehouse_factory.py     # Backend selector (sqlite/postgres)
├── ecosim.db                # SQLite database file
├── README.md                # This file
├── test_sample_data.py      # Sample data generator
├── migrations/
│   ├── __init__.py
│   └── 001_create_warehouse.py  # Migration script
│   └── 002_create_timescale_warehouse.py  # PostgreSQL/Timescale migration
└── tests/
    └── test_db_manager.py   # Unit tests (9 tests)
```

---

## Testing

### Unit Tests (9 tests)
```bash
python backend/data/tests/test_db_manager.py
```

Tests cover:
- ✅ Creating runs
- ✅ Updating run status
- ✅ Filtering runs by status
- ✅ Batch inserting tick metrics
- ✅ Querying tick ranges
- ✅ Getting run summaries
- ✅ Policy configuration
- ✅ Database statistics
- ✅ Custom queries

### Sample Data Test
```bash
python backend/data/test_sample_data.py
```

Generates a complete simulation run with:
- 500 ticks of realistic economic data
- Policy configuration
- Summary statistics
- Demonstrates full data warehouse functionality

---

## Next Steps (Phase 2)

Phase 1 is complete! Next up:

1. **Phase 2: Real-time Data Ingestion**
   - StreamCapture middleware
   - Integration with server.py WebSocket
   - Automatic data capture during simulations

2. **Phase 3: Analytics API**
   - REST API for querying data
   - Comparison endpoints
   - Export functionality

See [DATA_ENG_IMPLEMENTATION_ROADMAP.md](../../docs/DATA_ENG_IMPLEMENTATION_ROADMAP.md) for details.

---

## Support

- Database file: `backend/data/ecosim.db`
- Schema: `backend/data/schema.sql`
- Tests: `backend/data/tests/`
- Migration: `backend/data/migrations/001_create_warehouse.py`

For issues, check:
1. Database initialized? Run migration script
2. Tests passing? Run `test_db_manager.py`
3. Sample data works? Run `test_sample_data.py`

---

**Phase 1 Status**: ✅ COMPLETE
**Last Updated**: 2025-12-27
