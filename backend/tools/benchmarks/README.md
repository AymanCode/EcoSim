# EcoSim Benchmarks

Non-production benchmark CLIs for producing reproducible performance evidence.

Install the benchmark dependencies from the repository root:

```powershell
python -m pip install -c backend/requirements.lock -e ".[dev,ml,benchmarks]"
```

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

## Evidence Panel (PRs that change economic behavior)

```powershell
python -m backend.tools.benchmarks.run_evidence_panel --arm main --root main ../main --arm off --arm on --set on households.skills_dynamics=True --baseline main --out benchmarks/results/pr51-panel
```

The standard evidence for a behavior-changing PR, so a reviewer reruns one command instead of rebuilding a study. Defaults match the dashboard population (1,000 households, 5 firms per category, all three payment sequences with `income_first` first, seeds 42-46) and the checklist length: 312 ticks, windows 1-100 (reported, not judged) / 101-200 / 201-312 (judged) / 261-312 (judged). `--weeks 260` still runs; the last window is dropped and 201-312 is clipped to 201-260. A fragile judged result (fewer than 4/5 seeds agree, median and mean disagree in sign, or one seed carries more than half the delta) reruns seeds 47-54. Each arm, sequence and seed runs in its own process (`evidence_panel_worker.py`), built by the same `build_economy_from_setup` the server uses and observed each tick with the dashboard's own metric calls. The command refuses to start outside CPython 3.11 with packages matching `backend/requirements.lock` unless `--allow-nonref` is set, which stamps every output as not comparable.

- `--arm NAME` declares an arm; the first is the baseline unless `--baseline`. `--root ARM PATH` runs an arm from another checkout, such as `main` without the PR's flag.
- `--set ARM section.field=value` overrides a config field before the economy is built (an unknown or mistyped name fails the run). `--set ARM lever.name=value` applies a policy lever after it. `lever.name=value@WEEK` or `@WEEK..WEEK` applies it for that span and then restores the previous value. `--off-set KEY=VALUE` is `--set off`.
- `--sweep ARM section.field` adds arms at 0.5×, 1× and 1.5× the field's default. `--interact a:K=V b:K=V` adds arms a, b and a+b. `--hook ARM k06_hold_pool` keeps the misc pool from paying out.
- `--metrics-plugin FILE` may be repeated (one file per owner). FILE defines `extra_metrics(economy) -> dict[str, float]` and may define `METRICS` and `summarize(runs)`.
- `panel.md` gives, per sequence and window, the baseline level and the paired difference: mean, [min, max], median, and k/n seeds up. `!` marks a mean whose sign flips when one seed is left out. Identity is the per-week state digest. A new money leak fails the run where the baseline conserves; where the baseline already leaks, the drift gap is reported and does not fail. Bounds / non-finite values and the determinism repeat fail the process. `evaluator.json` carries the env, the labour-force unemployment scores, and the panel. The layoffs column is planned layoffs per month.
- Rerunning the same command reuses finished runs only when their settings, simulation source, measuring code, worker Python and numpy versions, `backend/requirements.lock` and thread settings are all unchanged; changing only `--windows` re-aggregates. Workers run with one numeric-library thread each (`OMP_NUM_THREADS=1` and the like) and refuse to start under a different interpreter than the one planned.

One 1,000-household, 260-tick run takes about 50 s on an Apple-silicon laptop, so the default two-arm panel (33 runs with the repeat checks) takes a few minutes with `--jobs` near the core count.

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

Each run includes raw JSON, CSV rows, a Markdown summary, and runtime metadata.
