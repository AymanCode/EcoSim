# EcoSim

A macroeconomic simulation built from the agent up. Households, firms, a bank, and a government interact across a labor market, a goods market, a housing market, a healthcare queue, and a credit system. There's a live React dashboard, a streaming API, and an optional warehouse for run history.

You can run it as a policy sandbox — change taxes, subsidies, wage floors, or social spending and watch the economy react. Or you can plug an LLM into the government's seat and see what the model does with the same controls.

> **Featured experiment:** [Can an AI run an economy?](llm_run_outputs_smoke/LLM_RESULTS.md) — I gave six LLMs (8B → 1T) the government's policy controls and compared the runs against a rule-based baseline. Short answer: yes, kind of. Long answer is more interesting.

---

## What it is in plain language

A tick-based agent-based model. Each tick is roughly one simulated week (52 ticks = 1 year). Every tick:

- **Households** look for work, earn wages or benefits, pay taxes, and spend on food, housing, services, and healthcare. Health and happiness move with income, prices, employment, and policy.
- **Firms** in four sectors (food, housing, services, healthcare) hire workers, set prices and wages, produce, and pay taxes. Cash-negative firms go distressed and can exit.
- **A bank** holds deposits, pays interest, processes loan repayments.
- **The government** collects taxes, runs unemployment benefits, and can pull 15+ policy levers (taxes, sector subsidies, wage floors, public works, social spending, bailouts, price/rent stabilization). It can be rule-based or LLM-driven.

The frontend streams metrics over WebSocket; the backend can persist every tick to a SQLite/Postgres/Timescale warehouse for later analysis.

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
| LLM orchestration | LangGraph, OpenRouter / Groq / Ollama |
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
backend/economy.py     tick coordinator, ~14 phases per tick
      ▼
backend/agents.py      HouseholdAgent · FirmAgent · BankAgent · GovernmentAgent
      +
backend/config.py      400+ tunable parameters, single source of truth
      +
backend/tools/         diagnostics, runners, LLM harness, analysis
```

Each tick runs the same fixed sequence: labor matching → production → goods market → housing → healthcare → banking → government → pricing → wage planning → firm exits → spawning → metrics broadcast. Every agent decision is split into a `plan_*` step (pure, no mutations) and an `apply_*` step (mutates state), which makes the plan phase safe to test in isolation and easy to reason about under failure.

---

## The LLM-as-government experiment

The government's action space lives in [`backend/policy_schema.py`](backend/policy_schema.py). Same schema drives the frontend policy sliders and the LLM government agent. When an LLM is driving policy, it gets a compact economy report every 26 ticks and proposes changes; the schema validates them before they apply. The model can't invent levers or push values out of range — the harness rejects malformed plans and tracks accepted decision rate and evidence match rate as separate signals from policy quality.

For the full six-model comparison (Granite 8B, Gemma 26B, Llama 70B, GPT-OSS 120B, Ring 2.6 1T) plus the rule-based baseline, with discussion of *why* bigger models didn't reliably win: **[llm_run_outputs_smoke/LLM_RESULTS.md](llm_run_outputs_smoke/LLM_RESULTS.md)**.

---

## Engineering details worth knowing

A few choices I'd flag if you're reading the code:

- **Plan / apply split.** Every agent decision is a pure plan dict followed by a state mutation. The plan layer is fully testable without touching state.
- **Pricing branches by sector.** Generic firms use an inventory-weeks adjustment with a marginal-cost floor. Housing uses obligation-coverage spread across rental unit count, not just occupied tenants. Healthcare uses break-even plus a surge multiplier on queue overload. A single pricing rule across all four sectors produced visibly worse behavior in testing — the branching is load-bearing.
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

Contract tests cover invariants (no negative cash, conservation across phases), behavior (price and wage responses to demand shifts), and short integration runs. LLM tests verify provider wiring and schema validation — not policy quality.

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
OLLAMA_BASE_URL=http://localhost:11434
```

400+ tunable simulation parameters live in `backend/config.py` as frozen dataclasses. No magic numbers buried in agent or economy code.

---

## Repository layout

```
backend/                simulation engine, API, persistence, tests
  agents.py               all four agent types (~7K lines)
  economy.py              tick coordinator (~7K lines)
  server.py               FastAPI + WebSocket (~2.7K lines)
  config.py               frozen dataclasses, single source of truth
  policy_schema.py        LLM + UI government action space
  tools/                  runners, LLM harness, analysis utilities
  tests_contracts/        regression coverage
  data/                   warehouse persistence + migrations

frontend-react/         React dashboard
docs/                   technical documentation
llm_run_outputs/        LLM government run artifacts
llm_run_outputs_smoke/  baseline + smaller runs (incl. LLM_RESULTS.md)
ops/                    optional infrastructure
```

For the simulation deep dive: [docs/SIMULATION.md](docs/SIMULATION.md). For configuration and implementation details: [docs/TECHNICAL.md](docs/TECHNICAL.md). For the full doc index: [docs/README.md](docs/README.md).
