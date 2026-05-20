# EcoSim

[![CI](https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml/badge.svg)](https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135%2B-009688?logo=fastapi&logoColor=white)](requirements.txt)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](frontend-react/package.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

EcoSim is an agent-based macroeconomic sandbox for testing how households, firms, a bank, and government policy interact over weekly simulation ticks. It models labor, goods, housing, healthcare, credit, taxes, transfers, live dashboards, LLM-guided policy experiments, deterministic policy stress tests, forecasting workflows, and optional warehouse persistence.

You can run a rule-based economy, change policy levers live from the dashboard, or enable the AI Policy Engine so an LLM can propose bounded government actions through the same validated policy schema used by the UI and backend.

| Track | What it shows | Start here |
|---|---|---|
| Live simulation | Households, firms, markets, fiscal policy, and banking evolving in real time | [Quickstart](#quickstart) |
| AI policy experiments | Five LLM governments compared against a rule-based baseline in the same 1,000-household economy | [Can an AI run an economy?](experiments/llm_government_1k/LLM_RESULTS.md) |
| Policy forecasting | Deterministic 10,000-household sweeps for matched-seed policy effects and leakage-safe unemployment forecasting | [Policy Forecasting V1](policy_forecasting/RESULTS.md) |

## Dashboard

The React dashboard opens in the Config view and streams live simulation state from the backend over WebSocket.

![Live macro dashboard during a rule-based run](docs/assets/dashboard-screenshot.png)
*Command view: macro metrics, stress signals, sector state, and live chart history.*

![Per-subject view with rotating wireframe avatar](docs/assets/subjects-hologram.gif)
*Population view: tracked household state, wage reasoning, health, morale, traits, and cash history.*

![Firm view with sector breakdown and tracked firms](docs/assets/firms-screenshot.png)
*Markets view: sector rollups, tracked firms, prices, wage offers, inventory, revenue, and profit.*

![Government policy panel with sliders and fiscal flow](docs/assets/gov-screenshot.png)
*Government console: manual policy controls, LLM status, fiscal flow, and policy decision history.*

## Model

Each tick represents roughly one simulated week:

- Households search for work, accept jobs, earn wages or transfers, pay taxes, buy food, housing, services, and healthcare, and update health, happiness, morale, skills, expectations, cash, deposits, and debt.
- Firms plan production, wages, prices, hiring, layoffs, capital investment, unit expansion, and quality/R&D. Private firms compete by sector; baseline firms provide a safety-net floor.
- The bank, when present, handles deposits, interest, credit scores, loan origination, repayments, defaults, and reserve-limited lending.
- The government collects wage/profit/property/investment taxes, pays transfers and subsidies, funds public works and investments, tracks fiscal pressure, and applies validated policy levers.
- The server streams aggregate metrics, tracked household/firm details, policy state, logs, and LLM government status to the frontend.

The main runtime sequence is implemented in [`backend/economy.py`](backend/economy.py). The API and streaming lifecycle are implemented in [`backend/server.py`](backend/server.py).

## Highlights

| Capability | Why it matters |
|---|---|
| Agent-based economy | Households, firms, government, banking, housing, healthcare, labor matching, goods clearing, and sector-specific firm behavior run in one tick lifecycle. |
| Live dashboard | React/Vite views for configuration, command metrics, population details, markets, finance, government policy, and logs. |
| Validated policy surface | [`backend/policy_schema.py`](backend/policy_schema.py) defines the government action space shared by the UI, runtime updates, and LLM government harness. |
| Optional LLM government | Provider calls run in the background, and accepted decisions apply only at safe tick boundaries. |
| Experiment warehouse | SQLite, PostgreSQL, or TimescaleDB can store run metadata, metrics, snapshots, events, policy actions, diagnostics, and full LLM decisions. |
| Forecasting package | [`policy_forecasting`](policy_forecasting) imports the simulator read-only, runs matched-seed policy sweeps, builds t+8 datasets, and reports policy effects with paired statistical tests. |
| Regression coverage | Contract-style backend tests plus frontend lint and build checks guard the main simulation and UI paths. |

## Performance

EcoSim's primary benchmark is a saturated weekly market simulation with 10,000 autonomous consumer agents and roughly 300 firm agents. Each tick advances labor matching, production, consumer choice, market clearing, banking, housing, healthcare, taxes, transfers, firm lifecycle, and wellbeing updates.

These are local workstation benchmarks, not hosted production-capacity claims.

| Area | 10k-agent workload | Throughput / latency | Event volume |
|---|---|---:|---:|
| Simulation engine | 3 deterministic seeds, 123 saturated-market ticks | `3.65s` p50 tick, `5.58s` p95 tick, `14.84` simulated weeks/min | `~160k` purchase events/tick |
| SQLite analytics warehouse | 3 runs, 600 ticks persisted | `49.94k` rows/sec, `0.36%` mean write overhead, `0.43 ms` p95 summary query | `421,328` analytical rows, `187.5 MB` SQLite DB |
| React dashboard browser | 10k-agent Chrome session, 100 live tick messages | `0.30 ms` p95 JSON parse, `57.7 ms` p95 next-frame latency, `1.64s` LCP | `4.05 MB` streamed, `47.9 KB` p95 payload |

Benchmark takeaways:

- Built a Python/FastAPI agent-based macroeconomic simulator that advances 10,000 autonomous consumers and hundreds of firms through labor, goods, banking, housing, healthcare, and policy markets at `3.65s` p50 tick latency.
- Designed a SQLite analytics warehouse for simulation experiments, persisting `421k+` analytical rows at `49.94k rows/sec` with `0.36%` mean tick-loop write overhead.
- Benchmarked a live React dashboard for 10k-agent simulations, streaming `100` tick updates with `47.9 KB` p95 payloads, `0.30 ms` p95 JSON parse time, and `57.7 ms` p95 next-frame latency.

Full methodology and artifacts are in [`benchmarks/results/2026-05-17-optimized-performance.md`](benchmarks/results/2026-05-17-optimized-performance.md).

## Policy Forecasting

Policy Forecasting V1 turns the simulator into a controlled data science workload. One frozen 10,000-household sweep dataset feeds two linked analyses: matched-seed policy-effect estimates and an 8-tick-ahead unemployment forecasting benchmark. The forecasting package lives outside the simulator core and imports `backend/` read-only, so the experiment measures EcoSim behavior without editing the base model. It also includes a small Streamlit demo for loading saved policy predictions and comparing t+8 unemployment and distress deltas against baseline.

This is simulator system identification, not a real-world macroeconomic forecast. The validity claim rests on deterministic replay, matched seeds, leakage-safe labels, held-out seeds, held-out policy lever vectors, and baseline comparisons.

| Area | Result |
|---|---:|
| Confirmatory sweep | `6` frozen policy arms x `24` matched seeds x `80` ticks |
| Raw sweep rows | `11,520` per-tick rows |
| Supervised forecasting rows | `10,368` rows (`6,480` train / `1,728` held-out final) |
| Determinism gate | `hash_equal=True`, `max_abs_delta=0.0` across fresh-process 10k baseline replicates |
| Best model | Gradient boosting on `unemployment@t+8` |
| Forecast quality | `R2=0.924`, `MAE=0.028` |
| Baseline lift | `+0.080` MAE vs policy-aware persistence, 95% CI `[0.056, 0.107]` |
| Negative result | `consumer_distress@t+8` did not beat persistence |
| Model interpretation | `gdp_ma4` was the dominant unemployment signal, about `10x` the next feature |

Matched-seed policy effects are paired against baseline with Wilcoxon signed-rank tests and Holm correction. Within the simulator, high minimum wage reduced `unemployment@t+8` by `0.021` and distress by `0.026`; high benefits increased `unemployment@t+8` by `0.073`; high wage tax increased distress by `0.040`; food subsidy reduced distress by `0.012`; high profit tax showed no detectable household effect in this sweep.

Forecasting takeaway:

- Built a leakage-safe policy forecasting and matched-seed experiment pipeline on a deterministic 10,000-household economic simulator, forecasting 8-tick-ahead unemployment at `R2=0.924` and beating a policy-aware persistence baseline by `0.080` MAE on held-out seeds and unseen policy lever vectors.

Full methodology, results, and reproduction commands are in [`policy_forecasting/RESULTS.md`](policy_forecasting/RESULTS.md). The design rationale is in [`docs/POLICY_FORECASTING_V1.md`](docs/POLICY_FORECASTING_V1.md), with the frozen feature contract in [`docs/POLICY_FORECASTING_SCHEMA.md`](docs/POLICY_FORECASTING_SCHEMA.md).

## Quickstart

Run the full stack with Docker. This builds the backend, frontend, and default SQLite-backed runtime.

macOS / Linux:

```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
./start.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
.\start.ps1
```

Plain Docker:

```bash
docker compose up --build -d --wait
```

Open `http://localhost:5173`. The frontend proxies `/ws` and `/health` to the backend inside Docker.

## Local Development

Backend:

```bash
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.server:app --reload --port 8002
```

On macOS/Linux, activate the virtual environment with `source .venv/bin/activate`.

Frontend:

```bash
cd frontend-react
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `ws://localhost:5173/ws` and `/health` to the backend on port `8002`.

## Testing

Stable backend gate:

```bash
pip install -r requirements-dev.txt
python -m pytest backend/tests_contracts backend/tests_server -q -m "not llm and not research"
```

Warehouse and API coverage:

```bash
python -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
```

LLM and research-marked backend tests:

```bash
python -m pytest backend/tests_contracts -q -m "llm or research"
```

Frontend:

```bash
cd frontend-react
npm ci
npm run lint
npm run build
```

## Configuration

The Docker stack enables SQLite warehouse persistence in `/app/runtime/ecosim.db`. Direct local backend runs leave persistence off unless enabled explicitly:

```env
ECOSIM_ENABLE_WAREHOUSE=1
ECOSIM_WAREHOUSE_BACKEND=sqlite
ECOSIM_SQLITE_PATH=backend/data/ecosim.db
```

PostgreSQL or TimescaleDB:

```env
ECOSIM_WAREHOUSE_BACKEND=postgres
ECOSIM_WAREHOUSE_DSN=postgresql://ecosim:ecosim@localhost:5432/ecosim
```

LLM government providers are optional. The live simulation remains usable without one.

```env
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
LMSTUDIO_BASE_URL=http://127.0.0.1:1234
OLLAMA_BASE_URL=http://localhost:11434
```

Labor matching and unemployment guardrails can be configured with:

```env
ECOSIM_LABOR_MATCH_MODE=fast
ECOSIM_FORCE_UNEMPLOYED_SEARCH=1
ECOSIM_CLAMP_UNEMPLOYED_RESERVATION=1
ECOSIM_UNEMPLOYED_CLAMP_TICKS=8
```

## Architecture

```mermaid
flowchart TD
  frontend["frontend-react<br/>React + Vite + Recharts"]
  websocket["WebSocket<br/>/ws"]
  rest["REST reads<br/>/health, /decision-context/live, /warehouse/..."]
  server["backend/server.py<br/>FastAPI, run lifecycle, streaming, warehouse batching"]
  economy["backend/economy.py<br/>tick coordinator and market clearing"]
  agents["backend/agents.py<br/>household, firm, bank, government agents"]
  policy["backend/policy_schema.py<br/>validated policy action space"]
  warehouse["backend/data<br/>SQLite/PostgreSQL/Timescale warehouse"]
  tools["backend/tools<br/>LLM runners, benchmarks, analysis, diagnostics"]
  forecasting["policy_forecasting<br/>matched-seed sweeps and t+8 forecasting"]
  artifacts["experiments + benchmarks<br/>reports and reproducible artifacts"]

  frontend --> websocket --> server --> economy --> agents
  frontend --> rest --> server
  server --> warehouse
  server --> policy
  tools --> economy
  tools --> policy
  tools --> artifacts
  forecasting --> economy
  forecasting --> artifacts
```

## Repository Layout

```text
backend/                  simulation engine, API, persistence, tools, tests
  agents.py               household, firm, bank, and government agents
  economy.py              tick lifecycle, markets, healthcare, banking, policy flow
  server.py               FastAPI REST/WebSocket API and live run manager
  policy_schema.py        canonical government policy action space
  config.py               frozen dataclass configuration tree
  data/                   warehouse managers, schemas, migrations, data tests
  tools/                  LLM, benchmark, analysis, and runner utilities
  tests_contracts/        simulation contract and regression tests
  tests_server/           API and live-server tests

frontend-react/           React dashboard
docs/                     active project documentation
policy_forecasting/       matched-seed policy sweeps and forecasting pipeline
experiments/              LLM government run artifacts and reports
benchmarks/               benchmark result artifacts
ops/                      optional infrastructure
```

Start with [docs/README.md](docs/README.md) for the full documentation index.

## License

MIT. See [LICENSE](LICENSE).

Built by Ayman. GitHub: [AymanCode](https://github.com/AymanCode)
