# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `89.673 ms`
- p95 tick latency: `125.454 ms`
- p99 tick latency: `127.469 ms`
- Throughput: `11.1168 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 89.673 | 125.454 | 127.469 | 11.1168 | 667.01 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| private_firm_ramp | 90 | 89.781 | 125.533 | 136.693 | 10.8095 | 648.57 |
| warmup | 10 | 58.644 | 99.813 | 99.813 | 14.9394 | 896.37 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `667.01` simulated weeks/minute at `125.454 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
