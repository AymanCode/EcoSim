# EcoSim Full-App Evidence 5-Run Ledger

## Scope

- Five same-machine runs of `python -m backend.tools.integration.run_full_app_evidence --households 10000 --firms-per-category 5 --seed 42 --ticks 50 --timeout-seconds 1200 --tick-batch-size 5`.
- Production React build served by Vite preview; real Chrome/CDP; FastAPI WebSocket; live SQLite warehouse; UI STOP + STOPPED ack; REST readback.
- LLM government excluded; zero LLM rows expected.

## Run Results

| Iteration | Run dir | Status | Frames | Tick rows | Total rows | Duration s | FPS | p95 backend tick ms | p95 payload bytes | REST ok | Duplicates | Console/errors |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | `2026-06-08-200816-full-app-evidence` | stopped | 50 | 51 | 174368 | 150.399 | 0.332 | 4078.0 | 39777 | True | 0 | 0/0 |
| 2 | `2026-06-08-201134-full-app-evidence` | stopped | 50 | 51 | 174368 | 150.453 | 0.332 | 4000.0 | 39772 | True | 0 | 0/0 |
| 3 | `2026-06-08-201440-full-app-evidence` | stopped | 50 | 51 | 174368 | 151.030 | 0.331 | 3906.0 | 39777 | True | 0 | 0/0 |
| 4 | `2026-06-08-201748-full-app-evidence` | stopped | 50 | 50 | 172810 | 150.186 | 0.333 | 4031.0 | 39777 | True | 0 | 0/0 |
| 5 | `2026-06-08-202056-full-app-evidence` | stopped | 50 | 51 | 174368 | 150.887 | 0.331 | 3969.0 | 39772 | True | 0 | 0/0 |

## Aggregate

- `stream_duration_s`: median `150.453`, mean `150.591`, min `150.186`, max `151.030`
- `frames_per_second`: median `0.332`, mean `0.332`, min `0.331`, max `0.333`
- `p50_backend_tick_ms`: median `2750.000`, mean `2740.800`, min `2688.000`, max `2781.000`
- `p95_backend_tick_ms`: median `4000.000`, mean `3996.800`, min `3906.000`, max `4078.000`
- `p95_payload_bytes`: median `39777.000`, mean `39775.000`, min `39772.000`, max `39777.000`
- `total_payload_bytes`: median `1773559.000`, mean `1773556.600`, min `1773522.000`, max `1773588.000`
- `p95_parse_ms`: median `0.300`, mean `0.300`, min `0.300`, max `0.300`
- `p95_next_frame_ms`: median `12.700`, mean `12.540`, min `10.400`, max `14.000`
- `p95_two_frame_ms`: median `19.600`, mean `19.400`, min `17.800`, max `20.800`
- `used_js_heap_mb`: median `15.501`, mean `18.903`, min `12.210`, max `32.084`
- `total_warehouse_rows`: median `174368.000`, mean `174056.400`, min `172810.000`, max `174368.000`
- `tick_metrics_rows`: median `51.000`, mean `50.800`, min `50.000`, max `51.000`

## Pre-Optimization Comparison

- Baseline p95 backend tick compute: `6156.0 ms` from `2026-06-08-032725-full-app-evidence`
- New 5-run median p95 backend tick compute: `4000.0 ms`
- Relative reduction: `35.02%`
