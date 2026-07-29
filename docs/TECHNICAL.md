# Technical Guide

This guide describes the active EcoSim implementation. Source code and runtime configuration are the authority; archived docs and inline comments may lag the code.

## Stack

| Layer | Current implementation |
|---|---|
| Simulation | Python 3.11, dataclasses, NumPy |
| API | FastAPI, WebSocket, Uvicorn |
| Frontend | React 19, Vite, Recharts, Tailwind CSS, lucide-react |
| Persistence | SQLite by default for Docker/local warehouse, PostgreSQL/Timescale optional |
| LLM tooling | LangGraph/LangChain Core orchestration with LM Studio, Ollama, Groq, and OpenRouter provider paths |
| Tests | pytest, pytest-asyncio, contract and integration suites, frontend Vitest/ESLint/build |
| Packaging | Docker Compose for the full stack |

## Entry Points

| File | Responsibility |
|---|---|
| [`backend/server.py`](../backend/server.py) | FastAPI app, WebSocket protocol, live run lifecycle, LLM scheduling, warehouse batching, REST read endpoints |
| [`backend/economy.py`](../backend/economy.py) | Tick lifecycle, market clearing, labor matching, housing, healthcare, banking, firm lifecycle, diagnostics |
| [`backend/agents.py`](../backend/agents.py) | Household, firm, bank, and government agent state and decision methods |
| [`backend/config.py`](../backend/config.py) | Frozen dataclass configuration tree and default simulation parameters |
| [`backend/policy_schema.py`](../backend/policy_schema.py) | Canonical policy action space for UI, runtime updates, and LLM government validation |
| [`frontend-react/src/App.jsx`](../frontend-react/src/App.jsx) | Dashboard state, WebSocket client, view rendering, runtime controls |
| [`backend/data/warehouse_factory.py`](../backend/data/warehouse_factory.py) | Warehouse backend selection |

## Runtime Flow

The browser connects to the backend over `/ws`. Each connection receives a session ID and its own `SimulationManager`, configuration snapshot, random-number state, economy, and lifecycle. A run starts with `SETUP`, then `START` launches that session's tick loop. The manager applies pending runtime config updates at safe tick boundaries, calls `Economy.step()`, builds a compact dashboard payload, and streams it back to that client. The session registry enforces a bounded connection count and removes state when a socket closes.

When the warehouse is enabled, the server buffers aggregate metrics, sector metrics, snapshots, events, diagnostics, policy actions, and LLM decision rows. Flushes are batched rather than committed per row.

When the LLM government is enabled, the server snapshots the economy at configured decision ticks, runs the provider call in a background task, keeps the simulation ticking, and applies accepted policy changes before the next economy step.

## WebSocket Protocol

Endpoint: `ws://localhost:8002/ws`

Accepted commands:

| Command | Purpose |
|---|---|
| `SETUP` | Initialize a new economy. Validated config includes `num_households`, `num_firms`, `seed`, `enable_llm_government`, `disable_stabilizers`, and `disabled_agents`. |
| `START` | Start or resume the tick loop. |
| `STOP` | Pause the tick loop and flush warehouse buffers. |
| `RESET` | Stop the run, close the warehouse run as stopped, and reset server tick state. |
| `CONFIG` | Queue runtime-safe policy/config updates. |
| `STABILIZERS` | Toggle household, firm, government, or all automatic stabilizers. |

The server first sends `SESSION` with the connection's session ID. Other messages include `SETUP_COMPLETE`, `STARTED`, `STOPPED`, `RESET`, `STABILIZERS_UPDATED`, errors, and tick payloads containing `metrics`, `firm_stats`, and `logs`.

## REST Surfaces

Core endpoints:

- `GET /health`
- `GET /decision-context/live?session_id={session_id}&window=20`
- `GET /warehouse/runs`
- `GET /warehouse/compare?run_ids=run_a&run_ids=run_b`
- `GET /warehouse/runs/{run_id}/summary`
- `GET /warehouse/runs/{run_id}/tick-metrics`
- `GET /warehouse/runs/{run_id}/decision-features`
- `GET /warehouse/runs/{run_id}/llm-government-decisions`
- `GET /warehouse/runs/{run_id}/tick-diagnostics`
- `GET /warehouse/runs/{run_id}/sector-metrics`
- `GET /warehouse/runs/{run_id}/sector-shortages`
- `GET /warehouse/runs/{run_id}/regime-events`
- `GET /warehouse/runs/{run_id}/policy-context`

Warehouse endpoints return `503` if the warehouse layer is unavailable in the current environment.

## Policy Surface

[`backend/policy_schema.py`](../backend/policy_schema.py) is the source of truth for validated government policy actions.

Continuous tax levers:

- `wage_tax_rate`: `0.0` to `0.50`, max change `0.05` per LLM decision
- `profit_tax_rate`: `0.0` to `0.50`, max change `0.05` per LLM decision
- `investment_tax_rate`: `0.0` to `0.30`, max change `0.05` per LLM decision

Discrete levers:

- `benefit_level`: `low`, `neutral`, `high`, `crisis`
- `public_works`: `off`, `on`
- `minimum_wage_policy`: `low`, `neutral`, `high`
- `sector_subsidy_target`: `none`, `food`, `housing`, `services`, `healthcare`
- `sector_subsidy_level`: `0`, `10`, `25`, `50`
- `price_stabilization_target`: `none`, `food`, `services`, `healthcare`
- `price_stabilization_level`: `off`, `monitor`, `soft`, `strict`
- `rent_stabilization_level`: `off`, `monitor`, `soft`, `strict`
- `infrastructure_spending`, `technology_spending`, `social_spending`: `none`, `low`, `medium`, `high`
- `bailout_policy`: `off`, `sector`, `all`
- `bailout_target`: `none`, `food`, `housing`, `services`, `healthcare`
- `bailout_budget`: `0`, `5000`, `10000`, `25000`, `50000`

The frontend still exposes some legacy-style sliders such as minimum wage and unemployment benefit rate. The server maps those controls onto the schema levers before applying them.

## Persistence

Direct local backend runs default to no warehouse unless `ECOSIM_ENABLE_WAREHOUSE=1` is set. Docker Compose enables SQLite persistence at `/app/runtime/ecosim.db`.

Supported backends:

- `sqlite`
- `postgres`
- `timescale`

Key environment variables:

```env
ECOSIM_ENABLE_WAREHOUSE=1
ECOSIM_WAREHOUSE_BACKEND=sqlite
ECOSIM_SQLITE_PATH=backend/data/ecosim.db
ECOSIM_WAREHOUSE_DSN=postgresql://ecosim:ecosim@localhost:5432/ecosim
ECOSIM_TICK_BATCH_SIZE=50
ECOSIM_SNAPSHOT_BATCH_SIZE=5000
ECOSIM_HOUSEHOLD_SNAPSHOT_STRIDE=5
ECOSIM_DECISION_CONTEXT_WINDOW=40
```

See [DATA_STORAGE_ARCHITECTURE.md](DATA_STORAGE_ARCHITECTURE.md) and [`backend/data/README.md`](../backend/data/README.md) for schema and migration details.

## LLM Government

The live LLM government is optional and disabled by default. It uses the same policy schema as manual runtime controls. Provider setup is selected by available environment and config.

Common provider variables:

```env
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
GROQ_API_KEY=...
LMSTUDIO_BASE_URL=http://127.0.0.1:1234
OLLAMA_BASE_URL=http://localhost:11434
```

The harness validates JSON, rejects malformed or out-of-range actions, limits substantive changes, tracks accepted/rejected changes, and persists full decision records when the warehouse is enabled.

## Dependency Reproducibility

`pyproject.toml` defines supported dependency ranges. `backend/requirements.lock` pins the backend and warehouse runtime used by Docker and can be supplied as a constraints file for local development. The forecasting package keeps its separate, frozen research environment in `policy_forecasting/requirements.txt`; the frontend is pinned by `frontend-react/package-lock.json`.

## Performance Notes

The hot path stays in memory. Database writes are buffered. The backend uses NumPy for labor and consumption paths where practical, caches selected metrics on a stride in the server loop, and supports `ECOSIM_LABOR_MATCH_MODE=fast` for the optimized matcher.

High-scale run controls:

```env
ECOSIM_LABOR_MATCH_MODE=fast
ECOSIM_COMPARE_LABOR_MATCH=0
ECOSIM_LABOR_DIAGNOSTICS=0
ECOSIM_FORCE_UNEMPLOYED_SEARCH=1
ECOSIM_CLAMP_UNEMPLOYED_RESERVATION=1
ECOSIM_UNEMPLOYED_CLAMP_TICKS=8
```

## Validation Commands

Stable backend:

```bash
python -m pip install -c backend/requirements.lock -e ".[dev,ml]"
python -m pytest backend/tests_contracts backend/tests_server -q -m "not llm and not research"
```

Warehouse/API:

```bash
python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
```

LLM and research-marked contracts:

```bash
python -m pytest backend/tests_contracts -q -m "llm or research"
```

Frontend:

```bash
cd frontend-react
npm ci
npm run lint
npm run test
npm run build
```

## File Structure

```text
EcoSim/
|-- backend/
|   |-- agents.py              household, firm, bank, and government agents
|   |-- economy.py             tick coordinator and market logic
|   |-- config.py              simulation parameters
|   |-- policy_schema.py       government action-space schema
|   |-- server.py              FastAPI + WebSocket entrypoint
|   |-- data/                  warehouse models, managers, schemas, migrations
|   |-- tools/                 benchmarks, LLM runners, analysis, checks
|   |-- tests_contracts/       contract-style simulation tests
|   `-- tests_server/          API and live-server tests
|-- frontend-react/            dashboard application
|-- docs/                      active technical documentation
|-- experiments/               experiment reports and artifacts
|-- benchmarks/                benchmark results
`-- ops/                       optional infrastructure files
```
