# EcoSim Benchmarks

Non-production benchmark CLIs for producing resume-ready, reproducible metrics.

## Simulation Throughput

```powershell
python -m backend.tools.benchmarks.run_sim_bench --households 1000,5000,10000 --ticks 80 --warmup-ticks 10 --seeds 42,43,44 --profile
```

Measures p50/p95/p99 tick duration, ticks/sec, memory RSS when available, and separates warmup from active private-market ticks.

## Warehouse Ingest

```powershell
python -m backend.tools.benchmarks.run_warehouse_bench --backend sqlite --households 1000,10000 --ticks 200
```

Measures rows/sec, tick-loop write overhead, flush p50/p95/p99 latency, query-suite latency, per-table row counts, SQLite file/WAL size, and database runtime metadata.

For PostgreSQL or TimescaleDB, start the database and set `ECOSIM_WAREHOUSE_DSN`, then use `--backend postgres` or `--backend timescale`.

## Policy Sweep

```powershell
python -m backend.tools.benchmarks.run_policy_sweep --seeds 42,43,44 --policies baseline,tax_grid,benefit_grid
```

Runs non-LLM policy grids and reports average outcomes plus 95% confidence intervals across seeds.

## Dashboard Probe

Start the backend first:

```powershell
python -m uvicorn backend.server:app --port 8002
python -m backend.tools.benchmarks.run_dashboard_bench --households 1000 --ticks 25
```

Measures WebSocket payload size, message cadence, and backend `tickComputeMs`.

## Frontend Browser

Start the backend and frontend first:

```powershell
python -m uvicorn backend.server:app --port 8002
cd frontend-react
$env:VITE_WS_URL = "ws://127.0.0.1:8002/ws"
npm run dev -- --host 127.0.0.1 --port 5173
cd ..
python -m backend.tools.benchmarks.run_frontend_bench --households 10000 --ticks 100
```

Launches Chrome through the Chrome DevTools Protocol, initializes the simulation through the real React UI, cycles dashboard views, and measures WebSocket payloads, JSON parse time, frame latency, long tasks, LCP, CLS, JS heap, DOM node count, and console errors.

## Outputs

By default, each command writes artifacts under:

```text
benchmarks/results/YYYY-MM-DD-HHMMSS-<benchmark>/
```

Each run includes raw JSON, CSV rows, a Markdown summary, runtime metadata, and resume bullet drafts.
