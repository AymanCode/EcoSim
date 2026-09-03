<p align="center">
  <img src="frontend-react/public/ecosim.svg" alt="EcoSim" width="72">
</p>

<h1 align="center">EcoSim</h1>

<p align="center">
  Reproducible agent-based economic simulation for controlled policy experiments and AI-governance research.
</p>

<p align="center">
  <a href="https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml"><img src="https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT license"></a>
</p>

## Overview

EcoSim models households, firms, a bank, and a government interacting over weekly simulation ticks. Households search for work, earn, consume, borrow, and respond to prices and policy. Firms hire, produce, price, invest, and exit. The government taxes, transfers, and spends through a fixed set of policy levers. Runs are seeded and deterministic: the same configuration produces the same trajectory.

A FastAPI and WebSocket runtime streams live economic state to a React dashboard, where policy can be changed while the economy runs, and persists experiments to SQLite, PostgreSQL, or TimescaleDB.

Two extensions build on the simulator. An optional LLM government proposes bounded policy actions through the same validated schema the dashboard uses, which allows controlled comparisons between rule-based and model-driven policy. A separate forecasting package drives the simulator as a library to run matched-seed policy sweeps and report within-simulator treatment effects and forecast quality.

> [!NOTE]
> EcoSim is a synthetic research environment. It supports controlled within-simulator comparisons and mechanism exploration. It is not calibrated to a real economy and should not be used for real-world forecasting or policy recommendations. See [Project status](#project-status).

![EcoSim Command view showing macro metrics, stress signals, sector state, and live chart history](docs/assets/dashboard-screenshot.png)

## Contents

- [Capabilities](#capabilities)
- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [Usage](#usage)
- [Configuration](#configuration)
- [Performance and reproducibility](#performance-and-reproducibility)
- [Research](#research)
- [Development](#development)
- [Documentation](#documentation)
- [Project status](#project-status)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)

## Capabilities

- **Agent-based economy.** Labor matching, goods clearing, housing, healthcare, banking and credit, taxation, transfers, and sector-specific firm behavior share one tick lifecycle.
- **Interactive runtime.** Each WebSocket connection owns an isolated simulation with its own state and random number generator. Seven dashboard views cover configuration, macro metrics, tracked households, sector and firm state, credit and fiscal flows, government policy, and logs.
- **Validated policy interface.** One schema defines the government's action space for the dashboard, runtime updates, and LLM proposals: tax rates, benefit and minimum-wage levels, sector subsidies, public spending, price and rent stabilization, and bailouts. Accepted changes apply only at safe tick boundaries.
- **Optional LLM government.** Supports OpenRouter, Groq, LM Studio, and Ollama. Model calls run outside the tick loop, invalid proposals are rejected before they reach the simulation, and every decision records its evidence, accepted and rejected changes, latency, provider, and resulting state.
- **Experiment persistence.** SQLite, PostgreSQL, or TimescaleDB backends store run metadata, per-tick metrics, snapshots, events, policy actions, diagnostics, and LLM decisions, with a read-only HTTP API for analysis.
- **Reproducible research.** Seeded runs, deterministic regression snapshots, matched-seed policy sweeps, and a forecasting pipeline with paired statistical tests.

## Quickstart

Requires Docker Engine with Compose v2.

```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
docker compose up --build -d --wait
```

Open http://localhost:5173. No local Python or Node.js installation is required.

The stack runs two containers: a FastAPI backend and an Nginx-served React build that proxies `/ws` and `/health` to it. SQLite persistence is enabled by default in the `ecosim_runtime` volume.

<details>
<summary>Run from source</summary>

Requires Python 3.11 or later, Node.js 22, and npm. Start the backend from the repository root:

```bash
python -m pip install -c backend/requirements.lock -e ".[dev,ml]"
python -m uvicorn backend.server:app --reload --port 8002
```

Start the dashboard in a second terminal:

```bash
cd frontend-react
npm ci
npm run dev
```

Vite serves the dashboard on http://localhost:5173 and proxies `/ws` and `/health` to the backend on port 8002. Persistence is off by default when running from source; see [Configuration](#configuration) to enable it.

</details>

## Architecture

```mermaid
flowchart TD
  subgraph runtime["Interactive runtime"]
    UI["React dashboard"] -->|WebSocket commands and frames| API["FastAPI server"]
    API --> SM["Per-session simulation manager"]
    SM --> ECO["Economy tick lifecycle"]
    ECO --> AG["Households, firms, government, bank"]
    SM --> WH["Warehouse: SQLite, PostgreSQL, TimescaleDB"]
    API -->|read-only analytics| WH
    LLM["Optional LLM government advisor"] -->|validated policy proposals| SM
  end
  subgraph research["Offline research"]
    EVAL["LLM evaluation harness"] --> ART["Reports and run artifacts"]
    PF["Policy forecasting package"] --> DS["Datasets and model results"]
  end
  EVAL -.-> ECO
  PF -.-> ECO
```

Dotted edges: the offline research tools drive the simulation engine as a library rather than through the server.

| Component | Location | Responsibility |
|---|---|---|
| Simulation engine | `backend/economy.py`, `backend/agents.py` | Tick lifecycle, market clearing, agent decisions, institutions |
| Policy schema | `backend/policy_schema.py` | Canonical government action space shared by all policy paths |
| Server | `backend/server.py` | REST and WebSocket API, session lifecycle, telemetry, LLM scheduling, warehouse batching |
| Configuration | `backend/config.py` | Frozen dataclass configuration tree, including LLM provider settings |
| Warehouse | `backend/data/` | Persistence managers, schemas, migrations |
| LLM tooling | `backend/tools/llm/` | Provider adapters, government advisor, evaluation harness |
| Dashboard | `frontend-react/` | React 19 and Vite application served by Nginx in Docker |
| Forecasting | `policy_forecasting/` | Matched-seed sweeps, dataset construction, models, evaluation |

## Usage

1. **Configure.** The dashboard opens in the Config view. Set the population size, simulation seed, and initial tax and spending levels, then initialize the run.
2. **Run.** The Command view shows macro metrics, stress signals, sector state, and chart history as ticks stream in.
3. **Adjust policy.** The Government view exposes the policy levers. Changes are validated against the policy schema and applied at the next tick boundary.
4. **Inspect.** The Population, Markets, and Finance views show tracked households, firms, and credit and fiscal flows. The Logs view shows the event stream.

To use the LLM government, configure a provider (see [Configuration](#configuration)), then enable the Policy Assistant in the Config view before initializing or the AI Policy Engine in the Government view during a run. The advisor reads a compact economic report on a fixed schedule and proposes changes within the policy schema. The Government view shows its status, latest decision, and accepted and rejected changes. If no provider is reachable, the feature disables itself and manual controls remain available.

<details>
<summary>More dashboard views</summary>

![Population view with tracked household state, wage reasoning, health, morale, and cash history](docs/assets/subjects-hologram.gif)

![Markets view with sector rollups, tracked firms, prices, wage offers, inventory, revenue, and profit](docs/assets/firms-screenshot.png)

![Government view with policy controls, LLM status, fiscal flow, and decision history](docs/assets/gov-screenshot.png)

</details>

## Configuration

All settings are environment variables. [`.env.example`](.env.example) lists every option with its default. The most commonly changed settings:

| Variable | Default | Purpose |
|---|---|---|
| `ECOSIM_ENABLE_WAREHOUSE` | `0` (`1` in Docker) | Persist completed ticks to the warehouse |
| `ECOSIM_WAREHOUSE_BACKEND` | `sqlite` | `sqlite`, `postgres`, or `timescale` |
| `ECOSIM_SQLITE_PATH` | `backend/data/ecosim.db` | SQLite database path |
| `ECOSIM_WAREHOUSE_DSN` | `postgresql://ecosim:ecosim@localhost:5432/ecosim` | PostgreSQL or TimescaleDB connection string |
| `ECOSIM_MAX_SESSIONS` | `8` | Maximum concurrent WebSocket sessions |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed dashboard origins |
| `OPENROUTER_API_KEY`, `GROQ_API_KEY` | unset | Hosted LLM provider credentials |
| `OPENROUTER_MODEL` | `inclusionai/ring-2.6-1t:free` | Model used through OpenRouter |
| `ECOSIM_LABOR_MATCH_MODE` | `fast` | `fast` (optimized matcher) or `legacy` |

LLM provider selection and the local LM Studio and Ollama endpoints are fields of `LLMConfig` in [`backend/config.py`](backend/config.py); the default provider is LM Studio. A TimescaleDB Compose file is provided at [`ops/docker-compose.timescale.yml`](ops/docker-compose.timescale.yml).

## Performance and reproducibility

Seeded runs are deterministic. A regression-snapshot tool compares aggregate, firm, and sampled household state against a saved golden at fixed ticks with a tolerance of 1e-6, and the stable test suite covers simulation contracts, server sessions, and warehouse behavior.

The end-to-end benchmark drives the production React build through Chrome, streams state over WebSocket, and persists every tick to SQLite, with the LLM government excluded. At 10,000 households, consumption-planning optimizations reduced p95 backend tick compute from 6,156 ms to 4,000 ms, a 35% reduction, without changing simulation outputs. The 3-seed median p95 is 4,625 ms, and browser JSON parse stays at 0.3 ms p95, so the remaining cost is in the backend. All figures are local workstation measurements.

Run ledgers: [5-run](benchmarks/results/2026-06-08-5run-full-app-evidence-ledger.md), [3-seed](benchmarks/results/2026-06-08-3seed-full-app-evidence-ledger.md). Isolated engine, warehouse, and browser benchmarks: [2026-05-17 report](benchmarks/results/2026-05-17-optimized-performance.md). Evidence standard: [docs/testing/full_app_evidence_test.md](docs/testing/full_app_evidence_test.md).

## Research

### AI-governance evaluation

Five LLMs and a rule-based baseline governed the same 1,000-household economy through the policy schema. Each run used seed 42, 10 warmup ticks, and 200 simulation ticks, with the first LLM decision at tick 15 and one decision every 26 ticks thereafter. The policymaker was the only variable.

| Government | Provider |
|---|---|
| Rule-based baseline | None |
| Granite 4.1 8B | LM Studio (local) |
| Gemma 4 26B | LM Studio (local) |
| Llama 3.3 70B | Groq |
| GPT-OSS 120B | Groq |
| Ring 2.6 1T | OpenRouter |

Results, per-model governing profiles, and decision-quality metrics: [docs/experiments/AI_GOVERNMENT_EXPERIMENT.md](docs/experiments/AI_GOVERNMENT_EXPERIMENT.md). Harness: [`backend/tools/llm/run_llm_government_test.py`](backend/tools/llm/run_llm_government_test.py). The protocol for a reusable benchmark, including claim boundaries, baselines, and scoring, is a draft: [docs/evals/ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md](docs/evals/ECOSIM_LLM_ECONOMIC_GOVERNANCE_EVAL_PROTOCOL.md).

### Policy forecasting

Policy Forecasting V1 ran six frozen policy arms across 24 matched seeds for 80 ticks each at 10,000 households, then trained models to predict unemployment and consumer distress eight ticks ahead with leakage-safe labels and held-out runs. The gradient-boosting unemployment model reached R² 0.924 (MAE 0.028) on held-out runs and beat the persistence baseline by 0.080 MAE. The consumer-distress target did not outperform persistence.

The reported figures come from [policy_forecasting/RESULTS.md](policy_forecasting/RESULTS.md). The raw sweep and model artifacts behind that report are not checked into the repository, so the numbers are attributed to the report rather than reproducible from the committed tree. Design rationale: [docs/POLICY_FORECASTING_V1.md](docs/POLICY_FORECASTING_V1.md). Dataset contract: [docs/POLICY_FORECASTING_SCHEMA.md](docs/POLICY_FORECASTING_SCHEMA.md).

## Development

Install the backend with development and ML extras:

```bash
python -m pip install -c backend/requirements.lock -e ".[dev,ml]"
```

Run the checks that CI runs:

```bash
python -m ruff check .
python -m pytest backend/tests_server -q
python -m pytest backend/tests_contracts -q -m "not llm and not research"
python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
```

Forecasting package tests use their own pinned requirements:

```bash
python -m pip install -r policy_forecasting/requirements.txt
python -m pytest policy_forecasting/tests -q
```

Frontend checks:

```bash
cd frontend-react
npm ci
npm run lint
npm run test
npm run build
```

A bare `python -m pytest` discovers only `backend/tests_contracts`. Name the server, warehouse, and forecasting paths explicitly. Tests marked `llm` or `research` depend on a provider or are exploratory and are excluded from the stable gate. Benchmarks and the full-application evidence harness do not run in CI.

## Documentation

| Document | Contents |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/MODEL_SCOPE.md](docs/MODEL_SCOPE.md) | Intended uses, assumptions, and interpretation rules |
| [docs/SIMULATION.md](docs/SIMULATION.md) | Tick lifecycle, agents, markets, policy, banking, LLM government |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | Stack, entry points, API surfaces, warehouse, validation, file structure |
| [docs/FRONTEND.md](docs/FRONTEND.md) | Dashboard views, WebSocket contract, runtime configuration |
| [docs/DATA_STORAGE_ARCHITECTURE.md](docs/DATA_STORAGE_ARCHITECTURE.md) | Warehouse design, tables, write cadence, read paths |
| [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) | Engineering choices and tradeoffs |

## Project status

The core simulator and dashboard are functional research software at version 2.0.0. The five-model AI-governance case study is complete. The reusable LLM governance benchmark protocol is a draft. Interfaces and schemas may change between commits.

- **Within-simulator claims only.** Deterministic replay and matched seeds support controlled comparisons inside the model. They do not support real-world forecasts, causal estimates, or policy recommendations.
- **Bounded AI governance.** The LLM government acts through a restricted schema on a fixed schedule. The evaluation compares models under EcoSim dynamics and does not establish general governance ability.
- **Local deployment.** The Compose stack is a single-host development topology. It has no TLS, authentication, or rate limiting and is not intended for public exposure.

## Contributing

Issues and pull requests are welcome. Before opening a pull request, run the backend, forecasting, and frontend checks listed under [Development](#development). Changes to the WebSocket protocol, warehouse schema, or policy schema should update the corresponding tests and documentation.

## Citation

```bibtex
@software{islam2026ecosim,
  author = {Islam, Ayman},
  title = {EcoSim: Agent-based economic simulator with bounded AI-governance experiments},
  year = {2026},
  url = {https://github.com/AymanCode/EcoSim},
  version = {2.0.0}
}
```

## License

MIT. See [LICENSE](LICENSE).
