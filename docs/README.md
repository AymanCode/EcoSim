# Documentation Index

Active documentation for the current EcoSim codebase. Code and runtime configuration are the source of truth; `docs/archive/` is historical reference material.

## Start Here

| Document | Purpose |
|---|---|
| [MODEL_SCOPE.md](MODEL_SCOPE.md) | Intended uses, interpretation rules, assumptions, limitations, and AI-governance benchmark status |
| [SIMULATION.md](SIMULATION.md) | Current model behavior, tick lifecycle, agents, markets, policy, banking, LLM government, and diagnostics |
| [TECHNICAL.md](TECHNICAL.md) | Stack, entry points, API surfaces, config, warehouse, LLM setup, performance notes, and validation commands |
| [FRONTEND.md](FRONTEND.md) | React dashboard views, WebSocket contract, runtime config mapping, and visual components |
| [DATA_STORAGE_ARCHITECTURE.md](DATA_STORAGE_ARCHITECTURE.md) | Warehouse design, implemented table families, write cadence, read paths, and reliability guarantees |
| [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) | Deliberate engineering choices and the tradeoffs behind them |

## Focused Topics

| Document | Purpose |
|---|---|
| [ECONOMIC_MODEL_PROPOSAL.md](ECONOMIC_MODEL_PROPOSAL.md) | Draft policy-comparison premise, economic audit, proposed workstreams, source citations, and reproducible evidence |
| [ECONOMIC_WORK_READINESS.md](ECONOMIC_WORK_READINESS.md) | Work divided into concrete corrections, focused specification/checks, and economic designs, with next steps and readiness criteria |
| [ECONOMIC_CONCRETE_PACKAGE.md](ECONOMIC_CONCRETE_PACKAGE.md) | W01–W05 implementation, field ownership, accounting decisions, evidence schema and validation |
| [ECONOMIC_IMPLEMENTATION_PLAN.md](ECONOMIC_IMPLEMENTATION_PLAN.md) | Implementation workflow and historical PAY-01 evidence; links to the integrated coordinated package |
| [ECONOMIC_IMPLEMENTATION_EXECUTION.md](ECONOMIC_IMPLEMENTATION_EXECUTION.md) | Integrated payment/agent mechanisms, explicit assumptions, public options and acceptance boundaries |
| [reviews/ECONOMIC_IMPLEMENTATION_REVIEW.md](reviews/ECONOMIC_IMPLEMENTATION_REVIEW.md) | Fable and coordinator findings, tests, reproducible comparisons and the unmet new-scenario performance target |
| [ECONOMIC_AGENT_RULES.md](ECONOMIC_AGENT_RULES.md) | Active rules v1.2 for proposal writers: current tick order, actor interactions, markets, accounting, information, individuality, performance and known limitations |
| [proposals/agent_round_01/README.md](proposals/agent_round_01/README.md) | Six Sol/high economic-role proposals, 17 ideas, primary citations, coordinator corrections and cross-agent integration decisions; no implementation |
| [proposals/agent_round_02/README.md](proposals/agent_round_02/README.md) | Fable source audit, concrete candidate mechanisms and actual cross-role objections/compromises for all 17 proposals; documents only |
| [reviews/ECONOMIC_AGENT_RULES_REVIEW.md](reviews/ECONOMIC_AGENT_RULES_REVIEW.md) | Fable's rules audit, source-verified coordinator dispositions and corrections incorporated in v1.1 |
| [reviews/ECONOMIC_DESIGN_COORDINATOR_AUDIT.md](reviews/ECONOMIC_DESIGN_COORDINATOR_AUDIT.md) | Audit of Fable’s W06–W18 proposals, required corrections and revised readiness |
| [reviews/ECONOMIC_BEHAVIOR_AND_DELEGATION_REVIEW.md](reviews/ECONOMIC_BEHAVIOR_AND_DELEGATION_REVIEW.md) | Latest Fable revision, coordinator qualifications, policy transmission, individual differences and subagent feasibility |
| [ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md](ECONOMIC_AGENT_PROPOSAL_TEMPLATE.md) | Independent proposal format, orchestrator review and cross-agent conflict register before implementation |
| [ECONOMIC_AGENT_WORKING_CONTRACT.md](ECONOMIC_AGENT_WORKING_CONTRACT.md) | Supporting execution contract under active agent rules: shared laws, ownership, integration, mechanism evidence and cumulative performance budget |
| [reviews/ECONOMIC_MODEL_FABLE_AUDIT_PROMPT.md](reviews/ECONOMIC_MODEL_FABLE_AUDIT_PROMPT.md) | Fable 5.1 repository-audit brief and review requirements |
| [reviews/ECONOMIC_MODEL_FABLE_AUDIT.md](reviews/ECONOMIC_MODEL_FABLE_AUDIT.md) | Completed independent Fable 5.1 source review with 13 findings and a proposed first package |
| [reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md](reviews/ECONOMIC_MODEL_AUDIT_FOLLOWUP.md) | Coordinator checks, five additional reproducible probes, corrections to review recommendations, and finding dispositions |
| [FIRM_DYNAMICS.md](FIRM_DYNAMICS.md) | Private-firm health signals, wage behavior, pricing, and hiring gates |
| [BANKING_SYSTEM.md](BANKING_SYSTEM.md) | Bank, deposits, lending, credit scoring, and credit-channel integration |
| [HOUSEHOLD_LABOR_DERISKING.md](HOUSEHOLD_LABOR_DERISKING.md) | Labor-search guardrails, reservation-wage clamping, diagnostics, and runtime flags |
| [POLICY_FORECASTING_V1.md](POLICY_FORECASTING_V1.md) | Policy stress-testing and forecasting design rationale |
| [POLICY_FORECASTING_SCHEMA.md](POLICY_FORECASTING_SCHEMA.md) | Frozen dataset schema for the policy forecasting pipeline |
| [evals/ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md](evals/ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md) | Draft protocol, claim boundaries, episode design, baselines, scoring, and reporting for the AI-governance benchmark |
| [testing/full_app_evidence_test.md](testing/full_app_evidence_test.md) | End-to-end evidence standard for the dashboard, server, stream, warehouse, and REST readback |

## Component Docs

| Document | Purpose |
|---|---|
| [../backend/README.md](../backend/README.md) | Backend package map and development commands |
| [../backend/data/README.md](../backend/data/README.md) | Warehouse backend scope, migrations, endpoints, and tests |
| [../backend/tools/README.md](../backend/tools/README.md) | Supplementary runner, benchmark, LLM, analysis, and check utilities |
| [../backend/tests_contracts/README.md](../backend/tests_contracts/README.md) | Contract-test suite layout and factory usage |
| [../frontend-react/README.md](../frontend-react/README.md) | Frontend startup notes |
| [experiments/AI_GOVERNMENT_EXPERIMENT.md](experiments/AI_GOVERNMENT_EXPERIMENT.md) | Featured AI engineering case study: five LLM governments, one controlled baseline, and the bounded evaluation harness |

## Experiments

| Document | Purpose |
|----------|---------|
| [AI_GOVERNMENT_EXPERIMENT.md](experiments/AI_GOVERNMENT_EXPERIMENT.md) | Curated 1,000-household LLM government comparison |

## Archive

`archive/` contains superseded plans, historical changelogs, and old implementation notes. Treat it as provenance, not current project documentation.
