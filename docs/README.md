# Documentation Index

Active documentation for the current EcoSim codebase. Code and runtime configuration are the source of truth.

## Start Here

| Document | Purpose |
|---|---|
| [MODEL_SCOPE.md](MODEL_SCOPE.md) | Intended uses, interpretation rules, assumptions, limitations, and AI-governance benchmark status |
| [SIMULATION.md](SIMULATION.md) | Current model behavior, tick lifecycle, agents, markets, policy, banking, LLM government, and diagnostics |
| [TECHNICAL.md](TECHNICAL.md) | Stack, entry points, API surfaces, config, warehouse, LLM setup, performance notes, and validation commands |
| [WEBSOCKET_PROTOCOL.md](WEBSOCKET_PROTOCOL.md) | WebSocket commands, replies, error strings, and tick-frame fields |
| [FRONTEND.md](FRONTEND.md) | Town Run screen: screens, live data flow, source layout, town drawings and checks; classic dashboard status |
| [DATA_STORAGE_ARCHITECTURE.md](DATA_STORAGE_ARCHITECTURE.md) | Warehouse design, implemented table families, write cadence, read paths, and reliability guarantees |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Deliberate engineering choices and the tradeoffs behind them |

## Model Topics

| Document | Purpose |
|---|---|
| [FIRM_DYNAMICS.md](FIRM_DYNAMICS.md) | Private-firm health signals, wage behavior, pricing, and hiring gates |
| [BANKING_SYSTEM.md](BANKING_SYSTEM.md) | Bank, deposits, lending, credit scoring, and credit-channel integration |
| [HOUSEHOLD_LABOR_DERISKING.md](HOUSEHOLD_LABOR_DERISKING.md) | Labor-search guardrails, reservation-wage clamping, diagnostics, and runtime flags |
| [POLICY_FORECASTING_V1.md](POLICY_FORECASTING_V1.md) | Policy stress-testing and forecasting design rationale |
| [POLICY_FORECASTING_SCHEMA.md](POLICY_FORECASTING_SCHEMA.md) | Frozen dataset schema for the policy forecasting pipeline |

## Experiments and Evaluations

| Document | Purpose |
|---|---|
| [experiments/AI_GOVERNMENT_EXPERIMENT.md](experiments/AI_GOVERNMENT_EXPERIMENT.md) | Five LLM governments against a rule-based baseline on the same 1,000-household economy |

## Testing

| Document | Purpose |
|---|---|
| [testing/full_app_evidence_test.md](testing/full_app_evidence_test.md) | End-to-end evidence standard for the dashboard, server, stream, warehouse, and REST readback |
| [testing/agent-scenarios.md](testing/agent-scenarios.md) | Small household and business experiments: cash, benefits, credit, rent, debt, health, demand, payroll, closure and a 24-household town |
| [testing/business-scenarios.md](testing/business-scenarios.md) | Controlled customer demand: money/no money, startups, hiring, wage changes, capacity, weak demand and recovery across complete business weeks |
| [testing/inflation-scenarios.md](testing/inflation-scenarios.md) | Observed price changes, annual private pay reviews and temporary demand/supply tests (`CONFIG.inflation.enabled`) |

## Component Docs

| Document | Purpose |
|---|---|
| [../backend/README.md](../backend/README.md) | Backend package map and development commands |
| [../backend/data/README.md](../backend/data/README.md) | Warehouse backend scope, migrations, endpoints, and tests |
| [../backend/tools/README.md](../backend/tools/README.md) | Supplementary runner, benchmark, LLM, analysis, and check utilities |
| [../backend/tests_contracts/README.md](../backend/tests_contracts/README.md) | Contract-test suite layout and factory usage |
| [../frontend-react/README.md](../frontend-react/README.md) | Frontend startup notes |
