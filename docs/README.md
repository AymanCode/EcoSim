# Documentation Index

Active documentation for the current EcoSim codebase. Code and runtime configuration are the source of truth; `docs/archive/` is historical reference material.

## Start Here

| Document | Purpose |
|---|---|
| [SIMULATION.md](SIMULATION.md) | Current model behavior, tick lifecycle, agents, markets, policy, banking, LLM government, and diagnostics |
| [TECHNICAL.md](TECHNICAL.md) | Stack, entry points, API surfaces, config, warehouse, LLM setup, performance notes, and validation commands |
| [FRONTEND.md](FRONTEND.md) | React dashboard views, WebSocket contract, runtime config mapping, and visual components |
| [DATA_STORAGE_ARCHITECTURE.md](DATA_STORAGE_ARCHITECTURE.md) | Warehouse design, implemented table families, write cadence, read paths, and reliability guarantees |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Deliberate engineering choices and the tradeoffs behind them |

## Focused Topics

| Document | Purpose |
|---|---|
| [FIRM_DYNAMICS.md](FIRM_DYNAMICS.md) | Private-firm health signals, wage behavior, pricing, and hiring gates |
| [BANKING_SYSTEM.md](BANKING_SYSTEM.md) | Bank, deposits, lending, credit scoring, and credit-channel integration |
| [HOUSEHOLD_LABOR_DERISKING.md](HOUSEHOLD_LABOR_DERISKING.md) | Labor-search guardrails, reservation-wage clamping, diagnostics, and runtime flags |
| [POLICY_FORECASTING_V1.md](POLICY_FORECASTING_V1.md) | Policy stress-testing and forecasting design rationale |
| [POLICY_FORECASTING_SCHEMA.md](POLICY_FORECASTING_SCHEMA.md) | Frozen dataset schema for the policy forecasting pipeline |

## Component Docs

| Document | Purpose |
|---|---|
| [../backend/README.md](../backend/README.md) | Backend package map and development commands |
| [../backend/data/README.md](../backend/data/README.md) | Warehouse backend scope, migrations, endpoints, and tests |
| [../backend/tools/README.md](../backend/tools/README.md) | Supplementary runner, benchmark, LLM, analysis, and check utilities |
| [../backend/tests_contracts/README.md](../backend/tests_contracts/README.md) | Contract-test suite layout and factory usage |
| [../frontend-react/README.md](../frontend-react/README.md) | Frontend startup notes |
| [../experiments/llm_government_1k/README.md](../experiments/llm_government_1k/README.md) | Public LLM government comparison artifacts |

## Archive

`archive/` contains superseded plans, historical changelogs, and old implementation notes. Treat it as provenance, not current project documentation.
