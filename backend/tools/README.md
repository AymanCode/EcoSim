# Backend Tools

Supplementary utilities for analysis, benchmarks, diagnostics, LLM experiments, and local runner workflows. These are not required for the live FastAPI dashboard path.

## Layout

| Directory | Purpose |
|---|---|
| `analysis/` | Audit digests, sample-data generation, training-data generation, LLM run analysis |
| `benchmarks/` | Simulation, dashboard, policy-sweep, and warehouse benchmark CLIs |
| `checks/` | Standalone behavior checks and diagnostic scripts |
| `llm/` | LLM provider abstractions, government runner, firm runner, household tester, comparison tools |
| `runners/` | Headless simulation runners and audit/diagnostic execution scripts |

## Notes

- Production server entry is `backend/server.py`, not a script in this folder.
- Benchmark-specific notes live in [`benchmarks/README.md`](benchmarks/README.md).
- LLM government public artifacts live under [`../../experiments/llm_government_1k`](../../experiments/llm_government_1k).
