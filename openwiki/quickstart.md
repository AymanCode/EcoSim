---
type: Repository Guide
title: EcoSim OpenWiki quickstart
description: Entry point to EcoSim's source-grounded architecture, simulation domains, runtime protocols, research workflows, operations, and narrow change-validation routes.
tags: [ecosim, quickstart, repository-navigation]
openwiki:
  roles: [repository, architecture]
  change_kinds: [repository-navigation]
  source_paths: [README.md, pyproject.toml, backend/economy.py, backend/server.py, frontend-react/src/App.jsx]
  symbols: [Economy.step, SimulationManager, SessionRegistry, EcoSimUI]
  test_paths: [backend/tests_contracts, backend/tests_server, backend/data/tests, policy_forecasting/tests, frontend-react/src/App.test.jsx]
  invariants: [EcoSim outcomes describe a synthetic simulator and are not real-world forecasts or policy recommendations.]
  validation_commands: [python -m pytest backend/tests_contracts/test_contracts_integration_smoke.py -q]
---

# EcoSim OpenWiki quickstart

EcoSim is a local-first, weekly-tick agent-based economic research environment. Households, firms, government, an optional bank, and specialized housing and healthcare mechanisms interact inside one synthetic economy. A FastAPI server gives each WebSocket connection an isolated simulation manager, a React dashboard controls and observes it, and an optional SQLite/PostgreSQL/Timescale warehouse records completed-tick evidence. Separate LLM-government and policy-forecasting workflows use the simulator for bounded, **simulator-only** experiments.

This wiki maps engineering intent to owning files, symbols, focused tests, and narrow validation. Start with [where to change what](where-to-change-what.md) for implementation work or the concept map below for system understanding. It incorporates the current working-tree startup and test-gate changes as well as committed source and tests.

## Run EcoSim

The shortest supported user path is the two-container local stack. Start Docker Desktop (macOS/Windows) or Docker Engine with a recent Compose v2 plugin (Linux) first; the first build needs network access for images and dependencies.

```bash
docker compose up --build -d --wait
```

Open `http://localhost:5173`, leave Config at its defaults, and select **Launch Simulation**. Nginx serves the production React build and proxies `/ws` and `/health` to Uvicorn; Compose enables the SQLite warehouse in the `ecosim_runtime` volume. Stop with `docker compose down` to retain saved experiments. This is a local/single-host topology, not a hardened public deployment.

If host port `5173` is occupied, set `ECOSIM_PORT` without changing internal service addresses:

```bash
ECOSIM_PORT=5183 docker compose up --build -d --wait
```

Then open `http://localhost:5183`. See [deployment and operations](operations/deployment.md) before changing images, proxies, environment settings, or persistence backends.

For backend development, use Python 3.11 and run:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c backend/requirements.lock -e ".[ml]"
python -m uvicorn backend.server:app --reload --port 8002
```

The frontend is an independent npm application under `frontend-react`; use Node 22.22.2 or later within the 22.x release line:

```bash
cd frontend-react
npm ci
npm run dev
```

## How the system fits together

The [React dashboard](frontend/dashboard.md) sends setup, lifecycle, policy, and stabilizer commands to the [session and WebSocket runtime](runtime/sessions-and-websocket.md). Each `SimulationManager` advances the authoritative [tick lifecycle](backend/tick-lifecycle.md), which resolves the plans described in [agents and markets](backend/agents-and-markets.md) and settles fiscal, bank, healthcare, and housing state through [public institutions](backend/public-institutions.md). Completed-tick adapters write optional [warehouse evidence](data/warehouse.md), which the read-only [HTTP API](runtime/http-api.md) exposes for historical analysis.

Manual controls and the optional [LLM government](llm/government.md) share the bounded action contract in [configuration and policy](backend/configuration-and-policy.md). LLM calls run off the tick path and accepted changes apply only at a later safe boundary. Other model consumers are standalone research tools documented in [LLM experiments and evaluation](llm/experiments-and-evaluation.md), not live-server household or firm agents.

The separate [policy forecasting pipeline](forecasting/pipeline.md) constructs matched-seed frozen policy arms and invokes the same simulator as a library. Its reported results, absent artifacts, implementation discrepancies, and Streamlit viewer are audited in [forecasting evidence and demo](forecasting/evidence-and-demo.md). Older and exploratory executables have different evidence contracts; consult [research tools](engineering/research-tools.md) rather than treating every script as a supported API or test.

For the repository-wide composition roots and dependency boundaries, read the [architecture overview](architecture/overview.md). For what CI actually proves, focused test ownership, hot-path equivalence, and conditional benchmark/full-app checks, read [testing, CI, and performance evidence](engineering/testing-performance.md).

## Major concept map

| Concept | What it owns | Consult it when |
|---|---|---|
| [Architecture overview](architecture/overview.md) | Package/runtime composition, subsystem ownership, architectural invariants | A change crosses multiple components or you need the first composition root |
| [Tick lifecycle](backend/tick-lifecycle.md) | Exact `Economy.step()` phase order and settlement constraints | Changing simulation ordering, state transition, warmup, metrics, or performance cadence |
| [Agents and markets](backend/agents-and-markets.md) | Household/firm decisions, labor, goods/services, entry/exit, wellbeing, shocks | Changing private behavior, matching, clearing, skills, prices, or inequality metrics |
| [Public institutions](backend/public-institutions.md) | Fiscal execution, bank/deposits/credit, healthcare, housing | Changing taxes/transfers, loans, queues, rentals, mortgages, or capacity |
| [Configuration and policy](backend/configuration-and-policy.md) | Context-local config, canonical policy schema, UI translation, fiscal guards | Adding a tuning field or government lever |
| [Sessions and WebSocket](runtime/sessions-and-websocket.md) | Per-connection state/RNG, commands, frames, loop and reconnect lifecycle | Changing setup/run/reset, telemetry, session isolation, or WebSocket protocol |
| [HTTP API](runtime/http-api.md) | Health, warehouse analytics, live/persisted policy context | Adding/changing a read route, query contract, or reader error behavior |
| [Warehouse](data/warehouse.md) | Typed rows, SQLite/Postgres managers, schemas, migrations, atomic flush watermark | Changing durable evidence, read models, schema, batching, or run finalization |
| [React dashboard](frontend/dashboard.md) | Seven screens, browser state, charts/canvases, protocol client | Changing controls, views, telemetry rendering, build, or reconnect behavior |
| [LLM government](llm/government.md) | Provider boundary, constrained observation, validation, deferred apply, telemetry | Changing the live optional policy advisor |
| [LLM experiments and evaluation](llm/experiments-and-evaluation.md) | Standalone government/firm/household consumers and evaluation limits | Running or changing provider-backed research harnesses |
| [Policy forecasting pipeline](forecasting/pipeline.md) | Frozen arms, sweep schema, labels, splits, models, treatment effects, SHAP | Changing offline forecasting implementation or dataset contract |
| [Forecasting evidence and demo](forecasting/evidence-and-demo.md) | Claim audit, missing artifacts, discrepancies, Streamlit viewer | Interpreting results or validating reproduction/evidence claims |
| [Research tools](engineering/research-tools.md) | Analysis, runners, checks, legacy ML, artifact and mutation risks | Using a standalone executable or deciding whether it is supported evidence |
| [Testing, CI, and performance](engineering/testing-performance.md) | Test discovery, CI gates, hot paths, benchmarks, full-app harness | Selecting validation or making performance/evidence claims |
| [Deployment and operations](operations/deployment.md) | Local/Docker execution, Nginx, environment, Timescale, health and security gaps | Changing runtime packaging, topology, storage provisioning, or operations |

## Task routing

Use the narrow command first. Escalate to a package build, complete CI-equivalent suite, provider-backed run, database service, browser harness, or 10k benchmark only when the change crosses that boundary.

| Change area or user intent | Relevant wiki page | Exact source entry points | Important symbols or types | Focused tests | Minimal validation command |
|---|---|---|---|---|---|
| Tick ordering or cross-market behavior | [Tick lifecycle](backend/tick-lifecycle.md) | `backend/economy.py`, `backend/agents.py` | `Economy.step`, `_run_labor_matching`, `_clear_goods_market` | `test_contracts_integration_smoke.py`, `test_contracts_invariants.py` | `python -m pytest backend/tests_contracts/test_contracts_integration_smoke.py -q` |
| Household, firm, labor, pricing, or consumption | [Agents and markets](backend/agents-and-markets.md) | `backend/agents.py`, `backend/economy.py` | `HouseholdAgent`, `FirmAgent`, `_batch_plan_consumption` | `test_contracts_behavior.py`, `test_hot_path_optimizations.py` | `python -m pytest backend/tests_contracts/test_contracts_behavior.py -q` |
| Wage contract pairing, earned-wage tax, or receipt consistency | [Tick lifecycle](backend/tick-lifecycle.md) | `backend/economy.py`, `backend/tests_contracts/test_wage_contract_consistency.py` | `Economy.step`, `_sync_firm_employee_rosters`, `_build_household_tax_snapshots`, `_batch_apply_household_updates` | `test_wage_contract_consistency.py` | `python -m pytest backend/tests_contracts/test_wage_contract_consistency.py -q` |
| Bank, healthcare, housing, or fiscal mechanics | [Public institutions](backend/public-institutions.md) | `backend/agents.py`, `backend/economy.py`, `backend/fiscal_guards.py` | `BankAgent`, `GovernmentAgent`, `LoanContract`, `_process_healthcare_services` | Focused bank/deposit/healthcare/housing files | `python -m pytest backend/tests_contracts/test_contracts_bank.py -q` |
| Configuration or policy lever | [Configuration and policy](backend/configuration-and-policy.md) | `backend/config.py`, `backend/policy_schema.py`, `backend/server.py` | `SimulationConfig`, `POLICY_SCHEMA`, `GovernmentAgent.set_lever`, `_normalize_runtime_policy_updates` | `test_contracts_llm.py`, `test_server_sessions.py` | `python -m pytest backend/tests_contracts/test_contracts_llm.py -q` |
| WebSocket command, frame, lifecycle, or isolation | [Sessions and WebSocket](runtime/sessions-and-websocket.md) | `backend/server.py`, `backend/config.py` | `SimulationManager`, `SessionRegistry`, `websocket_endpoint`, `use_config` | `test_server_sessions.py` | `python -m pytest backend/tests_server/test_server_sessions.py -q` |
| HTTP analytics route | [HTTP API](runtime/http-api.md) | `backend/server.py`, `backend/data/*_manager.py` | FastAPI route handlers, `create_warehouse_manager` | `test_server_api.py` | `python -m pytest backend/tests_server/test_server_api.py -q` |
| Warehouse row, schema, migration, or flush | [Warehouse](data/warehouse.md) | `backend/data/models.py`, schemas, managers, migrations; `backend/server.py` | Row dataclasses, `persist_flush_bundle`, watermark/finalization adapters | `test_db_manager.py`, `test_warehouse_integration.py` | `python -m pytest backend/data/tests/test_db_manager.py -q` |
| Dashboard screen or protocol client | [React dashboard](frontend/dashboard.md) | `frontend-react/src/App.jsx`, `src/main.jsx`, visualizers | `EcoSimUI`, `resolveWebSocketEndpoint`, `flushConfigUpdates` | `frontend-react/src/App.test.jsx` | `cd frontend-react && npm test` |
| Live LLM policy advisor | [LLM government](llm/government.md) | `backend/tools/llm/llm_government.py`, `llm_provider.py`, `backend/server.py` | `LLMProvider`, `LLMGovernmentAdvisor`, scheduling/apply methods | `test_contracts_llm.py`, `test_live_llm_government.py` | `python -m pytest backend/tests_server/test_live_llm_government.py -q` |
| Forecasting data/model/evaluation | [Policy forecasting](forecasting/pipeline.md) | `policy_forecasting/run_pipeline.py`, `dataset.py`, `split.py`, `models.py`, `evaluate.py` | `build_supervised_frame`, `assign_splits`, `fit_model_suite` | `policy_forecasting/tests` | `python -m pytest policy_forecasting/tests -q` |
| CI, optimization, benchmark, or evidence claim | [Testing and performance](engineering/testing-performance.md) | `.github/workflows/ci.yml`, `backend/tools/benchmarks`, `backend/tools/integration` | `smoke_startup.main`, hot-path helpers, benchmark CLIs, full-app harness | `test_hot_path_optimizations.py`, harness tests | `python -m pytest backend/tests_contracts/test_hot_path_optimizations.py -q` |
| Docker, proxy, startup port, or storage topology | [Deployment](operations/deployment.md) | `docker-compose.yml`, Dockerfiles, `frontend-react/nginx.conf`, `backend/tools/integration/smoke_startup.py` | Compose services, `ECOSIM_PORT`, Nginx locations, warehouse environment | CI startup probe; server/data/frontend suites as affected | `docker compose config -q` |

The denser [where-to-change-what guide](where-to-change-what.md) includes complete public/cross-component change surfaces and escalation conditions.

## Validation rules

- Bare `python -m pytest` discovers `backend/tests_contracts`, `backend/tests_server`, and `backend/data/tests` once each. Its strict-marker default includes provider-free mocked `llm` contracts and excludes only `research`; use `python -m pytest -m research` for exploratory policy checks. Forecasting remains an explicit suite in its own frozen dependency environment.
- Backend CI installs the lean `.[test,ml]` extra; the broader `dev` extra is for optional formatter, coverage, and type-checker tools. Internal correctness is not shipped-surface correctness: protocol changes require both backend session/API tests and the frontend consumer test. Warehouse model changes require schema/manager/adapters/readers, not only a dataclass unit test. A policy lever requires schema, agent consumption, server mapping, UI/provider surfaces as applicable, persistence, and cross-boundary tests.
- Do not run broad checks by default. Run the wheel build when packaging/public imports change; frontend build when bundling or dependencies change; the Compose startup probe when Docker, Nginx, startup wiring, or default SQLite persistence changes; Postgres/Timescale checks only when that backend/schema changes; provider-backed LLM runs only when external integration evidence is required; full-app/10k benchmarks only for performance or publication claims.
- Preserve simulator interpretation limits: deterministic replay and matched seeds support controlled within-model comparisons, not real-world calibration, causal transfer, policy recommendation, or autonomous authority.

## Backlog

No source-grounded documentation area is deferred in this initialization. Known implementation and evidence gaps are recorded on their owning concept pages rather than as missing wiki coverage.
