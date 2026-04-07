# EcoSim

EcoSim is an agent-based economic simulation of households, firms, healthcare,
housing, banks, and government interacting through labor markets, goods
markets, and fiscal policy.

## Why This Project

EcoSim is built as a policy sandbox: change core levers (taxes, benefits, wages, spending) and observe system-wide effects over time such as unemployment, prices, inequality, output, and household wellbeing.

## What It Does

- Simulates household, firm, and government decisions every tick
- Runs market clearing and policy adjustment in a phased simulation loop
- Streams live metrics to a React dashboard over WebSocket
- Persists run history, events, snapshots, and diagnostics through a local warehouse
- Supports scenario experimentation through runtime configuration
- Includes data generation and ML training scripts for policy-outcome forecasting

## Tech Stack

| Layer | Technology |
| --- | --- |
| Simulation engine | Python |
| API and streaming | FastAPI + WebSocket |
| Frontend | React + Vite |
| Data output | SQLite or PostgreSQL + TimescaleDB |
| ML pipeline | NumPy, Pandas, SciPy, XGBoost |

## High-Level Architecture

```text
frontend-react (dashboard)
    -> websocket
backend/server.py (simulation manager + streaming + warehouse buffering)
    ->
backend/economy.py (tick orchestration)
    ->
backend/agents.py (HouseholdAgent, FirmAgent, GovernmentAgent)
    +
backend/config.py (parameterized behavior)
    +
backend/data/ (warehouse managers, schema, migrations, tests)
```

Detailed documentation lives in [docs/README.md](docs/README.md).

## GitHub Hygiene

The repository is intentionally kept source-first:

- simulation code, dashboard code, tests, and docs are tracked
- generated logs, local LLM run outputs, databases, model artifacts, and build products are ignored
- local sandbox UIs and older experiments stay out of the published repo surface

That keeps the GitHub view focused on the parts another developer actually needs to clone, run, and extend the project.

## Docker Quickstart

This is the primary clone-and-run path.

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

If you prefer raw Docker:

```bash
docker compose up --build -d
```

Open the app:

- dashboard: `http://localhost:5173`
- health: `http://localhost:5173/health`

The frontend now proxies the backend internally, so the default stack comes up behind a single public entrypoint. SQLite warehouse persistence is enabled automatically inside the Docker stack.

If you deploy behind a different frontend origin or proxy layout, set `VITE_WS_URL` when building the frontend image.

The main stack does not require any local LLM runtime. The optional household / firm LLM test harnesses remain local developer tools.

## Local Development

```bash
git clone https://github.com/AymanCode/EcoSim.git
cd EcoSim
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn backend.server:app --reload --port 8002
```

In a second terminal:

```bash
cd frontend-react
npm install
npm run dev
```

Open: `http://localhost:5173`

Quick backend smoke test:

```bash
python backend/demo_skill_experience.py
```

## Local Timescale Warehouse (Optional)

Use this when you want durable run history and richer analytics locally.

```bash
# Start PostgreSQL + TimescaleDB
docker compose -f docker-compose.timescale.yml up -d

# Configure warehouse backend
# (PowerShell)
$env:ECOSIM_ENABLE_WAREHOUSE="1"
$env:ECOSIM_WAREHOUSE_BACKEND="timescale"
$env:ECOSIM_WAREHOUSE_DSN="postgresql://ecosim:ecosim@localhost:5432/ecosim"

# Apply schema
python backend/data/migrations/002_create_timescale_warehouse.py

# Run API
python -m uvicorn backend.server:app --reload --port 8002
```

Warehouse architecture and interview talking points: `docs/DATA_STORAGE_ARCHITECTURE.md`.

Current warehouse scope includes:

- run metadata and policy config
- aggregate tick metrics and sector metrics
- firm snapshots
- sampled household snapshots and tracked-household history
- labor, healthcare, policy, and regime events
- compact decision features
- compact explainability diagnostics

## Simulation and Data Commands

```bash
# Large-scale simulation
python backend/run_large_simulation.py

# Generate sample data for analysis/dashboard work
python backend/generate_sample_data.py

# Generate training data
cd backend
python generate_training_data.py

# Train ML models from generated CSV
python train_ml_model.py
```

## Tests

Core backend/data validation:

```bash
.\.venv\Scripts\python.exe -m pytest backend/data/tests backend/tests_server/test_server_api.py -q
```

Contract regression checks:

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests_contracts -q
```

## Repository Layout

```text
backend/            core simulation engine, API server, tests, data scripts
frontend-react/     main dashboard UI
docs/               technical docs and architecture notes
backend/data/       warehouse managers, schema, migrations, and tests
```

Older Chart.js / Godot / sandbox experiments are **not** in this repository (they stay local and are listed in `.gitignore`).

## Current Status

- Core simulation: functional and actively iterated
- Dashboard: functional, additional polish in progress
- ML tooling: data generation and model training scripts available
- Docker path: available for backend + dashboard out of the box

## Generated Artifacts Policy

Large generated files are intentionally not tracked in Git (databases, model binaries, logs, build artifacts, checkpoints, vendor directories). Generate them locally with the commands above.

## Documentation Map

- `docs/README.md`: active documentation index
- `docs/SIMULATION.md`: tick phases, agents, and market mechanics
- `docs/FIRM_DYNAMICS.md`: private-firm wage, hiring, pricing, and market-signal behavior
- `docs/TECHNICAL.md`: stack, configuration, testing, and implementation notes
- `docs/FRONTEND.md`: dashboard behavior and WebSocket protocol
- `docs/DATA_STORAGE_ARCHITECTURE.md`: warehouse plan, persistence guarantees, and explainability layer
- `docs/HOUSEHOLD_LABOR_DERISKING.md`: labor matching guardrails and rollout notes
- `docs/BANKING_SYSTEM.md`: banking model and credit mechanics
- `docs/archive/`: older docs kept for reference
