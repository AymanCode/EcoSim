# EcoSim Simulation Throughput Benchmark

## Runtime Context

- Commit: `4f69389`
- Python: `3.13.2`
- Platform: `macOS-27.0-arm64-arm-64bit-Mach-O`
- Logical CPUs: `10`

## Overall

- Ticks measured: `100`
- p50 tick latency: `90.348 ms`
- p95 tick latency: `128.299 ms`
- p99 tick latency: `134.255 ms`
- Throughput: `10.7813 ticks/sec`

## By Household Scale

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| 1000 | 100 | 90.348 | 128.299 | 134.255 | 10.7813 | 646.88 |

## By Tick Phase

| Group | Ticks | p50 ms | p95 ms | p99 ms | Ticks/sec | Weeks/min |
|---|---:|---:|---:|---:|---:|---:|
| private_firm_ramp | 90 | 90.514 | 128.706 | 169.636 | 10.4849 | 629.1 |
| warmup | 10 | 60.098 | 103.493 | 103.493 | 14.4604 | 867.63 |

## Evidence Summary

- The Python agent-based simulator was measured toward the 10k+ agents target at `1000` households, with p50/p95/p99 tick latency and `646.88` simulated weeks/minute at `128.299 ms` p95 tick latency on the recorded local environment.
- The harness records commit/runtime metadata, CSV/JSON outputs, and optional profiles so results can be compared and reproduced.
