# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `34.182 ms`
- p95 tick latency: `123.432 ms`
- p99 tick latency: `126.222 ms`
- Throughput: `22.0576 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 34.182 | 123.432 | 126.222 | 22.0576 | 1323.46 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 51 | 35.656 | 124.253 | 130.029 | 18.9808 | 1138.85 |
| private_firm_ramp | 39 | 27.164 | 113.742 | 114.947 | 24.9636 | 1497.82 |
| warmup | 10 | 11.135 | 109.022 | 109.022 | 35.1653 | 2109.92 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `1323.46` simulated weeks/minute at `123.432 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
