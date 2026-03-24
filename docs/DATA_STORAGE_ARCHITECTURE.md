# EcoSim Data Storage Architecture (Local-First)

## Goal

Provide durable, queryable simulation history for:
- scenario comparison
- policy evaluation
- future LLM-driven government decisions

without requiring paid cloud infrastructure.

## Architecture

```text
frontend-react
  -> websocket commands/updates

backend/server.py
  -> SimulationManager run loop
  -> batch metric writer (every N ticks)

warehouse factory (backend/data/warehouse_factory.py)
  -> sqlite manager (default)
  -> postgres/timescale manager

database
  -> simulation_runs
  -> policy_config
  -> tick_metrics (time-series)
```

## Why PostgreSQL + TimescaleDB

1. SQL + relational joins are ideal for your run metadata and policy tables.
2. Time-series optimization on `tick_metrics` with hypertables scales better than plain row tables.
3. You keep one query language (SQL) for both product metrics and research analysis.
4. It runs locally with Docker, so cost remains near zero for a new-grad portfolio project.

## Core Tables

1. `simulation_runs`
- one row per simulation run
- status lifecycle: `running | completed | failed | stopped`
- final outcome summary for quick ranking/filtering

2. `policy_config`
- run-scoped policy values (taxes, UBI, wage floor, etc.)
- supports scenario comparison and auditability

3. `tick_metrics`
- dense time-series aggregates per run and tick
- primary key `(run_id, tick)` for idempotent writes
- optimized for trend analysis and LLM policy context windows

## Run Lifecycle

1. `SETUP` opens a new run row.
2. Each tick buffers one aggregate metric record in memory.
3. Buffer flushes to DB in batches (`ECOSIM_TICK_BATCH_SIZE`).
4. `RESET`/disconnect/error finalizes run status and stores final metrics.

This gives strong reliability properties for interviews:
- explicit run boundaries
- reduced write overhead via batching
- deterministic upserts on `(run_id, tick)`

## Local Setup

1. Start DB:
```bash
docker compose -f docker-compose.timescale.yml up -d
```
2. Set env:
```bash
ECOSIM_ENABLE_WAREHOUSE=1
ECOSIM_WAREHOUSE_BACKEND=timescale
ECOSIM_WAREHOUSE_DSN=postgresql://ecosim:ecosim@localhost:5432/ecosim
```
3. Apply schema:
```bash
python backend/data/migrations/002_create_timescale_warehouse.py
```

## Adding New Aggregate Metrics (for future LLM government agent)

When you add a new metric:

1. Add column to `tick_metrics` in schema.
2. Add field to `TickMetrics` dataclass.
3. Populate in `server.py` tick capture path.
4. Backfill defaults or migration for historical runs.
5. Add query endpoint/feature extraction for LLM input.

Recommended LLM-ready features:
- inflation trend (short and long window)
- unemployment momentum (delta over 4/12 ticks)
- inequality pressure score
- fiscal stress score (debt trend + tax capacity)
- sector stress indicators (food/housing/services shortages)

## Interview Talking Points

1. "I implemented a backend-agnostic warehouse writer and switched from in-memory streams to durable run storage."
2. "I used batch ingestion with idempotent `(run_id, tick)` writes to prevent duplicate metrics."
3. "I modeled simulation lineage with run metadata + policy snapshots for reproducible policy experiments."
4. "I designed the metric store to feed a future local-LLM government policy agent."

## Next Steps

1. Add continuous aggregates for hourly/daily rollups.
2. Add data quality contracts (null/range/completeness) in CI.
3. Add `/api/runs` and `/api/compare` endpoints backed by warehouse queries.
4. Add a feature view specifically for LLM policy decision context.
