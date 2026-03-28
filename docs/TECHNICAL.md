# EcoSim Technical Reference

Tech stack, database schemas, configuration system, data pipelines, testing, and performance.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.10+ | Simulation engine |
| **Server** | FastAPI + Uvicorn | WebSocket server (port 8002) |
| **Frontend** | React + Vite | Dashboard UI (port 5173) |
| **Charts** | Recharts | Real-time line/area/bar charts |
| **Styling** | Tailwind CSS | UI framework |
| **Icons** | Lucide React | Icon library |
| **Numerics** | NumPy | Vectorized computation in hot paths |
| **Data** | Pandas, SciPy | Training data generation, Latin Hypercube Sampling |
| **Database** | SQLite | Data warehouse for simulation runs |
| **Communication** | WebSocket | Real-time bidirectional streaming |

### Python Dependencies

```bash
pip install numpy pandas scipy fastapi uvicorn
```

### Frontend Dependencies

```bash
cd frontend-react
npm install
```

---

## Configuration System

All 400+ simulation parameters live in `backend/config.py` as a hierarchical config object.

### Structure

```
SimulationConfig (CONFIG)
├── time              # warmup_ticks, ticks_per_year
├── households        # 90+ params: elasticity, health thresholds, skill rates
├── firms             # 80+ params: PID pricing, production, personality
├── government        # 40+ params: tax bounds, investment budgets
├── labor_market      # 15+ params: matching friction, wage floors
└── market            # 15+ params: clearing mechanics
```

### Usage

```python
from config import CONFIG

# Read parameters
warmup = CONFIG.time.warmup_ticks          # 52
elasticity = CONFIG.households.food_elasticity  # 0.5

# Modify at runtime
CONFIG.firms.target_inventory_weeks = 4.0
CONFIG.households.food_elasticity = 0.8
```

### Key Configuration Groups

**Household health/consumption:**
- `food_health_high_threshold`: 5.0 — food units for good health
- `food_health_mid_threshold`: 2.0 — food units for moderate health
- `food_starvation_penalty`: 0.05 — health loss per tick without food
- `health_recovery_per_medical_unit`: 0.02

**Firm production:**
- `diminishing_returns_exponent`: 0.82 — Cobb-Douglas alpha
- `pid_control_scaling`: 0.05 — pricing controller gain
- `target_inventory_weeks`: 2.0

**Government:**
- `infrastructure_investment_budget`: 1000.0
- `technology_investment_budget`: 500.0
- `social_investment_budget`: 750.0

---

## Database Schema

### Data Warehouse (SQLite)

Location: `backend/data/ecosim.db`

Initialize with:
```bash
python backend/data/migrations/001_create_warehouse.py
```

#### simulation_runs
```sql
CREATE TABLE simulation_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'stopped')),
    num_households INTEGER,
    num_firms INTEGER,
    total_ticks INTEGER,
    final_gdp REAL,
    final_unemployment REAL,
    final_gini REAL,
    final_avg_happiness REAL,
    final_avg_health REAL,
    final_gov_balance REAL,
    description TEXT,
    tags TEXT
);
```

#### tick_metrics
```sql
CREATE TABLE tick_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES simulation_runs(run_id),
    tick INTEGER NOT NULL,
    gdp REAL,
    unemployment_rate REAL,
    mean_wage REAL,
    median_wage REAL,
    avg_happiness REAL,
    avg_health REAL,
    avg_morale REAL,
    total_net_worth REAL,
    gini_coefficient REAL,
    top10_wealth_share REAL,
    bottom50_wealth_share REAL,
    gov_cash_balance REAL,
    gov_profit REAL,
    total_firms INTEGER,
    struggling_firms INTEGER,
    avg_food_price REAL,
    avg_housing_price REAL,
    avg_services_price REAL,
    UNIQUE(run_id, tick)
);
```

#### policy_config
```sql
CREATE TABLE policy_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE REFERENCES simulation_runs(run_id),
    wage_tax REAL,
    profit_tax REAL,
    wealth_tax_rate REAL,
    wealth_tax_threshold REAL,
    universal_basic_income REAL,
    unemployment_benefit_rate REAL,
    minimum_wage REAL,
    inflation_rate REAL,
    birth_rate REAL,
    agent_stabilizers_enabled BOOLEAN
);
```

### DatabaseManager API

```python
from data.db_manager import DatabaseManager, SimulationRun, TickMetrics, PolicyConfig

db = DatabaseManager()

# Create run
db.create_run(SimulationRun(run_id='run_001', num_households=1000, num_firms=30))

# Batch insert metrics (50-100 at a time for performance)
db.insert_tick_metrics([TickMetrics(...) for tick in range(500)])

# Query
summary = db.get_run_summary('run_001')  # avg_gdp, avg_unemployment, etc.
metrics = db.get_tick_metrics('run_001', tick_start=0, tick_end=500, columns=['tick', 'gdp'])
```

### Example Queries

```sql
-- Unemployment rate over time
SELECT tick,
       100.0 * SUM(CASE WHEN is_employed = 0 THEN 1 ELSE 0 END) / COUNT(*) AS unemployment_pct
FROM households
GROUP BY tick ORDER BY tick;

-- Firm performance by personality
SELECT personality, COUNT(*) AS num_firms,
       AVG(cash_balance) AS avg_cash, AVG(employee_count) AS avg_employees
FROM firms WHERE tick = 1000
GROUP BY personality;

-- Government investment trajectory
SELECT tick, infrastructure_productivity_multiplier,
       technology_quality_multiplier, social_happiness_multiplier
FROM government ORDER BY tick;

-- Wealth inequality (top 10% vs bottom 50%)
WITH ranked AS (
    SELECT tick, cash_balance,
           NTILE(10) OVER (PARTITION BY tick ORDER BY cash_balance) AS decile
    FROM households
)
SELECT tick,
       AVG(CASE WHEN decile = 10 THEN cash_balance END) AS top_10_avg,
       AVG(CASE WHEN decile <= 5 THEN cash_balance END) AS bottom_50_avg
FROM ranked GROUP BY tick;
```

### Storage Estimates

| Scale | Households | Firms | Ticks | Storage | Recommended DB |
|-------|-----------|-------|-------|---------|---------------|
| Small | 1,000 | 100 | 1,000 | ~50 MB | SQLite |
| Medium | 10,000 | 1,000 | 1,000 | ~500 MB | PostgreSQL |
| Large | 100,000 | 10,000 | 10,000 | ~50 GB | TimescaleDB |

---

## Running Simulations

### Interactive (Dashboard)

```bash
# Terminal 1: Backend
python -m uvicorn backend.server:app --reload --port 8002

# Terminal 2: Frontend
cd frontend-react && npm run dev
```

Open `http://localhost:5173`, configure parameters, click "INITIALIZE PROTOCOL".

### Headless (Large-Scale)

```bash
cd backend
python run_large_simulation.py
```

Default: 10,000 households, 33 firms, 500 ticks. Output: `sample_data/ecosim_10k_balanced.db`.

### Diagnostic

```bash
cd backend
python run_diagnostic.py
```

Runs 250 ticks and reports health, employment, GDP, and identifies economic issues.

---

## ML Training Data

Generate policy-outcome datasets for machine learning:

```bash
cd backend
python generate_training_data.py
```

**Configuration (in script):**
- `NUM_SAMPLES`: 500 policy configurations (Latin Hypercube Sampling)
- `NUM_TICKS`: 300 ticks per run
- `NUM_HOUSEHOLDS`: 1000

**Output**: `training_data_YYYYMMDD_HHMMSS.csv` with 20 columns:
- 9 policy inputs (wage tax, profit tax, UBI, minimum wage, etc.)
- 11 economic outcomes (GDP, unemployment, happiness, Gini, etc.)

**Runtime**: ~2 hours for 500 samples at standard settings.

Checkpoints saved every 50 samples. See `backend/RUN_TRAINING.md` for troubleshooting.

---

## Testing

### Test Suite

| Test File | Type | What It Tests |
|-----------|------|---------------|
| `test_household_agent.py` | Unit (8 tests) | Creation, labor supply, consumption, wellbeing, skill growth |
| `test_firm_behavior.py` | Integration (52 ticks) | Production, hiring, pricing, cash flow over time |
| `test_government_behavior.py` | Integration (52 ticks) | Tax collection, benefits, policy adjustment |
| `test_skill_experience_system.py` | Unit | Skill wages, experience accumulation, productivity |
| `test_dynamic_economy.py` | Integration | Consumption, bankruptcy, firm creation, policy adaptation |

```bash
cd backend
python test_household_agent.py
python test_firm_behavior.py
python test_government_behavior.py
```

### Data Warehouse Tests

```bash
python backend/data/tests/test_db_manager.py    # 9 unit tests
python backend/data/test_sample_data.py          # End-to-end sample data
```

---

## Performance

### Benchmarks

- 10,000 agents, 500 ticks: ~3-5 minutes (~300-400ms/tick)
- Profiling tool: `cProfile` or `py-spy`

### Known Hotspots

| Area | Issue | Mitigation |
|------|-------|-----------|
| Goods market clearing | Nested loops over households × firms | Precompute firm arrays, skip empty inventory |
| Labor matching | Dict-heavy matching per household | Cached lookups, batch processing |
| Production calculation | `next(...)` household lookup per employee | Use `household_lookup.get()` dict |
| Metrics computation | Full list sorts for percentiles each tick | Compute every N ticks for UI |
| Server payload | Large WS payloads every tick | Ring buffer for histories, cap payload size |

### Optimization Priorities

1. **Low effort**: Replace `next(...)` lookups, ring buffer histories, metrics every N ticks
2. **Medium effort**: Vectorize labor/goods matching, consolidate metrics computation
3. **High effort**: Data-oriented refactor (NumPy arrays for agent state), vectorized market clearing

---

## File Structure

```
EcoSim/
├── backend/
│   ├── agents.py              # Agent classes (~2900 lines)
│   ├── economy.py             # Tick coordinator (~2500 lines)
│   ├── config.py              # 400+ tunable parameters
│   ├── server.py              # FastAPI WebSocket server
│   ├── run_large_simulation.py # Headless large-scale runner
│   ├── run_diagnostic.py      # 250-tick diagnostic
│   ├── generate_training_data.py # ML dataset generation
│   ├── generate_sample_data.py   # Sample DB generation
│   └── data/
│       ├── schema.sql         # Database schema
│       ├── db_manager.py      # DatabaseManager + data models
│       ├── ecosim.db          # SQLite database
│       └── migrations/        # Schema migrations
├── frontend-react/
│   ├── src/App.jsx            # Main dashboard (~1720 lines)
│   ├── src/NeuralAvatar.jsx   # Household visualization
│   ├── src/NeuralBuilding.jsx # Firm visualization
│   └── package.json           # React + Recharts + Tailwind
├── docs/
│   ├── SIMULATION.md          # This simulation guide
│   ├── TECHNICAL.md           # This technical reference
│   └── FRONTEND.md            # Frontend dashboard guide
└── CONFIG_USAGE_GUIDE.md      # Full config parameter reference
```
