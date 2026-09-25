# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `33.918 ms`
- p95 tick latency: `121.859 ms`
- p99 tick latency: `126.287 ms`
- Throughput: `22.1247 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 33.918 | 121.859 | 126.287 | 22.1247 | 1327.48 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 51 | 35.487 | 125.604 | 130.553 | 19.1275 | 1147.65 |
| private_firm_ramp | 39 | 27.443 | 113.658 | 114.937 | 24.7789 | 1486.73 |
| warmup | 10 | 11.245 | 103.553 | 103.553 | 35.7645 | 2145.87 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `1327.48` simulated weeks/minute at `121.859 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
