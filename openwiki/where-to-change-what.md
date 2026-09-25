---
type: Change Guide
title: Where to change what in EcoSim
description: Symbol-level routing from common EcoSim changes to implementation seams, cross-component surfaces, focused tests, minimal commands, and conditional escalation checks.
tags: [ecosim, change-guide, repository-navigation]
openwiki:
  roles: [repository, testing, delivery]
  change_kinds: [implementation-routing, public-api, validation]
  source_paths: [backend/economy.py, backend/server.py, backend/policy_schema.py, backend/data/models.py, frontend-react/src/App.jsx, policy_forecasting/run_pipeline.py]
  symbols: [Economy.step, SimulationManager, GovernmentAgent.set_lever, persist_flush_bundle, EcoSimUI]
  test_paths: [backend/tests_contracts, backend/tests_server, backend/data/tests, policy_forecasting/tests, frontend-react/src/App.test.jsx]
  invariants: [Validate both defining-module correctness and the real consumer-facing boundary when a change crosses protocols packages schemas or registration.]
  validation_commands: [python -m pytest backend/tests_contracts/test_contracts_integration_smoke.py -q]
---

# Where to change what in EcoSim

Use this page when you know the intended change but not its complete surface. The tables route to the first owning symbol, one-hop dependencies, focused tests, and the smallest useful command. Follow the linked concept page before changing lifecycle ordering or a cross-component contract.

## Simulation mechanics

| Intent | Start at | Follow through | Invariants and narrow tests | Minimal command |
|---|---|---|---|---|
| Add or reorder a tick phase | `backend/economy.py::Economy.step` | Called resolver/apply method; metrics/diagnostics emitted after it; [tick lifecycle](backend/tick-lifecycle.md) | Plan before contention resolution; settlement ordering; one tick increment; `test_contracts_integration_smoke.py`, `test_contracts_invariants.py` | `python -m pytest backend/tests_contracts/test_contracts_integration_smoke.py -q` |
| Change household decisions or wellbeing | `backend/agents.py::HouseholdAgent` | `Economy._batch_plan_consumption`, labor matching, batch apply/wellbeing paths; [agents and markets](backend/agents-and-markets.md) | Cash/ledger pairing, bounded wellbeing, service non-inventory, seeded behavior; `test_contracts_behavior.py` | `python -m pytest backend/tests_contracts/test_contracts_behavior.py -q -k household` |
| Change firm planning, production, or exit | `backend/agents.py::FirmAgent` | `Economy.step`, `_handle_firm_exits`, `_maybe_create_new_firms`, sector statistics | Nonnegative price/wage/inventory, employee-roster consistency, baseline-sector floors; behavior/invariant/integration suites | `python -m pytest backend/tests_contracts/test_contracts_behavior.py -q -k firm` |
| Change labor matching | `backend/economy.py::_run_labor_matching` | fast/legacy implementation selection, `HouseholdAgent.apply_labor_outcome`, firm rosters, labor diagnostics | Household employer and firm roster remain two-sided; fast/legacy semantics and guardrails | `python -m pytest backend/tests_contracts/test_hot_path_optimizations.py -q -k labor` |
| Optimize consumption hot paths | `Economy._batch_plan_consumption`, `_build_firm_market_views`; `HouseholdAgent.refresh_awareness_pool` | tie-break noise cache, awareness filtering, batch application; [testing and performance](engineering/testing-performance.md) | Cache identity/read-only arrays, deterministic ordering and exact ledger semantics | `python -m pytest backend/tests_contracts/test_hot_path_optimizations.py -q` |
| Change banking or deposits | `backend/agents.py::BankAgent` | economy origination/repayment/deposit methods and optional-bank branches; [public institutions](backend/public-institutions.md) | Required reserves protected; borrower/bank cash paired; household deposit equals liability movement | `python -m pytest backend/tests_contracts/test_contracts_bank.py backend/tests_contracts/test_contracts_deposits.py -q` |
| Change named payment scenarios, funding priority, or arrears | `backend/economy.py::Economy.step`; `backend/payments.py::PaymentBook` | `payment_sectors.py` owns delivery/tenancy; `payment_loans.py` owns registered claims; `payment_projects.py` and `payment_government.py` own funded capacity; [tick lifecycle](backend/tick-lifecycle.md) | Keep `legacy` separate; one cash/claim owner; `income_late` cannot fund earlier purchases; clearing payables release once | `python -m pytest backend/tests_contracts/test_payment_acceptance.py -q` |
| Change healthcare | healthcare fields in `HouseholdAgent`/`FirmAgent`; `Economy._process_healthcare_services` | queue priority, capacity, medical training, affordability/credit, diagnostics | One queue placement, no healthcare inventory, completions bounded by capacity | `python -m pytest backend/tests_contracts/test_contracts_healthcare.py -q` |
| Change housing/rent/mortgages | `Economy._clear_housing_rental_market`, `_service_housing_mortgage_debt`, `_offer_housing_expansion_loans` | `FirmAgent.invest_in_unit_expansion`, `LoanContract`, repairs/property tax | Contract/provider/occupancy consistency; PMT and principal/interest money movement | `python -m pytest backend/tests_contracts/test_contracts_housing_loans.py backend/tests_contracts/test_contracts_housing_revenue.py -q` |
| Change payment housing projects or public Services capacity | `backend/payment_projects.py::{register_funded_housing_project,complete_payment_projects}`; `backend/payment_government.py::{reserve_payment_services_project,complete_payment_services_project}` | `Economy.step` phase placement, Treasury restrictions, mortgage/loan routes, provider exit, `payment_reporting.py`; [public institutions](backend/public-institutions.md) | Debit a real payer once; capacity only after configured lag; public Services work requires a fully paid newly hired worker | `python -m pytest backend/tests_contracts/test_payment_government.py backend/tests_contracts/test_payment_sectors.py -q` |

A kernel change that alters output shape or completion timing also affects the [session runtime](runtime/sessions-and-websocket.md), [warehouse adapters](data/warehouse.md), and potentially [forecasting snapshots](forecasting/pipeline.md). Do not treat those consumers as automatically compatible.

## Add or change a policy lever

The canonical path is **schema -> storage/validation -> mechanical consumption -> runtime translation -> consumer control -> evidence -> tests**. Read [configuration and policy](backend/configuration-and-policy.md) and [LLM government](llm/government.md) before editing.

1. Define the lever, legal values, prompt order, and atomic group where applicable in `backend/policy_schema.py` (`POLICY_SCHEMA`, `VALID_LEVERS`, `PROMPT_POLICY_LEVERS`, `POLICY_GROUPS`, `SPENDING_LEVERS`).
2. Store and validate it in `backend/agents.py::GovernmentAgent.set_lever`; make an owning `Economy.step` phase actually consume it. A serialized but unconsumed field is inert, as the documented `birthRate` example demonstrates.
3. Add fiscal admissibility in `backend/fiscal_guards.py` when it changes spending, reserves, taxes, or grouped affordability.
4. For manual control, update `backend/server.py::SimulationManager._normalize_runtime_policy_updates` and `frontend-react/src/App.jsx`. Running updates must remain coalesced and applied before the next tick; paused updates use the same validator.
5. For model control, update the advisor's action mask/prompt/sanitizer without bypassing the canonical schema. Preserve grouped atomicity, two-instrument limit, snapshot/apply separation, and live `set_lever` revalidation.
6. If evidence requires the lever, update warehouse policy baseline/action representation, aliases in persisted policy-context reconstruction, and any forecasting frozen vector intentionally using it. Update schemas and both SQL managers where a column changes.
7. Test schema bounds/step size, invalid values, group atomicity, manual translation, actual economic consumption, safe-boundary apply, prompt/action-mask synchronization, and persisted reconstruction.

### Named payment scenario setup and reporting

For launch-only scenario changes, start at `backend/config.py::SimulationConfig`, `backend/server.py::SetupConfig`, and `SimulationManager.initialize`; `Economy.__init__` snapshots the selected `payment_*` values, while `payment_reporting.py::payment_snapshot` supplies `metrics.payment`. Keep the library default `legacy`, validate all new-run values, preserve per-session isolation, and do not make a running sequence mutable. The public-facing check is:

```bash
python -m pytest backend/tests_server/test_payment_scenarios.py backend/tests_contracts/test_payment_reporting.py -q
```

For changes crossing payments and performance code, run the relevant correctness suite first. `income_first` exceeds the cumulative 5% performance gate, while the measured `legacy` pairs stayed within it; these focused tests do not establish that result.

Minimal provider-free checks:

```bash
python -m pytest backend/tests_contracts/test_contracts_llm.py -q
python -m pytest backend/tests_server/test_server_sessions.py backend/tests_server/test_live_llm_government.py -q
```

Add `cd frontend-react && npm test` when the dashboard changes, and `python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q` when durable policy evidence changes. Provider-backed harnesses are conditional: run them only to validate real provider compatibility, accepting nondeterministic latency/cost and retaining raw artifacts.

## Runtime protocol and application surfaces

| Intent | Complete change surface | Focused validation |
|---|---|---|
| Add/change a WebSocket command | `backend/server.py::websocket_endpoint` dispatch; `SimulationManager` lifecycle method; command/reply/error shape; `frontend-react/src/App.jsx` sender and `onmessage`; Nginx only if path/upgrade behavior changes | `python -m pytest backend/tests_server/test_server_sessions.py -q`; then `cd frontend-react && npm test` |
| Add/change tick telemetry | `SimulationManager._run_loop_scoped` frame builder and caches/histories; dashboard defensive merge and consuming screen/chart; warehouse adapters only if it must persist | Backend session test plus `cd frontend-react && npm test`; build conditionally for bundling/chart changes |
| Change setup/reset/reconnect | `SimulationManager.initialize_simulation`, start/stop/reset methods, `SessionRegistry`, endpoint cleanup; dashboard initialize/toggle/reset/reconnect handlers | `python -m pytest backend/tests_server/test_server_sessions.py -q`; `cd frontend-react && npm test` |
| Add/change an HTTP route | FastAPI handler in `backend/server.py`; query validators and error contract; warehouse manager read method; proxy only if browser/Nginx must expose it | `python -m pytest backend/tests_server/test_server_api.py -q` |
| Change session configuration or RNG | `backend/config.py::{clone_config,use_config,CONFIG}`; `SimulationManager._random_scope` and every synchronous scope entry | `python -m pytest backend/tests_server/test_server_sessions.py -q` |

The externally used surface is the browser-to-server protocol, not a Python barrel export. A backend-only passing test does not prove the dashboard's wire consumer still works. Conversely, jsdom tests do not prove the server's per-session config/RNG isolation. Consult [sessions and WebSocket](runtime/sessions-and-websocket.md) and [React dashboard](frontend/dashboard.md) for lifecycle boundaries.

## Warehouse and analytics

For a new durable fact or field, the full shipped surface is:

1. canonical row dataclass in `backend/data/models.py`;
2. fresh SQLite and PostgreSQL schemas plus paired incremental migrations for existing stores;
3. equivalent insert/read behavior in `db_manager.py` and `postgres_manager.py`;
4. server adapter/buffer creation and inclusion in `persist_flush_bundle`;
5. deterministic event key/natural key and retry semantics where the row is event-like;
6. atomic watermark/finalization behavior;
7. FastAPI read route and response serialization if externally queryable;
8. SQLite manager/integration/API tests, plus a conditional real PostgreSQL/Timescale check because CI does not prove backend parity.

Never hand-edit a derived database. Fresh SQLite schema application is automatic; PostgreSQL/Timescale migration is an operator responsibility. Preserve the contract that a flush commits all submitted domains and advances `last_fully_persisted_tick` together, or rolls back and retains server buffers. Start with [warehouse and durable evidence](data/warehouse.md).

```bash
python -m pytest backend/data/tests/test_db_manager.py -q
python -m pytest backend/data/tests/test_warehouse_integration.py backend/tests_server/test_server_api.py -q
```

## Frontend, build, and deployment

- **View/control behavior:** start at `frontend-react/src/App.jsx::EcoSimUI`; visual-only canvases live in `NeuralAvatar.jsx`, `NeuralBuilding.jsx`, and `NeuralGovernment.jsx`. Verify `npm test`; use `npm run lint` for static quality and `npm run build` when imports, chunks, dependencies, or production assets change.
- **Development transport:** `frontend-react/vite.config.js` owns `/ws` proxying. **Production transport:** `frontend-react/nginx.conf` owns static fallback plus `/ws` and `/health`. Read [deployment](operations/deployment.md) before assuming warehouse HTTP routes are proxied—they are not.
- **Dependency/public build boundary:** `frontend-react/package.json` and `package-lock.json` are the shipped dependency surface. A component test does not prove Rollup chunking or Nginx image assembly; run the build when that boundary changes.
- **Compose/backend image:** `docker-compose.yml`, `backend/Dockerfile`, `frontend-react/Dockerfile`; validate syntax with `docker compose config -q`. The fresh-Compose startup probe is a normal CI gate: it builds and starts the stack, then invokes `backend.tools.integration.smoke_startup` against the frontend and persistent SQLite path. Run its local equivalent when Dockerfile, dependency, healthcheck, proxy, startup wiring, or default SQLite persistence changes; it is not needed for an isolated application-logic edit.
- **Timescale:** `ops/docker-compose.timescale.yml` only starts the database. Backend DSN selection and migrations remain separate operator steps.

## LLM and forecasting research

| Intent | Owning implementation | Boundary to preserve | Minimal command |
|---|---|---|---|
| Provider adapter | `backend/tools/llm/llm_provider.py::LLMProvider`, provider implementations, `create_provider` | Live simulator must degrade gracefully when unavailable; do not expose credentials | `python -m pytest backend/tests_contracts/test_contracts_llm.py -q` |
| Government observation/sanitizer | `backend/tools/llm/llm_government.py` | Deterministic information constraints, canonical schema, grouped atomicity, no mutable live economy during inference | `python -m pytest backend/tests_contracts/test_contracts_llm.py -q` |
| Server scheduling/apply | `backend/server.py` LLM scheduling, pending result, apply and telemetry methods | At most one in flight/pending, frozen snapshot, later safe-boundary revalidation | `python -m pytest backend/tests_server/test_live_llm_government.py -q` |
| Standalone firm/household experiment | `backend/tools/llm/run_llm_firm_test.py`, household/all-archetype runners | These are not live-server integrations and have different artifacts | Inspect `--help`; use provider-backed execution only conditionally |
| Frozen forecasting arm/sweep | `policy_forecasting/config.py`, `sweep/wrapper.py` | Canonical vector/hash, matched seeds, same simulator factory and complete manifest | `python -m pytest policy_forecasting/tests/test_config.py -q` |
| Label/features/split | `dataset.py`, `split.py` | Forward-only labels, ID/future exclusion, policy/seed block meaning; known exclusion/discrepancies remain explicit | `python -m pytest policy_forecasting/tests/test_dataset.py policy_forecasting/tests/test_split.py -q` |
| Models/evaluation/explanation/demo | `models.py`, `evaluate.py`, `run_pipeline.py`, `explain.py`, `demo/app.py` | Simulator-only claims; prediction/artifact provenance; current demo has no producer | `python -m pytest policy_forecasting/tests -q` |

Read [experiments and evaluation](llm/experiments-and-evaluation.md) before treating a script as integrated, and [forecasting evidence and demo](forecasting/evidence-and-demo.md) before repeating reported numerical claims. The 10k confirm sweep, SHAP, Streamlit, or provider-backed runs are conditional evidence tasks, never routine validation.

## Validation escalation

| Scope crossed | Add this check | Why it is conditional |
|---|---|---|
| Python package metadata/public import | `pip wheel --no-deps --wheel-dir /tmp/ecosim-wheel .` | Defining-module tests do not prove the installable distribution contains/resolves it |
| Multiple backend domains | `python -m pytest --durations=10` | Mirrors the stable CI backend gate: configured discovery runs contracts, server, and SQLite warehouse tests, including provider-free mocked LLM tests; only `research` is excluded. |
| Warehouse/API integration | `python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q` | Required only when persistence/read boundaries change |
| Frontend shipped bundle | `cd frontend-react && npm run lint && npm run test && npm run build` | Build/lint are unnecessary for an isolated backend change |
| Postgres/Timescale schema | Provision service, apply paired migrations, run manager/read smoke | CI exercises SQLite only |
| Performance equivalence | regression snapshot save/compare and relevant benchmark | Wall-clock/equivalence evidence is needed only for hot-path/performance claims |
| Compose startup boundary | `docker compose up --build -d --wait --wait-timeout 120` followed by `docker compose exec -T backend python -m backend.tools.integration.smoke_startup --url http://frontend --sqlite-path /app/runtime/ecosim.db` | Normal CI gate for Docker, proxy, startup, and default SQLite changes; it does not replace a real-browser or full-app evidence run. Clean its disposable data with `docker compose down --volumes`. |
| Whole application | `python -m backend.tools.integration.run_full_app_evidence ...` | Expensive Chrome/server/SQLite artifact harness; use for cross-stack or publication claims |
| Forecast confirm result | six-arm, 24-seed, 10k sweep and retained artifacts | Multi-hour research reproduction, not a code-edit smoke test |

The canonical commands and evidence limitations are detailed in [testing, CI, and performance](engineering/testing-performance.md). Return to the [quickstart](quickstart.md) for the complete concept map.
