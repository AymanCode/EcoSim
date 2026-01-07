# EcoSim - Data Engineering Implementation Plan

## Executive Summary

Transform EcoSim from a real-time simulation tool into a comprehensive data analytics platform by building robust data pipelines, historical storage, and analytical query layers on top of the existing simulation infrastructure.

---

## Current State Analysis

### What We Have
✅ **Real-time simulation** generating rich economic data every tick
✅ **WebSocket streaming** delivering metrics to frontend (~50ms intervals)
✅ **500 training samples** with 20 features (policy inputs + economic outcomes)
✅ **SQLite database** with basic KPI storage (underutilized)
✅ **React dashboard** with 9 live charts and tracked subjects/firms
✅ **CSV export capability** for training data

### What's Missing
❌ **Historical data warehouse** - No long-term storage of simulation runs
❌ **Query/analytics layer** - No way to analyze past simulations
❌ **Data aggregation pipelines** - Metrics computed on-the-fly, not stored
❌ **Comparative analytics** - Can't compare policy scenarios
❌ **Data quality monitoring** - No validation or integrity checks
❌ **Batch processing** - No scheduled data jobs or ETL

---

## Data Engineering Goals

### Primary Objectives
1. **Build a Data Warehouse** - Store all simulation runs with full historical context
2. **Create Analytics APIs** - Enable complex queries over historical data
3. **Implement ETL Pipelines** - Transform raw simulation data into analytical datasets
4. **Enable Comparative Analysis** - Compare multiple policy scenarios side-by-side
5. **Add Data Quality Layer** - Validate, monitor, and ensure data integrity

### Success Metrics
- Store 100+ complete simulation runs with full tick-by-tick history
- Query response time <500ms for analytical queries
- Support 10+ simultaneous policy scenario comparisons
- 99.9% data pipeline uptime
- Zero data loss during simulation runs

---

## Proposed Architecture

### Data Flow (Enhanced)

```
┌─────────────────────────────────────────────────────────────────┐
│ SIMULATION LAYER (Existing)                                     │
│ • Economy.step() generates tick data                            │
│ • WebSocket streams to frontend                                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATA INGESTION LAYER (NEW)                                      │
│ • StreamCapture: Intercept WebSocket data                       │
│ • TickBuffer: Batch tick data for efficient writes              │
│ • DataValidator: Check data quality & completeness              │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATA WAREHOUSE (ENHANCED)                                       │
│                                                                  │
│ SQLite Database (Upgraded Schema):                              │
│ ├─ simulation_runs: Run metadata (id, start_time, config)      │
│ ├─ tick_metrics: Per-tick aggregated metrics                    │
│ ├─ household_snapshots: 50-tick household state                 │
│ ├─ firm_snapshots: 50-tick firm state                          │
│ ├─ market_history: Price/supply by category & tick             │
│ ├─ policy_changes: Log of mid-simulation policy updates        │
│ └─ simulation_events: Important economic events                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETL & AGGREGATION LAYER (NEW)                                   │
│ • Rollup jobs: Compute hourly/daily summaries                   │
│ • Feature engineering: Derive analytical metrics                │
│ • Policy impact analysis: Compare baseline vs scenarios        │
│ • Statistical computations: Trends, correlations, distributions │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ ANALYTICS API LAYER (NEW)                                       │
│                                                                  │
│ REST Endpoints:                                                  │
│ • GET /api/simulations - List all runs with metadata           │
│ • GET /api/simulations/{id} - Full run details                 │
│ • GET /api/compare?runs=id1,id2 - Compare scenarios            │
│ • GET /api/query - Flexible analytical queries                 │
│ • GET /api/insights/{metric} - Trend analysis & insights       │
│ • POST /api/export - Generate CSV/JSON exports                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│ VISUALIZATION & REPORTING (ENHANCED)                            │
│ • Historical dashboard: View past simulation runs               │
│ • Scenario comparator: Side-by-side policy analysis            │
│ • Data explorer: Interactive query builder                      │
│ • Export tools: CSV, JSON, Parquet downloads                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Data Warehouse Foundation (Week 1)
**Goal**: Enhance SQLite schema to capture full simulation history

**Tasks**:
1. **Design enhanced database schema**
   - `simulation_runs` table (run_id, config, start_time, end_time, status)
   - `tick_metrics` table (run_id, tick, gdp, unemployment, wages, etc.)
   - `household_snapshots` table (run_id, tick, household_id, cash, wage, health, etc.)
   - `firm_snapshots` table (run_id, tick, firm_id, category, cash, employees, etc.)
   - `market_history` table (run_id, tick, category, price, supply)
   - Add proper indexes for query performance

2. **Create migration script**
   - `backend/data/migrations/001_warehouse_schema.sql`
   - Safe migration from existing `kpis` table

3. **Implement data models**
   - `backend/data/models.py` - SQLAlchemy/Pydantic models for each table
   - Type validation and constraints

**Deliverables**:
- Enhanced database schema
- Migration scripts
- Data model definitions
- Documentation of schema design

---

### Phase 2: Data Ingestion Pipeline (Week 2)
**Goal**: Capture and persist all simulation data in real-time

**Tasks**:
1. **Build StreamCapture middleware**
   - `backend/data/stream_capture.py`
   - Intercept WebSocket messages before sending to frontend
   - Buffer data in memory (batches of 50-100 ticks)
   - Async writes to database (non-blocking)

2. **Implement TickBuffer**
   - `backend/data/tick_buffer.py`
   - Efficient batching for bulk inserts
   - Handle backpressure if DB writes slow
   - Graceful degradation (log warnings, don't crash simulation)

3. **Add DataValidator**
   - `backend/data/validator.py`
   - Check for missing/null values
   - Validate numeric ranges (e.g., unemployment 0-100%)
   - Log data quality issues

4. **Update server.py**
   - Integrate StreamCapture into WebSocket handler
   - Add run_id generation for each simulation
   - Store run metadata (config, timestamp)
   - Handle START/STOP/RESET events

**Deliverables**:
- Stream capture middleware
- Buffering and batch insert logic
- Data validation layer
- Integration with existing server

---

### Phase 3: Analytics API (Week 3)
**Goal**: Provide flexible query interface for historical data

**Tasks**:
1. **Design REST API**
   - `backend/data/analytics_api.py`
   - Flask-RESTful or FastAPI implementation
   - Authentication (optional: API keys)
   - Rate limiting for heavy queries

2. **Implement core endpoints**
   ```python
   GET /api/simulations
   # Returns: List of all simulation runs with metadata
   # Filters: ?start_date=, ?end_date=, ?policy=

   GET /api/simulations/{run_id}
   # Returns: Complete run details with all metrics

   GET /api/simulations/{run_id}/metrics?tick_start=&tick_end=
   # Returns: Time-series data for specific tick range

   POST /api/compare
   # Body: {"run_ids": ["id1", "id2"], "metrics": ["gdp", "unemployment"]}
   # Returns: Side-by-side comparison data

   GET /api/query
   # Body: SQL-like query DSL or filter params
   # Returns: Custom analytical results
   ```

3. **Add aggregation functions**
   - Time-window aggregations (avg GDP over ticks 100-500)
   - Policy impact calculations (difference from baseline)
   - Statistical summaries (mean, median, std dev, percentiles)

4. **Implement caching**
   - Redis or in-memory cache for frequent queries
   - Cache invalidation strategy
   - Pre-compute common aggregations

**Deliverables**:
- REST API server
- Core analytical endpoints
- Query optimization
- API documentation (Swagger/OpenAPI)

---

### Phase 4: ETL & Feature Engineering (Week 4)
**Goal**: Transform raw simulation data into analytical insights

**Tasks**:
1. **Build rollup pipelines**
   - `backend/data/etl/rollups.py`
   - Hourly rollups: Compute summaries every 100 ticks
   - Run summaries: Final statistics per simulation
   - Scheduled jobs (cron or APScheduler)

2. **Feature engineering**
   - `backend/data/etl/features.py`
   - Derive new metrics:
     - GDP growth rate (% change tick-to-tick)
     - Unemployment volatility (std dev over window)
     - Wage equality index (median/mean ratio)
     - Firm churn rate (firms created/destroyed)
     - Policy stability score (frequency of changes)
   - Store engineered features in `derived_metrics` table

3. **Policy impact analysis**
   - `backend/data/etl/policy_analyzer.py`
   - Compare runs with similar initial conditions but different policies
   - Calculate policy impact scores (delta from baseline)
   - Identify policy effectiveness patterns

4. **Data quality monitoring**
   - `backend/data/etl/quality_monitor.py`
   - Track completeness (missing ticks, null values)
   - Anomaly detection (sudden GDP spikes, negative values)
   - Data quality dashboard

**Deliverables**:
- ETL pipeline scripts
- Feature engineering functions
- Policy analysis tools
- Data quality monitors

---

### Phase 5: Enhanced Visualizations (Week 5)
**Goal**: Frontend components to explore historical data

**Tasks**:
1. **Historical runs browser**
   - New React component: `HistoricalDashboard.jsx`
   - List all past simulation runs with filters
   - Quick stats preview (final GDP, avg unemployment, etc.)
   - Click to load full run details

2. **Scenario comparison view**
   - `ScenarioComparator.jsx`
   - Side-by-side charts for 2-5 runs
   - Highlight differences in outcomes
   - Policy diff viewer (what changed between runs)

3. **Data explorer interface**
   - `DataExplorer.jsx`
   - Query builder UI (select metrics, time ranges, filters)
   - Interactive charts with zoom/pan
   - Export results to CSV

4. **Insights panel**
   - `InsightsPanel.jsx`
   - Auto-generated observations (e.g., "Raising UBI by $100 increased happiness by 8%")
   - Trend indicators (improving/worsening metrics)
   - Recommendations based on patterns

**Deliverables**:
- Historical dashboard UI
- Scenario comparison tool
- Data explorer interface
- Automated insights display

---

## Database Schema Details

### simulation_runs
```sql
CREATE TABLE simulation_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed', 'stopped')),
    total_ticks INTEGER,

    -- Initial configuration
    num_households INTEGER,
    num_firms INTEGER,

    -- Policy configuration (JSON for flexibility)
    policy_config TEXT, -- JSON: {wageTax, profitTax, inflationRate, ...}

    -- Metadata
    description TEXT,
    tags TEXT, -- Comma-separated tags for categorization

    -- Final outcomes (computed at end)
    final_gdp REAL,
    final_unemployment REAL,
    final_gini REAL,
    avg_happiness REAL
);

CREATE INDEX idx_runs_created ON simulation_runs(created_at DESC);
CREATE INDEX idx_runs_status ON simulation_runs(status);
```

### tick_metrics
```sql
CREATE TABLE tick_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,

    -- Economic metrics
    gdp REAL,
    unemployment_rate REAL,
    mean_wage REAL,
    median_wage REAL,
    total_net_worth REAL,

    -- Government
    gov_cash_balance REAL,
    gov_profit REAL,

    -- Wellbeing
    mean_happiness REAL,
    mean_health REAL,
    mean_morale REAL,

    -- Inequality
    gini_coefficient REAL,
    top10_wealth_share REAL,
    bottom50_wealth_share REAL,

    -- Market
    total_firms INTEGER,
    struggling_firms INTEGER,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id),
    UNIQUE(run_id, tick)
);

CREATE INDEX idx_metrics_run_tick ON tick_metrics(run_id, tick);
CREATE INDEX idx_metrics_tick ON tick_metrics(tick);
```

### household_snapshots
```sql
CREATE TABLE household_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    household_id INTEGER NOT NULL,

    -- Financials
    cash_balance REAL,
    net_worth REAL,
    wage REAL,
    medical_debt REAL,

    -- Employment
    is_employed BOOLEAN,
    employer_id INTEGER,

    -- Attributes
    age INTEGER,
    skills_level REAL,
    happiness REAL,
    health REAL,
    morale REAL,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

CREATE INDEX idx_hh_snapshots ON household_snapshots(run_id, tick, household_id);
```

### firm_snapshots
```sql
CREATE TABLE firm_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    firm_id INTEGER NOT NULL,

    -- Basics
    name TEXT,
    category TEXT CHECK(category IN ('Food', 'Housing', 'Services')),

    -- Financials
    cash_balance REAL,
    revenue REAL,
    profit REAL,

    -- Operations
    employee_count INTEGER,
    wage_offer REAL,
    price REAL,
    inventory REAL,
    quality_level REAL,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

CREATE INDEX idx_firm_snapshots ON firm_snapshots(run_id, tick, firm_id);
CREATE INDEX idx_firm_category ON firm_snapshots(category);
```

### market_history
```sql
CREATE TABLE market_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    category TEXT CHECK(category IN ('Food', 'Housing', 'Services')),

    avg_price REAL,
    total_supply REAL,
    firm_count INTEGER,
    total_employees INTEGER,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id),
    UNIQUE(run_id, tick, category)
);

CREATE INDEX idx_market_hist ON market_history(run_id, tick, category);
```

### policy_changes
```sql
CREATE TABLE policy_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tick INTEGER NOT NULL,

    policy_name TEXT,
    old_value REAL,
    new_value REAL,

    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

CREATE INDEX idx_policy_changes ON policy_changes(run_id, tick);
```

---

## Key Data Engineering Patterns

### 1. Batch Inserts for Performance
```python
# Instead of insert per tick (slow):
for tick_data in stream:
    db.execute("INSERT INTO tick_metrics ...")

# Use batching (fast):
buffer = []
for tick_data in stream:
    buffer.append(tick_data)
    if len(buffer) >= 100:
        db.executemany("INSERT INTO tick_metrics ...", buffer)
        buffer.clear()
```

### 2. Async Writing (Non-blocking)
```python
import asyncio
from queue import Queue

write_queue = Queue()

async def db_writer():
    while True:
        batch = []
        while not write_queue.empty() and len(batch) < 100:
            batch.append(write_queue.get())
        if batch:
            await async_db_write(batch)
        await asyncio.sleep(0.1)

# In WebSocket handler:
write_queue.put(tick_data)  # Non-blocking
```

### 3. Materialized Views for Fast Queries
```sql
-- Pre-compute common aggregations
CREATE TABLE run_summaries AS
SELECT
    run_id,
    AVG(gdp) as avg_gdp,
    AVG(unemployment_rate) as avg_unemployment,
    MAX(gini_coefficient) as peak_inequality,
    COUNT(*) as total_ticks
FROM tick_metrics
GROUP BY run_id;
```

### 4. Partitioning by Time
```python
# For very large datasets, partition by date
# Create separate tables: tick_metrics_2025_01, tick_metrics_2025_02, etc.
# Use view unions for querying across partitions
```

---

## Analytical Use Cases Enabled

### 1. Policy Impact Analysis
**Question**: "What happens to unemployment when we increase UBI from $0 to $500?"

**Query**:
```python
GET /api/compare
{
  "baseline_run": "run_001",
  "comparison_runs": ["run_045", "run_102", "run_233"],
  "metric": "unemployment_rate",
  "aggregate": "mean"
}
```

**Response**:
```json
{
  "baseline": {"avg_unemployment": 8.5},
  "comparisons": [
    {"run_id": "run_045", "ubi": 100, "avg_unemployment": 7.2, "delta": -1.3},
    {"run_id": "run_102", "ubi": 250, "avg_unemployment": 5.8, "delta": -2.7},
    {"run_id": "run_233", "ubi": 500, "avg_unemployment": 4.1, "delta": -4.4}
  ]
}
```

### 2. Time-Series Trend Analysis
**Question**: "Show me GDP growth trajectory for the last 10 runs"

**Query**:
```python
GET /api/query
{
  "select": ["run_id", "tick", "gdp"],
  "from": "tick_metrics",
  "where": {"run_id": {"$in": last_10_run_ids}},
  "order_by": "tick"
}
```

### 3. Cohort Analysis
**Question**: "How do high-wage policies perform vs low-wage policies?"

**Approach**:
- Tag runs with "high_minimum_wage" or "low_minimum_wage"
- Aggregate metrics by cohort
- Compare distributions (boxplots, violin plots)

### 4. Anomaly Detection
**Question**: "Which simulation runs had unusual economic collapses?"

**Query**:
```sql
SELECT run_id, MIN(gdp) as lowest_gdp
FROM tick_metrics
GROUP BY run_id
HAVING MIN(gdp) < 1000  -- Threshold for "collapse"
ORDER BY lowest_gdp;
```

### 5. Correlation Analysis
**Question**: "Is there a correlation between wealth inequality (Gini) and GDP growth?"

**Approach**:
- Extract (gini, gdp_growth_rate) pairs from all runs
- Compute Pearson correlation coefficient
- Visualize scatter plot with regression line

---

## Data Quality & Monitoring

### Quality Checks
1. **Completeness**: Every tick should have a row in `tick_metrics`
2. **Range validation**: Unemployment 0-100%, GDP > 0, etc.
3. **Consistency**: Sum of household wealth ≈ total net worth
4. **Referential integrity**: All firm/household IDs in snapshots exist

### Monitoring Dashboard
Track:
- Total simulation runs stored
- Total ticks captured
- Database size (MB)
- Query response times (p50, p95, p99)
- Data quality score (% of checks passing)
- Write throughput (ticks/second)

### Alerts
- Data quality score drops below 95%
- Database size exceeds threshold
- Query latency > 1 second
- Write queue backlog > 1000 items

---

## Technology Stack

### Storage
- **Primary**: SQLite (simple, embedded, no setup)
- **Alternative**: PostgreSQL (if scale beyond 10GB)
- **Future**: Parquet files for archival (cold storage)

### APIs
- **Framework**: Flask (existing) or FastAPI (faster, better typing)
- **Caching**: Redis (optional, for heavy queries)

### ETL
- **Scheduler**: APScheduler (Python, simple)
- **Alternative**: Airflow (overkill for now, future consideration)

### Frontend
- **Existing**: React
- **Charts**: Recharts (already in use)
- **New**: React Query for API data fetching

---

## Estimated Effort

| Phase | Tasks | Estimated Hours | Priority |
|-------|-------|-----------------|----------|
| Phase 1: Database Schema | 8 tasks | 12-16 hours | HIGH |
| Phase 2: Ingestion Pipeline | 7 tasks | 16-20 hours | HIGH |
| Phase 3: Analytics API | 6 tasks | 12-16 hours | MEDIUM |
| Phase 4: ETL & Features | 8 tasks | 16-20 hours | MEDIUM |
| Phase 5: Visualizations | 8 tasks | 20-24 hours | LOW |
| **TOTAL** | **37 tasks** | **76-96 hours** | |

**Timeline**: 5 weeks (assuming 16-20 hours/week)

---

## Success Criteria

✅ **Phase 1**: Database stores 100+ simulation runs with full tick history
✅ **Phase 2**: Zero data loss during simulation (100% capture rate)
✅ **Phase 3**: API responds in <500ms for 95% of queries
✅ **Phase 4**: Automated insights generated for every run
✅ **Phase 5**: Users can compare 3+ scenarios side-by-side in UI

---

## Next Steps

1. **Review this plan** - Confirm approach aligns with goals
2. **Prioritize phases** - Which phases to implement first?
3. **Resource allocation** - Who works on what?
4. **Proof of concept** - Implement Phase 1 (database) as POC
5. **Iterate** - Gather feedback, adjust plan

---

## Open Questions

1. **Scale target**: How many simulation runs do we expect? (100? 1000? 10,000?)
2. **Retention policy**: Keep all data forever, or archive/delete old runs?
3. **Multi-user**: Will multiple users run simulations concurrently?
4. **Real-time vs batch**: Priority on real-time ingestion or batch analysis?
5. **Export formats**: CSV only, or also JSON/Parquet/Excel?
6. **Authentication**: Public API or require auth for analytics endpoints?

---

**Document Version**: 1.0
**Last Updated**: 2025-12-27
**Author**: Data Engineering Team
