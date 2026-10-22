<p align="center">
  <img src="frontend-react/public/ecosim.svg" alt="EcoSim" width="72">
</p>

<h1 align="center">EcoSim</h1>

<p align="center">
  An agent-based economy you can run, steer, and replay, built to test economic policy and LLM policymakers under controlled conditions.
</p>

<p align="center">
  <a href="https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml"><img src="https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT license"></a>
</p>

EcoSim simulates thousands of households (benchmarked at 10,000) plus firms, a bank, and a government in weekly ticks. Households look for work, earn, spend, borrow, and react to prices and policy. Firms hire, produce, set prices, invest, and close. The government taxes, pays benefits, and spends through a fixed set of policy levers. Labor, goods, housing, healthcare, and credit markets all run inside the same tick.

You change taxes, benefits, and subsidies from a live dashboard while the economy runs and watch both the macro picture (output, unemployment, prices, the government budget) and what happens to individual households and firms. You can also hand the government to an LLM and compare it against a rule-based baseline on the same seed. Every run is seeded, so the same configuration gives the same trajectory, and every tick can be saved to SQLite, PostgreSQL, or TimescaleDB for analysis.

![EcoSim Command view with macro metrics, stress signals, sector state, and chart history](docs/assets/dashboard-screenshot.png)

EcoSim started in Fall 2025 as a UC Berkeley club project that I led as project manager. I wrote the version we presented, and I have built everything in this repo since December 2025.

> [!NOTE]
> EcoSim is a synthetic research environment. It is not calibrated to a real economy. Use it for comparisons inside the model, not for real-world forecasts or policy advice. [docs/MODEL_SCOPE.md](docs/MODEL_SCOPE.md) explains what the model can and cannot support.

## Tech stack

| Layer | Tools |
|---|---|
| Simulation engine | Python 3.11, NumPy |
| Server | FastAPI, WebSockets, Pydantic |
| LLM government | LangGraph, with OpenRouter, Groq, LM Studio, or Ollama |
| Storage | SQLite, PostgreSQL, TimescaleDB |
| Dashboard | React 19, Vite, Tailwind, Recharts |
| Forecasting | pandas, scikit-learn (see `policy_forecasting/`) |
| Packaging and CI | Docker Compose, Nginx, GitHub Actions |
| Cloud batch runs | AWS EC2, S3, and IAM through the AWS CLI (see `ops/aws-runner/`) |

## Quickstart

You need Docker with Compose v2, and Docker must be running. The first build downloads images and dependencies.

```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
docker compose up --build -d --wait
```

Open http://localhost:5173, keep the defaults in Config, and click **Launch Simulation**. You do not need Python, Node.js, API keys, or a database. Docker runs two containers: the FastAPI backend on port 8002 inside the network, and an Nginx build of the dashboard that proxies `/ws` and `/health` to it. Runs are saved to SQLite in the `ecosim_runtime` volume.

Stop it with `docker compose down`. Your saved runs stay in the volume. To delete them too, run `docker compose down --volumes --rmi local`. More cleanup commands are in [docs/TECHNICAL.md](docs/TECHNICAL.md#docker-storage-cleanup).

If port 5173 is taken, run `ECOSIM_PORT=5183 docker compose up --build -d --wait` and open http://localhost:5183. If startup fails, check `docker compose ps -a` and `docker compose logs --tail 100`.

<details>
<summary>Run from source</summary>

You need Python 3.11 and Node.js 22 (22.22.2 or newer in the 22.x line).

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c backend/requirements.lock -e ".[ml]"
python -m uvicorn backend.server:app --reload --port 8002
```

In a second terminal:

```bash
cd frontend-react
npm ci
npm run dev
```

On Windows, create the environment with `py -3.11 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

Vite serves the dashboard on http://localhost:5173 and proxies `/ws` and `/health` to port 8002. Saving runs is off by default from source. Set `ECOSIM_ENABLE_WAREHOUSE=1` to turn it on.

</details>

## Using the dashboard

1. **Configure.** The dashboard opens in Config. Set the population size, seed, and starting tax and spending levels, then launch the run.
2. **Watch.** The Command view shows macro metrics, stress signals, sector state, and chart history as ticks stream in.
3. **Change policy.** The Government view holds the policy levers. Every change is checked against the policy schema and applies at the next tick boundary.
4. **Look closer.** Population follows tracked households, Markets shows sectors and firms, Finance shows credit and fiscal flows, and Logs shows the event stream.

To try the LLM government, set up a provider (see [Configuration](#configuration)), then turn on the Policy Assistant in Config before launch or the AI Policy Engine in the Government view during a run. It reads a short economic report on a fixed schedule and proposes changes inside the policy schema. If no provider is reachable, it turns itself off and the manual controls keep working.

A newer view for first-time users is in progress at http://localhost:5173/?view=next. You pick a question, run one to four towns side by side on the real simulation, pull levers, and compare what happens. `?view=next&demo` plays a recorded two-town demo without starting a run. The classic dashboard stays the default until the new view is finished.

<details>
<summary>More dashboard views</summary>

![Population view with tracked household state, wage reasoning, health, morale, and cash history](docs/assets/subjects-hologram.gif)

![Markets view with sector rollups, tracked firms, prices, wage offers, inventory, revenue, and profit](docs/assets/firms-screenshot.png)

![Government view with policy controls, LLM status, fiscal flow, and decision history](docs/assets/gov-screenshot.png)

</details>

## Architecture

```mermaid
flowchart TD
  UI["React dashboard"] -->|WebSocket commands and tick frames| API["FastAPI server"]
  API --> SM["Per-session simulation manager"]
  SM --> ECO["Economy tick loop"]
  ECO --> AG["Households, firms, bank, government"]
  SM --> WH["Warehouse: SQLite, PostgreSQL, TimescaleDB"]
  API -->|read-only HTTP analytics| WH
  LLM["Optional LLM government"] -->|validated policy proposals| SM
  PF["Policy forecasting package"] -.->|uses the engine as a library| ECO
```

Each WebSocket connection gets its own simulation and random number generator, up to `ECOSIM_MAX_SESSIONS` (default 8). One schema in `backend/policy_schema.py` defines every policy lever, and the dashboard, runtime updates, and the LLM government all go through it. Policy changes apply at the next tick boundary. LLM calls run outside the tick loop, invalid proposals are rejected before they reach the simulation, and each decision is recorded with its evidence, accepted and rejected changes, latency, and provider.

| Part | Where |
|---|---|
| Tick loop and agents | `backend/economy.py`, `backend/agents.py` |
| Policy schema | `backend/policy_schema.py` |
| Server and sessions | `backend/server.py` |
| Simulation parameters | `backend/config.py` |
| Storage and migrations | `backend/data/` |
| LLM government | `backend/tools/llm/` |
| Dashboard | `frontend-react/` |
| Forecasting | `policy_forecasting/` |
| AWS batch runner | `ops/aws-runner/` |

The WebSocket message format is documented in [docs/WEBSOCKET_PROTOCOL.md](docs/WEBSOCKET_PROTOCOL.md).

## Results

**Tick performance.** At 10,000 households, changes to consumption planning cut p95 backend tick time from 6,156 ms in the baseline run to a median of 4,000 ms across five later runs on the same seed (3,906 to 4,078 ms), about 35%. A separate three-seed set measured 4,125 to 4,703 ms (median 4,625 ms, about 25%), so expect a 25 to 35% cut on this machine. The baseline is a single run. A regression snapshot at 1,500 households matched the pre-change output within 1e-6. Browser JSON parsing stays at 0.3 ms p95, so the remaining cost is in the backend. These are local workstation numbers from a benchmark that drives the production dashboard build in Chrome and saves every tick to SQLite, with the LLM government off. Ledgers: [5-run](benchmarks/results/2026-06-08-5run-full-app-evidence-ledger.md), [3-seed](benchmarks/results/2026-06-08-3seed-full-app-evidence-ledger.md), [isolated benchmarks](benchmarks/results/2026-05-17-optimized-performance.md).

**LLM government comparison.** Five LLMs (Granite 4.1 8B, Gemma 4 26B, Llama 3.3 70B, GPT-OSS 120B, Ring 2.6 1T) and a rule-based baseline each governed the same 1,000-household economy for 200 ticks on seed 42, deciding every 26 ticks. The policymaker was the only thing that changed. Results: [docs/experiments/AI_GOVERNMENT_EXPERIMENT.md](docs/experiments/AI_GOVERNMENT_EXPERIMENT.md). Harness: [`backend/tools/llm/run_llm_government_test.py`](backend/tools/llm/run_llm_government_test.py).

**Policy forecasting.** Six policy arms ran across 24 matched seeds for 80 ticks at 10,000 households. A gradient-boosting model predicted unemployment eight ticks ahead with R² 0.924 (MAE 0.028) on held-out runs and beat the persistence baseline by 0.080 MAE. The consumer-distress model did not beat persistence. Numbers come from [policy_forecasting/RESULTS.md](policy_forecasting/RESULTS.md); the design is in [docs/POLICY_FORECASTING_V1.md](docs/POLICY_FORECASTING_V1.md). The raw sweep artifacts are not committed, so these numbers cannot be reproduced from the repo alone.

## Configuration

Runtime settings are environment variables, listed with defaults in [`.env.example`](.env.example). The ones you are most likely to change:

| Variable | Default | Purpose |
|---|---|---|
| `ECOSIM_ENABLE_WAREHOUSE` | `0` (`1` in Docker) | Save ticks to the warehouse |
| `ECOSIM_WAREHOUSE_BACKEND` | `sqlite` | `sqlite`, `postgres`, or `timescale` |
| `ECOSIM_WAREHOUSE_DSN` | `postgresql://ecosim:ecosim@localhost:5432/ecosim` | Postgres or TimescaleDB connection |
| `ECOSIM_MAX_SESSIONS` | `8` | Concurrent WebSocket sessions |
| `OPENROUTER_API_KEY`, `GROQ_API_KEY` | unset | Hosted LLM keys |

The LLM provider and the local LM Studio and Ollama endpoints are set in `LLMConfig` in [`backend/config.py`](backend/config.py), not in environment variables. The default provider is LM Studio at `http://127.0.0.1:8080`. A TimescaleDB Compose file is at [`ops/docker-compose.timescale.yml`](ops/docker-compose.timescale.yml).

## Development

```bash
python -m pip install -c backend/requirements.lock -c backend/requirements-test.lock -e ".[test,ml]"
python -m ruff check .
python -m pytest
```

Frontend:

```bash
cd frontend-react
npm ci
npm run lint
npm run test
npm run build
```

Forecasting tests use their own pins: `pip install -r policy_forecasting/requirements.txt` then `python -m pytest policy_forecasting/tests -q`. CI also builds the Docker stack and runs a startup probe (`backend/tools/integration/smoke_startup.py`). Before a refactor that should not change results, save a golden with [`backend/tools/benchmarks/regression_snapshot.py`](backend/tools/benchmarks/regression_snapshot.py) and compare against it afterward. More detail: [docs/testing/README.md](docs/testing/README.md).

[`ops/aws-runner/`](ops/aws-runner/README.md) runs the 1,000-household benchmark once on a temporary EC2 instance, verifies the results after an S3 round trip, and removes the compute and IAM resources afterward. Its README covers permissions, cost, and cleanup.

## Documentation

- [docs/SIMULATION.md](docs/SIMULATION.md): tick lifecycle, agents, markets, banking, LLM government
- [docs/TECHNICAL.md](docs/TECHNICAL.md): entry points, APIs, storage, file layout
- [docs/WEBSOCKET_PROTOCOL.md](docs/WEBSOCKET_PROTOCOL.md): commands, replies, and tick frames
- [docs/FRONTEND.md](docs/FRONTEND.md): dashboard views and runtime config
- [docs/DATA_STORAGE_ARCHITECTURE.md](docs/DATA_STORAGE_ARCHITECTURE.md): warehouse tables and write cadence
- [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md): tradeoffs
- [docs/MODEL_SCOPE.md](docs/MODEL_SCOPE.md): what the model can and cannot support
- [docs/README.md](docs/README.md): full documentation index

## Limits

The Compose stack is for one machine. It has no TLS, authentication, or rate limiting, so do not expose it publicly. The LLM government acts only through the policy schema on a fixed schedule, so the comparison says how models behave in EcoSim, not how they would govern in general. Interfaces and schemas may change between commits.

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
