# EcoSim 3-Seed Full App Evidence Ledger

Scope: 10,000 households, 5 firms/category, 50 target WebSocket frames, live FastAPI server, production React/Vite preview, Chrome/CDP, SQLite warehouse persistence, REST readback. LLM government excluded; zero LLM decision rows expected.

## Runs

| seed | artifact | run_id | status | frames | tick_rows | p95_tick_ms | p95_payload_bytes | warehouse_rows | duplicate_event_keys | rest_tick_metrics | console/errors |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | `benchmarks\results\2026-06-08-205430-full-app-evidence` | `run_1780977280_6d540fb2` | stopped | 50 | 51 | 4703.0 | 39515 | 175770 | 0 | 51 | 0/0 |
| 42 | `benchmarks\results\2026-06-08-205806-full-app-evidence` | `run_1780977497_4c55f962` | stopped | 50 | 51 | 4625.0 | 39778 | 174368 | 0 | 51 | 0/0 |
| 99 | `benchmarks\results\2026-06-08-210142-full-app-evidence` | `run_1780977714_e39603ec` | stopped | 50 | 51 | 4125.0 | 39793 | 175208 | 0 | 51 | 0/0 |

## Aggregate

- `duration_s`: median `177.360`, mean `173.306`, min `162.265`, max `180.293`
- `fps`: median `0.282`, mean `0.289`, min `0.277`, max `0.308`
- `p95_payload_bytes`: median `39778.000`, mean `39695.333`, min `39515.000`, max `39793.000`
- `total_payload_bytes`: median `1773546.000`, mean `1775367.000`, min `1768448.000`, max `1784107.000`
- `p50_backend_tick_ms`: median `3266.000`, mean `3182.333`, min `2984.000`, max `3297.000`
- `p95_backend_tick_ms`: median `4625.000`, mean `4484.333`, min `4125.000`, max `4703.000`
- `p95_parse_ms`: median `0.300`, mean `0.300`, min `0.300`, max `0.300`
- `p95_next_frame_ms`: median `13.800`, mean `13.533`, min `12.000`, max `14.800`
- `used_js_heap_mb`: median `22.291`, mean `20.837`, min `16.048`, max `24.173`
- `total_warehouse_rows`: median `175208.000`, mean `175115.333`, min `174368.000`, max `175770.000`
- `tick_metrics_rows`: median `51.000`, mean `51.000`, min `51.000`, max `51.000`
- `household_snapshot_rows`: median `110000.000`, mean `110000.000`, min `110000.000`, max `110000.000`
- `labor_event_rows`: median `39161.000`, mean `39219.667`, min `38656.000`, max `39842.000`
- `healthcare_event_rows`: median `14117.000`, mean `14140.000`, min `14059.000`, max `14244.000`
- `duplicate_event_keys`: median `0.000`, mean `0.000`, min `0.000`, max `0.000`
- `rest_tick_metrics_count`: median `51.000`, mean `51.000`, min `51.000`, max `51.000`
- `browser_console_rows`: median `0.000`, mean `0.000`, min `0.000`, max `0.000`
- `browser_error_rows`: median `0.000`, mean `0.000`, min `0.000`, max `0.000`

## Seed Wiring

- seed `7`: seed_source=`visible dashboard seed control sent in SETUP config`, set_seed_ok=`True`, set_seed_value=`7`
- seed `42`: seed_source=`visible dashboard seed control sent in SETUP config`, set_seed_ok=`True`, set_seed_value=`42`
- seed `99`: seed_source=`visible dashboard seed control sent in SETUP config`, set_seed_ok=`True`, set_seed_value=`99`
