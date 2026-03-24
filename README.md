# EcoSim

EcoSim is an agent-based economic simulation of households, firms, and government interacting through labor markets, goods markets, and fiscal policy.

## Why This Project

EcoSim is built as a policy sandbox: change core levers (taxes, benefits, wages, spending) and observe system-wide effects over time such as unemployment, prices, inequality, output, and household wellbeing.

## What It Does

- Simulates household, firm, and government decisions every tick
- Runs market clearing and policy adjustment in a phased simulation loop
- Streams live metrics to a React dashboard over WebSocket
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
backend/server.py (simulation manager + streaming)
    ->
backend/economy.py (tick orchestration)
    ->
backend/agents.py (HouseholdAgent, FirmAgent, GovernmentAgent)
    +
backend/config.py (parameterized behavior)
```

Detailed architecture: `docs/ARCHITECTURE.md`.

## Quickstart

```bash
# Clone
 git clone https://github.com/AymanCode/EcoSim.git
 cd EcoSim

# Create environment
 python -m venv .venv

# Activate
# Windows (PowerShell)
 .venv\Scripts\Activate.ps1
# macOS/Linux
 source .venv/bin/activate

# Install backend dependencies
 pip install -r requirements.txt

# Run a quick demo
 python backend/demo_skill_experience.py
```

## Run the Dashboard

```bash
# Terminal 1: backend API
uvicorn backend.server:app --reload --port 8002

# Terminal 2: frontend
cd frontend-react
npm install
npm run dev
```

Open: `http://localhost:5173`

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
uvicorn backend.server:app --reload --port 8002
```

Warehouse architecture and interview talking points: `docs/DATA_STORAGE_ARCHITECTURE.md`.

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

```bash
cd backend
python test_stochastic.py
python test_training_setup.py
python test_household_agent.py
python test_firm_behavior.py
python test_government_behavior.py
```

## Repository Layout

```text
backend/            core simulation engine, API server, tests, data scripts
frontend-react/     main dashboard UI
docs/               technical docs and architecture notes
data/               utility data modules
sample_data/        generated outputs (not source-of-truth code)
frontend/           experimental static prototype
ecosim_chartjs/     experimental Chart.js prototype
ecosim-visual/      experimental Godot prototype
practice/           sandbox experiments
```

## Current Status

- Core simulation: functional and actively iterated
- Dashboard: functional, additional polish in progress
- ML tooling: data generation and model training scripts available
- Experimental folders: retained for reference, not core product path

## Generated Artifacts Policy

Large generated files are intentionally not tracked in Git (databases, model binaries, logs, build artifacts, checkpoints, vendor directories). Generate them locally with the commands above.

## Documentation Map

- `docs/ARCHITECTURE.md`: system design, tick phases, data flow
- `docs/DYNAMIC_FEATURES.md`: simulation behaviors and market mechanics
- `docs/DATA_SPECIFICATION.md`: schema and data usage guidance
- `docs/DATA_STORAGE_ARCHITECTURE.md`: local-first warehouse design (SQLite and Timescale)
- `backend/TESTING.md`: test inventory and run instructions
