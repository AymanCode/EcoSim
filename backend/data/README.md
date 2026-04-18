# EcoSim Warehouse Backend

This directory contains the local warehouse implementation for EcoSim.

Current runtime backends:

- `sqlite`
- `postgres`
- `timescale`

Core files:

- `models.py`: typed warehouse row models shared by all backends
- `db_manager.py`: SQLite warehouse manager
- `postgres_manager.py`: PostgreSQL/Timescale warehouse manager
- `schema.sql`: SQLite schema
- `postgres_schema.sql`: PostgreSQL/Timescale schema
- `warehouse_factory.py`: backend selector
- `migrations/`: schema application scripts

## Migration Guide

The migration scripts are backend-specific and intentionally incremental.

1. `001_create_warehouse.py`
- creates the initial SQLite warehouse
- use this for a fresh local SQLite database

2. `002_create_timescale_warehouse.py`
- creates the initial PostgreSQL/Timescale warehouse
- use this for a fresh local Postgres/Timescale database

3. `003_expand_sqlite_aggregate_warehouse.py`
- upgrades an existing SQLite warehouse to the richer aggregate schema
- adds `simulation_runs.seed`
- expands `tick_metrics` with runtime and labor fields
- creates `sector_tick_metrics`

4. `004_expand_postgres_aggregate_warehouse.py`
- upgrades an existing Postgres/Timescale warehouse to the richer aggregate schema
- adds the same aggregate fields as SQLite
- creates `sector_tick_metrics` and converts it to a hypertable when Timescale is available

5. `005_add_sqlite_event_tables.py`
- upgrades an existing SQLite warehouse with append-only event tables
- adds `labor_events`, `healthcare_events`, and `policy_actions`

6. `006_add_postgres_event_tables.py`
- upgrades an existing Postgres/Timescale warehouse with the same event tables
- uses `JSONB` for policy action payloads

7. `007_add_sqlite_firm_snapshots.py`
- upgrades an existing SQLite warehouse with per-firm snapshot storage
- adds `firm_snapshots`
- adds indexes for `(run_id, tick)`, `(run_id, firm_id, tick)`, and `(run_id, sector, tick)`

8. `008_add_postgres_firm_snapshots.py`
- upgrades an existing Postgres/Timescale warehouse with the same firm snapshot table
- adds the same indexes as SQLite
- converts `firm_snapshots` to a hypertable when Timescale is available

9. `009_add_sqlite_household_snapshots.py`
- upgrades an existing SQLite warehouse with sampled household-state storage
- adds `household_snapshots` and `tracked_household_history`
- adds indexes for sampled population reads and tracked-subject history reads

10. `010_add_postgres_household_snapshots.py`
- upgrades an existing Postgres/Timescale warehouse with the same household tables
- adds the same indexes as SQLite
- converts both tables to hypertables when Timescale is available

11. `011_add_sqlite_decision_features.py`
- upgrades an existing SQLite warehouse with per-tick decision-context storage
- adds `decision_features`
- adds the primary `(run_id, tick)` analytical index

12. `012_add_postgres_decision_features.py`
- upgrades an existing Postgres/Timescale warehouse with the same decision table
- adds the same index as SQLite
- converts `decision_features` to a hypertable when Timescale is available

13. `013_add_sqlite_reliability_manifest.py`
- upgrades an existing SQLite warehouse with run-manifest and reliability fields
- adds `config_json`, version fields, persisted watermark fields, and lifecycle flags
- adds `event_key` to event tables plus unique `(run_id, event_key)` indexes

14. `014_add_postgres_reliability_manifest.py`
- upgrades an existing Postgres/Timescale warehouse with the same manifest and reliability fields
- backfills legacy event rows before adding the unique idempotency indexes

15. `015_add_sqlite_diagnostics_and_regime_events.py`
- upgrades an existing SQLite warehouse with explainability-oriented diagnostics
- adds `simulation_runs.diagnostics_version`
- adds `tick_diagnostics`, `sector_shortage_diagnostics`, and `regime_events`

16. `016_add_postgres_diagnostics_and_regime_events.py`
- upgrades an existing Postgres/Timescale warehouse with the same diagnostics/regime-event layer
- converts the diagnostics tables to hypertables when Timescale is available

## Current Implemented Warehouse Scope

The currently implemented warehouse covers:

1. `simulation_runs`
2. `tick_metrics`
3. `sector_tick_metrics`
4. `firm_snapshots`
5. `household_snapshots`
6. `tracked_household_history`
7. `labor_events`
8. `healthcare_events`
9. `policy_actions`
10. `decision_features`
11. `tick_diagnostics`
12. `sector_shortage_diagnostics`
13. `regime_events`
14. `policy_config`

This is enough for:

- run metadata
- aggregate macro history
- per-sector aggregate history
- firm-by-firm state history
- sampled population state history
- every-tick tracked-household trajectories
- labor event history
- healthcare service event history
- policy action history
- compact per-tick policy / LLM decision context
- compact per-tick explainability diagnostics
- explicit regime/state transition events
- run-level policy configuration
- replay/debug manifest metadata
- persisted run lifecycle and durability status

It is still not the full long-term warehouse model.

## Reliability Guarantees

The warehouse now has a practical correctness baseline for simulation
debugging and future policy/LLM work.

Current guarantees:

1. flushes are atomic per buffered bundle
- one bundle commit now includes aggregates, decision rows, snapshots, events, and the watermark update
- if any insert fails, the entire bundle rolls back and the in-memory buffers remain available for retry

2. runs expose durability state
- `simulation_runs.last_fully_persisted_tick` records the highest durably committed tick
- `simulation_runs.analysis_ready` is only set on a clean completed close
- `simulation_runs.termination_reason` distinguishes normal completion from stop/fail or warehouse-flush failure

3. event inserts are idempotent
- `labor_events`, `healthcare_events`, and `policy_actions` now use deterministic `event_key`
- retries insert with conflict-ignore semantics instead of duplicating rows

This is intentionally a minimum strong foundation, not a full observability system.

## Explainability Diagnostics

The warehouse now persists a lightweight always-on explainability layer:

1. `tick_diagnostics`
- one row per run/tick
- compact policy-relevant explanations for unemployment change, health change,
  firm distress, housing failure, and shortage breadth

2. `sector_shortage_diagnostics`
- one row per run/tick/sector
- explicit shortage state plus compact severity and driver metrics

3. `regime_events`
- sparse transition events for:
  - `firm_distress_enter`
  - `firm_distress_exit`
  - `firm_bankrupt`
  - `failed_hiring`
  - `eviction`
  - `shortage_regime_enter`
  - `shortage_regime_exit`

Design intent:
- keep this layer cheap enough for always-on debugging
- make the economy legible for later policy logic
- avoid building a large generic tracing system too early

## Replay Manifest

Each run now stores a minimal manifest in `simulation_runs`:

- `seed`
- `config_json`
- `code_version`
- `schema_version`
- `decision_feature_version`

This is enough for debugging, run comparison, and future policy evaluation
without overbuilding exact replay yet.

## Household Snapshot Cadence

The current household-storage path is intentionally split in two:

1. `household_snapshots`
- full sampled population state
- captured at tick `1` and then every `ECOSIM_HOUSEHOLD_SNAPSHOT_STRIDE` ticks
- default stride is `5`

2. `tracked_household_history`
- narrow every-tick history for the tracked household subset already used by the live UI
- avoids a full household scan on non-snapshot ticks

This keeps the warehouse analytically useful without turning 10k-household runs
into a write-heavy bottleneck immediately.

## Planned Warehouse Expansion

The long-term storage plan now lives in:

- [docs/DATA_STORAGE_ARCHITECTURE.md](../../docs/DATA_STORAGE_ARCHITECTURE.md)

That document defines:

- why `PostgreSQL + TimescaleDB` is the primary target
- what stays in memory vs websocket vs warehouse
- proposed table families
- key/index strategy
- migration sequencing
- write cadence rules
- anti-patterns to avoid

## Migration Sequence

The intended rollout order is:

1. expand aggregate warehouse
2. add event tables
3. add firm snapshots
4. add household snapshots
5. add decision-feature tables
6. add diagnostics and regime-change events
7. add query views and product-facing endpoints

The aggregate, event, firm snapshot, household snapshot, decision-feature,
and diagnostics layers are now implemented.

The next concrete implementation target is:

- keep explainability semantics stable as simulation mechanics evolve
- add only targeted trace depth where debugging value is clear
- keep future history APIs aligned with the warehouse grain rather than websocket payloads

## Decision Feature Definitions

The current `decision_features` table stores one row per tick with compact,
trend-aware values derived in memory from exact tick telemetry. The current
implementation uses:

- `unemployment_short_ma` / `unemployment_long_ma`
  - 5-tick and 20-tick moving averages of unemployment rate
- `inflation_short_ma`
  - 5-tick moving average of percentage change in the consumer price basket
  - basket currently uses mean `Food`, `Housing`, and `Services` prices
- `hiring_momentum` / `layoff_momentum`
  - short minus long moving average of hires / layoffs per 100 households
- `vacancy_fill_ratio`
  - current tick `total_hires / open_vacancies`, clamped to `[0, 1]`
- `wage_pressure`
  - percentage gap between unemployed expected wage and current mean wage
  - guarded by the configured minimum-wage floor to avoid divide-by-zero blowups
- `healthcare_pressure`
  - current healthcare queue depth per healthcare staff member
- `consumer_distress_score`
  - weighted score from unemployment, low-cash share, low-health share, and low-happiness share
- `fiscal_stress_score`
  - weighted score from negative government cash and negative fiscal flow relative to current GDP
- `inequality_pressure_score`
  - weighted score from Gini plus the `top10_share - bottom50_share` concentration gap

This table is intentionally compact. It is for live policy context and audit,
not for replacing raw aggregate or snapshot storage.

## Live Decision Context

The server now also maintains a rolling in-memory decision context for future
policy logic and local LLM integration.

Purpose:

- give a live agent a recent trend window without scraping websocket payloads
- keep the freshest context available even before a warehouse batch flush

Current surfaces:

1. `SimulationManager.get_live_decision_context(window=...)`
2. `GET /decision-context/live`

The live context window stores:

- current macro state (`unemploymentRate`, `meanWage`, `gdp`, government cash / flow)
- labor pressure (`openVacancies`, `totalHires`, `totalLayoffs`)
- healthcare pressure (`healthcareQueueDepth`)
- key prices (`avgFoodPrice`, `avgHousingPrice`, `avgServicesPrice`)
- the derived decision-feature scores
- the most recent policy changes

When the warehouse is enabled, persisted `decision_features` still come from
the exact aggregate path. When the warehouse is disabled, the live decision
window still updates from the server's in-memory metrics path.

## Implementation Rules

These rules matter for speed:

1. keep simulation execution in memory
2. batch writes
3. avoid per-row commits
4. avoid full-household snapshotting by default until profiled
5. do not let websocket payloads dictate warehouse schema

## Validation

The storage and query layer now has three test levels:

1. manager/unit coverage in `backend/data/tests/test_db_manager.py`
2. end-to-end SQLite warehouse coverage in `backend/data/tests/test_warehouse_integration.py`
3. server API coverage in `backend/tests_server/test_server_api.py`

The integration test exercises the real server-side warehouse path:

- open warehouse run
- execute real economy ticks
- batch aggregates, decision features, firm snapshots, sampled household snapshots, tracked-household history, and events
- flush to SQLite
- verify reads through `DatabaseManager`

The server API tests verify:

- live rolling decision-context reads
- persisted run listing
- persisted run comparison reads
- persisted policy-context reads
- persisted tick-metric reads
- persisted decision-feature reads
- persisted tick-diagnostic reads
- persisted sector drill-down reads
- persisted sector-shortage reads
- persisted regime-event reads

## Local Setup

SQLite:

```bash
python backend/data/migrations/001_create_warehouse.py
```

Existing SQLite DB upgrade:

```bash
python backend/data/migrations/003_expand_sqlite_aggregate_warehouse.py
```

PostgreSQL/Timescale:

```bash
docker compose -f ops/docker-compose.timescale.yml up -d
python backend/data/migrations/002_create_timescale_warehouse.py
```

Existing PostgreSQL/Timescale DB upgrade:

```bash
python backend/data/migrations/004_expand_postgres_aggregate_warehouse.py
```

Existing SQLite event-table upgrade:

```bash
python backend/data/migrations/005_add_sqlite_event_tables.py
```

Existing SQLite firm-snapshot upgrade:

```bash
python backend/data/migrations/007_add_sqlite_firm_snapshots.py
```

Existing PostgreSQL/Timescale event-table upgrade:

```bash
python backend/data/migrations/006_add_postgres_event_tables.py
```

Existing PostgreSQL/Timescale firm-snapshot upgrade:

```bash
python backend/data/migrations/008_add_postgres_firm_snapshots.py
```

Existing SQLite household-snapshot upgrade:

```bash
python backend/data/migrations/009_add_sqlite_household_snapshots.py
```

Existing PostgreSQL/Timescale household-snapshot upgrade:

```bash
python backend/data/migrations/010_add_postgres_household_snapshots.py
```

Existing SQLite decision-feature upgrade:

```bash
python backend/data/migrations/011_add_sqlite_decision_features.py
```

Existing PostgreSQL/Timescale decision-feature upgrade:

```bash
python backend/data/migrations/012_add_postgres_decision_features.py
```

Existing SQLite reliability/manifest upgrade:

```bash
python backend/data/migrations/013_add_sqlite_reliability_manifest.py
```

Existing PostgreSQL/Timescale reliability/manifest upgrade:

```bash
python backend/data/migrations/014_add_postgres_reliability_manifest.py
```

Existing SQLite diagnostics/regime-event upgrade:

```bash
python backend/data/migrations/015_add_sqlite_diagnostics_and_regime_events.py
```

Existing PostgreSQL/Timescale diagnostics/regime-event upgrade:

```bash
python backend/data/migrations/016_add_postgres_diagnostics_and_regime_events.py
```

Warehouse tests:

```bash
.\.venv\Scripts\python.exe -m pytest backend/data/tests -q
```

Server API tests:

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests_server/test_server_api.py -q
```

Combined validation:

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests_server/test_server_api.py backend/data/tests -q
```

Current read endpoints:

- `GET /decision-context/live?window=20`
- `GET /warehouse/runs`
- `GET /warehouse/compare?run_ids=run_a&run_ids=run_b`
- `GET /warehouse/runs/{run_id}/policy-context?tick=120&window=20&policy_lookback=12&impact_horizon=12`
- `GET /warehouse/runs/{run_id}/summary`
- `GET /warehouse/runs/{run_id}/tick-metrics`
- `GET /warehouse/runs/{run_id}/decision-features`
- `GET /warehouse/runs/{run_id}/tick-diagnostics`
- `GET /warehouse/runs/{run_id}/sector-metrics`
- `GET /warehouse/runs/{run_id}/sector-shortages`
- `GET /warehouse/runs/{run_id}/regime-events`

The policy-context endpoint is the compact warehouse surface intended for a
future government model or policy-RAG assistant. It returns:

- a rolling macro/decision/diagnostic window
- current sector shortage context
- recent regime events
- recent policy actions with compact observed post-action deltas
- reconstructed current policy state from the initial config plus actions

Environment variables:

- `ECOSIM_ENABLE_WAREHOUSE`
- `ECOSIM_WAREHOUSE_BACKEND`
- `ECOSIM_SQLITE_PATH`
- `ECOSIM_WAREHOUSE_DSN`
