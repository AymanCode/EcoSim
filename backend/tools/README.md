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
- Small household/business experiments: run `python -m backend.tools.checks.run_agent_scenarios` from the repository root. See the [scenario guide](../../docs/testing/agent-scenarios.md) for the eleven cases and readable reports.
- Controlled business demand: run `python -m backend.tools.checks.run_business_scenarios` for cash, hiring, wages, capacity and weak-demand cases. See the [business guide](../../docs/testing/business-scenarios.md) to set opening demand and weekly orders directly.
- `checks/money_supply_drift.py` prints total money (cash everywhere plus bank reserves) after each tick of a seeded large run, with per-tick and cumulative drift.
  Run `python -m backend.tools.checks.money_supply_drift --households 1500 --ticks 120 --seed 42`; any nonzero delta is money created or destroyed that tick.
- The curated LLM government report lives at [`../../docs/experiments/AI_GOVERNMENT_EXPERIMENT.md`](../../docs/experiments/AI_GOVERNMENT_EXPERIMENT.md).
