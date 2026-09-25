# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `35.818 ms`
- p95 tick latency: `126.462 ms`
- p99 tick latency: `130.982 ms`
- Throughput: `21.6761 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 35.818 | 126.462 | 130.982 | 21.6761 | 1300.57 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| full_private_market | 11 | 37.603 | 126.562 | 126.562 | 18.5969 | 1115.82 |
| private_firm_ramp | 79 | 35.81 | 128.28 | 132.3 | 21.08 | 1264.8 |
| warmup | 10 | 10.873 | 103.304 | 103.304 | 36.4625 | 2187.75 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `1300.57` simulated weeks/minute at `126.462 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
