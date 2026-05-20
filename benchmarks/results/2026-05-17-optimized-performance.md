# EcoSim Performance Benchmarks

Generated from local benchmark runs on 2026-05-17. These results describe workstation performance, not hosted production capacity.

## Summary

EcoSim is a weekly agent-based macroeconomic simulation. The primary benchmark uses a 10,000-agent economy with autonomous consumers, private firms, government policy, banking, labor matching, goods-market clearing, housing, healthcare, taxes, transfers, firm lifecycle, and wellbeing updates.

The table below reports the current benchmark results without requiring project-specific context. Each row shows what was measured, how much activity the system processed, and the practical performance result.

| System Area | Workload | Activity Measured | Performance Result | Artifact |
|---|---|---:|---:|---|
| Simulation engine | 10,000 consumer agents, roughly 300 firm agents, 3 deterministic seeds | `123` saturated-market ticks, `~160k` purchase events/tick | `3.65s` p50 tick, `5.58s` p95 tick, `14.84` simulated weeks/min | `2026-05-17-134809-sim` |
| SQLite analytics warehouse | 10,000-agent runs persisted across 3 seeds | `421,328` analytical rows from `600` ticks, `30` flushes, `187.5 MB` DB | `49.94k` rows/sec, `0.36%` mean write overhead, `0.43 ms` p95 summary query | `2026-05-17-151357-warehouse-sqlite` |
| React dashboard browser | 10,000-agent Chrome session with view cycling | `100` tick messages, `4.05 MB` streamed, `47.9 KB` p95 payload | `0.30 ms` p95 JSON parse, `57.7 ms` p95 next-frame latency, `1.64s` LCP | `2026-05-17-155409-frontend-browser` |

## Simulation Engine

The engine benchmark isolates the full private-market phase: ticks after queued private firms have activated. This avoids mixing startup/warmup behavior with the saturated workload.

| Metric | Value |
|---|---:|
| Consumer agents | `10,000` |
| Approximate firm agents | `~300` |
| Seeds | `42`, `43`, `44` |
| Total measured ticks | `240` |
| Saturated-market ticks | `123` |
| Purchase-event volume | `~160k events/tick` |
| p50 saturated tick | `3.653s` |
| p95 saturated tick | `5.579s` |
| p99 saturated tick | `5.759s` |
| Throughput | `14.84 simulated weeks/min` |
| Peak RSS | `272.6 MB` |

## SQLite Warehouse

The warehouse benchmark persists simulation outputs into the SQLite analytics schema. Rows include aggregate tick metrics, sector rollups, decision features, firm snapshots, and sampled household snapshots.

| Stored Data Type | Rows |
|---|---:|
| Household snapshots | `300,000` |
| Firm snapshots | `117,728` |
| Sector tick metrics | `2,400` |
| Tick metrics | `600` |
| Decision features | `600` |
| **Total analytical rows** | **`421,328`** |

| Warehouse Metric | Value |
|---|---:|
| Backend | `SQLite` |
| Runs | `3` |
| Ticks persisted | `600` |
| Flushes | `30` |
| Aggregate ingest throughput | `49,935.76 rows/sec` |
| Mean write overhead | `0.362%` |
| p95 flush latency | `504.34 ms` |
| p95 summary-query latency | `0.43 ms` |
| p95 practical query-suite latency | `42.53 ms` |
| Max SQLite DB size | `187.5 MB` |

| Practical Query | p95 Latency | Rows Returned |
|---|---:|---:|
| Full 10k household snapshot read | `42.53 ms` | `10,000` |
| Latest firm snapshot read | `1.04 ms` | `208-215` |
| Full-run sector rollup | `1.15 ms` | `4` |
| Recent tick metrics window | `0.23 ms` | `26` |
| Run summary aggregate | `0.29 ms` | `1` |

## React Dashboard Browser

The browser benchmark launches Chrome, initializes the simulation through the real React UI, cycles dashboard views every 20 tick messages, and records WebSocket, parse, frame, long-task, memory, and Core Web Vitals-style metrics.

| Browser Metric | Value |
|---|---:|
| Economy size | `10,000` consumer agents |
| Browser | `Chrome 148` |
| Viewport | `1440 x 1000` |
| Tick messages received | `100` |
| Total streamed payload | `4.05 MB` |
| Mean payload size | `40.5 KB` |
| p95 payload size | `47.9 KB` |
| Tracked entities in final payload | `12` subjects, `7` firms |
| p95 JSON parse time | `0.30 ms` |
| p95 next-frame latency | `57.7 ms` |
| p95 two-frame latency | `71.4 ms` |
| p95 backend tick compute | `5.72s` |
| LCP | `1.64s` |
| CLS | `0.035` |
| Long tasks | `28` total, `125 ms` p95 |
| Used JS heap | `25.9 MB` |
| In-page runtime errors | `0` |

## Methodology

All runs were measured locally on Windows with Python 3.11, 24 logical CPUs, and Chrome 148 for the browser run. Benchmarks write raw CSV/JSON artifacts with runtime metadata, deterministic seeds, per-tick timings, database sizes, query latencies, browser metrics, screenshots, and workload-specific counters.

| Benchmark | Command |
|---|---|
| Simulation engine | `python -m backend.tools.benchmarks.run_sim_bench --households 10000 --ticks 80 --warmup-ticks 10 --seeds 42,43,44 --output-root benchmarks\results --verbose` |
| SQLite warehouse | `python -m backend.tools.benchmarks.run_warehouse_bench --backend sqlite --households 10000 --ticks 200 --seeds 42,43,44 --flush-every 20 --household-snapshot-stride 20 --output-root benchmarks\results --verbose` |
| Frontend browser | `python -m backend.tools.benchmarks.run_frontend_bench --url http://127.0.0.1:5173 --households 10000 --ticks 100 --timeout-seconds 1200 --remote-debugging-port 9231 --view-cycle-interval 20 --output-root benchmarks\results` |

## Reusable Summary

- Built a Python/FastAPI agent-based macroeconomic simulator that advances 10,000 autonomous consumers and hundreds of firms through labor, goods, banking, housing, healthcare, and policy markets at `3.65s` p50 tick latency.
- Designed a SQLite analytics warehouse for simulation experiments, persisting `421k+` analytical rows at `49.94k rows/sec` with `0.36%` mean tick-loop write overhead.
- Benchmarked a live React dashboard for 10k-agent simulations, streaming `100` tick updates with `47.9 KB` p95 payloads, `0.30 ms` p95 JSON parse time, and `57.7 ms` p95 next-frame latency.

## Caveats

- These are local workstation results, not cloud-hosted production results.
- The browser benchmark ran in headless Chrome using the real React UI and Chrome DevTools Protocol instrumentation.
- The repo was dirty during benchmark runs. Use the artifact folders and raw CSVs for auditability, and rerun from a clean commit if exact publication numbers are needed.
