# EcoSim

[![CI](https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml/badge.svg)](https://github.com/AymanCode/EcoSim/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135%2B-009688?logo=fastapi&logoColor=white)](requirements.txt)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](frontend-react/package.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A macroeconomic simulation built from the agent up. Households, firms, a bank, and a government interact across a labor market, a goods market, a housing market, a healthcare queue, and a credit system. There's a live React dashboard, a streaming API, and an optional warehouse for run history.

You can run it as a policy sandbox. Change taxes, subsidies, wage floors, or social spending and watch the economy react. Or plug an LLM into the government's seat and see what the model does with the same controls.

> **Featured experiment:** [Can an AI run an economy?](llm_run_outputs_smoke/LLM_RESULTS.md). I compared five LLMs plus a rule-based baseline on the current **1,000-household** run, from an 8B local model to an experimental 1T model, under the same schema-validated government policy controls. The underlying question wasn't only whether an AI could do it, but whether more parameters and more "thinking power" translated into better governance. Short answer: yes, kind of. Long answer is more interesting.

---

## Views

Four panes share the same simulation state and update live as the model ticks.

![Live macro dashboard during a rule-based run](docs/assets/dashboard-screenshot.png)
*Dash. Macro metrics streamed over WebSocket. Shown mid-run on a rule-based baseline, system distress firing as the economy strains.*

![Per-subject view with rotating wireframe avatar](docs/assets/subjects-hologram.gif)
*Subjects. Per-household drill-down with wage drivers, traits, and inventory. The wireframe avatar rotates live and turns red when health drops.*

![Firm view with sector breakdown and tracked firms](docs/assets/firms-screenshot.png)
*Firms. Sector breakdown, market mood, and per-firm cash and profit history.*

![Government policy panel with sliders and fiscal flow](docs/assets/gov-screenshot.png)
*Gov. Where the policy levers live. The LLM government writes through the same schema that drives these sliders.*

---

## What is it?

A tick-based agent-based model. Each tick is roughly one simulated week (52 ticks = 1 year). Every tick:

- **Households** look for work, earn wages or benefits, pay taxes, and spend on food, housing, services, and healthcare. Health and happiness move with income, prices, employment, and policy.
- **Firms** in four sectors (food, housing, services, healthcare) hire workers, set prices and wages, produce, and pay taxes. Cash-negative firms go distressed and can exit.
- **A bank** holds deposits, pays interest, processes loan repayments.
- **The government** collects taxes, runs unemployment benefits, and can pull 15+ policy levers (taxes, sector subsidies, wage floors, public works, social spending, bailouts, price/rent stabilization). It can be rule-based or LLM-driven.

The frontend streams metrics over WebSocket. The backend optionally persists tick metrics, policy actions, decision features, diagnostics, and agent snapshots to SQLite, Postgres, or TimescaleDB, sized for post-run analysis rather than in-the-loop logging.

---

## Highlights

- **LLM orchestration layer** with schema-validated tool calls, JSON-repair retries for malformed model output, and decision telemetry captured per cycle.
- **Reproducible multi-model evaluation** comparing five LLMs from 8B to 1T under a shared action schema, with per-decision logs and final-state metrics persisted for analysis.
- **Tick-level data warehouse** for run metadata, tick metrics, policy actions, decision features, diagnostics, and firm/household snapshots across SQLite, Postgres, or TimescaleDB.
- **Agent-based macroeconomic engine** across households, firms, banking, housing, healthcare, labor, and goods markets, served over a Dockerized FastAPI + WebSocket backend with a React dashboard, pytest contract suites, and CI.

---

## Quickstart

One command, full stack.

**macOS / Linux:**
```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
./start.sh
```

**Windows PowerShell:**
```powershell
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
.\start.ps1
```

**Plain Docker:**
```bash
docker compose up --build -d --wait
```

Open `http://localhost:5173`.

---

## Stack

| Layer | Tech |
|---|---|
| Simulation engine | Python 3.11+ |
| API + streaming | FastAPI, WebSockets |
| Frontend | React + Vite + Recharts |
| Persistence | SQLite (default) / PostgreSQL / TimescaleDB |
| LLM orchestration | LangGraph, LM Studio / Groq / OpenRouter / Ollama |
| Tests | pytest, contract-style regression suites |

---

## Architecture

```
frontend-react/        live dashboard (React + Recharts)
      │
      │  WebSocket  ws://localhost:8002/ws
      ▼
backend/server.py      FastAPI + simulation lifecycle
      ▼
backend/economy.py     tick coordinator, market clearing, simulation loop
      ▼
backend/agents.py      household, firm, bank, and government agent behavior
      +
backend/config.py      400+ tunable parameters, single source of truth
      +
backend/tools/         diagnostics, runners, LLM harness, analysis
```

Each tick runs the same fixed sequence: labor matching → production → goods market → housing → healthcare → banking → government → pricing → wage planning → firm exits → spawning → metrics broadcast. Every agent decision is split into a `plan_*` step (pure, no mutations) and an `apply_*` step (mutates state), which makes the plan phase safe to test in isolation and easy to reason about under failure.

---

## The LLM-as-government experiment

The government's action space lives in [`backend/policy_schema.py`](backend/policy_schema.py). Same schema drives the frontend policy sliders and the LLM government agent. When an LLM is driving policy, it gets a compact economy report every 26 ticks and proposes changes; the schema validates them before they apply. The model can't invent levers or push values out of range. The harness rejects malformed plans and tracks accepted decision rate and evidence match rate as separate signals from policy quality.

For the full 1,000-household comparison across five LLMs (Granite 8B, Gemma 26B, Llama 70B, GPT-OSS 120B, Ring 2.6 1T) plus the rule-based baseline, with discussion of *why* bigger models didn't reliably win: **[llm_run_outputs_smoke/LLM_RESULTS.md](llm_run_outputs_smoke/LLM_RESULTS.md)**.

---

## LLM harness

The government runner is the same orchestration shape you'd want for any production agent.

- **Structured I/O.** Every model call returns JSON validated against `policy_schema.py`. Malformed plans are rejected before touching state.
- **Retry and repair.** Blank or truncated provider responses trigger a JSON-repair retry, then fall back to the prior policy if the model can't recover.
- **Provider-agnostic.** Same harness drives LM Studio, Groq, OpenRouter, and Ollama. Swapping models is a config change.
- **Behavior metrics separate from outcomes.** Accepted decision rate and evidence match rate are logged independently from policy quality. A model can govern badly while citing perfectly, and vice versa.
- **Per-decision logs.** Each cycle persists the prompt context, the model's plan, what passed validation, what was rejected, and the resulting state delta.

---

## Engineering details worth knowing

A few choices I'd flag if you're reading the code:

- **Plan / apply split.** Every agent decision is a pure plan dict followed by a state mutation. The plan layer is fully testable without touching state.
- **Pricing branches by sector.** Generic firms use an inventory-weeks adjustment with a marginal-cost floor. Housing uses obligation-coverage spread across rental unit count, not just occupied tenants. Healthcare uses break-even plus a surge multiplier on queue overload. A single pricing rule across all four sectors produced visibly worse behavior in testing. The branching is load-bearing.
- **Wage setting has three paths.** Baseline firms pin to the wage floor. Post-warmup non-baseline firms run a Phillips Curve with a revenue ceiling that caps `max_labor_share × revenue / workers` per worker (prevents wage spirals during tight labor). Healthcare and warmup use a target-labor-share rule dampened by unemployment.
- **New firms spawn into under-served sectors.** Score is `unmet_demand × (1 + 1/private_count)` so a monopolist that suppresses demand still draws competitors.
- **Schema-validated policy actions.** `policy_schema.py` is the contract between the rule-based UI, the LLM government, and the runtime. One source of truth.

---

## Local development

```bash
python --version            # 3.11+
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
python -m uvicorn backend.server:app --reload --port 8002
```

In a second terminal:
```bash
cd frontend-react
npm install
npm run dev                 # localhost:5173
```

---

## Testing

CI gate (excludes slow LLM and research suites):
```bash
pip install -r requirements-dev.txt
pytest backend/tests_contracts/ backend/tests_server/ -q -m "not llm and not research"
```

LLM and research suite (requires `OPENROUTER_API_KEY`):
```bash
pytest backend/tests_contracts/ -q -m "llm or research"
```

Frontend:
```bash
cd frontend-react
npm ci && npm run lint && npm run build
```

Contract tests cover invariants (no negative cash, conservation across phases), behavior (price and wage responses to demand shifts), and short integration runs. LLM tests verify provider wiring and schema validation, not policy quality.

---

## Configuration

Warehouse persistence (off by default):
```
ECOSIM_ENABLE_WAREHOUSE=1
ECOSIM_WAREHOUSE_BACKEND=sqlite     # or postgres / timescale
```

LLM government (any subset works depending on which models you want to run):
```
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
LMSTUDIO_BASE_URL=http://127.0.0.1:1234
OLLAMA_BASE_URL=http://localhost:11434
```

400+ tunable simulation parameters live in `backend/config.py` as frozen dataclasses. No magic numbers buried in agent or economy code.

---

## Repository layout

```
backend/                simulation engine, API, persistence, tests
  agents.py               household, firm, bank, and government agent behavior
  economy.py              tick coordinator, market clearing, and simulation loop
  server.py               FastAPI + WebSocket API
  config.py               frozen dataclasses, single source of truth
  policy_schema.py        LLM + UI government action space
  tools/                  runners, LLM harness, analysis utilities
  tests_contracts/        regression coverage
  data/                   warehouse persistence + migrations

frontend-react/         React dashboard
docs/                   technical documentation
llm_run_outputs/        LLM government run artifacts
llm_run_outputs_1000/   1,000-household per-run LLM artifacts
llm_run_outputs_smoke/  public comparison writeup (incl. LLM_RESULTS.md)
ops/                    optional infrastructure
```

For the simulation deep dive: [docs/SIMULATION.md](docs/SIMULATION.md). For configuration and implementation details: [docs/TECHNICAL.md](docs/TECHNICAL.md). For the full doc index: [docs/README.md](docs/README.md).
