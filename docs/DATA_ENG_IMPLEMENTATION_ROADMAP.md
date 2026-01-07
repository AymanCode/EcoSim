# EcoSim Data Engineering - Implementation Roadmap
**Priority: Phases 1-3 (Core Infrastructure)**

---

## Overview

**Goal**: Build a functional data warehouse with real-time ingestion and analytics API in ~40-50 hours

**Focus Areas**:
1. ✅ **Phase 1**: Data Warehouse Foundation (12-16 hours)
2. ✅ **Phase 2**: Real-time Data Ingestion (16-20 hours)
3. ✅ **Phase 3**: Analytics API (12-16 hours)
4. ⏸️ **Phase 4**: ETL & Features (STRETCH GOAL - if time permits)
5. ⏸️ **Phase 5**: Visualizations (STRETCH GOAL - if time permits)

---

## Phase 1: Data Warehouse Foundation
**Timeline**: Days 1-2 (12-16 hours)
**Priority**: CRITICAL

### Tasks Breakdown

#### 1.1 Database Schema Design (2-3 hours)
**Files to create**:
- `backend/data/schema.sql` - Complete database schema with tables and indexes
- `backend/data/README.md` - Schema documentation

**Schema Tables**:
```sql
-- Core tables (MUST HAVE)
✅ simulation_runs      -- Metadata for each simulation run
✅ tick_metrics         -- Per-tick economic aggregates
✅ household_snapshots  -- Household state at 50-tick intervals
✅ firm_snapshots       -- Firm state at 50-tick intervals
✅ market_history       -- Market prices/supply by category

-- Optional (NICE TO HAVE)
⏸️ policy_changes       -- Log of mid-sim policy updates (add if time)
⏸️ simulation_events    -- Economic event log (add if time)
```

**Deliverable**: Complete `schema.sql` file ready to execute

---

#### 1.2 Database Migration Script (2 hours)
**Files to create**:
- `backend/data/migrations/001_create_warehouse.py`
- `backend/data/migrations/__init__.py`

**Script should**:
- Check if tables exist (safe re-run)
- Create all tables with proper types and constraints
- Add indexes for query performance
- Migrate existing `kpis` data if present
- Print migration status

**Example**:
```python
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), '../ecosim.db')
    conn = sqlite3.connect(db_path)

    # Read schema.sql
    with open('backend/data/schema.sql') as f:
        schema = f.read()

    # Execute migrations
    conn.executescript(schema)
    print("✓ Database schema created")

    # Verify tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    print(f"✓ Created {len(tables)} tables: {tables}")

if __name__ == "__main__":
    migrate()
```

**Deliverable**: Runnable migration script that creates the warehouse

---

#### 1.3 Data Models & ORM (4-5 hours)
**Files to create**:
- `backend/data/models.py` - SQLAlchemy or dataclass models
- `backend/data/db_manager.py` - Database connection manager

**Models needed**:
```python
@dataclass
class SimulationRun:
    run_id: str
    created_at: datetime
    status: str  # 'running', 'completed', 'failed', 'stopped'
    num_households: int
    num_firms: int
    policy_config: dict  # Store as JSON
    final_gdp: Optional[float]
    final_unemployment: Optional[float]

@dataclass
class TickMetrics:
    run_id: str
    tick: int
    gdp: float
    unemployment_rate: float
    mean_wage: float
    median_wage: float
    # ... all metrics from WebSocket

@dataclass
class HouseholdSnapshot:
    run_id: str
    tick: int
    household_id: int
    cash_balance: float
    wage: float
    is_employed: bool
    happiness: float
    health: float
    # ... tracked subject data

# Similar for FirmSnapshot, MarketHistory
```

**DB Manager**:
```python
class DatabaseManager:
    def __init__(self, db_path='data/ecosim.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

    def insert_run(self, run: SimulationRun):
        """Insert new simulation run"""

    def insert_tick_metrics(self, metrics: List[TickMetrics]):
        """Batch insert tick metrics"""

    def update_run_status(self, run_id: str, status: str):
        """Update run status (completed, failed, etc.)"""

    def get_run(self, run_id: str) -> SimulationRun:
        """Fetch simulation run by ID"""
```

**Deliverable**: Models and DB manager ready for use

---

#### 1.4 Unit Tests (2-3 hours)
**Files to create**:
- `backend/data/tests/test_models.py`
- `backend/data/tests/test_db_manager.py`

**Test coverage**:
- ✅ Database connection
- ✅ Table creation (migration)
- ✅ Insert simulation run
- ✅ Batch insert tick metrics
- ✅ Query runs by status
- ✅ Update run status

**Deliverable**: 10+ passing tests for core DB operations

---

#### 1.5 Documentation (1-2 hours)
**Files to update**:
- `backend/data/README.md` - How to use the database layer

**Contents**:
- Schema overview
- How to run migrations
- Example queries
- Model usage examples

**Deliverable**: Complete README for Phase 1

---

### Phase 1 Success Criteria
✅ Database schema created with 5 core tables
✅ Migration script runs successfully
✅ Models defined for all tables
✅ DB manager can insert/query data
✅ 10+ unit tests passing
✅ Documentation complete

**Checkpoint**: Can manually insert a simulation run and query it back

---

## Phase 2: Real-time Data Ingestion
**Timeline**: Days 3-4 (16-20 hours)
**Priority**: CRITICAL

### Tasks Breakdown

#### 2.1 Stream Capture Middleware (4-5 hours)
**Files to create**:
- `backend/data/stream_capture.py`

**Functionality**:
```python
class StreamCapture:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.current_run_id = None
        self.tick_buffer = []

    def on_simulation_start(self, config: dict) -> str:
        """Create new run in DB, return run_id"""
        run_id = generate_run_id()  # e.g., "run_20251227_150959"
        run = SimulationRun(
            run_id=run_id,
            status='running',
            policy_config=config,
            ...
        )
        self.db.insert_run(run)
        self.current_run_id = run_id
        return run_id

    def on_tick_data(self, tick: int, metrics: dict):
        """Capture tick metrics for current run"""
        tick_metric = TickMetrics(
            run_id=self.current_run_id,
            tick=tick,
            gdp=metrics['gdp'],
            unemployment_rate=metrics['unemployment'],
            ...
        )
        self.tick_buffer.append(tick_metric)

        # Flush buffer every 50 ticks
        if len(self.tick_buffer) >= 50:
            self.flush_buffer()

    def flush_buffer(self):
        """Write buffered ticks to database"""
        if self.tick_buffer:
            self.db.insert_tick_metrics(self.tick_buffer)
            self.tick_buffer.clear()

    def on_simulation_end(self, final_metrics: dict):
        """Mark run as completed"""
        self.flush_buffer()  # Ensure all data written
        self.db.update_run_status(
            self.current_run_id,
            'completed',
            final_gdp=final_metrics.get('gdp'),
            final_unemployment=final_metrics.get('unemployment')
        )
```

**Deliverable**: StreamCapture class that intercepts and stores data

---

#### 2.2 Integrate with WebSocket Server (5-6 hours)
**Files to modify**:
- `backend/server.py` - Add StreamCapture to WebSocket handler

**Integration points**:
```python
# In server.py
from data.stream_capture import StreamCapture
from data.db_manager import DatabaseManager

class SimulationManager:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.stream_capture = StreamCapture(self.db_manager)
        # ... existing code

    async def handle_setup(self, websocket, message):
        # Existing setup logic...

        # NEW: Start capturing
        run_id = self.stream_capture.on_simulation_start(config)
        print(f"📊 Started data capture for run: {run_id}")

    async def handle_start(self, websocket, message):
        # Existing simulation loop...

        while self.running:
            # ... step simulation

            # NEW: Capture tick data
            metrics = self.get_current_metrics()
            self.stream_capture.on_tick_data(self.tick, metrics)

            # ... send to websocket

    async def handle_stop(self, websocket, message):
        # Existing stop logic...

        # NEW: End capture
        final_metrics = self.get_current_metrics()
        self.stream_capture.on_simulation_end(final_metrics)
        print(f"📊 Saved simulation run: {self.stream_capture.current_run_id}")
```

**Deliverable**: Server captures all simulation data to database

---

#### 2.3 Household & Firm Snapshot Capture (3-4 hours)
**Files to modify**:
- `backend/data/stream_capture.py` - Add snapshot methods

**Functionality**:
```python
class StreamCapture:
    # ... existing code

    def on_tick_data(self, tick: int, metrics: dict):
        """Capture tick metrics AND snapshots every 50 ticks"""
        # ... existing tick metrics code

        # Capture snapshots every 50 ticks
        if tick % 50 == 0:
            self.capture_household_snapshots(tick, metrics['trackedSubjects'])
            self.capture_firm_snapshots(tick, metrics['trackedFirms'])
            self.capture_market_history(tick, metrics['priceHistory'], metrics['supplyHistory'])

    def capture_household_snapshots(self, tick: int, subjects: list):
        """Store tracked household data"""
        snapshots = [
            HouseholdSnapshot(
                run_id=self.current_run_id,
                tick=tick,
                household_id=s['id'],
                cash_balance=s['cash'],
                wage=s['wage'],
                is_employed=s['state'] == 'employed',
                happiness=s['happiness'],
                health=s['health'],
                ...
            )
            for s in subjects
        ]
        self.db.insert_household_snapshots(snapshots)

    # Similar for firms and market
```

**Deliverable**: Snapshots captured every 50 ticks

---

#### 2.4 Data Validation Layer (2-3 hours)
**Files to create**:
- `backend/data/validator.py`

**Validation rules**:
```python
class DataValidator:
    @staticmethod
    def validate_tick_metrics(metrics: TickMetrics) -> List[str]:
        """Return list of validation errors"""
        errors = []

        # Range checks
        if metrics.unemployment_rate < 0 or metrics.unemployment_rate > 100:
            errors.append(f"Invalid unemployment: {metrics.unemployment_rate}")
        if metrics.gdp < 0:
            errors.append(f"Negative GDP: {metrics.gdp}")
        if metrics.gini_coefficient < 0 or metrics.gini_coefficient > 1:
            errors.append(f"Invalid Gini: {metrics.gini_coefficient}")

        # Null checks
        if metrics.mean_wage is None:
            errors.append("Missing mean_wage")

        return errors

    @staticmethod
    def validate_snapshot_completeness(run_id: str, db: DatabaseManager):
        """Check if all expected snapshots exist"""
        # For tracked subjects (12 households), should have 12 rows every 50 ticks
        # ... validation logic
```

**Integration**:
```python
# In StreamCapture.on_tick_data()
errors = DataValidator.validate_tick_metrics(tick_metric)
if errors:
    print(f"⚠️ Data quality issues at tick {tick}: {errors}")
```

**Deliverable**: Validation layer catching data quality issues

---

#### 2.5 Error Handling & Resilience (2-3 hours)
**Files to modify**:
- `backend/data/stream_capture.py`
- `backend/data/db_manager.py`

**Error scenarios**:
1. **DB write fails**: Log error, continue simulation (don't crash)
2. **Missing metrics**: Fill with NULL, log warning
3. **Run ID collision**: Generate new ID
4. **Buffer overflow**: Force flush before buffer gets too large

**Example**:
```python
def flush_buffer(self):
    """Write buffered ticks to database"""
    try:
        if self.tick_buffer:
            self.db.insert_tick_metrics(self.tick_buffer)
            self.tick_buffer.clear()
    except Exception as e:
        print(f"❌ Failed to write tick metrics: {e}")
        # Log to file for later recovery
        with open('failed_writes.log', 'a') as f:
            f.write(f"{datetime.now()}: {e}\n")
```

**Deliverable**: System continues running even if DB writes fail

---

#### 2.6 Testing & Verification (2-3 hours)
**Files to create**:
- `backend/data/tests/test_stream_capture.py`

**Test scenarios**:
- ✅ Start simulation → run created in DB
- ✅ Run 100 ticks → 100 tick_metrics rows inserted
- ✅ Every 50 ticks → snapshots captured
- ✅ Stop simulation → run marked 'completed'
- ✅ Validation catches bad data
- ✅ Buffer flushes correctly

**Manual test**:
```bash
# Start server with data capture
python backend/server.py

# Run frontend, start simulation, let it run 500 ticks, stop

# Check database
sqlite3 backend/data/ecosim.db
sqlite> SELECT COUNT(*) FROM tick_metrics;  -- Should be ~500
sqlite> SELECT COUNT(*) FROM household_snapshots;  -- Should be ~120 (12 subjects * 10 snapshots)
sqlite> SELECT * FROM simulation_runs;  -- Should show completed run
```

**Deliverable**: End-to-end test proving data is captured

---

### Phase 2 Success Criteria
✅ StreamCapture middleware functional
✅ Server integrated with data capture
✅ All tick metrics stored in DB
✅ Household/firm snapshots captured every 50 ticks
✅ Data validation running
✅ Error handling prevents crashes
✅ Tests verify data capture works

**Checkpoint**: Run simulation, verify data in database

---

## Phase 3: Analytics API
**Timeline**: Days 5-6 (12-16 hours)
**Priority**: HIGH

### Tasks Breakdown

#### 3.1 API Framework Setup (2 hours)
**Files to create**:
- `backend/data/analytics_api.py` - Main API server
- `backend/data/api_models.py` - Request/response schemas

**Framework choice**: Flask (already in use) or FastAPI (better for APIs)

**Basic structure**:
```python
from flask import Flask, jsonify, request
from data.db_manager import DatabaseManager

app = Flask(__name__)
db = DatabaseManager()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "version": "1.0"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)  # Different port from main server
```

**Deliverable**: API server running on port 5001

---

#### 3.2 Core Query Endpoints (4-5 hours)
**Files to modify**:
- `backend/data/analytics_api.py`

**Endpoints to implement**:

```python
@app.route('/api/simulations', methods=['GET'])
def list_simulations():
    """
    List all simulation runs with metadata
    Query params: ?status=completed&limit=10&offset=0
    """
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    runs = db.get_runs(status=status, limit=limit, offset=offset)
    return jsonify({
        "total": len(runs),
        "runs": [run.to_dict() for run in runs]
    })

@app.route('/api/simulations/<run_id>', methods=['GET'])
def get_simulation(run_id):
    """Get full details for a specific run"""
    run = db.get_run(run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404

    # Include basic stats
    stats = db.get_run_summary(run_id)

    return jsonify({
        "run": run.to_dict(),
        "stats": stats
    })

@app.route('/api/simulations/<run_id>/metrics', methods=['GET'])
def get_metrics(run_id):
    """
    Get time-series metrics for a run
    Query params: ?tick_start=0&tick_end=1000&metrics=gdp,unemployment
    """
    tick_start = int(request.args.get('tick_start', 0))
    tick_end = int(request.args.get('tick_end', 999999))
    metrics_param = request.args.get('metrics', 'all')

    metrics = db.get_tick_metrics(
        run_id,
        tick_start,
        tick_end,
        columns=metrics_param.split(',') if metrics_param != 'all' else None
    )

    return jsonify({
        "run_id": run_id,
        "tick_start": tick_start,
        "tick_end": tick_end,
        "data": metrics
    })

@app.route('/api/simulations/<run_id>/snapshots', methods=['GET'])
def get_snapshots(run_id):
    """Get household/firm snapshots"""
    snapshot_type = request.args.get('type', 'household')  # or 'firm'

    if snapshot_type == 'household':
        snapshots = db.get_household_snapshots(run_id)
    else:
        snapshots = db.get_firm_snapshots(run_id)

    return jsonify({
        "run_id": run_id,
        "type": snapshot_type,
        "snapshots": snapshots
    })
```

**Deliverable**: 4 core endpoints for querying data

---

#### 3.3 Comparison Endpoint (3-4 hours)
**Files to modify**:
- `backend/data/analytics_api.py`
- `backend/data/db_manager.py` - Add comparison queries

**Endpoint**:
```python
@app.route('/api/compare', methods=['POST'])
def compare_runs():
    """
    Compare multiple simulation runs

    Request body:
    {
        "run_ids": ["run_001", "run_002", "run_003"],
        "metrics": ["gdp", "unemployment_rate", "gini_coefficient"]
    }

    Response:
    {
        "comparison": [
            {
                "run_id": "run_001",
                "policy": {...},
                "avg_gdp": 52.3,
                "avg_unemployment": 8.5,
                "avg_gini": 0.42
            },
            ...
        ]
    }
    """
    data = request.json
    run_ids = data.get('run_ids', [])
    metrics = data.get('metrics', ['gdp', 'unemployment_rate'])

    comparison = []
    for run_id in run_ids:
        run = db.get_run(run_id)
        stats = db.get_run_summary(run_id, metrics=metrics)

        comparison.append({
            "run_id": run_id,
            "policy": run.policy_config,
            **stats  # avg_gdp, avg_unemployment, etc.
        })

    return jsonify({"comparison": comparison})
```

**DB Manager method**:
```python
def get_run_summary(self, run_id: str, metrics: list) -> dict:
    """Compute aggregate statistics for a run"""
    query = f"""
        SELECT
            AVG(gdp) as avg_gdp,
            AVG(unemployment_rate) as avg_unemployment,
            AVG(gini_coefficient) as avg_gini,
            MAX(gdp) as peak_gdp,
            MIN(unemployment_rate) as min_unemployment
        FROM tick_metrics
        WHERE run_id = ?
    """
    result = self.conn.execute(query, (run_id,)).fetchone()
    return dict(result)
```

**Deliverable**: Comparison endpoint for side-by-side analysis

---

#### 3.4 Query Builder Endpoint (2-3 hours)
**Files to modify**:
- `backend/data/analytics_api.py`

**Flexible query endpoint**:
```python
@app.route('/api/query', methods=['POST'])
def flexible_query():
    """
    Flexible query builder

    Request body:
    {
        "table": "tick_metrics",
        "select": ["tick", "gdp", "unemployment_rate"],
        "where": {
            "run_id": "run_001",
            "tick": {">=": 100, "<=": 500}
        },
        "order_by": "tick",
        "limit": 100
    }
    """
    data = request.json
    table = data.get('table', 'tick_metrics')
    select = data.get('select', ['*'])
    where = data.get('where', {})
    order_by = data.get('order_by')
    limit = data.get('limit', 1000)

    # Build SQL query safely (prevent injection)
    query = build_safe_query(table, select, where, order_by, limit)
    results = db.execute_query(query)

    return jsonify({"data": results})
```

**Deliverable**: Flexible query endpoint (with SQL injection protection)

---

#### 3.5 Export Endpoint (1-2 hours)
**Files to modify**:
- `backend/data/analytics_api.py`

**Export endpoint**:
```python
@app.route('/api/export', methods=['POST'])
def export_data():
    """
    Export data as CSV or JSON

    Request body:
    {
        "run_id": "run_001",
        "format": "csv",  // or "json"
        "tables": ["tick_metrics", "household_snapshots"]
    }
    """
    data = request.json
    run_id = data.get('run_id')
    format_type = data.get('format', 'csv')
    tables = data.get('tables', ['tick_metrics'])

    export_data = {}
    for table in tables:
        export_data[table] = db.get_table_data(run_id, table)

    if format_type == 'csv':
        # Generate CSV files (zip multiple tables)
        return send_csv_export(export_data, run_id)
    else:
        return jsonify(export_data)
```

**Deliverable**: Export endpoint for CSV/JSON downloads

---

#### 3.6 API Testing & Documentation (2-3 hours)
**Files to create**:
- `backend/data/tests/test_analytics_api.py`
- `backend/data/API_DOCS.md` - API documentation

**Test coverage**:
- ✅ GET /api/simulations - returns runs
- ✅ GET /api/simulations/{id} - returns run details
- ✅ GET /api/simulations/{id}/metrics - returns time series
- ✅ POST /api/compare - compares runs
- ✅ POST /api/query - flexible queries work
- ✅ POST /api/export - generates exports

**Documentation**:
```markdown
# Analytics API Documentation

## Base URL
`http://localhost:5001/api`

## Endpoints

### List Simulations
`GET /simulations`

Query Parameters:
- `status` (optional): Filter by status (running, completed, failed)
- `limit` (optional): Max results (default: 100)
- `offset` (optional): Pagination offset (default: 0)

Example:
```bash
curl http://localhost:5001/api/simulations?status=completed&limit=5
```

Response:
```json
{
  "total": 42,
  "runs": [
    {
      "run_id": "run_20251227_150959",
      "created_at": "2025-12-27T15:09:59",
      "status": "completed",
      "final_gdp": 52.3,
      ...
    }
  ]
}
```

... (document all endpoints)
```

**Deliverable**: Tested API with complete documentation

---

### Phase 3 Success Criteria
✅ Analytics API server running on port 5001
✅ 6+ endpoints implemented and tested
✅ Comparison endpoint works for multiple runs
✅ Export functionality generates CSV/JSON
✅ API documentation complete
✅ All tests passing

**Checkpoint**: Query historical runs via API, compare scenarios

---

## Testing Strategy

### Unit Tests
- `test_models.py` - Data model validation
- `test_db_manager.py` - Database operations
- `test_stream_capture.py` - Data ingestion
- `test_analytics_api.py` - API endpoints

### Integration Tests
1. **End-to-end simulation capture**:
   - Start server with data capture
   - Run 500-tick simulation via WebSocket
   - Stop simulation
   - Verify all data in database
   - Query via analytics API
   - Compare with baseline run

2. **Multi-run comparison**:
   - Generate 3 simulations with different policies
   - Use comparison endpoint
   - Verify policy impact calculations

### Performance Tests
- ✅ Batch insert 1000 tick metrics in < 1 second
- ✅ Query 500 ticks in < 100ms
- ✅ Compare 5 runs in < 500ms
- ✅ Export run as CSV in < 2 seconds

---

## Deployment Checklist

### Before Launch
- [ ] All unit tests pass
- [ ] Integration test passes end-to-end
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Error handling tested
- [ ] Database migrations run successfully

### Deployment Steps
1. Run database migration: `python backend/data/migrations/001_create_warehouse.py`
2. Start analytics API: `python backend/data/analytics_api.py` (port 5001)
3. Start main server: `python backend/server.py` (port 8002)
4. Verify health: `curl http://localhost:5001/api/health`
5. Run test simulation
6. Check data: `sqlite3 backend/data/ecosim.db`

---

## Success Metrics

### Phase 1 Success
- [ ] Can create and query simulation runs
- [ ] Database schema supports all data types
- [ ] Models serialize/deserialize correctly

### Phase 2 Success
- [ ] Zero data loss during simulation
- [ ] All 500 ticks captured for test run
- [ ] Snapshots saved every 50 ticks
- [ ] Validation catches anomalies

### Phase 3 Success
- [ ] Can query list of all runs
- [ ] Can retrieve full run details
- [ ] Can compare 3+ scenarios side-by-side
- [ ] Can export run data to CSV
- [ ] API responds in < 500ms

---

## Timeline Summary

| Phase | Days | Hours | Key Deliverables |
|-------|------|-------|------------------|
| Phase 1 | 1-2 | 12-16 | Database schema, models, migrations |
| Phase 2 | 3-4 | 16-20 | Real-time data capture, validation |
| Phase 3 | 5-6 | 12-16 | Analytics API, comparison, exports |
| **TOTAL** | **6 days** | **40-52 hours** | **Functional data warehouse + API** |

---

## Next Steps

1. **Review this roadmap** - Confirm tasks and priorities
2. **Set up dev environment** - Install dependencies, create folder structure
3. **Start Phase 1** - Begin with database schema
4. **Iterate** - Test each phase before moving to next

---

## Questions to Resolve

1. **SQLite vs PostgreSQL**: Stick with SQLite or upgrade?
2. **API Authentication**: Add API keys or leave open for now?
3. **Data retention**: How long to keep simulation runs? (all forever? 30 days? 100 runs?)
4. **Caching**: Add Redis for API caching or keep simple?
5. **Background jobs**: Need scheduled ETL or just on-demand?

---

**Document Version**: 1.0
**Created**: 2025-12-27
**Focus**: Phases 1-3 (Core Infrastructure)
